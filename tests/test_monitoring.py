"""
Pruebas para CookAIMonitor: métricas agregadas, trazabilidad con Trace ID /
Span ID / Parent Span ID (IL3.2), y persistencia de precisión/consistencia (IL3.1).

Usa una base SQLite temporal (tmp_path) para no tocar data/agent_memory.db real,
e intercepta logging.info para no escribir en data/logs/cookai_execution.log real
(log_trace usa un logger a nivel de módulo, compartido por todas las instancias).
"""
import json

from app import monitoring as monitoring_module
from app.monitoring import CookAIMonitor


def _monitor_temporal(tmp_path):
    return CookAIMonitor(db_path=str(tmp_path / "test_metrics.db"))


def _interceptar_logs(monkeypatch):
    """Reemplaza logging.info por una lista en memoria para no tocar el log real."""
    capturados = []
    monkeypatch.setattr(monitoring_module.logging, "info", lambda msg: capturados.append(json.loads(msg)))
    return capturados


class TestMetricasAgregadas:
    def test_sin_operaciones_devuelve_valores_neutros(self, tmp_path):
        monitor = _monitor_temporal(tmp_path)
        metricas = monitor.get_aggregated_metrics()
        assert metricas["total_operaciones"] == 0
        assert metricas["tasa_exito"] == 100.0

    def test_calcula_latencia_y_tasa_de_exito_reales(self, tmp_path):
        monitor = _monitor_temporal(tmp_path)
        monitor.save_metric(latencia_ms=1000, status="SUCCESS", tipo_operacion="chat")
        monitor.save_metric(latencia_ms=3000, status="SUCCESS", tipo_operacion="recomendar")
        monitor.save_metric(latencia_ms=2000, status="FAILED", tipo_operacion="recomendar")

        metricas = monitor.get_aggregated_metrics()
        assert metricas["total_operaciones"] == 3
        assert metricas["latencia_promedio"] == 2000.0
        assert round(metricas["tasa_exito"], 2) == 66.67

    def test_precision_promedio_solo_considera_valores_no_nulos(self, tmp_path):
        monitor = _monitor_temporal(tmp_path)
        # Una operación de chat sin precisión aplicable (None) y dos de recomendar con valor real.
        monitor.save_metric(latencia_ms=500, tipo_operacion="chat", precision_score=None)
        monitor.save_metric(latencia_ms=500, tipo_operacion="recomendar", precision_score=1.0)
        monitor.save_metric(latencia_ms=500, tipo_operacion="recomendar", precision_score=0.5)

        metricas = monitor.get_aggregated_metrics()
        assert metricas["precision_promedio"] == 0.75

    def test_trace_id_queda_asociado_a_la_metrica(self, tmp_path):
        monitor = _monitor_temporal(tmp_path)
        monitor.save_metric(latencia_ms=100, tipo_operacion="chat", trace_id="trace-abc")
        registros = monitor.get_raw_records(limit=1)
        # get_raw_records: timestamp, latencia_ms, status, tokens_input, tokens_output,
        # tipo_operacion, consistency_score, precision_score, trace_id
        assert registros[0][8] == "trace-abc"


class TestTrazabilidad:
    def test_log_trace_genera_span_id_unico_por_llamada(self, tmp_path, monkeypatch):
        capturados = _interceptar_logs(monkeypatch)
        monitor = _monitor_temporal(tmp_path)

        span1 = monitor.log_trace(user_id="u1", step_name="Paso1", tool_used="ToolA", status="SUCCESS")
        span2 = monitor.log_trace(user_id="u1", step_name="Paso2", tool_used="ToolB", status="SUCCESS")

        assert span1 != span2
        assert len(capturados) == 2

    def test_pasos_del_mismo_trace_id_comparten_identificador(self, tmp_path, monkeypatch):
        capturados = _interceptar_logs(monkeypatch)
        monitor = _monitor_temporal(tmp_path)

        trace_id = "trace-de-prueba-123"
        root_span = monitor.log_trace(
            user_id="u1", step_name="Pipeline_Start", tool_used="Orchestrator",
            status="STARTED", trace_id=trace_id
        )
        monitor.log_trace(
            user_id="u1", step_name="Domain_Validation", tool_used="DomainValidator",
            status="SUCCESS", trace_id=trace_id, parent_span_id=root_span
        )

        assert all(r["trace_id"] == trace_id for r in capturados)
        assert capturados[1]["parent_span_id"] == root_span
        assert capturados[0]["parent_span_id"] is None  # el span raíz no tiene padre

    def test_sin_trace_id_explicito_genera_uno_propio(self, tmp_path, monkeypatch):
        capturados = _interceptar_logs(monkeypatch)
        monitor = _monitor_temporal(tmp_path)

        span_id = monitor.log_trace(user_id="u1", step_name="Paso", tool_used="Tool", status="SUCCESS")

        # Sin trace_id explícito, el span se vuelve su propio trace de un solo paso.
        assert capturados[0]["trace_id"] == span_id
        assert capturados[0]["span_id"] == span_id

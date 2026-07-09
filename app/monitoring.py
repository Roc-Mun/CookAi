# app/monitoring.py
import sqlite3
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path

# Configurar el Logger para Trazabilidad Estructurada en JSON (IL3.2 / IE2)
LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "cookai_execution.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(message)s' # Guardamos únicamente el string JSON crudo por línea
)

class CookAIMonitor:
    def __init__(self, db_path="data/agent_memory.db"): # Centralizado en data/
        self.db_path = db_path
        self._create_table()

    def _create_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # WAL (Write-Ahead Logging): permite que lecturas (dashboard, /metrics) no
        # bloqueen escrituras (cada request guardando su métrica) y viceversa.
        # Mejora la concurrencia real de SQLite sin migrar de motor de base de datos.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS execution_metrics (
                                                                        id_ejecucion TEXT PRIMARY KEY,
                                                                        timestamp TEXT NOT NULL,
                                                                        latencia_ms REAL,
                                                                        tokens_input INTEGER,
                                                                        tokens_output INTEGER,
                                                                        status TEXT,
                                                                        tipo_operacion TEXT,
                                                                        consistency_score REAL DEFAULT 1.0
                       )
                       """)
        # Migración incremental: agrega columnas nuevas sin perder los datos ya guardados
        # (precision_score para IL3.1, trace_id para correlacionar con el log de trazas IL3.2).
        cursor.execute("PRAGMA table_info(execution_metrics)")
        columnas_existentes = {row[1] for row in cursor.fetchall()}
        if "precision_score" not in columnas_existentes:
            cursor.execute("ALTER TABLE execution_metrics ADD COLUMN precision_score REAL")
        if "trace_id" not in columnas_existentes:
            cursor.execute("ALTER TABLE execution_metrics ADD COLUMN trace_id TEXT")
        conn.commit()
        conn.close()

    def save_metric(self, latencia_ms, tokens_input=0, tokens_output=0, status="SUCCESS",
                     tipo_operacion="chat", consistency_score=1.0, precision_score=None, trace_id=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO execution_metrics
                           (id_ejecucion, timestamp, latencia_ms, tokens_input, tokens_output,
                            status, tipo_operacion, consistency_score, precision_score, trace_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           str(uuid.uuid4()),
                           datetime.now().isoformat(),
                           latencia_ms,
                           tokens_input,
                           tokens_output,
                           status,
                           tipo_operacion,
                           consistency_score,
                           precision_score,
                           trace_id
                       ))
        conn.commit()
        conn.close()

    def log_trace(self, user_id, step_name, tool_used, status, error_message=None,
                   trace_id=None, parent_span_id=None):
        """
        Genera una traza de auditoría en JSON plano para Trazabilidad del Pipeline (IL3.2).

        Incluye Trace ID / Span ID / Parent Span ID (componentes clave de trazabilidad):
        - trace_id: identifica toda la ejecución de una solicitud de punta a punta.
        - span_id: identifica esta operación puntual (se genera una por cada log_trace).
        - parent_span_id: referencia al span raíz de la misma solicitud, para poder
          reconstruir qué pasos pertenecen a la misma ejecución y en qué orden ocurrieron.

        Si no se pasa trace_id (compatibilidad con llamadas antiguas), el span se
        vuelve su propio trace de un solo paso.
        """
        span_id = str(uuid.uuid4())
        trace_data = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id or span_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "user_id": user_id,
            "step_name": step_name,
            "tool_used": tool_used,
            "status": status,
            "error_message": error_message
        }
        # Escribe la línea estructurada en el archivo de log físico
        logging.info(json.dumps(trace_data))
        return span_id

    def get_aggregated_metrics(self):
        """Calcula métricas clave agregadas exigidas por la rúbrica (IL3.1)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metrics = {"latencia_promedio": 0.0, "tasa_exito": 100.0, "total_operaciones": 0, "precision_promedio": None}
        try:
            # 1. Total operaciones
            cursor.execute("SELECT COUNT(*) FROM execution_metrics")
            total = cursor.fetchone()[0]
            if total > 0:
                metrics["total_operaciones"] = total

                # 2. Latencia promedio
                cursor.execute("SELECT AVG(latencia_ms) FROM execution_metrics")
                metrics["latencia_promedio"] = round(cursor.fetchone()[0], 2)

                # 3. Tasa de éxito
                cursor.execute("SELECT COUNT(*) FROM execution_metrics WHERE status = 'SUCCESS'")
                exitos = cursor.fetchone()[0]
                metrics["tasa_exito"] = round((exitos / total) * 100, 2)

                # 4. Precisión promedio (IL3.1): solo sobre operaciones donde se calculó
                # de verdad (recomendaciones con ingredientes reales), no un valor fijo.
                cursor.execute("SELECT AVG(precision_score) FROM execution_metrics WHERE precision_score IS NOT NULL")
                fila = cursor.fetchone()
                metrics["precision_promedio"] = round(fila[0], 2) if fila and fila[0] is not None else None
        except Exception as e:
            print(f"⚠️ Error al calcular métricas agregadas: {e}")
        finally:
            conn.close()

        return metrics

    def get_raw_records(self, limit=50):
        """Extrae los registros crudos de telemetría para alimentar el Dashboard real"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT timestamp, latencia_ms, status, tokens_input, tokens_output,
                              tipo_operacion, consistency_score, precision_score, trace_id
                       FROM execution_metrics
                       ORDER BY timestamp DESC LIMIT ?
                       """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows

# Instancia global única para ser importada en el pipeline
cookai_monitor = CookAIMonitor()
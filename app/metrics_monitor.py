# app/metrics_monitor.py
import time
from datetime import datetime
from typing import List, Dict, Any

class LocalhostMetricsMonitor:
    def __init__(self):
        # IL3.1: Estructuras en memoria para Métricas Operacionales
        self.total_consultas = 0
        self.exitos = 0
        self.fallidos = 0
        self.rechazados_dominio = 0
        self.historial_latencias: List[float] = []
        self.tokens_estimados_totales = 0

        # IL3.2: Estructura para Trazabilidad (Bitácora de ejecución)
        self.trazas_log: List[Dict[str, Any]] = []

    def save_metric(self, latencia_ms: float, tokens_input: int, tokens_output: int, status: str, tipo_operacion: str):
        """Registra métricas de rendimiento en cada llamada del chat (IL3.1)"""
        self.total_consultas += 1
        self.historial_latencias.append(round(latencia_ms / 1000, 3)) # Convertimos a segundos

        # Si no calcula tokens el LLM de forma nativa, hacemos una estimación estándar
        self.tokens_estimados_totales += (tokens_input + tokens_output) if (tokens_input + tokens_output) > 0 else 150

        if status == "SUCCESS":
            self.exitos += 1
        elif status == "REJECTED":
            self.rechazados_dominio += 1
        else:
            self.fallidos += 1

    def log_trace(self, user_id: str, step_name: str, tool_used: str, status: str, error_message: str = None):
        """Guarda registros secuenciales del pipeline del agente (IL3.2)"""
        uid = user_id or "local_host_user"
        self.trazas_log.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": uid,
            "step_name": step_name,
            "tool_used": tool_used,
            "status": status,
            "error": error_message
        })
        # Evitamos saturar la RAM manteniendo los últimos 40 eventos
        if len(self.trazas_log) > 40:
            self.trazas_log.pop(0)

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Este es el método exacto que llama tu app.get('/metrics').
        Compila toda la información de observabilidad exigida por Duoc UC.
        """
        latencia_promedio = (sum(self.historial_latencias) / len(self.historial_latencias)) if self.historial_latencias else 0.0
        pct_acierto = (self.exitos / self.total_consultas * 100) if self.total_consultas else 0.0

        return {
            "meta_evaluacion": "Duoc UC - ISY0101 - Evidencia de Observabilidad",
            "estado_motor": "OPERATIONAL",
            "metricas_rendimiento_il3_1": {
                "total_peticiones_recibidas": self.total_consultas,
                "consultas_exitosas_llm": self.exitos,
                "consultas_bloqueadas_guardrails": self.rechazados_dominio,
                "errores_criticos_sistema": self.fallidos,
                "porcentaje_precision_y_acierto": f"{pct_acierto:.2f}%",
                "latencia_promedio_sistema": f"{latencia_promedio:.3f} segundos",
                "uso_acumulado_tokens_estimados": self.tokens_estimados_totales,
                "ultimos_diez_tiempos_respuesta_segundos": self.historial_latencias[-10:]
            },
            "bitacora_trazabilidad_il3_2": {
                "descripcion": "Logs en tiempo real del pipeline de ejecución secuencial del Agente",
                "total_registros_en_sesion": len(self.trazas_log),
                "lineas_de_traza": self.trazas_log[::-1] # Muestra lo más nuevo arriba
            }
        }

# Instancia global compartida para todo el ciclo de vida del Localhost
monitor = LocalhostMetricsMonitor()
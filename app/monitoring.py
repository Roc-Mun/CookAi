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
        conn.commit()
        conn.close()

    def save_metric(self, latencia_ms, tokens_input=0, tokens_output=0, status="SUCCESS", tipo_operacion="chat", consistency_score=1.0):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO execution_metrics (id_ejecucion, timestamp, latencia_ms, tokens_input, tokens_output, status, tipo_operacion, consistency_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           str(uuid.uuid4()),
                           datetime.now().isoformat(),
                           latencia_ms,
                           tokens_input,
                           tokens_output,
                           status,
                           tipo_operacion,
                           consistency_score
                       ))
        conn.commit()
        conn.close()

    def log_trace(self, user_id, step_name, tool_used, status, error_message=None):
        """Genera una traza de auditoría en JSON plano para Trazabilidad del Pipeline (IL3.2)"""
        trace_data = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "step_name": step_name,
            "tool_used": tool_used,
            "status": status,
            "error_message": error_message
        }
        # Escribe la línea estructurada en el archivo de log físico
        logging.info(json.dumps(trace_data))

    def get_aggregated_metrics(self):
        """Calcula métricas clave agregadas exigidas por la rúbrica (IL3.1)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metrics = {"latencia_promedio": 0.0, "tasa_exito": 100.0, "total_operaciones": 0}
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
                              tipo_operacion, consistency_score
                       FROM execution_metrics
                       ORDER BY timestamp DESC LIMIT ?
                       """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows

# Instancia global única para ser importada en el pipeline
cookai_monitor = CookAIMonitor()
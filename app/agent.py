import time
import re
import uuid
from app.llm import LLMClient
from app.domain_validator import DomainValidator
from app.planning_agent import PlanningAgent, DynamicAgentExecutor
from app.rag import RAGSystem
from app.persistent_memory import persistent_db  # Centralizador de persistencia e interacciones
from app.tools import COOKAI_TOOLKIT, buscar_recetas_rag_cacheado  # Herramientas del sistema unificadas


# =========================================================
# INICIALIZACIÓN DE COMPONENTES CENTRALES
# =========================================================

domain_validator = DomainValidator()
llm_client = LLMClient()

# IL2.3 - Inyección de dependencia del LLM en el generador de planes
planning_agent = PlanningAgent(llm_client=llm_client)
rag_system = RAGSystem()

# Fase de Orquestación (IL2.3): ejecuta de verdad los pasos del plan generado
# (RAG y/o Web) con el filtro estricto de fidelidad a los ingredientes del usuario.
dynamic_executor = DynamicAgentExecutor()


# =========================================================
# UTILIDADES INTERNAS DE EXTRACCIÓN
# =========================================================

def _extract_ingredients_from_text(text: str) -> list[str]:
    """
    Extrae de forma robusta los ingredientes desde textos del usuario mediante expresiones regulares.
    """
    if not text:
        return []

    match = re.search(
        r"ingredientes?\s*:\s*(.+?)(?:\s+y\s+prefiero|\.\s*$|\s*$)",
        text,
        flags=re.IGNORECASE
    )

    if not match:
        # Intento secundario: separar palabras si el usuario solo envía una lista directa
        parts = re.split(r",|\s+y\s+|\s+e\s+|;|/", text)
        cleaned = [p.strip().lower() for p in parts if len(p.strip()) > 2 and "necesito" not in p]
        return cleaned[:8] if cleaned else []

    raw = match.group(1)
    raw = re.split(r"\s+y\s+prefiero\s+", raw, flags=re.IGNORECASE)[0]
    parts = re.split(r",|\s+y\s+|\s+e\s+|;|/", raw)

    cleaned = [p.strip().lower() for p in parts if p and p.strip()]

    seen = set()
    result = []
    for item in cleaned:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


# =========================================================
# INTERFAZ DE COMPATIBILIDAD (AGENT SHIM)
# =========================================================

class _AgentShim:
    """Mantiene la interfaz estándar .invoke() compatible con routers y FastAPI."""
    def __init__(self, llm_client_obj: LLMClient):
        self._llm_client = llm_client_obj

    def invoke(self, payload: dict) -> dict:
        prompt = payload.get("input") or payload.get("prompt") or ""
        user_id = payload.get("user_id", "default")
        response = execute_with_planning(prompt, user_id=user_id)
        return {"output": response}

# Instancia expuesta para el enrutador de FastAPI (main.py)
agent = _AgentShim(llm_client)


# =========================================================
# EJECUCIÓN DEL PIPELINE AGENTE (REASONING & EXECUTION)
# =========================================================

from app.monitoring import cookai_monitor  # Importamos el monitor global único

def execute_with_planning(
        user_input: str,
        user_id: str = "default",
        contexto_externo: str | None = None,
        fuente: str = "RAG",
        trace_id: str | None = None
) -> str:
    """
    Orquestador Central de CookAI con Observabilidad y Sanitización PII integradas.

    trace_id: identificador de la solicitud de punta a punta (IL3.2). Si el llamador
    (main.py) ya generó uno para correlacionar con sus propios pasos, se reutiliza;
    si no, se genera aquí para que la ejecución siga siendo trazable igual.
    """
    inicio_pipeline = time.time()
    trace_id = trace_id or str(uuid.uuid4())
    # Span raíz de esta ejecución: todos los pasos del pipeline quedan como hijos de este.
    root_span_id = cookai_monitor.log_trace(
        user_id=user_id, step_name="Pipeline_Start", tool_used="Orchestrator",
        status="STARTED", trace_id=trace_id
    )

    # --- APLICACIÓN DE SANITIZACIÓN PII ANTES DE PROCESAR O LOGUEAR (IE6) ---
    if hasattr(domain_validator, 'sanitize_pii'):
        user_input = domain_validator.sanitize_pii(user_input)
    else:
        # Fallback de limpieza básico por regex en caso de que falte en la clase
        user_input = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', user_input)
        user_input = re.sub(r'\b\+?[0-9]{9,15}\b', '[PHONE_REDACTED]', user_input)

    try:
        # =================================================
        # 1. VALIDACIÓN DE FRONTERAS DE DOMINIO
        # =================================================
        try:
            is_valid, validation_msg = domain_validator.validate_and_filter(user_input)
            cookai_monitor.log_trace(user_id=user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="SUCCESS" if is_valid else "REJECTED", trace_id=trace_id, parent_span_id=root_span_id)
            if not is_valid:
                return validation_msg
        except Exception as err_val:
            cookai_monitor.log_trace(user_id=user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="ERROR", error_message=str(err_val), trace_id=trace_id, parent_span_id=root_span_id)
            raise err_val

        # =================================================
        # 2. GENERACIÓN Y VALIDACIÓN DEL PLAN DE ACCIÓN
        # =================================================
        try:
            plan = planning_agent.create_plan(user_input)
            plan_valid, plan_msg = planning_agent.validate_plan(plan)
            cookai_monitor.log_trace(user_id=user_id, step_name="Action_Planning", tool_used="PlanningAgent", status="SUCCESS", trace_id=trace_id, parent_span_id=root_span_id)
        except Exception as err_plan:
            cookai_monitor.log_trace(user_id=user_id, step_name="Action_Planning", tool_used="PlanningAgent", status="ERROR", error_message=str(err_plan), trace_id=trace_id, parent_span_id=root_span_id)
            plan = []

        # =================================================
        # 3. RECUPERACIÓN DE MEMORIA Y PREFERENCIAS
        # =================================================
        historial_contexto = "No hay interacciones registradas en la sesión actual."
        contexto_preferencias = "El usuario no registra restricciones alimentarias previas."
        try:
            interacciones = persistent_db.get_recent_interactions(user_id, limit=6) if hasattr(persistent_db, 'get_recent_interactions') else []
            if interacciones:
                historial_contexto = "\n".join([f"{i['role'].capitalize()}: {domain_validator.sanitize_pii(i['content'])}" for i in interacciones])

            prefs = persistent_db.get_user_preferences(user_id)
            if prefs:
                contexto_preferencias = (
                    f"- Restricciones: {', '.join(prefs.get('dietary_restrictions', []))}\n"
                    f"- Cocinas: {', '.join(prefs.get('favorite_cuisines', []))}"
                )
            cookai_monitor.log_trace(user_id=user_id, step_name="Memory_Retrieval", tool_used="PersistentDB", status="SUCCESS", trace_id=trace_id, parent_span_id=root_span_id)
        except Exception as err_mem:
            cookai_monitor.log_trace(user_id=user_id, step_name="Memory_Retrieval", tool_used="PersistentDB", status="ERROR", error_message=str(err_mem), trace_id=trace_id, parent_span_id=root_span_id)

        # =================================================
        # 4. EJECUCIÓN DE HERRAMIENTAS RAG (CONSULTAS)
        # =================================================
        try:
            if contexto_externo is not None:
                resultados_rag = contexto_externo
            else:
                resultados_rag = buscar_recetas_rag_cacheado(user_input)
            cookai_monitor.log_trace(user_id=user_id, step_name="Vector_Search", tool_used="ChromaDB_RAG", status="SUCCESS", trace_id=trace_id, parent_span_id=root_span_id)
        except Exception as err_rag:
            cookai_monitor.log_trace(user_id=user_id, step_name="Vector_Search", tool_used="ChromaDB_RAG", status="ERROR", error_message=str(err_rag), trace_id=trace_id, parent_span_id=root_span_id)
            resultados_rag = "No se encontraron recetas válidas debido a una interrupción técnica."

        # =================================================
        # 5. ANÁLISIS DE COINCIDENCIA DE INGREDIENTES
        # =================================================
        analisis_herramienta_msg = "No se requiere análisis analítico para este prompt."
        try:
            ingredientes_disponibles = _extract_ingredients_from_text(user_input)
            if ingredientes_disponibles and "No se encontraron recetas" not in resultados_rag:
                resultado_analisis = COOKAI_TOOLKIT["analizar_coincidencia_ingredientes"](
                    ingredientes_usuario=ingredientes_disponibles,
                    texto_receta=resultados_rag
                )
                analisis_herramienta_msg = f"Porcentaje de Coincidencia Real: {resultado_analisis.get('porcentaje_coincidencia', '0%')}"
            cookai_monitor.log_trace(user_id=user_id, step_name="Ingredient_Analysis", tool_used="MathToolkit", status="SUCCESS", trace_id=trace_id, parent_span_id=root_span_id)
        except Exception as err_tool:
            cookai_monitor.log_trace(user_id=user_id, step_name="Ingredient_Analysis", tool_used="MathToolkit", status="ERROR", error_message=str(err_tool), trace_id=trace_id, parent_span_id=root_span_id)

        # =================================================
        # 6. ORQUESTACIÓN DINÁMICA DEL PLAN (IL2.3 — Fase de Orquestación)
        # =================================================
        # Ejecuta de verdad el plan validado en el paso 2: recorre sus pasos llamando
        # a RAG y/o Web con el filtro estricto de fidelidad a los ingredientes del
        # usuario. Si falla por cualquier motivo, se conserva el camino simple
        # (prompt directo) como respaldo para no romper la continuidad del servicio.
        response = None
        if contexto_externo is None:
            try:
                # Reutiliza el plan del paso 2 (ya generado y validado) en vez de que
                # DynamicAgentExecutor pida uno nuevo al LLM — 1 llamada menos por request.
                plan_para_ejecutar = plan if isinstance(plan, dict) and plan.get("pasos") else None
                response = dynamic_executor.run(user_input, plan=plan_para_ejecutar)
                cookai_monitor.log_trace(user_id=user_id, step_name="Dynamic_Orchestration", tool_used="DynamicAgentExecutor", status="SUCCESS", trace_id=trace_id, parent_span_id=root_span_id)
            except Exception as err_dyn:
                cookai_monitor.log_trace(user_id=user_id, step_name="Dynamic_Orchestration", tool_used="DynamicAgentExecutor", status="ERROR", error_message=str(err_dyn), trace_id=trace_id, parent_span_id=root_span_id)
                response = None

        if not response or not str(response).strip():
            # =================================================
            # 6b. RESPALDO: CONSTRUCCIÓN DE PROMPT SIMPLE E INFERENCIA LLM
            # =================================================
            es_busqueda_web = fuente.upper() == "WEB"
            bloque_contexto = f"=== CONTEXTO ===\n{resultados_rag}"

            # REGLA DE FIDELIDAD: este camino se usa cuando ya se validó (o se pasó
            # explícitamente) el contexto real a utilizar — por eso, a diferencia de
            # DynamicAgentExecutor, aquí NUNCA se permite inventar una receta distinta.
            # Se incluye la solicitud original explícitamente: sin esto, el modelo solo
            # veía el contexto y terminaba repitiendo la receta completa en vez de
            # responder puntualmente lo que se le preguntó (ej. una sustitución).
            final_prompt = (
                "Eres CookAI. Responde específicamente a la SOLICITUD DEL USUARIO usando "
                "ÚNICAMENTE información respaldada por el CONTEXTO entregado a continuación. "
                "No inventes ingredientes, pasos, ni recetas distintas a las que aparecen en "
                "el contexto. Si la solicitud es una pregunta puntual (por ejemplo, un ajuste "
                "o sustitución), respóndela directamente en vez de repetir la receta completa.\n\n"
                f"SOLICITUD DEL USUARIO: {user_input}\n\n"
                f"{bloque_contexto}\n{analisis_herramienta_msg}\n{historial_contexto}\n{contexto_preferencias}\n"
                "Respuesta:"
            )

            try:
                response = llm_client.generate_response(final_prompt)
                cookai_monitor.log_trace(user_id=user_id, step_name="LLM_Inference", tool_used="GroqClient", status="SUCCESS", trace_id=trace_id, parent_span_id=root_span_id)
            except Exception as err_llm:
                cookai_monitor.log_trace(user_id=user_id, step_name="LLM_Inference", tool_used="GroqClient", status="ERROR", error_message=str(err_llm), trace_id=trace_id, parent_span_id=root_span_id)
                raise err_llm

        # =================================================
        # SANITIZACIÓN Y LIMPIEZA DE ENCABEZADOS PROHIBIDOS
        # =================================================
        # 1. Cortar si el modelo genera texto a partir de etiquetas divs extrañas
        for token_corte in ["<div style=\"margin-top", "Nota importante:", "Justificación del beneficio:", "<div"]:
            if token_corte in response:
                response = response.split(token_corte)[0]

        # 2. Reemplazo directo mediante expresiones regulares para limpiar la estructura
        response = re.sub(r"\*\*Nota importante:\*\*.*", "", response, flags=re.DOTALL)
        response = re.sub(r"\*\*Justificación del beneficio:\*\*.*", "", response, flags=re.DOTALL)
        response = re.sub(r"<.*?>", "", response, flags=re.DOTALL)

        # Eliminar espacios en blanco sobrantes tras el recorte
        response = response.strip()

        # =================================================
        # 7. PERSISTENCIA SANITIZADA EN CALIENTE (IE6)
        # =================================================
        try:
            response_sanitizada = domain_validator.sanitize_pii(response) if hasattr(domain_validator, 'sanitize_pii') else response
            if hasattr(persistent_db, 'save_interaction'):
                persistent_db.save_interaction(user_id=user_id, role="user", content=user_input)
                persistent_db.save_interaction(user_id=user_id, role="assistant", content=response_sanitizada)
        except Exception as memory_error:
            print(f"⚠️ Alerta en guardado de interacción: {memory_error}")

        return response

    except Exception as e:
        cookai_monitor.log_trace(user_id=user_id, step_name="Pipeline_Execution", tool_used="Orchestrator", status="CRITICAL_FAILED", error_message=str(e), trace_id=trace_id, parent_span_id=root_span_id)
        return f"Disculpe, ocurrió una inconsistencia interna al procesar su solicitud culinaria. Reporte: {str(e)}"
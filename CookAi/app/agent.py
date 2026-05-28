import re
from app.llm import LLMClient
from app.domain_validator import DomainValidator
from app.planning_agent import PlanningAgent
from app.rag import RAGSystem
from app.persistent_memory import persistent_db  # Centralizador de persistencia e interacciones
from app.tools import COOKAI_TOOLKIT  # Herramientas del sistema unificadas

# =========================================================
# INICIALIZACIÓN DE COMPONENTES CENTRALES
# =========================================================

domain_validator = DomainValidator()
llm_client = LLMClient()

# IL2.3 - Inyección de dependencia del LLM en el generador de planes
planning_agent = PlanningAgent(llm_client=llm_client)
rag_system = RAGSystem()


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

def execute_with_planning(user_input: str, user_id: str = "default") -> str:
    """
    Orquestador Central de CookAI.
    Ejecuta el ciclo cognitivo del agente integrando validación de fronteras,
    planificación de tareas, recuperación semántica e invocación determinista de herramientas.
    """
    try:
        # =================================================
        # 1. VALIDACIÓN DE FRONTERAS DE DOMINIO (Filtro lúdico)
        # =================================================
        is_valid, validation_msg = domain_validator.validate_and_filter(user_input)
        if not is_valid:
            return validation_msg

        # =================================================
        # 2. GENERACIÓN Y VALIDACIÓN DEL PLAN DE ACCIÓN (IL2.3)
        # =================================================
        plan = planning_agent.create_plan(user_input)
        plan_valid, plan_msg = planning_agent.validate_plan(plan)
        if not plan_valid:
            print(f"⚠️ Plan optimizado por contingencia: {plan_msg}")

        # =================================================
        # 3. RECUPERACIÓN DE MEMORIA DE CORTO PLAZO (IL2.2)
        # =================================================
        # Obtenemos las últimas interacciones reales indexadas en la BD para la ventana de contexto
        interacciones_recientes = persistent_db.get_saved_recipes(user_id)  # O método equivalente de historial

        # Formatear el historial de corto plazo de forma segura y limpia
        historial_contexto = "No hay interacciones registradas en la sesión actual."
        try:
            # Recuperar las últimas interacciones formateadas de la BD relacional
            interacciones = persistent_db.get_recent_interactions(user_id, limit=6) if hasattr(persistent_db, 'get_recent_interactions') else []
            if interacciones:
                historial_contexto = "\n".join([f"{i['role'].capitalize()}: {i['content']}" for i in interacciones])
        except Exception:
            pass

        # =================================================
        # 4. RECUPERACIÓN DE PREFERENCIAS (LARGO PLAZO - IL2.2)
        # =================================================
        prefs = persistent_db.get_user_preferences(user_id)
        contexto_preferencias = "El usuario no registra restricciones alimentarias previas."
        if prefs:
            contexto_preferencias = (
                f"- Restricciones Médicas/Dietéticas: {', '.join(prefs.get('dietary_restrictions', []))}\n"
                f"- Cocinas de preferencia: {', '.join(prefs.get('favorite_cuisines', []))}\n"
                f"- Tiempo de cocina base: {prefs.get('cooking_time_preference', 'Flexible')}"
            )

        # =================================================
        # 5. EJECUCIÓN DE HERRAMIENTAS DE CONSULTA Y RAZONAMIENTO (IL2.1)
        # =================================================
        # Invocamos la herramienta unificada del Toolkit para buscar en la Base Vectorial
        resultados_rag = COOKAI_TOOLKIT["buscar_recetas_rag"](user_input)

        # Herramienta de Razonamiento: Análisis determinista de ingredientes disponibles
        analisis_herramienta_msg = "No se requiere análisis analítico de ingredientes para este prompt."
        ingredientes_disponibles = _extract_ingredients_from_text(user_input)

        if ingredientes_disponibles and "No se encontraron recetas" not in resultados_rag:
            # Ejecutamos la herramienta de cómputo matemático/conjuntos del Toolkit unificado
            resultado_analisis = COOKAI_TOOLKIT["analizar_coincidencia_ingredientes"](
                ingredientes_usuario=ingredientes_disponibles,
                texto_receta=resultados_rag
            )
            analisis_herramienta_msg = (
                f"Porcentaje de Coincidencia Real: {resultado_analisis.get('porcentaje_coincidencia', '0%')}\n"
                f"Ingredientes que sí utiliza la receta: {', '.join(resultado_analisis.get('ingredientes_utilizados', []))}\n"
                f"Ingredientes descartados o no requeridos: {', '.join(resultado_analisis.get('ingredientes_no_requeridos', []))}\n"
                f"¿Es la receta viable con lo que tiene el usuario?: {'SÍ' if resultado_analisis.get('viable') else 'NO'}"
            )

        # =================================================
        # 6. CONSTRUCCIÓN DEL PROMPT ESTRUCTURADO FINAL (Inferencia)
        # =================================================
        final_prompt = f"""
Eres CookAI, un agente inteligente de automatización culinaria y chef experto. 
Genera una respuesta rigurosa, clara y adaptada utilizando los siguientes bloques de contexto fidedignos:

=================================================
CONTEXTO DE RECETAS RECUPERADAS (RAG - ÚNICA FUENTE VÁLIDA)
=================================================
{resultados_rag}

=================================================
HERRAMIENTA DE RAZONAMIENTO: INGREDIENTES DETERMINISTAS
=================================================
{analisis_herramienta_msg}

=================================================
HISTORIAL DE INTERACCIÓN RECIENTE (MEMORIA CORTO PLAZO)
=================================================
{historial_contexto}

=================================================
PERFIL Y RESTRICCIONES ALIMENTARIAS (LARGO PLAZO)
=================================================
{contexto_preferencias}

=================================================
PLAN DE ACCIÓN SECUENCIAL VALIDADO
=================================================
{planning_agent.format_plan_for_prompt(plan)}

=================================================
REGLAS CRÍTICAS DE COMPORTAMIENTO Y COMPLIANCE
=================================================
1. Responde basándote EXCLUSIVAMENTE en las recetas provistas en el bloque RAG. No inventes procedimientos.
2. Si el bloque de ingredientes indica que la receta NO es viable, adviérteselo al usuario de entrada y sugiérenle buscar sustitutos utilizando herramientas de reemplazo.
3. Almacena un tono empático, profesional y estructurado. 
4. Justifica brevemente el beneficio de la receta seleccionada según el perfil de largo plazo del usuario.

Genera tu respuesta final estructurada:
"""

        # =================================================
        # 7. INFERENCIA DEL MODELO FUNDACIONAL
        # =================================================
        response = llm_client.generate_response(final_prompt)

        # =================================================
        # 8. PERSISTENCIA EN CALIENTE DE LA CONVERSACIÓN (IL2.2)
        # =================================================
        try:
            # Guardamos la interacción actual de forma relacional para alimentar el corto plazo de la siguiente pregunta
            if hasattr(persistent_db, 'save_interaction'):
                persistent_db.save_interaction(user_id=user_id, role="user", content=user_input)
                persistent_db.save_interaction(user_id=user_id, role="assistant", content=response)
            elif hasattr(persistent_db, 'store_conversation'):
                persistent_db.store_conversation(user_id, [("user", user_input), ("assistant", response)])
        except Exception as memory_error:
            print(f"⚠️ Alerta no bloqueante en guardado de interacción: {memory_error}")

        return response

    except Exception as e:
        print(f"❌ Error catastrófico en el pipeline del agente: {e}")
        return (
            "Disculpe, ocurrió una inconsistencia interna al procesar su solicitud culinaria. "
            f"Reporte técnico: {str(e)}"
        )
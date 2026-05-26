import os
import re

from app.ingredient_match import bloque_analisis_para_prompt
from app.llm import LLMClient
from app.domain_validator import DomainValidator
from app.planning_agent import PlanningAgent
from app.semantic_retriever import SemanticContextRetriever
from app.rag import RAGSystem

# Inicializar componentes avanzados
domain_validator = DomainValidator()
planning_agent = PlanningAgent(llm_client=None)  # Usa LLMClient interno
semantic_retriever = SemanticContextRetriever()
rag_system = RAGSystem()
llm_client = LLMClient()


def _extract_ingredients_from_text(text: str) -> list[str]:
    """
    Intenta extraer ingredientes desde textos típicos del frontend.
    Caso esperado (en /recomendar): "Tengo estos ingredientes: A, B, C ..."
    """
    t = text or ""
    m = re.search(r"ingredientes?\s*:\s*(.+?)(?:\s+y\s+prefiero|\.\s*$|\s*$)", t, flags=re.IGNORECASE)
    if not m:
        return []

    raw = m.group(1)
    # Quitar posibles sufijos
    raw = re.split(r"\s+y\s+prefiero\s+", raw, flags=re.IGNORECASE)[0]

    parts = re.split(r",|\s+y\s+|\s+e\s+|;|/", raw)
    cleaned = [p.strip().lower() for p in parts if p and p.strip()]
    # Normalizar espacios y remover duplicados conservando orden
    seen = set()
    out: list[str] = []
    for c in cleaned:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


# Para compatibilidad con `from .agent import agent` en `app/main.py`.
# En esta versión el endpoint se apoya en RAG + LLM directamente desde `execute_with_planning`.
class _AgentShim:
    def __init__(self, llm_client_: LLMClient):
        self._llm_client = llm_client_

    def invoke(self, payload: dict) -> dict:
        prompt = payload.get("input") or payload.get("prompt") or ""
        return {"output": self._llm_client.generate_response(prompt)}


agent = _AgentShim(llm_client)


def validate_and_filter_input(user_input: str) -> tuple[bool, str]:
    """
    Valida que la entrada sea sobre recetas.
    Cumple requisito: Solo responde sobre recetas.
    
    Args:
        user_input: Texto del usuario
    
    Returns:
        Tupla (es_válido, mensaje_si_inválido)
    """
    is_valid, message = domain_validator.validate_and_filter(user_input)
    return is_valid, message


def execute_with_planning(user_input: str, user_id: str = "default") -> str:
    """
    Ejecuta consulta con planificación y contexto enriquecido.
    Cumple IL2.3: Planificación y IL2.2 + IL2.4: Memoria persistente + Recuperación semántica.
    
    Args:
        user_input: Pregunta del usuario
        user_id: ID del usuario para contexto personalizado
    
    Returns:
        Respuesta del agente
    """
    
    # 1. Validar dominio (CRÍTICO: Solo sobre recetas)
    is_valid, error_msg = validate_and_filter_input(user_input)
    if not is_valid:
        return error_msg
    
    # 2. Crear plan para tareas complejas (IL2.3)
    plan = planning_agent.create_plan(user_input)
    plan_valid, plan_msg = planning_agent.validate_plan(plan)
    
    if not plan_valid:
        print(f"⚠️ Plan inválido: {plan_msg}")
    
    # 3. Enriquecer prompt con contexto histórico (IL2.4)
    enriched_prompt = semantic_retriever.build_enriched_prompt(
        user_id=user_id,
        current_query=user_input,
        base_prompt=user_input
    )
    
    # 4. Generar respuesta usando RAG + LLM (sin Agents de LangChain)
    try:
        chunks = rag_system.search_chunks(user_input, top_k=5)
        resultados_rag = ""
        analisis_ing = ""
        if chunks:
            resultados_rag = "\n---\n".join(
                [f"Fuente: {c['source']}\n{c['text']}" for c in chunks]
            )

            ingredientes = _extract_ingredients_from_text(user_input)
            if ingredientes:
                analisis_ing = bloque_analisis_para_prompt(ingredientes, chunks)

        prompt = f"""
=== RECETAS EN TU BASE DE DATOS PERSONAL (RAG) ===
{resultados_rag or "(Sin fragmentos RAG.)"}

=== COINCIDENCIA INGREDIENTES (hecha con hechos; no inventes cifras) ===
{analisis_ing or "—"}

=== CONTEXTO DEL USUARIO (preferencias + historial) ===
{enriched_prompt}

=== INSTRUCCIONES ===
Solo usa recetas que aparezcan en el bloque RAG. No inventes recetas ni cifras.
Recomienda hasta 3 recetas, priorizando mayor coincidencia.
Incluye una breve explicación de por qué recomiendas cada receta según el contexto del usuario.
"""

        response = llm_client.generate_response(prompt)
        
        # 5. Guardar conversación en memoria persistente (IL2.2)
        memory_db = semantic_retriever.memory_db
        memory_db.store_conversation(user_id, [
            ("user", user_input),
            ("assistant", response)
        ])
        
        return response
    
    except Exception as e:
        print(f"Error en ejecución: {e}")
        return f"Hubo un error procesando tu pregunta: {str(e)}"
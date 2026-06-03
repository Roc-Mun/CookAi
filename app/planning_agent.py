import json
import re
from typing import List, Dict, Any, Optional
from app.llm import LLMClient
from app.tools import web_search_tool, tu_herramienta_rag_local


class PlanningAgent:

    def __init__(self, llm_client: Optional[LLMClient] = None):
        # Inyección correcta del cliente centralizado (Garantiza consistencia)
        self.llm_client = llm_client or LLMClient()

    def create_plan(self, objective: str, context: str = "") -> Dict[str, Any]:

        # Si no se provee contexto, asegurar un string vacío para evitar fallos de interpolación
        context_str = context if context else "No se registra contexto adicional previo."

        prompt = f"""
Eres CookAI, el submódulo de planificación de un sistema experto culinario.
Tu tarea es tomar la solicitud del usuario y diseñar un plan estructurado de pasos lógicos para resolverla.

=================================================
CONTEXTO E HISTORIAL DEL USUARIO (MEMORIA)
=================================================
{context_str}

=================================================
SOLICITUD / OBJETIVO A RESOLVER
=================================================
{objective}

Genera un plan de ejecución detallado adaptado a este objetivo.
Debes responder ÚNICAMENTE con un objeto JSON válido, que siga la siguiente estructura exacta (no agregues texto introductorio ni de cierre):

{{
    "objetivo": "Breve resumen de la meta culinaria del usuario",
    "pasos": [
        {{
            "numero": 1,
            "accion": "Descripción clara de la acción lúdica o de filtrado a realizar",
            "herramienta_recomendada": "buscar_recetas_rag | analizar_ingredientes | aplicar_restricciones",
            "entrada_esperada": "Datos requeridos para ejecutar este paso",
            "salida_esperada": "Resultado esperado de este paso",
            "depende_de": null
        }},
        {{
            "numero": 2,
            "accion": "Segunda acción lógica del proceso",
            "herramienta_recomendada": "analizar_ingredientes",
            "entrada_esperada": "Datos del paso anterior",
            "salida_esperada": "Resultado del análisis",
            "depende_de": 1
        }}
    ],
    "criterio_completitud": "Cómo se constata que la recomendación final cumple con las restricciones del usuario."
}}
"""
        try:
            response = self.llm_client.generate_response(prompt)
            return self._parse_json_safely(response, objective)

        except Exception as e:
            print(f"⚠️ Error en generación del LLM para el plan: {e}")
            return self._default_plan(objective)

    def _parse_json_safely(self, raw_text: str, objective: str) -> Dict[str, Any]:
        """Extrae de forma robusta estructuras JSON mitigando prefijos basura del LLM."""
        try:
            # Limpieza básica de bloques de código Markdown
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()

            # Intento de extracción mediante RegEx si el LLM incluyó texto antes/después
            json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(0)

            return json.loads(clean_text)
        except Exception:
            print("⚠️ Falla de formato JSON en respuesta del planificador. Activando plan de respaldo.")
            return self._default_plan(objective)

    def _default_plan(self, objective: str) -> Dict[str, Any]:
        """Estrategia de contingencia (Fallback) para garantizar la continuidad del flujo (IL2.3)."""
        return {
            "objetivo": objective,
            "pasos": [
                {
                    "numero": 1,
                    "accion": "Consultar la base de datos vectorial RAG para extraer recetas candidatas.",
                    "herramienta_recomendada": "buscar_recetas_rag",
                    "entrada_esperada": objective,
                    "salida_esperada": "Documentos y recetas que coincidan semánticamente.",
                    "depende_de": None
                },
                {
                    "numero": 2,
                    "accion": "Ejecutar análisis determinístico de porcentajes de ingredientes y cruce con el perfil del usuario.",
                    "herramienta_recommended": "analizar_ingredientes",
                    "entrada_esperada": "Insumos detectados en el prompt",
                    "salida_esperada": "Nivel de compatibilidad de recetas encontradas",
                    "depende_de": 1
                },
                {
                    "numero": 3,
                    "accion": "Formatear y presentar recomendaciones personalizadas respetando los límites de la base de conocimiento.",
                    "herramienta_recomendada": "generar_respuesta_llm",
                    "entrada_esperada": "Contexto e ingredientes consolidados",
                    "salida_esperada": "Respuesta final entregada al cliente",
                    "depende_de": 2
                }
            ],
            "criterio_completitud": "El usuario obtiene una respuesta culinaria pertinente sin alucinaciones."
        }

    def validate_plan(self, plan: Dict[str, Any]) -> tuple[bool, str]:
        """Valida las reglas de consistencia de la descomposición de tareas."""
        if not plan or not isinstance(plan, dict):
            return False, "Estructura de plan inválida o vacía."

        pasos = plan.get("pasos", [])
        if not pasos:
            return False, "El plan no contiene un mapa de pasos a seguir."

        for i, paso in enumerate(pasos, 1):
            if paso.get("numero") != i:
                return False, f"Inconsistencia en secuencia: El paso {paso.get('numero')} rompe el orden esperado."

            depende = paso.get("depende_de")
            if depende and (not isinstance(depende, int) or depende >= i):
                return False, f"Error de dependencia en paso {i}: Hace referencia a un paso posterior o inexistente."

        return True, "Plan verificado con éxito."

    def format_plan_for_prompt(self, plan: Dict[str, Any]) -> str:

        if not plan:
            return "No se pudo estructurar un plan válido."

        lines = [f"Meta del Plan: {plan.get('objetivo', 'Procesar consulta')}\n"]
        for paso in plan.get("pasos", []):
            lines.append(
                f"  [Paso {paso.get('numero')}] {paso.get('accion')}\n"
                f"    - Enfoque técnico: {paso.get('herramienta_recomendada')}\n"
                f"    - Requiere: {paso.get('entrada_esperada')}\n"
                f"    - Generará: {paso.get('salida_esperada')}"
            )
        lines.append(f"\nCriterio de Éxito: {plan.get('criterio_completitud', 'Validación del orquestador')}")
        return "\n".join(lines)


class ExecutionContext:

    def __init__(self, plan: Dict[str, Any]):
        self.plan = plan
        self.step_results = {}
        self.failures = []
        self.current_step = 0
        self.progress = 0.0

    def record_step_result(self, step_num: int, result: str):
        """Registra el resultado de un paso intermedio calculando el progreso incremental."""
        self.step_results[step_num] = result
        self.current_step = step_num
        total = len(self.plan.get("pasos", [1]))
        self.progress = (step_num / total) * 100

    def record_failure(self, step_num: int, error: str):
        """Registra una anomalía operativa para permitir decisiones reactivas."""
        self.failures.append((step_num, error))

    def is_complete(self) -> bool:
        """Verifica si el ciclo completo de ejecución planeado concluyó."""
        return self.current_step == len(self.plan.get("pasos", []))


    # Lista de herramientas ahora tiene DOS opciones:
tools = [
    tu_herramienta_rag_local,  # Opción 1: Tu RAG local (chroma_db)
    web_search_tool            # Opción 2: El buscador de internet en vivo
]

# Lista de herramientas ahora tiene DOS opciones (Mantener igual)
tools = [
    tu_herramienta_rag_local,  # Opción 1: Tu RAG local (chroma_db)
    web_search_tool            # Opción 2: El buscador de internet en vivo
]
# =========================================================
# ORQUESTADOR DINÁMICO RECIPIENTE DE PLANES (PRO + FILTRO ESTRICTO)
# =========================================================
class DynamicAgentExecutor:
    def __init__(self):
        # Reutilizamos tu cliente centralizado para mantener consistencia arquitectónica
        self.llm_client = LLMClient()
        self.planner = PlanningAgent(llm_client=self.llm_client)

    def run(self, query: str) -> str:
        # 1. Generamos el plan formal usando la estructura académica que ya programaste
        plan_json = self.planner.create_plan(objective=query)

        # 2. Inicializamos el contexto de ejecución para trazar el flujo
        contexto_ejecucion = ExecutionContext(plan=plan_json)

        informacion_recuperada = ""
        pasos = plan_json.get("pasos", [])

        # 3. Simulamos la ejecución del plan recorriendo las herramientas asignadas
        for paso in pasos:
            num = paso.get("numero", 1)
            herramienta = paso.get("herramienta_recomendada", "")

            try:
                if "rag" in herramienta.lower():
                    resultado = tu_herramienta_rag_local(query)
                    if resultado and "no se encontr" not in str(resultado).lower():
                        informacion_recuperada += f"\n[Datos RAG]: {str(resultado)}"
                    contexto_ejecucion.record_step_result(num, "Búsqueda RAG completada.")
                else:
                    resultado = web_search_tool(query)
                    informacion_recuperada += f"\n[Datos Web]: {str(resultado)}"
                    contexto_ejecucion.record_step_result(num, "Búsqueda Web en vivo completada.")
            except Exception as e:
                contexto_ejecucion.record_failure(num, str(e))

        if not informacion_recuperada.strip():
            informacion_recuperada = "No se logró consolidar datos externos del motor de búsqueda."

        # 4. PASAMOS EL CONTEXTO AL LLM CON LAS REGLAS DE CONTROL DE INGREDIENTES
        prompt_formateador = f"""
Eres CookAI, un asistente de cocina profesional de élite. Tu tarea es procesar la solicitud del usuario utilizando la información real recuperada por nuestras herramientas del sistema.

REGLAS CRÍTICAS DE CONTROL DE INGREDIENTES Y FILTRADO (¡MÁXIMA PRIORIDAD!):
1) Analiza cuidadosamente la consulta del usuario. Si el usuario menciona tener ingredientes específicos (ejemplo: 'tengo lentejas y fideos', 'tengo pollo', 'qué cocino con papas y queso', etc.), las recetas que propongas deben incluir OBLIGATORIAMENTE esos ingredientes principales en la sección de ingredientes y en la preparación paso a paso.
2) Si la información recuperada de Internet o RAG contiene platos que NO usan los ingredientes que el usuario dijo tener (como una Pascualina de acelga cuando el usuario pidió fideos/lentejas), ignora por completo esa receta intrusa. En su lugar, usa tus conocimientos de chef para inventar y estructurar 1 o 2 recetas lógicas y deliciosas que SÍ utilicen de forma real y protagónica los insumos del usuario (por ejemplo: 'Guiso de fideos con lentejas' o 'Sopa nutritiva de lentejas y pasta').

REGLAS DE FORMATO EXIGIDO:
- Diseña de 1 a 2 recetas detalladas que cumplan con la restricción anterior.
- Cada receta debe iniciar con un título limpio usando emojis atractivos.
- Crea una sección llamada '**Ingredientes a usar o reemplazar:**'.
- Crea una sección llamada '**Preparación Paso a Paso:**' numerada estrictamente como 1), 2), 3)... etc. Los pasos deben tener sentido culinario real para el plato.
- Finaliza cada receta con la línea exacta: '⏱️ **Tiempo de cocción:**' o '⏱️ **Tiempo de preparación:**' con un estimado real.

Consulta del usuario: {query}
Información recuperada por el sistema (¡FíLocalízala y descarta lo que no sirva!):
{informacion_recuperada}

Genera tu respuesta gastronómica estructurada y 100% coherente con los ingredientes solicitados:
"""
        try:
            # Mandamos el prompt final a tu cliente LLM unificado
            respuesta_gourmet = self.llm_client.generate_response(prompt_formateador)
            return respuesta_gourmet
        except Exception as e:
            return f"⚠️ Error al formatear la respuesta del agente: {str(e)}"

    def invoke(self, inputs: dict) -> dict:
        q = inputs.get("input", "") if isinstance(inputs, dict) else str(inputs)
        resultado_texto = self.run(q)
        return {
            "output": resultado_texto,
            "respuesta": resultado_texto,
            "response": resultado_texto,
            "message": resultado_texto,
            "status": "success"
        }

# Instanciamos el agente unificado con el mismo nombre exacto que requiere app/main.py
agent = DynamicAgentExecutor()
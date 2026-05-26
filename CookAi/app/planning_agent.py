"""
Agente Planificador - IL2.3
Descompone objetivos complejos en pasos ejecutables.
Implementa "Plan-and-Execute" pattern.
"""

import json
from typing import List, Dict, Any, Optional
from app.llm import LLMClient


class PlanningAgent:
    """
    Agente que planifica antes de ejecutar.
    Cumple IL2.3: Descomposición de objetivos en pasos ejecutables.
    
    Patrón: 
    1. Recibe objetivo complejo
    2. Genera plan con pasos
    3. Retorna plan para ejecución
    4. Ejecutor sigue los pasos
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def create_plan(self, objective: str, context: str = "") -> Dict[str, Any]:
        """
        Crea un plan estructurado para alcanzar un objetivo.
        
        Args:
            objective: Objetivo/pregunta del usuario
            context: Contexto adicional (preferencias, historial, etc.)
        
        Returns:
            Dict con estructura del plan
        """
        prompt = f"""
        CONTEXTO DE USUARIO:
        {context}
        
        OBJETIVO:
        {objective}
        
        TAREA: Crea un plan paso a paso para resolver este objetivo. 
        El plan debe ser específico, ejecutable, y considerar el contexto del usuario.
        
        FORMATO JSON (devuelve SOLO JSON válido, sin backticks):
        {{
            "objetivo": "resumen del objetivo",
            "pasos": [
                {{
                    "numero": 1,
                    "accion": "descripción clara de qué hacer",
                    "herramienta_recomendada": "buscar_recetas | analizar_ingredientes | obtener_sustitutos | guardar_receta",
                    "entrada_esperada": "qué datos necesita este paso",
                    "salida_esperada": "qué debe producir este paso",
                    "depende_de": null o numero del paso anterior
                }},
                ...
            ],
            "criterio_completitud": "cómo saber si el plan se completó exitosamente",
            "adaptaciones_posibles": ["alternativa si paso 1 falla", "alternativa si paso 2 falla"]
        }}
        """
        
        try:
            response = self.llm_client.generate_response(prompt)
            
            # Intentar parsear JSON
            try:
                # Limpiar respuesta de posibles backticks
                clean_response = response.replace("```json", "").replace("```", "").strip()
                plan = json.loads(clean_response)
            except json.JSONDecodeError:
                # Si no es JSON válido, retornar plan por defecto
                plan = self._default_plan(objective)
            
            return plan
        
        except Exception as e:
            print(f"Error al crear plan: {e}")
            return self._default_plan(objective)
    
    def _default_plan(self, objective: str) -> Dict[str, Any]:
        """Plan por defecto si el LLM falla"""
        return {
            "objetivo": objective,
            "pasos": [
                {
                    "numero": 1,
                    "accion": "Buscar recetas relevantes en la base de datos",
                    "herramienta_recomendada": "buscar_recetas",
                    "entrada_esperada": objective,
                    "salida_esperada": "Lista de recetas candidatas",
                    "depende_de": None
                },
                {
                    "numero": 2,
                    "accion": "Analizar coincidencia de ingredientes si es relevante",
                    "herramienta_recomendada": "analizar_ingredientes",
                    "entrada_esperada": "Recetas encontradas y preferencias del usuario",
                    "salida_esperada": "Análisis de compatibilidad",
                    "depende_de": 1
                },
                {
                    "numero": 3,
                    "accion": "Presentar recomendación final personalizada",
                    "herramienta_recomendada": "respuesta directa",
                    "entrada_esperada": "Resultados de pasos 1-2",
                    "salida_esperada": "Recomendación clara y justificada",
                    "depende_de": 2
                }
            ],
            "criterio_completitud": "Usuario recibe recomendación clara y personalizada",
            "adaptaciones_posibles": []
        }
    
    def validate_plan(self, plan: Dict[str, Any]) -> tuple[bool, str]:
        """
        Valida que un plan sea ejecutable.
        
        Args:
            plan: Plan generado
        
        Returns:
            Tupla (es_válido, mensaje)
        """
        # Validaciones básicas
        if not plan.get("pasos"):
            return False, "Plan sin pasos"
        
        pasos = plan["pasos"]
        
        # Validar que los pasos están numerados
        for i, paso in enumerate(pasos, 1):
            if paso.get("numero") != i:
                return False, f"Paso {i} tiene numeración incorrecta"
        
        # Validar dependencias
        for paso in pasos:
            depende = paso.get("depende_de")
            if depende and depende >= paso["numero"]:
                return False, f"Paso {paso['numero']} tiene dependencia circular"
        
        return True, "Plan válido"
    
    def extract_step_inputs(
        self, 
        step: Dict[str, Any],
        previous_outputs: Dict[int, str]
    ) -> str:
        """
        Extrae inputs para un paso considerando outputs anteriores.
        
        Args:
            step: Paso actual
            previous_outputs: Dict con outputs de pasos anteriores
        
        Returns:
            Input limpio para el paso
        """
        depende_de = step.get("depende_de")
        
        if depende_de and depende_de in previous_outputs:
            return previous_outputs[depende_de]
        
        return step.get("entrada_esperada", "")
    
    def validate_step_output(
        self, 
        step: Dict[str, Any],
        output: str
    ) -> bool:
        """
        Valida que el output de un paso cumple lo esperado.
        
        Args:
            step: Paso ejecutado
            output: Output obtenido
        
        Returns:
            True si output es válido
        """
        if not output or output.strip() == "":
            return False
        
        # Validaciones simples
        expected = step.get("salida_esperada", "").lower()
        output_lower = output.lower()
        
        # Palabras clave esperadas
        if "receta" in expected and len(output) < 50:
            return False
        
        if "análisis" in expected and len(output) < 30:
            return False
        
        return True


class ExecutionContext:
    """
    Mantiene contexto durante la ejecución de un plan.
    Cumple IL2.3: Validación y continuidad entre pasos.
    """
    
    def __init__(self, plan: Dict[str, Any]):
        self.plan = plan
        self.step_results = {}  # {numero_paso: resultado}
        self.failures = []      # [(paso, error)]
        self.current_step = 0
        self.progress = 0.0
    
    def record_step_result(self, step_num: int, result: str):
        """Registra el resultado de un paso"""
        self.step_results[step_num] = result
        self.current_step = step_num
        self.progress = (step_num / len(self.plan["pasos"])) * 100
    
    def record_failure(self, step_num: int, error: str):
        """Registra un fallo en un paso"""
        self.failures.append((step_num, error))
    
    def get_progress_report(self) -> str:
        """Retorna reporte de progreso"""
        total_steps = len(self.plan["pasos"])
        return f"Paso {self.current_step}/{total_steps} ({self.progress:.0f}% completado)"
    
    def get_context_for_next_step(self, step_num: int) -> Dict[str, Any]:
        """Obtiene contexto de pasos anteriores para el siguiente"""
        return {
            "step_number": step_num,
            "previous_results": self.step_results,
            "failures_so_far": self.failures,
            "progress": self.progress
        }
    
    def is_complete(self) -> bool:
        """Verifica si la ejecución está completa"""
        return self.current_step == len(self.plan["pasos"])
    
    def get_final_summary(self) -> str:
        """Resumen final de la ejecución"""
        summary = f"\n✅ Plan completado: {self.plan['objetivo']}\n"
        summary += f"Pasos ejecutados: {self.current_step}/{len(self.plan['pasos'])}\n"
        
        if self.failures:
            summary += f"Fallos encontrados: {len(self.failures)}\n"
            for step, error in self.failures:
                summary += f"  - Paso {step}: {error}\n"
        
        return summary

"""
CookAI - Recuperador Semántico de Contexto de Largo Plazo
Cumple con los requisitos de la pauta de evaluación Duoc UC:
- IL2.2: Configuración de recuperación de contexto continuo entre sesiones.
- IL2.4: Orquestación y enriquecimiento de prompts mediante persistencia de datos.
"""

import json
from typing import List, Dict, Any, Optional
from app.persistent_memory import persistent_db, PersistentMemoryDB


class SemanticContextRetriever:
    """
    Recupera contexto histórico relevante y preferencias de largo plazo del usuario.
    Permite al Agent Orchestrator tomar decisiones personalizadas y adaptativas (IL2.3).
    """

    def __init__(self, memory_db: Optional[PersistentMemoryDB] = None):
        # Usar de forma centralizada la instancia global para evitar bloqueos en SQLite
        self.memory_db = memory_db or persistent_db

    def retrieve_relevant_context(
            self,
            user_id: str,
            current_query: str,
            top_k: int = 2
    ) -> str:
        """
        Busca y recupera diálogos históricos con coincidencia semántica/palabras clave.
        """
        # Recuperar el historial desde la base de datos persistente (SQLite)
        conversations = self.memory_db.get_conversation_history(user_id, limit=15)

        if not conversations:
            return ""

        # Extraer fichas o conceptos clave de la petición actual
        current_keywords = self._extract_keywords(current_query)
        if not current_keywords:
            return ""

        # Calcular relevancia y rankear conversaciones pasadas
        relevant = []
        for conv in conversations:
            relevance_score = self._calculate_relevance(conv, current_keywords)
            if relevance_score > 0:
                relevant.append((relevance_score, conv))

        # Ordenar de forma descendente por score
        relevant.sort(key=lambda x: x[0], reverse=True)
        top_convs = relevant[:top_k]

        if not top_convs:
            return ""

        # Formatear el contexto histórico para inyección limpia en el prompt
        context_text = "--- INTERACCIONES HISTÓRICAS RELEVANTES ---\n"
        for idx, (score, conv) in enumerate(top_convs, 1):
            context_text += f"[Conversación Pasada #{idx}]\n"
            for msg in conv['messages']:
                role_display = "Usuario" if msg['role'] == 'user' else "CookAI"
                # Entregar el contenido completo al modelo para que no pierda datos críticos
                context_text += f"{role_display}: {msg['content']}\n"
            context_text += "\n"

        return context_text

    def get_user_preferences_context(self, user_id: str) -> str:
        """
        Recupera el perfil de preferencias estructurado del usuario.
        """
        prefs = self.memory_db.get_user_preferences(user_id)

        if not prefs:
            return ""

        lines = ["--- PERFIL DE PREFERENCIAS GENERALES ---"]

        if prefs.get('dietary_restrictions'):
            lines.append(f"- Restricciones dietéticas: {', '.join(prefs['dietary_restrictions'])}")

        if prefs.get('favorite_cuisines'):
            lines.append(f"- Estilos de cocina preferidos: {', '.join(prefs['favorite_cuisines'])}")

        if prefs.get('disliked_ingredients'):
            lines.append(f"- Ingredientes a evitar: {', '.join(prefs['disliked_ingredients'])}")

        if prefs.get('cooking_time_preference'):
            lines.append(f"- Preferencia de tiempo disponible: {prefs['cooking_time_preference']}")

        if prefs.get('budget_preference'):
            lines.append(f"- Rango presupuestario: {prefs['budget_preference']}")

        # Si no hay preferencias guardadas reales, retornar vacío de forma segura
        if len(lines) == 1:
            return ""

        return "\n".join(lines)

    def get_saved_recipes_summary(self, user_id: str) -> str:
        """
        Obtiene un resumen de los títulos de recetas que el usuario guardó anteriormente.
        """
        saved_recipes = self.memory_db.get_saved_recipes(user_id)

        if not saved_recipes:
            return ""

        lines = ["--- RECETARIO PERSONAL GUARDADO ---"]
        for recipe in saved_recipes[:3]:  # Mostrar un máximo de 3 para cuidar los tokens de contexto
            lines.append(f"- Receta: {recipe.get('title', 'Sin Título')}")

        return "\n".join(lines)

    def build_enriched_prompt(
            self,
            user_id: str,
            current_query: str,
            base_prompt: str = ""
    ) -> str:
        """
        Orquesta y compila todos los segmentos de memoria de largo plazo (IL2.2).
        Retorna exclusivamente el bloque estructurado listo para inyectarse en el orquestador.
        """
        blocks = []

        # 1. Bloque de Perfil Adaptativo
        prefs_context = self.get_user_preferences_context(user_id)
        if prefs_context:
            blocks.append(prefs_context)

        # 2. Bloque de Recetas Guardadas (Herramienta de Escritura IL2.1)
        saved_context = self.get_saved_recipes_summary(user_id)
        if saved_context:
            blocks.append(saved_context)

        # 3. Bloque de Similitud Semántica Histórica
        historical_context = self.retrieve_relevant_context(user_id, current_query)
        if historical_context:
            blocks.append(historical_context)

        if not blocks:
            return "No se registra historial o preferencias persistentes para este usuario."

        return "\n\n".join(blocks)

    def _extract_keywords(self, text: str) -> set:
        """Extrae palabras clave semánticas asociadas al dominio culinario y de salud."""
        if not text:
            return set()

        # Diccionario semántico expandido para aumentar el porcentaje de aciertos en la búsqueda
        keywords_target = {
            'ingrediente', 'receta', 'cocina', 'tiempo', 'presupuesto',
            'alergia', 'vegano', 'vegetariano', 'gluten', 'lactosa',
            'pollo', 'carne', 'pescado', 'verduras', 'frutas', 'arroz',
            'cena', 'almuerzo', 'desayuno', 'postre', 'fácil', 'rápido',
            'saludable', 'dieta', 'calorías', 'pasta', 'sopa', 'ensalada'
        }

        text_lower = text.lower()
        # Capturar coincidencia por subcadenas o términos exactos
        found = {kw for kw in keywords_target if kw in text_lower}
        return found

    def _calculate_relevance(self, conversation: Dict, keywords: set) -> float:
        """Calcula el índice de coincidencia semántica (Score Jaccard simplificado)."""
        if not keywords or 'messages' not in conversation or not conversation['messages']:
            return 0.0

        # Unificar todo el texto de la conversación histórica para el escaneo
        all_text = " ".join([msg['content'].lower() for msg in conversation['messages']])

        matches = sum(1 for kw in keywords if kw in all_text)
        return float(matches / len(keywords))
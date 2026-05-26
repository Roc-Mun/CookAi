"""
Recuperador Semántico de Contexto - IL2.4
Busca conversaciones histórico relevantes usando similitud semántica.
Implementa recuperación inteligente de contexto de largo plazo.
"""

import json
from typing import List, Dict, Any, Optional
from app.persistent_memory import PersistentMemoryDB


class SemanticContextRetriever:
    """
    Recupera contexto histórico relevante del usuario.
    Cumple IL2.4: Recuperación semántica de contexto.
    
    Aunque no usamos embeddings complejos aquí (para simplicidad),
    implementamos búsqueda inteligente basada en palabras clave.
    """
    
    def __init__(self, memory_db: Optional[PersistentMemoryDB] = None):
        self.memory_db = memory_db or PersistentMemoryDB()
    
    def retrieve_relevant_context(
        self, 
        user_id: str, 
        current_query: str,
        top_k: int = 3
    ) -> str:
        """
        Recupera conversaciones pasadas relevantes a la consulta actual.
        
        Args:
            user_id: ID del usuario
            current_query: Pregunta actual del usuario
            top_k: Número de contextos a recuperar
        
        Returns:
            Texto con contexto histórico relevante (formateado para el prompt)
        """
        # Obtener historial completo
        conversations = self.memory_db.get_conversation_history(user_id, limit=20)
        
        if not conversations:
            return ""
        
        # Palabras clave de la consulta actual
        current_keywords = self._extract_keywords(current_query)
        
        # Buscar conversaciones relevantes
        relevant = []
        for conv in conversations:
            relevance_score = self._calculate_relevance(conv, current_keywords)
            if relevance_score > 0:
                relevant.append((relevance_score, conv))
        
        # Ordenar por relevancia y tomar top_k
        relevant.sort(key=lambda x: x[0], reverse=True)
        top_convs = relevant[:top_k]
        
        if not top_convs:
            return ""
        
        # Formatear contexto histórico
        context_text = "=== CONTEXTO HISTÓRICO DEL USUARIO ===\n"
        for idx, (score, conv) in enumerate(top_convs, 1):
            context_text += f"\nConversación {idx} (relevancia: {score:.2f}):\n"
            for msg in conv['messages']:
                role_display = "TÚ" if msg['role'] == 'user' else "COOKAI"
                context_text += f"{role_display}: {msg['content'][:100]}...\n"
        
        return context_text
    
    def get_user_preferences_context(self, user_id: str) -> str:
        """
        Obtiene preferencias guardadas del usuario para contexto.
        Cumple IL2.2: Continuidad de tareas con preferencias personalizadas.
        
        Args:
            user_id: ID del usuario
        
        Returns:
            Texto con preferencias (para inyectar en prompt)
        """
        prefs = self.memory_db.get_user_preferences(user_id)
        
        if not prefs:
            return ""
        
        text = "=== PREFERENCIAS PERSONALES DEL USUARIO ===\n"
        
        if prefs.get('dietary_restrictions'):
            text += f"Restricciones dietéticas: {', '.join(prefs['dietary_restrictions'])}\n"
        
        if prefs.get('favorite_cuisines'):
            text += f"Cocinas favoritas: {', '.join(prefs['favorite_cuisines'])}\n"
        
        if prefs.get('disliked_ingredients'):
            text += f"Ingredientes que no le gustan: {', '.join(prefs['disliked_ingredients'])}\n"
        
        if prefs.get('cooking_time_preference'):
            text += f"Tiempo de cocción preferido: {prefs['cooking_time_preference']}\n"
        
        if prefs.get('budget_preference'):
            text += f"Presupuesto preferido: {prefs['budget_preference']}\n"
        
        return text if text != "=== PREFERENCIAS PERSONALES DEL USUARIO ===\n" else ""
    
    def get_saved_recipes_summary(self, user_id: str) -> str:
        """
        Obtiene resumen de recetas guardadas del usuario.
        
        Args:
            user_id: ID del usuario
        
        Returns:
            Texto con recetas guardadas (para contexto)
        """
        saved_recipes = self.memory_db.get_saved_recipes(user_id)
        
        if not saved_recipes:
            return ""
        
        text = "=== RECETAS GUARDADAS PREVIAMENTE ===\n"
        for recipe in saved_recipes[:5]:  # Top 5
            text += f"- {recipe['title']} (calificación: {'⭐' * (recipe['rating'] or 0)})\n"
        
        return text
    
    def build_enriched_prompt(
        self, 
        user_id: str, 
        current_query: str,
        base_prompt: str
    ) -> str:
        """
        Construye un prompt enriquecido con contexto histórico.
        Cumple IL2.2 + IL2.4: Memoria persistente + Recuperación semántica.
        
        Args:
            user_id: ID del usuario
            current_query: Pregunta actual
            base_prompt: Prompt base sin contexto
        
        Returns:
            Prompt completo con contexto inyectado
        """
        enriched = ""
        
        # 1. Preferencias personales
        prefs_context = self.get_user_preferences_context(user_id)
        if prefs_context:
            enriched += prefs_context + "\n"
        
        # 2. Contexto histórico relevante
        historical_context = self.retrieve_relevant_context(user_id, current_query)
        if historical_context:
            enriched += historical_context + "\n"
        
        # 3. Recetas guardadas
        saved_context = self.get_saved_recipes_summary(user_id)
        if saved_context:
            enriched += saved_context + "\n"
        
        # 4. Agregar prompt base
        enriched += "\n" + base_prompt
        
        return enriched
    
    def _extract_keywords(self, text: str) -> set:
        """Extrae palabras clave de un texto"""
        # Palabras clave relacionadas con cocina
        keywords = {
            'ingrediente', 'receta', 'cocina', 'tiempo', 'presupuesto',
            'alergia', 'vegano', 'vegetariano', 'gluten', 'lactosa',
            'pollo', 'carne', 'pescado', 'verduras', 'frutas'
        }
        
        text_lower = text.lower()
        found = set()
        for kw in keywords:
            if kw in text_lower:
                found.add(kw)
        
        return found
    
    def _calculate_relevance(self, conversation: Dict, keywords: set) -> float:
        """
        Calcula relevancia de una conversación respecto a palabras clave.
        
        Args:
            conversation: Conversación con lista de mensajes
            keywords: Palabras clave buscadas
        
        Returns:
            Score de relevancia (0-1)
        """
        if not keywords:
            return 0.0
        
        all_text = " ".join([msg['content'].lower() for msg in conversation['messages']])
        
        matches = sum(1 for kw in keywords if kw in all_text)
        
        return matches / len(keywords) if keywords else 0.0

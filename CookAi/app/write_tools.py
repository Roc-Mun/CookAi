"""
Herramientas de Escritura para el Agente - IL2.1
Permite al agente guardar, modificar y persistir datos.
Cumple IL2.1: Herramientas de ESCRITURA (no solo lectura).
"""

from langchain_core.tools import tool
from app.persistent_memory import PersistentMemoryDB


# Inicializar BD persistente
persistent_db = PersistentMemoryDB()


@tool
def guardar_receta_seleccionada(
    user_id: str,
    titulo: str,
    contenido: str,
    fuente: str = "manual"
) -> str:
    """
    Guarda una receta seleccionada por el usuario en su historial personal.
    
    Args:
        user_id: ID único del usuario
        titulo: Título de la receta
        contenido: Texto completo de la receta
        fuente: Dónde se encontró la receta (RAG, generada, etc.)
    
    Returns:
        Confirmación de guardado
    """
    try:
        persistent_db.save_recipe(user_id, titulo, contenido, fuente)
        return f"✅ Receta '{titulo}' guardada exitosamente en tu historial personal."
    except Exception as e:
        return f"❌ Error al guardar receta: {str(e)}"


@tool
def actualizar_preferencias_usuario(
    user_id: str,
    dietary_restrictions: list = None,
    favorite_cuisines: list = None,
    disliked_ingredients: list = None,
    cooking_time_preference: str = None,
    budget_preference: str = None
) -> str:
    """
    Actualiza las preferencias de cocina del usuario basadas en el contexto.
    Cumple IL2.2: Aprendizaje y adaptación entre sesiones.
    
    Args:
        user_id: ID del usuario
        dietary_restrictions: Restricciones dietéticas (vegetariano, sin gluten, etc.)
        favorite_cuisines: Cocinas favoritas
        disliked_ingredients: Ingredientes que no le gustan
        cooking_time_preference: Tiempo de cocción preferido
        budget_preference: Presupuesto preferido
    
    Returns:
        Confirmación de actualización
    """
    try:
        preferences = {
            "dietary_restrictions": dietary_restrictions or [],
            "favorite_cuisines": favorite_cuisines or [],
            "disliked_ingredients": disliked_ingredients or [],
            "cooking_time_preference": cooking_time_preference or "",
            "budget_preference": budget_preference or ""
        }
        
        persistent_db.update_user_preferences(user_id, preferences)
        
        # Construir mensaje de confirmación
        msg = "✅ Preferencias actualizadas:\n"
        if dietary_restrictions:
            msg += f"- Restricciones: {', '.join(dietary_restrictions)}\n"
        if favorite_cuisines:
            msg += f"- Cocinas favoritas: {', '.join(favorite_cuisines)}\n"
        if disliked_ingredients:
            msg += f"- Ingredientes a evitar: {', '.join(disliked_ingredients)}\n"
        if cooking_time_preference:
            msg += f"- Tiempo preferido: {cooking_time_preference}\n"
        if budget_preference:
            msg += f"- Presupuesto preferido: {budget_preference}\n"
        
        return msg
    
    except Exception as e:
        return f"❌ Error al actualizar preferencias: {str(e)}"


@tool
def calificar_receta(user_id: str, recipe_title: str, rating: int) -> str:
    """
    Califica una receta que el usuario guardó.
    
    Args:
        user_id: ID del usuario
        recipe_title: Título de la receta a calificar
        rating: Calificación de 1-5 estrellas
    
    Returns:
        Confirmación de calificación
    """
    try:
        if not 1 <= rating <= 5:
            return "❌ La calificación debe estar entre 1 y 5 estrellas."
        
        # Nota: Esto es simplificado. En una BD real, actualizaríamos el registro existente
        persistent_db.save_recipe(user_id, recipe_title, "", "calificada", rating)
        
        stars = "⭐" * rating
        return f"✅ Receta calificada: {rating}/5 {stars}"
    
    except Exception as e:
        return f"❌ Error al calificar: {str(e)}"


@tool
def obtener_recetas_guardadas(user_id: str) -> str:
    """
    Obtiene todas las recetas que el usuario ha guardado.
    
    Args:
        user_id: ID del usuario
    
    Returns:
        Lista formateada de recetas guardadas
    """
    try:
        saved_recipes = persistent_db.get_saved_recipes(user_id)
        
        if not saved_recipes:
            return "No tienes recetas guardadas aún. ¡Guarda algunas para tener un historial personal!"
        
        msg = f"📚 Tu historial personal ({len(saved_recipes)} recetas):\n\n"
        for recipe in saved_recipes[:10]:  # Top 10
            stars = "⭐" * (recipe['rating'] or 0) if recipe['rating'] else "Sin calificar"
            msg += f"- {recipe['title']} ({stars})\n"
        
        return msg
    
    except Exception as e:
        return f"❌ Error al obtener recetas: {str(e)}"


@tool
def obtener_preferencias_usuario(user_id: str) -> str:
    """
    Obtiene las preferencias personalizadas del usuario.
    
    Args:
        user_id: ID del usuario
    
    Returns:
        Resumen de preferencias guardadas
    """
    try:
        prefs = persistent_db.get_user_preferences(user_id)
        
        if not prefs:
            return "No tienes preferencias guardadas. Cuéntame más sobre tus gustos culinarios para personalizarte mejor."
        
        msg = "📋 Tus preferencias personales:\n"
        if prefs.get('dietary_restrictions'):
            msg += f"- Restricciones: {', '.join(prefs['dietary_restrictions'])}\n"
        if prefs.get('favorite_cuisines'):
            msg += f"- Cocinas favoritas: {', '.join(prefs['favorite_cuisines'])}\n"
        if prefs.get('disliked_ingredients'):
            msg += f"- Ingredientes a evitar: {', '.join(prefs['disliked_ingredients'])}\n"
        if prefs.get('cooking_time_preference'):
            msg += f"- Tiempo preferido: {prefs['cooking_time_preference']}\n"
        if prefs.get('budget_preference'):
            msg += f"- Presupuesto: {prefs['budget_preference']}\n"
        
        return msg
    
    except Exception as e:
        return f"❌ Error al obtener preferencias: {str(e)}"

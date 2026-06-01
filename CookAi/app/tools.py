import json
from typing import Dict, Any, List
# Importamos las instancias globales centralizadas para evitar bloqueos de archivos
from app.rag import RAGSystem
from app.persistent_memory import persistent_db

# Compartir la misma instancia para evitar excepciones de ChromaDB
rag_system = RAGSystem()

# =========================================================
# 1. HERRAMIENTAS DE CONSULTA / RECUPERACIÓN
# =========================================================

def buscar_recetas_rag(query: str) -> str:
    """
    Herramienta de Consulta: Busca recetas relevantes en la base vectorial RAG
    utilizando emparejamiento semántico por distancia coseno.
    """
    if not query or not query.strip():
        return "Debe ingresar un término o ingrediente válido para buscar."

    resultados = rag_system.search(query, top_k=3)
    if not resultados:
        return "No se encontraron recetas que coincidan con la búsqueda en la base de conocimientos."

    return resultados


def obtener_sustitutos(ingrediente: str) -> str:
    """
    Herramienta de Consulta: Sugiere sustituciones culinarias saludables o
    aptas para alérgenos basadas en un ingrediente base.
    """
    if not ingrediente:
        return "Por favor, especifica un ingrediente para buscar su alternativa."

    sustituciones = {
        "leche": "Bebida vegetal (soya, almendra, avena o coco).",
        "azucar": "Stevia, alulosa, eritritol o miel natural.",
        "azúcar": "Stevia, alulosa, eritritol o miel natural.",
        "mantequilla": "Ghee, aceite de oliva o puré de palta/aguacate.",
        "harina": "Harina de avena integral, harina de almendras o harina sin gluten.",
        "huevo": "Semillas de chía hidratadas (1 cucharada por huevo) o puré de plátano.",
        "crema": "Crema de coco o yogur griego natural.",
        "queso": "Queso vegano a base de almendras o levadura nutricional."
    }

    target = ingrediente.lower().strip().replace("á", "a").replace("ú", "u")
    return sustituciones.get(
        target,
        f"No se registra una sustitución directa para '{ingrediente}'. Se sugiere consultar alternativas genéricas sin alérgenos."
    )


# =========================================================
# 2. HERRAMIENTAS DE RAZONAMIENTO / CÓMPUTO
# =========================================================

def analizar_coincidencia_ingredientes(ingredientes_usuario: List[str], texto_receta: str) -> Dict[str, Any]:
    """
    Herramienta de Razonamiento: Evalúa de forma determinista el porcentaje de
    coincidencia entre los ingredientes disponibles del usuario y los requeridos por la receta.
    Previene alucinaciones del LLM calculando intersecciones de conjuntos.
    """
    if not ingredientes_usuario or not texto_receta:
        return {"error": "Faltan parámetros: ingredientes del usuario o texto de la receta."}

    # Limpiar y normalizar los insumos del usuario
    user_set = {i.lower().strip() for i in ingredientes_usuario if i.strip()}

    # Extraer palabras del cuerpo de la receta (Buscador adaptativo simple)
    receta_lower = texto_receta.lower()

    ingredientes_encontrados = []
    ingredientes_faltantes = []

    for ing in user_set:
        if ing in receta_lower:
            ingredientes_encontrados.append(ing)
        else:
            ingredientes_faltantes.append(ing)

    total_disponibles = len(user_set)
    coincidencias = len(ingredientes_encontrados)
    porcentaje = (coincidencias / total_disponibles * 100) if total_disponibles > 0 else 0.0

    return {
        "porcentaje_coincidencia": f"{porcentaje:.1f}%",
        "ingredientes_utilizados": ingredientes_encontrados,
        "ingredientes_no_requeridos": ingredientes_faltantes,
        "viable": porcentaje >= 50.0
    }


# =========================================================
# 3. HERRAMIENTAS DE ESCRITURA / PERSISTENCIA
# =========================================================

def guardar_receta_usuario(user_id: str, titulo: str, contenido: str) -> str:
    """
    Herramienta de Escritura: Almacena de forma persistente una receta generada
    o recomendada en el historial de largo plazo (SQLite) y la indexa en el RAG.
    """
    if not user_id or not titulo or not contenido:
        return "Error: Faltan campos obligatorios para persistir la receta."

    try:
        # 1. Persistencia en la Base de Datos Relacional de largo plazo (IL2.2)
        persistent_db.save_recipe(
            user_id=user_id,
            recipe_title=titulo,
            recipe_content=contenido,
            source="Generada por CookAI"
        )

        # 2. Retroalimentación de la base de conocimientos RAG (IL2.1)
        meta_adicional = {"receta_titulo": titulo}
        rag_system.add_single_recipe_document(
            content=contenido,
            source=f"Usuario_{user_id}_Recetario",
            extra_metadata=meta_adicional
        )

        return f"✅ La receta '{titulo}' ha sido guardada con éxito en su perfil y re-indexada en el RAG."
    except Exception as e:
        return f"❌ Fallo al ejecutar la escritura de la receta: {str(e)}"


def registrar_preferencias(user_id: str, restricciones: List[str], gustos: List[str]) -> str:
    """
    Herramienta de Escritura: Actualiza de manera directa las preferencias de perfil
    del usuario en la memoria persistente para habilitar respuestas adaptativas posteriores (IL2.3).
    """
    if not user_id:
        return "Error: Identificador de usuario requerido."

    try:
        data_preferencias = {
            "dietary_restrictions": restricciones,
            "favorite_cuisines": gustos,
            "disliked_ingredients": [],
            "cooking_time_preference": "Variable",
            "budget_preference": "Variable"
        }
        persistent_db.update_user_preferences(user_id, data_preferencias)
        return "✅ Perfil culinario actualizado correctamente en la memoria de largo plazo."
    except Exception as e:
        return f"❌ Fallo al registrar las preferencias del usuario: {str(e)}"


# =========================================================
# MAPA CENTRALIZADO DE HERRAMIENTAS (TOOLKIT)
# =========================================================
# Permite al orquestador (agent.py) mandar a llamar las funciones dinámicamente por su string clave
COOKAI_TOOLKIT = {
    "buscar_recetas_rag": buscar_recetas_rag,
    "obtener_sustitutos": obtener_sustitutos,
    "analizar_coincidencia_ingredientes": analizar_coincidencia_ingredientes,
    "guardar_receta_usuario": guardar_receta_usuario,
    "registrar_preferencias": registrar_preferencias
}
from langchain_core.tools import tool
from app.rag import RAGSystem
from app.ingredient_match import analyze_overlap
from app.write_tools import (
    guardar_receta_seleccionada,
    actualizar_preferencias_usuario,
    calificar_receta,
    obtener_recetas_guardadas,
    obtener_preferencias_usuario
)

rag_system = RAGSystem()

@tool
def buscar_recetas(query: str) -> str:
    """
    Busca recetas relevantes en la base vectorial RAG.
    """
    resultados = rag_system.search(query, top_k=3)

    if not resultados:
        return "No encontré recetas relacionadas en la base de datos."

    return str(resultados)


@tool
def obtener_sustitutos(ingrediente: str) -> str:
    """
    Sugiere sustituciones para ingredientes comunes.
    """
    sustituciones = {
        "leche": "bebida vegetal (soya, almendra, avena)",
        "azúcar": "stevia o miel",
        "mantequilla": "aceite de oliva",
        "harina": "harina de avena o almendra",
        "huevo": "chía hidratada o linaza"
    }

    return sustituciones.get(
        ingrediente.lower().strip(),
        "No encontré sustituciones específicas para ese ingrediente."
    )


@tool
def analizar_ingredientes(input_text: str) -> str:
    """
    Analiza coincidencia entre ingredientes del usuario y una receta.

    FORMATO DE ENTRADA:
    ingredientes1, ingredientes2 || texto de la receta
    """
    try:
        user_ingredients, recipe_text = input_text.split("||")

        ingredientes = [
            i.strip()
            for i in user_ingredients.split(",")
            if i.strip()
        ]

        resultado = analyze_overlap(ingredientes, recipe_text)

        return str(resultado)

    except Exception:
        return (
            "Error en formato. Usa: "
            "ingrediente1, ingrediente2 || texto de la receta"
        )
"""
Coincidencia ingredientes usuario ↔ recetas RAG.
Análisis determinístico (sin LLM).
"""

import re
import unicodedata
from typing import Any


# =====================================
# NORMALIZACIÓN
# =====================================

def _strip_accents(text: str) -> str:

    return "".join(

        c for c in unicodedata.normalize(
            "NFD",
            text
        )

        if unicodedata.category(c) != "Mn"
    )


def normalize(text: str) -> str:

    if not text:

        return ""

    return _strip_accents(

        text.lower().strip()

    )


# =====================================
# DETECCIÓN SUSTITUCIÓN
# =====================================

def es_consulta_sustitucion(
        mensaje: str
) -> bool:

    text = normalize(mensaje)

    pattern = (

        r"reemplaz|"
        r"sustitu|"
        r"alternativ|"
        r"en vez de|"
        r"en lugar de|"
        r"cambiar.{0,40}por"
    )

    return bool(

        re.search(
            pattern,
            text
        )
    )


# =====================================
# MATCH INGREDIENTES
# =====================================

def user_ingredient_in_text(
        ingredient: str,
        haystack: str
) -> bool:

    ing = normalize(ingredient)

    text = normalize(haystack)

    if not ing:

        return False

    pattern = rf"\b{re.escape(ing)}\b"

    return bool(

        re.search(
            pattern,
            text
        )
    )


# =====================================
# EXTRACCIÓN INGREDIENTES
# =====================================

def extract_ingredientes_block(
        recipe_text: str
) -> str:

    if not recipe_text:

        return ""

    patterns = [

        r"ingredientes?\s*:\s*(.*?)(?=\n\s*(?:preparaci[oó]n|elaboraci[oó]n|instrucciones|pasos|tiempo)|\Z)",

        r"ingredientes?\s*\n(.*?)(?=\n\s*(?:preparaci[oó]n|pasos)|\Z)"
    ]

    for pattern in patterns:

        match = re.search(

            pattern,

            recipe_text,

            flags=re.IGNORECASE | re.DOTALL
        )

        if match:

            return match.group(1).strip()

    return ""


def lines_from_ingredient_block(
        block: str
) -> list[str]:

    if not block:

        return []

    output = []

    for line in block.splitlines():

        line = line.strip()

        if not line:

            continue

        if re.search(

                r"^(tiempo|dificultad|preparaci[oó]n)",

                line,

                re.IGNORECASE
        ):

            break

        output.append(line)

    return output


# =====================================
# ANÁLISIS
# =====================================

def analyze_overlap(

        user_ingredients: list[str],

        recipe_text: str

) -> dict[str, Any]:

    user_clean = [

        normalize(i)

        for i in user_ingredients

        if i and str(i).strip()
    ]

    recipe_text = recipe_text or ""

    ingredient_block = extract_ingredientes_block(

        recipe_text
    )

    recipe_lines = (

        lines_from_ingredient_block(

            ingredient_block

        )

        if ingredient_block

        else []
    )

    if not recipe_lines:

        recipe_lines = [

            line.strip()

            for line in recipe_text.splitlines()

            if line.strip()

        ][:40]

    encontrados = [

        ing

        for ing in user_clean

        if user_ingredient_in_text(

            ing,

            recipe_text
        )
    ]

    faltantes = [

        ing

        for ing in user_clean

        if ing not in encontrados
    ]

    unmatched_lines = []

    for line in recipe_lines:

        if not any(

                user_ingredient_in_text(

                    ing,

                    line

                )

                for ing in user_clean
        ):

            unmatched_lines.append(

                line[:100]
            )

    n_user = len(user_clean)

    ratio = (

        len(encontrados) / n_user

        if n_user

        else 0
    )

    if ratio >= 0.70:

        nivel = "alto"

    elif ratio >= 0.35:

        nivel = "medio"

    else:

        nivel = "bajo"

    return {

        "n_usuario": n_user,

        "n_en_receta": len(encontrados),

        "usuario_en_receta": encontrados,

        "usuario_no_en_receta": faltantes,

        "n_lineas_ingredientes_receta":

            len(recipe_lines),

        "n_lineas_receta_con_match":

            len(recipe_lines)

            - len(unmatched_lines),

        "n_lineas_sin_match":

            len(unmatched_lines),

        "lineas_receta_sin_match_usuario":

            unmatched_lines[:10],

        "ratio_usuario_en_receta":

            ratio,

        "nivel_coincidencia":

            nivel
    }


# =====================================
# PROMPT SUPPORT
# =====================================

def _titulo_corto(
        text: str
) -> str:

    first = (

        text.strip()

        .splitlines()[0]

        if text

        else "Sin título"
    )

    return first[:80]


def bloque_analisis_para_prompt(

        user_ingredients: list[str],

        chunks: list[dict]

) -> str:

    if not chunks:

        return "(Sin fragmentos RAG)"

    bloques = []

    for idx, chunk in enumerate(

            chunks,

            start=1
    ):

        analysis = analyze_overlap(

            user_ingredients,

            chunk.get(
                "text",
                ""
            )
        )

        faltantes = ", ".join(

            analysis[
                "usuario_no_en_receta"
            ]

        ) or "ninguno"

        bloques.append(

            f"""
Chunk {idx}
Fuente: {chunk.get('source','?')}
Título: {_titulo_corto(chunk.get('text',''))}

Coincidencia:
{analysis['n_en_receta']}/{analysis['n_usuario']}

Nivel:
{analysis['nivel_coincidencia']}

Faltantes:
{faltantes}
"""
        )

    return "\n".join(bloques)
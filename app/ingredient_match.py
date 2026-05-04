"""
Coincidencia ingredientes usuario ↔ texto de receta (RAG), sin LLM.
"""
import re
import unicodedata
from typing import Any


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def normalize(s: str) -> str:
    return _strip_accents((s or "").lower().strip())


def es_consulta_sustitucion(mensaje: str) -> bool:
    m = normalize(mensaje or "")
    return bool(
        re.search(
            r"reemplaz|sustitu|en vez de|en lugar de|alternativ|cambiar.{0,40}por",
            m,
        )
    )


def user_ingredient_in_text(ing: str, haystack: str) -> bool:
    ing_n = normalize(ing)
    h = normalize(haystack)
    if len(ing_n) < 2:
        return ing_n in h
    return ing_n in h


def extract_ingredientes_block(text: str) -> str:
    m = re.search(
        r"(?is)ingredientes?\s*:\s*(.*?)(?=\n\s*(?:instrucciones|elaboraci[oó]n|preparaci[oó]n|===|tiempo\s*:)|\Z)",
        text,
        re.DOTALL,
    )
    return (m.group(1) if m else "").strip()


def lines_from_ingredient_block(block: str) -> list[str]:
    lines = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("tiempo") or low.startswith("dificultad"):
            break
        lines.append(line)
    return lines


def analyze_overlap(user_ingredients: list[str], recipe_text: str) -> dict[str, Any]:
    user_ings_clean = [i.strip() for i in user_ingredients if i and str(i).strip()]
    full = recipe_text or ""
    block = extract_ingredientes_block(full)
    rec_lines = lines_from_ingredient_block(block) if block else []
    if not rec_lines:
        rec_lines = [
            l.strip()
            for l in full.split("\n")
            if l.strip() and "===" not in l and not l.strip().lower().startswith("instrucc")
        ][:35]

    encontrados = [u for u in user_ings_clean if user_ingredient_in_text(u, full)]
    no_en_texto_usuario = [u for u in user_ings_clean if u not in encontrados]

    lineas_sin_match: list[str] = []
    for line in rec_lines:
        if not any(user_ingredient_in_text(u, line) for u in user_ings_clean):
            lineas_sin_match.append(line[:100])

    n_user = len(user_ings_clean)
    n_found = len(encontrados)
    n_lines = len(rec_lines)
    n_lines_match = n_lines - len(lineas_sin_match)

    ratio_u = (n_found / n_user) if n_user else 0.0

    # Mayoría / minoría según ingredientes del usuario que aparecen en la receta
    if n_user == 0:
        nivel = "desconocido"
    elif n_user == 1:
        nivel = "alto" if n_found >= 1 else "bajo"
    elif ratio_u >= 0.5:
        nivel = "alto"
    elif n_user >= 4 and ratio_u < 0.35:
        nivel = "bajo"
    elif n_found <= 1 and n_user >= 5:
        nivel = "bajo"
    else:
        nivel = "medio"

    n_sin_match = len(lineas_sin_match)
    return {
        "n_usuario": n_user,
        "n_en_receta": n_found,
        "usuario_en_receta": encontrados,
        "usuario_no_en_receta": no_en_texto_usuario,
        "n_lineas_ingredientes_receta": n_lines,
        "n_lineas_receta_con_match": n_lines_match,
        "n_lineas_sin_match": n_sin_match,
        "lineas_receta_sin_match_usuario": lineas_sin_match[:10],
        "ratio_usuario_en_receta": ratio_u,
        "nivel_coincidencia": nivel,
    }


def _titulo_corto(text: str) -> str:
    for line in (text or "").split("\n"):
        if "===" in line:
            return line.strip()[:90]
    t = (text or "").strip().split("\n", 1)[0]
    return (t[:80] + "…") if len(t) > 80 else t


def bloque_analisis_para_prompt(user_ingredients: list[str], chunks: list[dict]) -> str:
    """Un párrafo por chunk, solo hechos calculados."""
    if not chunks:
        return "(Sin fragmentos RAG.)"
    partes = []
    for i, ch in enumerate(chunks, 1):
        an = analyze_overlap(user_ingredients, ch.get("text", ""))
        tit = _titulo_corto(ch.get("text", ""))
        fuente = ch.get("source", "?")
        faltan = an["lineas_receta_sin_match_usuario"][:4]
        faltan_txt = "; ".join(faltan) if faltan else "(ninguna línea suelta detectada)"
        partes.append(
            f"#{i} [{fuente}] «{tit}»: el usuario tiene {an['n_en_receta']} de {an['n_usuario']} "
            f"ingredientes de su lista que aparecen en el texto de la receta "
            f"({', '.join(an['usuario_en_receta']) or 'ninguno'}). "
            f"De su lista no aparecen en la receta: {', '.join(an['usuario_no_en_receta']) or '—'}. "
            f"En la sección ingredientes hay {an['n_lineas_ingredientes_receta']} líneas; "
            f"{an['n_lineas_receta_con_match']} con algún ingrediente de la lista del usuario y "
            f"{an['n_lineas_sin_match']} sin coincidencia con esa lista "
            f"(posibles faltantes en despensa, ej.: {faltan_txt}). "
            f"Nivel: {an['nivel_coincidencia']}."
        )
    return "\n".join(partes)

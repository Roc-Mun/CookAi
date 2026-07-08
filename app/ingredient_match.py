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

def es_solicitud_generar_receta(mensaje: str) -> bool:
    """Detecta si el usuario pide desde el Chat que se invente/genere una receta nueva
    (a diferencia de una consulta o ajuste sobre una receta ya existente en el rack)."""
    m = normalize(mensaje or "")
    return bool(
        re.search(
            r"(genera(me)?|invent(a|ame)|crea(me)?|dame|sug[ié]ren?me|prop[oó]n(me)?)"
            r".{0,40}(otra |una |nueva )*receta",
            m,
        )
    )

def user_ingredient_in_text(ingredient: str, haystack: str) -> bool:
    ing = normalize(ingredient)
    text = normalize(haystack)
    if not ing: return False
    
    # Búsqueda más flexible para ingredientes: 
    # Permitir si la palabra es parte de otra, pero solo si tiene al menos 3 letras
    if len(ing) < 3:
        pattern = rf"\b{re.escape(ing)}\b"
        return bool(re.search(pattern, text))
    else:
        return ing in text

def extract_ingredientes_block(text: str) -> str:
    patterns = [
        r"(?is)ingredientes?\s*:\s*(.*?)(?=\n\s*(?:instrucciones|elaboraci[oó]n|preparaci[oó]n|===|tiempo\s*:|pasos)|\Z)",
        r"(?is)ingredientes?\s*\n(.*?)(?=\n\s*(?:preparaci[oó]n|pasos|===)|\Z)"
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return ""

def lines_from_ingredient_block(block: str) -> list[str]:
    lines = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("tiempo") or low.startswith("dificultad") or low.startswith("preparaci"):
            break
        lines.append(line)
    return lines

def analyze_overlap(user_ingredients: list[str], recipe_text: str) -> dict[str, Any]:
    user_clean = [normalize(i) for i in user_ingredients if i and str(i).strip()]
    full = recipe_text or ""
    
    block = extract_ingredientes_block(full)
    rec_lines = lines_from_ingredient_block(block) if block else []
    
    if not rec_lines:
        rec_lines = [
            l.strip() for l in full.split("\n")
            if l.strip() and "===" not in l and not l.strip().lower().startswith("instrucc")
        ][:35]

    encontrados = [u for u in user_clean if user_ingredient_in_text(u, full)]
    faltantes = [u for u in user_clean if u not in encontrados]

    lineas_sin_match: list[str] = []
    for line in rec_lines:
        if not any(user_ingredient_in_text(u, line) for u in user_clean):
            lineas_sin_match.append(line[:100])

    n_user = len(user_clean)
    n_found = len(encontrados)
    n_lines = len(rec_lines)
    n_lines_match = n_lines - len(lineas_sin_match)

    # ratio_u: de lo que el usuario tiene, cuánto aparece en la receta.
    # Por sí solo es insuficiente: un usuario con un solo ingrediente muy común
    # (ej. "sal") calzaría al 100% con casi cualquier receta sin tener nada más.
    ratio_u = (n_found / n_user) if n_user else 0.0

    # ratio_receta: de lo que la receta necesita, cuánto cubre el usuario.
    # Esto es lo que realmente determina si la receta es viable de preparar.
    ratio_receta = (n_lines_match / n_lines) if n_lines else 0.0

    # Ingrediente principal: la primera línea del bloque de ingredientes suele
    # ser el componente protagónico de la receta (proteína/base). Si el usuario
    # no lo tiene, la receta no es viable aunque coincidan ingredientes menores.
    ingrediente_principal = rec_lines[0] if rec_lines else ""
    ingrediente_principal_match = bool(rec_lines) and any(
        user_ingredient_in_text(u, ingrediente_principal) for u in user_clean
    )

    # Nota: no exigimos cubrir TODA la lista de ingredientes de la receta (ratio_receta)
    # como condición dura — un usuario normal no lista sal, aceite o pimienta al buscar
    # recetas. Lo que sí es obligatorio es tener el ingrediente principal.
    if n_user == 0 or n_lines == 0:
        nivel = "bajo"  # Seguro para evitar falsos positivos
    elif not ingrediente_principal_match:
        nivel = "bajo"
    elif ratio_u >= 0.70:
        nivel = "alto"
    elif ratio_u >= 0.35:
        nivel = "medio"
    else:
        nivel = "bajo"

    return {
        "n_usuario": n_user,
        "n_en_receta": n_found,
        "usuario_en_receta": encontrados,
        "usuario_no_en_receta": faltantes,
        "n_lineas_ingredientes_receta": n_lines,
        "n_lineas_receta_con_match": n_lines_match,
        "n_lineas_sin_match": len(lineas_sin_match),
        "lineas_receta_sin_match_usuario": lineas_sin_match[:10],
        "ratio_usuario_en_receta": ratio_u,
        "ratio_receta_cubierta_por_usuario": ratio_receta,
        "ingrediente_principal": ingrediente_principal[:80],
        "ingrediente_principal_coincide": ingrediente_principal_match,
        "nivel_coincidencia": nivel,
    }

def _titulo_corto(text: str) -> str:
    for line in (text or "").split("\n"):
        if "===" in line:
            return line.strip()[:90]
    t = (text or "").strip().split("\n", 1)[0]
    return (t[:80] + "…") if len(t) > 80 else t

def bloque_analisis_para_prompt(user_ingredients: list[str], chunks: list[dict]) -> str:
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
            f"ingredientes requeridos ({', '.join(an['usuario_en_receta']) or 'ninguno'}). "
            f"Faltan de su lista: {', '.join(an['usuario_no_en_receta']) or '—'}. "
            f"Nivel de coincidencia: {an['nivel_coincidencia'].upper()}."
        )
    return "\n".join(partes)
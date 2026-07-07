# app/domain_validator.py
import re
from typing import Tuple

class DomainValidator:

    DOMAIN_KEYWORDS = {
        "receta", "ingrediente", "cocina", "cocinar", "preparar", "comida",
        "plato", "postre", "horno", "cocción", "sustituir", "salsa",
        "desayuno", "almuerzo", "cena", "vegano", "vegetariano", "gluten",
        "lactosa", "calorías", "proteína",
        # Ingredientes comunes
        "pollo", "carne", "arroz", "queso", "tomate", "cebolla", "ajo",
        "leche", "harina", "huevo", "papas", "zanahoria", "pescado", "sopa",
        "caldo"
    }

    REJECT_PATTERNS = [
        r"\bcapital\b", r"\bpresidente\b", r"\bmatem[aá]tica\b",
        r"\bprogramaci[oó]n\b", r"\bpython\b", r"\bsql\b",
        r"\bf[ií]sica\b", r"\bgeograf[ií]a\b"
    ]

    # IL3.3 / IE3: Expresiones Regulares para Mitigación de Prompt Injection (Ataques de Evasión)
    PROMPT_INJECTION_PATTERNS = [
        r"olvida\s+(tus|las)\s+instrucciones",
        r"ignore\s+(previous|system)\s+instructions",
        r"act[uú]a\s+como\s+un\s+(hacker|asistente\s+sin\s+restricciones)",
        r"ignore\s+los\s+guardrails",
        r"cambia\s+tu\s+rol\s+a",
        r"reveal\s+your\s+system\s+prompt"
    ]

    # IL3.3 / IE3: Patrones para detectar contenido gastronómico peligroso o dañino (Seguridad Física)
    HAZARDOUS_CONTENT_PATTERNS = [
        r"\bveneno\b", r"\bt[oó]xico\b", r"\bcianuro\b", r"\bexplosivo\b",
        r"\bvenenoso\b", r"\bdroga\b", r"\bqu[ií]mico\s+peligroso\b"
    ]

    INGREDIENT_PATTERN = r"tengo\s+(estos\s+)?ingredientes?:"

    @classmethod
    def sanitize_pii(cls, text: str) -> str:
        """
        Garantiza la privacidad del usuario (PII) anonimizando información sensible 
        antes de que sea procesada por el LLM o guardada en BD.
        """
        if not text:
            return text

        # 1. Anonimizar RUT Chileno (Formatos comunes: 12.345.678-9 o 12345678-9)
        rut_pattern = r"\b\d{1,2}(?:\.?\d{3}){2}-[\dkK]\b"
        text = re.sub(rut_pattern, "[RUT_ANONIMIZADO]", text)

        # 2. Anonimizar Correos Electrónicos
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        text = re.sub(email_pattern, "[CORREO_ANONIMIZADO]", text)

        # 3. Anonimizar Números Telefónicos de Chile (ej: +56912345678 o 912345678)
        phone_pattern = r"(\+?56\s?9\s?\d{4}\s?\d{4}|\b9\d{8}\b)"
        text = re.sub(phone_pattern, "[TELEFONO_ANONIMIZADO]", text)

        return text

    @classmethod
    def validate_and_filter(cls, text: str) -> Tuple[bool, str]:
        """
        Valida el mensaje del usuario aplicando filtros perimetrales de dominio,
        mitigación de Prompt Injections y seguridad de contenido.
        """
        if not text:
            return False, "Pregunta vacía."

        lower = text.lower()

        # ── 1. DETECCIÓN DE PROMPT INJECTION (IL3.3) ─────────────────────────
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, lower):
                return (
                    False,
                    "Error de Seguridad: Se ha detectado un intento de evasión de directivas. "
                    "Por favor, realice consultas exclusivamente gastronómicas convencionales."
                )

        # ── 2. FILTRO DE CONTENIDO DAÑINO/PELIGROSO (IL3.3) ──────────────────
        for pattern in cls.HAZARDOUS_CONTENT_PATTERNS:
            if re.search(pattern, lower):
                return (
                    False,
                    "Consulta rechazada por políticas de uso responsable y seguridad alimentaria. "
                    "CookAI solo asiste en recetas con ingredientes seguros y aptos para el consumo."
                )

        # ── 3. DETECTAR PREGUNTAS CLARAMENTE FUERA DE DOMINIO ────────────────
        for pattern in cls.REJECT_PATTERNS:
            if re.search(pattern, lower):
                return (
                    False,
                    "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
                )

        # ── 4. FORMATO INGREDIENTES FRONTEND ─────────────────────────────────
        if re.search(cls.INGREDIENT_PATTERN, lower):
            return True, ""

        # ── 5. TOKENIZACIÓN SIMPLE Y COINCIDENCIA DE PALABRAS CLAVE ──────────
        words = set(re.findall(r"\b[\wáéíóúñ]+\b", lower))
        matches = words & cls.DOMAIN_KEYWORDS
        if matches:
            return True, ""

        # ── 6. FRASES CULINARIAS COMUNES ─────────────────────────────────────
        cooking_patterns = [
            r"cómo hacer", r"cómo preparar", r"qué cocinar",
            r"qué puedo hacer", r"con qué reemplazo", r"qué receta",
            r"qué hago con"
        ]

        for p in cooking_patterns:
            if re.search(p, lower):
                return True, ""

        return (
            False,
            "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
        )
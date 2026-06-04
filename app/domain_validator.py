import re
from typing import Tuple


class DomainValidator:

    DOMAIN_KEYWORDS = {

        "receta",
        "ingrediente",
        "cocina",
        "cocinar",
        "preparar",
        "comida",
        "plato",
        "postre",
        "horno",
        "cocción",
        "sustituir",
        "salsa",
        "desayuno",
        "almuerzo",
        "cena",
        "vegano",
        "vegetariano",
        "gluten",
        "lactosa",
        "calorías",
        "proteína",

        # ingredientes comunes

        "pollo",
        "carne",
        "arroz",
        "queso",
        "tomate",
        "cebolla",
        "ajo",
        "leche",
        "harina",
        "huevo",
        "papas",
        "zanahoria",
        "pescado"
    }

    REJECT_PATTERNS = [

        r"\bcapital\b",
        r"\bpresidente\b",
        r"\bmatem[aá]tica\b",
        r"\bprogramaci[oó]n\b",
        r"\bpython\b",
        r"\bsql\b",
        r"\bf[ií]sica\b",
        r"\bgeograf[ií]a\b"
    ]

    INGREDIENT_PATTERN = r"tengo\s+(estos\s+)?ingredientes?:"

    @classmethod
    def validate_and_filter(
            cls,
            text: str
    ) -> Tuple[bool, str]:

        if not text:

            return False, "Pregunta vacía."

        lower = text.lower()

        # 1. formato ingredientes frontend

        if re.search(
                cls.INGREDIENT_PATTERN,
                lower
        ):

            return True, ""

        # 2. detectar preguntas claramente fuera dominio

        for pattern in cls.REJECT_PATTERNS:
            if re.search(pattern, lower):
                return (
                    False,
                    "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
                )

        # 3. tokenización simple

        words = set(

            re.findall(
                r"\b[\wáéíóúñ]+\b",
                lower
            )
        )

        matches = words & cls.DOMAIN_KEYWORDS

        # una coincidencia basta

        if matches:

            return True, ""

        # 4. frases culinarias comunes

        cooking_patterns = [

            r"cómo hacer",
            r"cómo preparar",
            r"qué cocinar",
            r"qué puedo hacer",
            r"con qué reemplazo",
            r"qué receta",
            r"qué hago con"
        ]

        for p in cooking_patterns:

            if re.search(p, lower):

                return True, ""

        return (
            False,
            "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
        )
        
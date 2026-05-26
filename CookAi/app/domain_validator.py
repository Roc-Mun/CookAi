"""
Validador de Dominio - Restricción de Temas
Asegura que el agente SOLO responda sobre recetas y cocina.
Implementa restricción: Si pregunta sobre otros temas, responde "Su pregunta no tiene relación".
"""

import re
from typing import Tuple

class DomainValidator:
    """
    Valida que una pregunta sea sobre recetas/cocina.
    Si no está relacionada, retorna rechazo.
    """
    
    # Palabras clave de dominio permitidas (RECETAS/COCINA)
    DOMAIN_KEYWORDS = {
        'receta', 'recetas', 'ingrediente', 'ingredientes', 'cocina', 'cocinar',
        'preparacion', 'preparación', 'instrucciones', 'pasos', 'tiempo',
        'cocinero', 'chef', 'comida', 'plato', 'platillo', 'postre',
        'entrada', 'plato principal', 'acompañamiento', 'salsa', 'salsas',
        'caldo', 'caldo de pollo', 'sopa', 'sopas', 'ensalada', 'ensaladas',
        'pan', 'panes', 'pastel', 'pasteles', 'torta', 'tortas',
        'galletas', 'cookie', 'brownies', 'brownie', 'pan de molde',
        'huevo', 'huevos', 'leche', 'queso', 'mantequilla', 'aceite',
        'azúcar', 'sal', 'pimienta', 'ajo', 'cebolla', 'tomate',
        'pollo', 'carne', 'pescado', 'camarones', 'mariscos',
        'vegetales', 'verduras', 'frutas', 'fruta', 'nueces', 'semillas',
        'alergia', 'alergias', 'alérgico', 'intolerancia', 'intolerancias',
        'gluten', 'lactosa', 'vegano', 'vegetariano', 'kosher', 'halal',
        'sustitucion', 'sustitución', 'reemplazar', 'en lugar de', 'alternativa',
        'tiempo de cocción', 'temperatura', 'horno', 'estufa', 'plancha',
        'presupuesto', 'económica', 'barata', 'caro', 'económico',
        'dificultad', 'difícil', 'fácil', 'principiante', 'avanzado',
        'desayuno', 'almuerzo', 'comida', 'cena', 'merienda', 'brunch',
        'dieta', 'nutrición', 'calorías', 'proteína', 'carbohidrato',
        'técnica', 'técnicas', 'picado', 'cortado', 'hervir', 'freír',
        'hornear', 'asar', 'saltear', 'guisar', 'cocción', 'cocer'
    }
    
    # Preguntas no relacionadas (ejemplos de RECHAZO)
    REJECTED_KEYWORDS = {
        'capital', 'presidente', 'historia', 'geografia', 'matemática',
        'letras', 'abecedario', 'física', 'química', 'biología',
        'religión', 'política', 'deporte', 'música', 'película',
        'libro', 'autor', 'programación', 'código', 'python',
        'javascript', 'html', 'css', 'base de datos', 'sql',
        'covid', 'virus', 'enfermedad', 'medicina', 'doctor',
        'hospital', 'vacuna', 'síntoma', 'diagnóstico',
        'dinero', 'precio', 'costo', 'pago', 'tarjeta',
        'viaje', 'hotel', 'vuelo', 'turismo', 'destino',
        'coche', 'auto', 'carro', 'moto', 'bicicleta',
        'ropa', 'zapatos', 'moda', 'marca', 'diseño',
        'casas', 'apartamento', 'inmueble', 'venta', 'alquiler'
    }
    
    COOKING_ACTIONS = {
        'puedo', 'se puede', 'cómo', 'que es', 'qué es',
        'cuánto', 'cuanto', 'cuándo', 'cuanto', 'dónde', 'donde',
        'cuáles', 'cuales', 'diferencia', 'ventaja', 'desventaja'
    }
    
    @classmethod
    def is_recipe_related(cls, text: str) -> Tuple[bool, str]:
        """
        Valida si una pregunta es sobre recetas/cocina.
        
        Args:
            text: Texto de la pregunta del usuario
        
        Returns:
            Tupla (es_válida: bool, motivo: str)
        """
        text_lower = text.lower()
        
        # Limpieza básica
        text_clean = re.sub(r'[?¿!¡.,;:]', '', text_lower)
        words = set(text_clean.split())
        
        # Contar palabras del dominio vs rechazadas
        domain_matches = len(words & cls.DOMAIN_KEYWORDS)
        rejected_matches = len(words & cls.REJECTED_KEYWORDS)
        
        # Si hay palabras rechazadas explícitas, rechaza
        if rejected_matches > 0:
            return False, "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
        
        # Si hay palabras del dominio, es válida
        if domain_matches > 1:
            return True, ""
        
        # Patrones específicos permitidos
        patterns_allowed = [
            r'receta.*?con',
            r'cómo.*?hacer',
            r'cómo.*?preparar',
            r'qué.*?ingrediente',
            r'puedo.*?sustituir',
            r'se puede.*?cambiar',
            r'alternativa.*?para',
            r'tiempo.*?de.*?cocción',
            r'puede.*?dejar.*?menos',
            r'instrucción',
        ]
        
        for pattern in patterns_allowed:
            if re.search(pattern, text_lower):
                return True, ""
        
        # Si no cumple ningún criterio de dominio, rechaza
        if domain_matches == 0:
            return False, "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
        
        return True, ""
    
    @classmethod
    def validate_and_filter(cls, text: str) -> Tuple[bool, str]:
        """
        Valida texto y retorna si debe ser procesado.
        
        Args:
            text: Entrada del usuario
        
        Returns:
            Tupla (permitido: bool, mensaje_si_rechazado: str)
        """
        is_valid, message = cls.is_recipe_related(text)
        return is_valid, message

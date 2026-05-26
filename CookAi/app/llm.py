import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key:
            raise ValueError(
                "⚠️ API KEY no configurada en .env\n"
                "Añade: GROQ_API_KEY=gsk-..."
            )
        
        # Conexión limpia a Groq usando el cliente oficial compatible de OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = "llama-3.3-70b-versatile"
        self.temperature = 0.5
        self.max_tokens = 1500
    
    
    def generate_response(self, prompt: str) -> str:
        """
        Generar respuesta con Groq (Llama).
        
        Args:
            prompt: Instrucción/pregunta para el modelo
        
        Returns:
            Respuesta generada por el LLM
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Eres CookAI, un asistente experto en recomendación de recetas.
                        Tu objetivo es ayudar a los usuarios a encontrar recetas personalizadas basadas en:
                        - Ingredientes disponibles
                        - Tiempo de preparación
                        - Restricciones alimentarias
                        - Presupuesto
                        - Preferencias culinarias
                        
                        Sé amable, útil y proporciona explicaciones detalladas de por qué recomendas cada receta."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            return f"❌ Error al generar respuesta: {str(e)}\nVerifica que tu API key sea válida."
    
    
    def validate_api_key(self) -> bool:
        """Verificar que la API key es válida"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            return True
        except Exception as e:
            print(f"❌ API key inválida: {e}")
            return False
    
    
    def set_model(self, model: str):
        """Cambiar modelo de LLM"""
        self.model = model
        print(f"✅ Modelo cambiado a: {model}")
    
    
    def set_temperature(self, temperature: float):
        """
        Establecer temperatura (creatividad).
        0.0 = determinista
        1.0 = muy creativo
        """
        self.temperature = max(0.0, min(1.0, temperature))
        print(f"✅ Temperatura: {self.temperature}")
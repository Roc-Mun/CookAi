import os
import re
import threading
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Prefijo fijo y detectable de los mensajes de fallo de conexión con el LLM.
# Permite a los llamadores (main.py) distinguir un fallo real de una receta
# válida, en vez de tratar en silencio un error de API como una recomendación.
LLM_FALLBACK_PREFIX = "⚠️ No fue posible conectar con el servicio de IA"


def is_llm_fallback(text: str) -> bool:
    """True si el texto es un mensaje de fallo del LLM y no una respuesta real."""
    return bool(text) and text.startswith(LLM_FALLBACK_PREFIX)


# Límite de llamadas concurrentes al LLM que este proceso puede disparar a la vez.
# Sin esto, varias solicitudes simultáneas (chat + recomendador + orquestación
# interna, que hace más de una llamada por request) pueden saturar el rate limit
# de Groq y generar la cascada de 429 Too Many Requests que vimos en el log real.
_LLM_CONCURRENCIA_MAXIMA = int(os.getenv("LLM_MAX_CONCURRENT_CALLS", "3"))
_llm_semaphore = threading.Semaphore(_LLM_CONCURRENCIA_MAXIMA)


class LLMClient:
    """
    Cliente LLM centralizado para CookAI optimizado para evitar Rate Limits (429).
    Usa Groq mediante la API compatible de OpenAI, segmentando prompts
    para cumplir con la pauta de evaluación y habilitar un chat fluido.
    """

    # PROMPT 1: Diseñado exclusivamente para cumplir los indicadores de evaluación (IE5, IE6, IE8)
    RECOMENDADOR_SYSTEM_PROMPT = """
Eres CookAI, un agente inteligente de recomendación culinaria basado en arquitectura RAG.

Tu tarea es analizar información proveniente de recuperación contextual (RAG), restricciones del usuario y contexto culinario para seleccionar la mejor recomendación posible.

REGLAS INTERNAS DE RAZONAMIENTO (NO MOSTRAR EXPLÍCITAMENTE):
- Analiza recetas recuperadas desde la base vectorial.
- Evalúa ingredientes disponibles, presupuesto, tiempo, restricciones alimentarias y complejidad.
- Prioriza recetas con mayor compatibilidad semántica y práctica.
- Si no existe coincidencia exacta, selecciona la alternativa más cercana de forma adaptativa.
- Prioriza eficiencia, viabilidad culinaria y experiencia del usuario.
- Construye internamente un plan lógico de preparación antes de responder.
- Justifica internamente por qué descartaste otras opciones, pero NO expliques el proceso completo.

FORMATO DE RESPUESTA OBLIGATORIO:

1. Comienza directamente indicando la receta recomendada.
2. Explica brevemente por qué se ajusta a lo solicitado.
3. Entrega ingredientes necesarios (solo los relevantes).
4. Entrega pasos de preparación claros y priorizados.
5. Agrega tips útiles o sustituciones si aportan valor.
6. Mantén un tono natural, culinario y conversacional.
7. Evita encabezados técnicos como:
   - Contexto RAG
   - Toma de decisiones
   - Justificación adaptativa
   - Análisis vectorial
8. No menciones procesos internos, embeddings, recuperación, ranking ni razonamiento oculto.
9. Sé directo y evita relleno innecesario.

La respuesta debe parecer hecha por un experto culinario humano, no por un sistema técnico.
"""

    # PROMPT 2: Diseñado para el Chat libre (Ajustes, sustituciones, dudas culinarias libres)
    CHAT_SYSTEM_PROMPT = """
Eres CookAI, un asistente conversacional experto en cocina y gastronomía. 

REGLAS:

1. Responde de forma natural y útil.

2. Mantén respuestas breves y claras.

3. Ayuda con sustituciones, técnicas, ingredientes y dudas culinarias.

4. Mantén continuidad conversacional.

5. No uses formatos rígidos.
"""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "⚠️ API KEY no configurada en .env\n"
                "Añade: GROQ_API_KEY=gsk-..."
            )

        # Conexión limpia a Groq usando el cliente oficial compatible de OpenAI.
        # max_retries/timeout quedan explícitos y configurables (antes dependían
        # del valor implícito por defecto del SDK, sin control ni documentación).
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        )
        # Cambiamos a un modelo 'instant' de 8B parámetros. Evita bloqueos por límite de tokens y responde al instante.
        self.model = "llama-3.1-8b-instant"
        self.temperature = 0.4
        self.max_tokens = 1000

        # TELEMETRÍA: Estado inicial de volumetría de tokens consumidos
        self.last_usage = {"input": 0, "output": 0}

    def generate_response(self, prompt: str) -> str:
        """
        Método utilizado por el RECOMENDADOR.
        Aplica el prompt estructurado requerido por la rúbrica de evaluación.
        """
        try:
            with _llm_semaphore:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.RECOMENDADOR_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

            # Extraer y actualizar la volumetría real de tokens
            if hasattr(response, "usage") and response.usage:
                self.last_usage = {
                    "input": response.usage.prompt_tokens,
                    "output": response.usage.completion_tokens
                }
            return response.choices[0].message.content

        except Exception as e:
            print(f"⚠️ Alerta API / Rate Limit en recomendador: {str(e)}")
            # En caso de error, dejamos la telemetría en 0 para evitar errores de tipo
            self.last_usage = {"input": 0, "output": 0}

            # FALLBACK HONESTO: antes se devolvía una receta inventada de "Pollo al
            # Ajillo" fija, sin relación con lo pedido — el usuario no podía distinguir
            # un fallo de API de una recomendación real ("no asumir recetas"). Ahora se
            # informa el fallo real para que quede claro que no hubo generación válida.
            return (
                f"{LLM_FALLBACK_PREFIX} (Groq). Detalle técnico: {type(e).__name__}. "
                "Verifica tu conexión y tu GROQ_API_KEY en el archivo .env, y vuelve a intentarlo."
            )

    def chat(self, user_message: str) -> str:
        """
        Método exclusivo para la pestaña de CHAT conversacional continuo.
        """
        try:
            with _llm_semaphore:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.CHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.5,
                    max_tokens=500
                )

            # Extraer y actualizar la volumetría real de tokens en el chat libre
            if hasattr(response, "usage") and response.usage:
                self.last_usage = {
                    "input": response.usage.prompt_tokens,
                    "output": response.usage.completion_tokens
                }
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Alerta API / Rate Limit en chat: {str(e)}")
            self.last_usage = {"input": 0, "output": 0}
            # Fallback honesto (ver nota en generate_response): no inventamos una
            # respuesta conversacional genérica que aparente ser válida.
            return (
                f"{LLM_FALLBACK_PREFIX} (Groq). Detalle técnico: {type(e).__name__}. "
                "Verifica tu conexión y tu GROQ_API_KEY en el archivo .env, y vuelve a intentarlo."
            )

    def generate_chat_stream(self, prompt: str):
        """
        Genera la respuesta token por token (streaming real desde Groq), para el
        endpoint /chat/stream. Es un método nuevo y separado: NO modifica ni
        reemplaza generate_response() ni chat(), que siguen usándose tal cual en
        /recommend y /chat sin streaming.

        Es un generador síncrono a propósito (el cliente de Groq/OpenAI no es
        async por defecto); quien lo consuma en un contexto async debe iterarlo
        en un threadpool para no bloquear el event loop (ver main.py).
        """
        with _llm_semaphore:
            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.CHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5,
                    max_tokens=500,
                    stream=True
                )
                for evento in stream:
                    if not evento.choices:
                        continue
                    delta = evento.choices[0].delta.content
                    if delta:
                        yield delta
            except Exception as e:
                print(f"⚠️ Alerta API / Rate Limit en chat streaming: {str(e)}")
                yield (
                    f"{LLM_FALLBACK_PREFIX} (Groq). Detalle técnico: {type(e).__name__}. "
                    "Verifica tu conexión y tu GROQ_API_KEY en el archivo .env, y vuelve a intentarlo."
                )

    def validate_api_key(self) -> bool:
        """Verificar que la API key es válida de forma segura"""
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            return True
        except Exception as e:
            print(f"⚠️ Error al validar la API Key en Groq: {str(e)}")
            return False
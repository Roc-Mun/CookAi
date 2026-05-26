from langchain.memory import ConversationBufferMemory, ConversationSummaryBufferMemory
from app.llm import LLMClient

# Configuración de memoria CORTO PLAZO (en sesión actual)
# Cumple IL2.2: Mantiene contexto de conversación actual
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=False  # Entrega historial en formato texto plano para el prompt ReAct
)

# Nota: Memoria LARGO PLAZO implementada en persistent_memory.py
# Usa SQLite para persistencia entre sesiones
# Implementa cumplimiento completo de IL2.2 y IL2.4
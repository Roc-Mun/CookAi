from langchain.memory import ConversationBufferMemory

# Configuración de memoria obligatoria para que el agente retenga el contexto (Cumple IL2.2)
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=False  # Al ser False, entrega el historial en formato texto plano idóneo para el prompt ReAct
)
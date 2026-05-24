import os
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate
from app.memory import memory
from app.tools import buscar_recetas, analizar_ingredientes, obtener_sustitutos

# 1. Inicialización del LLM (Groq compatible con OpenAI)
llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"),
    temperature=0.5
)

# 2. Arreglo del cierre del bloque de herramientas (Requisito IL2.1)
tools = [
    buscar_recetas,
    analizar_ingredientes,
    obtener_sustitutos
]

# 3. Prompt ReAct estructurado para el Agente
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Eres CookAI, un asistente experto en cocina.\n"
        "Tienes acceso a herramientas para:\n"
        "- Buscar recetas en una base de datos RAG\n"
        "- Analizar ingredientes disponibles vs recetas\n"
        "- Sugerir sustituciones de ingredientes faltantes\n\n"
        "Instrucciones:\n"
        "- Usa herramientas cuando sea necesario.\n"
        "- Si no necesitas herramientas, responde directamente.\n"
        "- Sé claro, práctico y en español."
    ),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])

# 4. Crear Agente Moderno (Corrección del parámetro llm)
base_agent = create_openai_tools_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

# 5. Ejecutor Final con soporte de memoria (Cumple IL2.2)
agent = AgentExecutor(
    agent=base_agent,
    tools=tools,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True
)
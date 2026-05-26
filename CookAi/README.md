🍳 CookAI — Agente Inteligente de Recomendación de Recetas con IA, RAG y Memoria Conversacional

CookAI es un sistema inteligente de recomendación culinaria desarrollado con arquitectura RAG (Retrieval-Augmented Generation), agentes autónomos basados en LangChain, memoria conversacional y recuperación semántica mediante ChromaDB.

El proyecto fue diseñado como una solución organizacional orientada a la automatización de recomendaciones gastronómicas personalizadas utilizando LLMs, recuperación de contexto y toma de decisiones adaptativa.

⸻

🚀 Características Principales

* 🧠 Agente Inteligente Autónomo
    * Implementado con LangChain Agents.
    * Capaz de ejecutar herramientas automáticamente.
    * Planifica tareas y toma decisiones según el contexto.
* 📚 Arquitectura RAG
    * Recuperación semántica de recetas mediante embeddings.
    * Uso de ChromaDB como vector database.
    * Reduce alucinaciones del modelo LLM.
* 💬 Memoria Conversacional
    * Mantiene continuidad entre interacciones.
    * Conserva contexto de recomendaciones previas.
    * Permite flujos prolongados y coherentes.
* ⚡ LLM de Alto Rendimiento
    * Modelo: llama-3.3-70b-versatile
    * Infraestructura Groq de baja latencia.
* 📂 Carga de Documentos
    * Soporte para PDF, TXT, DOCX y DOC.
    * Extracción automática de contenido.
* 🔍 Análisis Inteligente de Ingredientes
    * Detección automática de coincidencias.
    * Clasificación:
        * Alta coincidencia
        * Media coincidencia
        * Baja coincidencia
* 🎨 Interfaz Web Moderna
    * HTML5 + JavaScript + CSS3.
    * Interfaz responsive y dinámica.

⸻

🏗️ Arquitectura General

Flujo del Sistema

Usuario
   ↓
Frontend HTML
   ↓
FastAPI (/recomendar)
   ↓
Agente LangChain
   ↓
Herramientas (Tools)
   ├── Buscar recetas (RAG)
   ├── Analizar ingredientes
   ├── Obtener sustitutos
   ↓
ChromaDB (Vector Store)
   ↓
LLM Llama 3 vía Groq
   ↓
Respuesta personalizada
   ↓
Frontend

⸻

🧩 Arquitectura del Agente

CookAI implementa un agente conversacional usando:

* LangChain Agents
* Tool Calling
* Conversational Memory
* Retrieval-Augmented Generation (RAG)

Herramientas Integradas

Herramienta	Función
BuscarRecetas	Recupera recetas relevantes desde ChromaDB
AnalizarIngredientes	Evalúa coincidencia entre ingredientes
ObtenerSustitutos	Sugiere reemplazos culinarios
LLM	Generación final de respuesta

⸻

🛠️ Stack Tecnológico

Componente	Tecnología
Backend	FastAPI
Agente IA	LangChain
LLM	Groq + Llama 3
Vector Database	ChromaDB
Embeddings	HuggingFace
Frontend	HTML5 + CSS3 + JavaScript
Memoria Conversacional	ConversationBufferMemory
Procesamiento de Archivos	PyPDF, python-docx

⸻

📂 Estructura del Proyecto

CookAI/
│
├── app/
│   ├── main.py
│   ├── rag.py
│   ├── llm.py
│   ├── agent.py
│   ├── memory.py
│   ├── tools.py
│   ├── ingredient_match.py
│   └── __init__.py
│
├── frontend/
│   ├── index.html
│   └── favicon.svg
│
├── data/
│   ├── recetas_ejemplo.txt
│   └── uploads/
│
├── chroma_db/
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md

⸻

⚙️ Instalación

1. Clonar Repositorio

git clone https://github.com/Roc-Mun/CookAi.git
cd CookAi

⸻

2. Crear Entorno Virtual

macOS / Linux

python -m venv venv
source venv/bin/activate

Windows

python -m venv venv
venv\Scripts\activate

⸻

3. Instalar Dependencias

pip install -r requirements.txt

⸻

🔑 Configuración de API Key

Crear archivo .env

macOS/Linux

cp .env.example .env

Windows

copy .env.example .env

⸻

Obtener API Key de Groq

Ir a:

Groq Cloud Console￼

Crear una API Key y agregarla al archivo .env.

⸻

Ejemplo .env

GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxx

⸻

▶️ Ejecución del Proyecto

Iniciar Backend

python -m app.main

Servidor:

http://localhost:8000

Documentación automática FastAPI:

http://localhost:8000/docs

⸻

🧠 Funcionamiento del Agente

El agente utiliza planificación secuencial basada en herramientas:

Flujo de Decisión

1. Recuperar recetas relevantes.
2. Analizar coincidencia semántica.
3. Priorizar recetas compatibles.
4. Detectar ingredientes faltantes.
5. Sugerir sustituciones.
6. Generar respuesta final.

⸻

🧠 Recuperación Semántica (RAG)

CookAI implementa Retrieval-Augmented Generation:

Proceso

Usuario → Query → Embeddings → ChromaDB → Recuperación de chunks → LLM → Respuesta

Objetivos

* Reducir alucinaciones.
* Mejorar precisión.
* Responder usando datos reales.
* Mantener trazabilidad de información.

⸻

🧠 Memoria Conversacional

CookAI utiliza memoria conversacional para mantener continuidad contextual.

Implementación

ConversationBufferMemory

Beneficios

* Continuidad en conversaciones largas.
* Persistencia temporal de contexto.
* Mejor experiencia de usuario.

⸻

📚 Endpoints Principales

GET /status

Estado general del sistema.

⸻

POST /upload

Carga documentos PDF/TXT/DOCX al sistema RAG.

⸻

POST /recommend

Genera recomendaciones usando RAG tradicional.

⸻

POST /recomendar

Genera recomendaciones usando el agente inteligente LangChain.

Ejemplo

{
  "ingredientes": ["pollo", "arroz"],
  "preferencia": "comida italiana"
}

⸻

POST /chat

Chat conversacional inteligente.

⸻

POST /recommend_more

Genera nuevas recetas evitando repeticiones.

⸻

🧠 Planificación del Agente

El agente sigue un esquema de planificación dinámico:

1. Analizar solicitud
2. Seleccionar herramientas
3. Recuperar contexto
4. Evaluar coincidencias
5. Tomar decisiones
6. Generar respuesta

Esto permite demostrar:

* autonomía,
* razonamiento,
* priorización,
* adaptación contextual.

⸻

📊 Ejemplo de Flujo Completo

Usuario:
"Quiero recetas con pollo, tomate y arroz"
↓
Agente:
1. Busca recetas en ChromaDB
2. Analiza coincidencias
3. Evalúa ingredientes faltantes
4. Prioriza mejores recetas
5. Genera respuesta personalizada
↓
Usuario recibe:
- 3 recetas
- nivel de coincidencia
- posibles sustituciones
- explicación contextual

⸻

🔒 Seguridad

CookAI implementa:

* Variables sensibles en .env
* Exclusión mediante .gitignore
* Separación frontend/backend
* Gestión segura de API Keys

⸻

🧪 Tecnologías IA Utilizadas

Framework	Uso
LangChain	Agentes y herramientas
ChromaDB	Vector Store
HuggingFace	Embeddings
Groq	Inferencia LLM
FastAPI	API REST
Llama 3	Generación de lenguaje

⸻

🧹 Reiniciar Base Vectorial

python -c "from app.rag import RAGSystem; rag = RAGSystem(); rag.clear_database()"

⸻

🐛 Troubleshooting

Error API Key

Verificar:

GROQ_API_KEY=

⸻

Error ChromaDB

Eliminar carpeta:

chroma_db/

y reiniciar sistema.

⸻

Error Puerto 8000

Verificar procesos usando el puerto:

lsof -i :8000

⸻

📋 Indicadores Cubiertos EP2

Indicador	Implementación
IE1	Herramientas autónomas
IE2	Integración LangChain
IE3	Memoria conversacional
IE4	Recuperación semántica RAG
IE5	Planificación de tareas
IE6	Toma de decisiones adaptativa
IE7	README + arquitectura
IE8	Justificación técnica
IE9	Documentación técnica
IE10	Lenguaje técnico

⸻

📖 Referencias

* LangChain Documentation￼
* ChromaDB Documentation￼
* Groq Documentation￼
* FastAPI Documentation￼
* HuggingFace Sentence Transformers￼

⸻

👨‍💻 Repositorio Oficial

CookAI GitHub Repository￼

⸻

📄 Licencia

Proyecto académico desarrollado para la asignatura:

Ingeniería de Soluciones con Inteligencia Artificial — Duoc UC

⸻

✨ Autores

-Rocio Muñoz
-Francesca Valencia


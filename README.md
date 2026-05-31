🍳 CookAI - Agente inteligente de automatización culinaria

CookAI es un econsistema avanzado basado en Inteligencia Artificial Generativa y agentes cognitivos para la gestión, planificación y optimización culinaria.

Su arquitectura combina memoria híbrida, RAG semántico, y un sistema de agentes con control de dominio estricto, permitiendo continuidad contextual multiusuario y respuestas altamente consistentes.

🎯 Arquitectura del sistema (Indicadores de Logro)
El sistema está alineado con una arquitectura evaluativa estructurada:

🧠 IL2.1 — Capacidades del Agente

Toolkit centralizado en app/tools.py

Herramientas deterministas:

🔎 Consulta (RAG semántico)

🧩 Razonamiento (intersección de ingredientes sin alucinaciones)

✍️ Escritura con persistencia en caliente

🧠 IL2.2 / IE3 — Sistema de Memoria

Memoria de corto plazo: historial de sesión

Memoria de largo plazo: SQLite (persistent_memory.py)

Aprendizaje de restricciones dietéticas entre sesiones

🧠 IL2.3 / IE5 — Planificación Secuencial

Patrón Plan-and-Execute

Implementado en planning_agent.py

Generación de grafos de subtareas

Sistema de fallback y contingencias

📚 IE4 — Recuperación Semántica (RAG)

Motor basado en ChromaDB

Búsqueda por similitud coseno

Indexación local de documentos culinarios

🛡️ IE6 — Control de Frontera de Dominio

Validación en domain_validator.py

Filtrado de prompts fuera de dominio

Protección contra consultas irrelevantes o maliciosas

📂 Arquitectura de Directorios

CookAI-Segunda-Evaluacion/
└── CookAI/
    ├── .vscode/
    ├── app/
    │   ├── agent.py
    │   ├── domain_validator.py
    │   ├── ingredient_match.py
    │   ├── llm.py
    │   ├── main.py
    │   ├── persistent_memory.py
    │   ├── planning_agent.py
    │   ├── rag.py
    │   └── tools.py
    ├── data/
    │   ├── chroma_db/
    │   ├── uploads/
    │   └── agent_memory.db
    ├── frontend/
    ├── venv/                      
    ├── .env
    ├── .gitignore
    ├── EJEMPLOS_FUNCTIONAMIENTO.md
    ├── IMPLEMENTACION_COMPLETA.md
    ├── iniciar.bat
    ├── iniciar.ps1
    ├── iniciar.sh
    ├── README.md
    └── requirements.txt


🛠️ Requisitos Previos e Configuración

1. Clonar o ubicar el proyecto

Abre tu terminal (o símbolo del sistema) y asegúrate de estar dentro de la carpeta raíz del proyecto (CookAi-Segunda-Evaluacion).

2. Configurar variables de entorno (.env)

Antes de arrancar, necesitas configurar tus credenciales:

1. Crea tu archivo .env:

cp .env.example .env


2. Copia y edita:

GROQ_API_KEY=gsk_tu_api_key_real_aqui
GROQ_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.4
LLM_MAX_TOKENS=1200


Puedes crear tu clave groq en Groq.

🚀 Despliegue Automatizado (IE7)

Para facilitar la ejecución, primero entra a la carpeta interna del proyecto desde tu terminal:

cd CookAi


Una vez dentro de la carpeta CookAi, ejecuta los comandos correspondientes a tu sistema operativo para configurar el entorno y arrancar el servidor:

🪟 Windows (CMD)

Ejecuta el archivo por lotes directamente:

iniciar.bat


🪟 Windows (PowerShell)

Si es tu primera vez, es posible que debas saltar las restricciones de ejecución de scripts:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\iniciar.ps1


🍎 Linux / macOS

Si el sistema te dice que no tienes permisos de entorno virtual o ejecuciones, prepara e instala los componentes con estas líneas (una por una):

# 1. Crear el entorno virtual de Python
python3 -m venv venv

# 2. Activar el entorno virtual
source venv/bin/activate

# 3. Instalar dependencias necesarias
pip install -r requirements.txt

# 4. Dar permisos de ejecución al script de arranque
chmod +x iniciar.sh

# 5. Iniciar el servidor
./iniciar.sh


📍 Servidor Disponible

Una vez que el script se quede ejecutando, el sistema estará listo. No cierres la terminal y abre en tu navegador web:

👉 http://localhost:8000

📡 Endpoints principales (REST API)

🔹 POST /chat
Pipeline cognitivo completo:

Validación de dominio

Planificación de consulta

RAG + memoria

Generación de respuesta

🔹 POST /recomendar
Recibe ingredientes y devuelve recetas optimizadas usando razonamiento interno libre de alucinaciones.

🧪 Prueba rápida del sistema (Sanity Check)

Puedes probar el control de frontera de dominio enviando una consulta no culinaria mediante curl en una nueva terminal:

curl -X POST "http://localhost:8000/chat" \
-H "Content-Type: application/json" \
-d '{"mensaje": "¿Cuál es la capital de Perú?", "user_id": "test_user"}'


Respuesta esperada:

{
  "output": "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
}


🎓 Conclusión

CookAI representa una arquitectura de agentes inteligentes modular y escalable, diseñada bajo principios de:

Desacoplamiento de dependencias

Memoria híbrida persistente

Recuperación semántica avanzada

Control estricto de dominio

Pipeline cognitivo planificado

El sistema está optimizado para ejecución local, evaluación académica y escalabilidad futura.

👥 Integrantes del Proyecto:

CookAI Team — Rocío Muñoz & Francesca Valencia.

# 🍳 CookAI - Agente Inteligente de Automatización Culinaria

CookAI es un sistema inteligente de recomendación culinaria basado en Inteligencia Artificial Generativa, arquitectura RAG (Retrieval-Augmented Generation) y agentes cognitivos.

La aplicación integra recuperación semántica mediante ChromaDB, memoria persistente en SQLite, planificación dinámica, observabilidad y un dashboard de monitoreo que permite analizar el rendimiento, la latencia y la consistencia del sistema en tiempo real.

---

# 🎯 Arquitectura del Sistema (Indicadores de Logro)

El sistema está alineado con una arquitectura evaluativa estructurada.

---

## 🧠 Capacidades del Agente

Toolkit centralizado en:

```text
app/tools.py
```

Herramientas deterministas:

- 🔎 Consulta mediante RAG semántico.
- 🌐 Consulta adaptativa mediante búsqueda web en vivo (web_search_tool) si los datos locales son insuficientes.
- 🧩 Razonamiento mediante intersección de ingredientes sin alucinaciones.
- ✍️ Escritura con persistencia en caliente.

---

## 🧠 Sistema de Memoria

Características implementadas:

- Memoria de corto plazo mediante historial de sesión
- Memoria de largo plazo mediante SQLite (`persistent_memory.py`)
- Aprendizaje persistente de restricciones dietéticas entre sesiones

---

## 🧠 Planificación Secuencial

Implementaciones:

- Patrón **Plan-and-Execute**
- Implementado en `planning_agent.py`
- Fase de Planificación (PlanningAgent): Recibe la solicitud, evalúa el contexto histórico de la memoria y genera un plan formal estructurado en formato JSON (metas, herramientas recomendadas y dependencias lógicas).
- Fase de Validación (ExecutionContext): Registra el progreso incremental del plan paso a paso y maneja de forma reactiva las anomalías o fallas de las herramientas.
- Fase de Orquestación (DynamicAgentExecutor): Ejecuta dinámicamente las tareas simuladas llamando al RAG o la Web, consolidando la información real. Un prompt maestro en el LLMClient actúa como auditor de coherencia, obligando al sistema a respetar estrictamente los ingredientes del usuario y descartar datos intrusos.

---

## 📚 Recuperación Semántica (RAG)

Características:

- Motor basado en **ChromaDB**.
- Búsqueda por similitud coseno.
- Indexación local de documentos culinarios.

---

## 🛡️ Control de Frontera de Dominio

Implementado mediante:

- Validación en `domain_validator.py` combinada con un enrutador flexible en main.py.
- Filtrado de prompts fuera del dominio culinario.
- Protección frente a consultas irrelevantes o maliciosas.

---

# 📂 Arquitectura de Directorios

```text
CookAI/
├── .vscode/
├── app/
│   ├── agent.py
│   ├── domain_validator.py
│   ├── ingredient_match.py
│   ├── llm.py
│   ├── main.py
│   ├── metrics_monitor.py
│   ├── monitoring.py
│   ├── persistent_memory.py
│   ├── planning_agent.py
│   ├── rag.py
│   ├── semantic_retriever.py
│   └── tools.py
│
├── data/
│   ├── chroma_db/
│   ├── logs/
│   ├── uploads/
│   ├── recetas_ejemplo.txt
│   └── agent_memory.db
│
├── frontend/
├── temp_uploads
├── venv/
├── .env
├── .gitignore
├── dashboard.py
├── iniciar.bat
├── iniciar.ps1
├── iniciar.sh
├── README.md
└── requirements.txt
```
---

## 📈 IE1 — Observabilidad

CookAI incorpora un sistema de observabilidad que registra cada ejecución del agente y permite monitorear su comportamiento mediante métricas persistentes.

Características implementadas:

- Registro de latencia por operación.
- Conteo de tokens utilizados por el LLM.
- Registro de errores del sistema.
- Persistencia histórica en SQLite.
- Dashboard interactivo desarrollado en Streamlit.
- Métricas expuestas mediante endpoint `/metrics`.
---

# 🛠️ Requisitos Previos

- Python 3.11 o superior.
- Entorno virtual (venv).
- Dependencias especificadas en `requirements.txt`.
- Clave de acceso a Groq (`GROQ_API_KEY`).

# 🛠️ Instalación

## Paso 1: Clonar el proyecto

Ubica el proyecto en tu entorno local.

---

## Paso 2: Configurar variables de entorno

Crear archivo `.env`:

```bash
cp .env.example .env
```

Editar las variables:

```env
GROQ_API_KEY=edita_tu_clave_groq_aqui
GROQ_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.4
LLM_MAX_TOKENS=1200
```

Obtén tu clave desde:

**Groq Console:**  
https://console.groq.com/keys

---

# 🚀 Despliegue Automatizado (IE7)

Antes de ejecutar cualquier comando:

```bash
cd CookAI
```

---

## 🪟 Windows (Ejecución Manual por CMD)

Si deseas iniciar el proyecto manualmente o el script automático presenta problemas:

### 1. Entrar al directorio del proyecto

```cmd
cd ruta\del\proyecto\CookAI
```

### 2. Activar el entorno virtual

```cmd
call venv\Scripts\activate.bat
```

### 3. Instalar dependencias del proyecto

```cmd
pip install -r requirements.txt
python -m pip install langchain-community duckduckgo-search google-search-results streamlit matplotlib pandas
```

### 4. Instalar dependencias faltantes (solo si aparecen errores)

Si aparece:
ModuleNotFoundError: No module named 'langchain_community'

Ejecutar:

```cmd
python -m pip install langchain-community duckduckgo-search google-search-results
```

Se utiliza `python -m pip` porque algunos entornos Windows pueden bloquear `pip.exe` mediante políticas de seguridad (ej.: Device Guard).

### 5. Iniciar servidor FastAPI

```cmd
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Salida esperada:

INFO: Uvicorn running on http://0.0.0.0:8000.
INFO: Application startup complete.


### 6. Abrir aplicación

Abrir en navegador:

```text
http://localhost:8000
```


---

## 🪟 Windows (PowerShell)

Ejecutar:

```powershell
.\iniciar.ps1
```

Si aparecen restricciones:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 🍎🐧 macOS / Linux

### 1. Crear entorno virtual

```bash
python3 -m venv venv
```

### 2. Activar entorno virtual

```bash
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
pip install langchain-community duckduckgo-search google-search-results
pip install langchain-community duckduckgo-search google-search-results streamlit matplotlib pandas
```

### 4. Dar permisos de ejecución

```bash
chmod +x iniciar.sh
```

### 5. Iniciar servidor

```bash
./iniciar.sh
```

---

# 📍 Servidor Disponible

Una vez iniciado el sistema, mantén la terminal abierta.

Abrir en navegador:

```text
http://localhost:8000
```

---

# 📊 Dashboard de Observabilidad

CookAI incorpora un dashboard desarrollado en Streamlit para visualizar en tiempo real el comportamiento del sistema.

El panel obtiene la información desde la base de datos SQLite donde se almacenan las métricas de observabilidad, permitiendo analizar el comportamiento histórico del sistema.

## Indicadores disponibles

- ⏱️ Latencia promedio.
- ⚡ Tokens promedio utilizados por consulta.
- ✅ Tasa de éxito.
- ❌ Tasa de errores.
- 📈 Evolución temporal de la latencia.
- 🥧 Consistencia del sistema (éxito/error).
- 📋 Historial completo de operaciones.
- 🔎 Latencia por tipo de operación.

Toda la información queda almacenada de forma persistente para facilitar la trazabilidad y el análisis histórico del sistema.

## 🚀 Cómo Ejecutar el Dashboard

1. Asegúrate de estar en el directorio raíz del proyecto y con el entorno virtual activo.
2. Ejecuta el siguiente comando en tu terminal:

```bash
streamlit run dashboard.py
```
---

# 📡 Endpoints Principales (REST API)

## 🔹 POST `/chat`

Pipeline ejecutado:

- Validación de dominio.
- Recuperación semántica mediante RAG.
- Búsqueda web como contingencia cuando la información local es insuficiente.
- Planificación de acciones.
- Recuperación de memoria persistente.
- Análisis de ingredientes.
- Generación de respuesta mediante Llama 3 (Groq).
- Registro de métricas de observabilidad.

---

## 🔹 POST `/recomendar`

Funcionalidad:

- Recibe ingredientes ingresados por el usuario.
- Recupera recetas mediante RAG.
- Evalúa coincidencia mediante IngredientMatch.
- Genera recomendaciones utilizando planificación dinámica.
- Registra métricas de observabilidad.

---

## 🔹 GET `/metrics`

Entrega las métricas de observabilidad del sistema en formato JSON:

- Latencia promedio.
- Tasa de éxito.
- Total de operaciones.
- Consistencia.
- Tokens promedio.

Este endpoint consolida las métricas registradas durante la ejecución y es utilizado tanto por el dashboard para tareas de monitoreo y evaluación del sistema.

# 🧪 Prueba Rápida del Sistema

## Ejemplo fuera de dominio

```bash
curl -X POST "http://localhost:8000/chat" \
-H "Content-Type: application/json" \
-d '{"mensaje":"¿Cuál es la capital de Perú?","user_id":"test_user"}'
```

### Respuesta esperada:

```json
{
  "output": "Su pregunta no tiene relación con recetas o cocina. Por favor, pregunte sobre recetas, ingredientes o técnicas de cocina."
}
```

---
# 📋 Persistencia de Métricas

Cada ejecución del agente queda registrada en SQLite para mantener trazabilidad histórica.

Los registros almacenan:

- UUID de la operación.
- Fecha y hora.
- Tipo de operación.
- Latencia.
- Tokens utilizados.
- Estado de ejecución.
- Consistencia.

Esta información es utilizada posteriormente por el dashboard para generar indicadores, gráficos de rendimiento, realizar análisis históricos, calcular indicadores de desempeño y respaldar el proceso de observabilidad del sistema.

---

# 🎓 Conclusión

CookAI integra Inteligencia Artificial Generativa, recuperación semántica mediante RAG, memoria persistente y planificación dinámica para ofrecer recomendaciones culinarias contextualizadas.

La incorporación de observabilidad permitió medir objetivamente el comportamiento del sistema mediante métricas de latencia, consumo de tokens, tasa de errores y consistencia. Gracias a la persistencia de estos datos en SQLite y a su visualización mediante un dashboard interactivo, es posible monitorear continuamente el rendimiento, detectar cuellos de botella y facilitar futuras optimizaciones de CookAI.

Esta arquitectura convierte a CookAI en una solución modular, escalable y preparada para futuras extensiones, manteniendo un enfoque centrado en la confiabilidad y el monitoreo continuo.

---

# 👥 Integrantes del Proyecto

**CookAI Team**

- Rocío Muñoz
- Francesca Valencia

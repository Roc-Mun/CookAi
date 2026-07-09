# 🍳 CookAI - Agente Inteligente de Automatización Culinaria

CookAI es un ecosistema avanzado basado en Inteligencia Artificial Generativa y agentes cognitivos para la gestión, planificación y optimización culinaria.

Su arquitectura combina memoria híbrida, recuperación semántica mediante RAG y un sistema de agentes con control de dominio estricto, permitiendo continuidad contextual multiusuario y respuestas altamente consistentes.

---

# 🎯 Arquitectura del Sistema (Indicadores de Logro)

El sistema está alineado con una arquitectura evaluativa estructurada.

---

## 🧠 IL2.1 — Capacidades del Agente

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

## 🧠 IL2.2 / IE3 — Sistema de Memoria

Características implementadas:

- Memoria de corto plazo mediante historial de sesión
- Memoria de largo plazo mediante SQLite (`persistent_memory.py`)
- Aprendizaje persistente de restricciones dietéticas entre sesiones

---

## 🧠 IL2.3 / IE5 — Planificación Secuencial

Implementaciones:

- Patrón **Plan-and-Execute**
- Implementado en `planning_agent.py`
- Fase de Planificación (PlanningAgent): Recibe la solicitud, evalúa el contexto histórico de la memoria y genera un plan formal estructurado en formato JSON (metas, herramientas recomendadas y dependencias lógicas).
- Fase de Validación (ExecutionContext): Registra el progreso incremental del plan paso a paso y maneja de forma reactiva las anomalías o fallas de las herramientas.
- Fase de Orquestación (DynamicAgentExecutor): Ejecuta dinámicamente las tareas simuladas llamando al RAG o la Web, consolidando la información real. Un prompt maestro en el LLMClient actúa como auditor de coherencia, obligando al sistema a respetar estrictamente los ingredientes del usuario y descartar datos intrusos.

---

## 📚 IE4 — Recuperación Semántica (RAG)

Características:

- Motor basado en **ChromaDB**.
- Búsqueda por similitud coseno.
- Indexación local de documentos culinarios.

---

## 🛡️ IE6 — Control de Frontera de Dominio

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
│   ├── persistent_memory.py
│   ├── planning_agent.py
│   ├── rag.py
│   └── tools.py
│
├── data/
│   ├── chroma_db/
│   ├── uploads/
│   ├── recetas_ejemplo.txt
│   └── agent_memory.db
│
├── frontend/
├── venv/
├── .env
├── .gitignore
├── dashboard.py
├── EJEMPLOS_FUNCIONAMIENTO.md
├── IMPLEMENTACION_COMPLETA.md
├── iniciar.bat
├── iniciar.ps1
├── iniciar.sh
├── README.md
└── requirements.txt
```

---

# 🛠️ Requisitos Previos e Instalación

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

# 📊 Dashboard de Observabilidad y Monitoreo (IE1, IE2, IE5)

CookAI cuenta con una interfaz gráfica independiente desarrollada en **Streamlit** diseñada para medir el desempeño, consistencia y trazabilidad del agente en tiempo real.

El dashboard expone interactivamente los datos capturados durante los ciclos de ejecución.

### Métricas Clave Implementadas:
- ⏱️ **Latencia Promedio (IE2):** Mide en segundos el tiempo de respuesta del LLM (Groq) ante variabilidad de datos.
- ❌ **Frecuencia de Errores (IE1):** Evalúa la precisión y consistencia determinando la tasa porcentual de fallos del sistema.
- ⚡ **Uso de Recursos (IE2):** Monitorea el consumo computacional mediante el conteo promedio de tokens procesados por interacción.
- 📈 **Consistencia Visual:** Gráficos de línea temporales para analizar cuellos de botella y diagramas de sectores para la relación éxito/error.

## 🚀 Cómo Ejecutar el Dashboard

1. Asegúrate de estar en el directorio raíz del proyecto y con el entorno virtual activo.
2. Ejecuta el siguiente comando en tu terminal:

```bash
streamlit run dashboard.py
```
---

# 🧪 Tests Automatizados (IL3.1)

Cubren escenarios variados de validación de dominio, seguridad (prompt injection,
contenido peligroso, PII) y matching de ingredientes (incluyendo el caso de
"ingrediente principal" que evita falsos positivos por ingredientes comunes).

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

# 🐳 Despliegue con Docker

```bash
docker compose up --build
```

Levanta el backend (`localhost:8000`) y el dashboard (`localhost:8501`) como
servicios separados, compartiendo `data/` como volumen persistente.

## Escalabilidad y Sostenibilidad

- **Horizontal**: `docker compose up --scale backend=3` permite correr varias
  instancias del backend. Limitación actual: SQLite tiene un solo escritor a la
  vez, por lo que con múltiples instancias escribiendo métricas/recetas concurrentemente
  se recomendaría migrar `data/agent_memory.db` a Postgres antes de escalar en producción.
- **WAL mode**: SQLite corre en modo Write-Ahead Logging (activado automáticamente
  al iniciar), lo que mejora la concurrencia lectura/escritura respecto al modo
  por defecto, sin necesidad de cambiar de motor de base de datos.
- **Cache de RAG**: las consultas semánticas repetidas se cachean en memoria
  (TTL de 5 minutos) para reducir latencia y costo de tokens en consultas similares.
- **Optimización de costos**: `LLM_MAX_CONCURRENT_CALLS`, `LLM_MAX_RETRIES` y
  `LLM_TIMEOUT_SECONDS` (variables de entorno opcionales) controlan explícitamente
  cuántas llamadas simultáneas al LLM puede disparar el proceso, para evitar
  cascadas de error 429 y su consumo de tokens en reintentos innecesarios.

---

# 📡 Endpoints Principales (REST API)

## 🔹 POST `/chat`

Pipeline ejecutado:

- Validación de dominio
- Planificación de consulta
- RAG + Búsqueda Web en Vivo.
- Orquestación inteligente con filtro estricto de ingredientes y generación de respuesta estructurada.

---

## 🔹 POST `/recomendar`

Funcionalidad:

- Recibe ingredientes.
- Ejecuta razonamiento interno.
- Devuelve recetas optimizadas.

---

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

# 🎓 Conclusión

CookAI representa una arquitectura de agentes inteligentes modular y escalable diseñada bajo principios de:

- Desacoplamiento de dependencias e inyección de clientes centrales (LLMClient).
- Memoria híbrida persistente corto y largo plazo.
- Recuperación semántica avanzada combinada con fallback dinámico a la web en tiempo real.
- Control estricto de dominio sin falsos negativos en solicitudes culinarias complejas.
- Pipeline cognitivo planificado bajo el estándar Plan-and-Execute.

El sistema está optimizado para:

- Ejecución local.
- Evaluación académica.
- Escalabilidad futura.

---

# 👥 Integrantes del Proyecto

**CookAI Team**

- Rocío Muñoz
- Francesca Valencia

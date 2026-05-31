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

- 🔎 Consulta mediante RAG semántico
- 🧩 Razonamiento mediante intersección de ingredientes sin alucinaciones
- ✍️ Escritura con persistencia en caliente

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
- Generación automática de subtareas
- Sistema de contingencias y fallback

---

## 📚 IE4 — Recuperación Semántica (RAG)

Características:

- Motor basado en **ChromaDB**
- Búsqueda por similitud coseno
- Indexación local de documentos culinarios

---

## 🛡️ IE6 — Control de Frontera de Dominio

Implementado mediante:

- Validación en `domain_validator.py`
- Filtrado de prompts fuera del dominio culinario
- Protección frente a consultas irrelevantes o maliciosas

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
LLM_TEMPERATURE=0.5
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

## 🪟 Windows (CMD)

Ejecutar:

```cmd
iniciar.bat
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

# 📡 Endpoints Principales (REST API)

## 🔹 POST `/chat`

Pipeline ejecutado:

- Validación de dominio
- Planificación de consulta
- RAG + memoria híbrida
- Generación de respuesta

---

## 🔹 POST `/recomendar`

Funcionalidad:

- Recibe ingredientes
- Ejecuta razonamiento interno
- Devuelve recetas optimizadas

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

- Desacoplamiento de dependencias
- Memoria híbrida persistente
- Recuperación semántica avanzada
- Control estricto de dominio
- Pipeline cognitivo planificado

El sistema está optimizado para:

- Ejecución local
- Evaluación académica
- Escalabilidad futura

---

# 👥 Integrantes del Proyecto

**CookAI Team**

- Rocío Muñoz
- Francesca Valencia

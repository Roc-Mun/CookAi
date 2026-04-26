# 🍳 CookAI - Sistema de Recomendación de Recetas con IA

Recomendación de recetas personalizadas usando arquitectura **RAG** (Retrieval-Augmented Generation) y **LLM** (OpenAI GPT-4o mini).

## 📋 Descripción del Proyecto

**CookAI** es un chatbot inteligente que:
- ✅ Busca recetas similares en tu base de datos (ChromaDB)
- ✅ Genera recomendaciones personalizadas basadas en:
  - Ingredientes disponibles
  - Tiempo de preparación
  - Restricciones alimentarias
  - Presupuesto
  - Preferencias culinarias
- ✅ Aprende de recetas previas del usuario
- ✅ Responde preguntas sobre cocina en tiempo real

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| RAG (Almacenamiento) | ChromaDB |
| LLM (Generación) | OpenAI GPT-4o mini |
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Procesamiento de texto | PyPDF2, python-docx |
| Gestión de secretos | python-dotenv |

---

## 📁 Estructura del Proyecto

```
cookai/
├── app/
│   ├── main.py           # API FastAPI con todos los endpoints
│   ├── rag.py            # Sistema RAG con ChromaDB
│   └── llm.py            # Cliente de OpenAI
├── data/
│   ├── recetas_ejemplo.txt    # Recetas de ejemplo para empezar
│   ├── uploads/          # Carpeta para archivos subidos
│   └── chroma_db/        # Base de datos vectorial (se crea automáticamente)
├── frontend/
│   └── index.html        # Interfaz web del usuario
├── .env                  # 🔐 Tu API key de OpenAI aquí
├── requirements.txt      # Dependencias Python
├── README.md             # Este archivo
└── venv/                 # Entorno virtual
```

---

## 🚀 Instalación y Configuración

### 1. Preparar el Entorno Virtual (ya hecho ✅)

```bash
cd cookai
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
```

### 2. Configurar la API Key

**Importante:** Sin esto, el sistema no funcionará.

```bash
# Copia .env.example a .env
cp .env.example .env  # macOS/Linux
copy .env.example .env  # Windows

# Luego abre .env y completa con tu clave de OpenAI
# OPENAI_API_KEY=sk-proj-abc123...xyz
```

**¿Dónde obtener tu API key?**
1. Ve a https://platform.openai.com/
2. Inicia sesión
3. Ve a API Keys
4. Crea una nueva key
5. Cópiala en `.env` (⚠️ NUNCA compartas este archivo)

### 3. Instalar Dependencias Específicas

Si no las instalaste aún:

```bash
pip install -r requirements.txt
```

---

## 🎯 Cómo Usar

### Opción 1: Iniciar el Servidor (Recomendado)

```bash
cd app
python main.py
```

El servidor estará en: **http://localhost:8000**

Abre en el navegador: **http://localhost:8000/docs** (documentación interactiva)

### Opción 2: Interfaz Web

1. Abre `frontend/index.html` en tu navegador
2. Interactúa con las 3 pestañas:
   - 🔍 **Recomendador**: Obtén recomendaciones personalizadas
   - 📤 **Subir Recetas**: Añade tus propias recetas
   - 💬 **Chat**: Pregunta directamente a CookAI

---

## 📚 Endpoints de la API

### GET `/`
Estado general del sistema

**Respuesta:**
```json
{
  "mensaje": "Bienvenido a CookAI",
  "endpoints": {...}
}
```

---

### GET `/status`
Verificar estado del RAG y conexión con OpenAI

**Respuesta:**
```json
{
  "rag_inicializado": true,
  "documentos_cargados": 5,
  "api_key_configurada": true
}
```

---

### POST `/upload`
Subir archivos de recetas (PDF, TXT, DOCX)

**Body (multipart/form-data):**
```
file: [tu_archivo.pdf]
```

**Respuesta:**
```json
{
  "mensaje": "Archivo subido exitosamente",
  "archivo": "recetas.pdf",
  "documentos_totales": 12
}
```

---

### POST `/recommend`
Obtener recomendaciones personalizadas

**Body:**
```json
{
  "ingredientes": ["tomate", "queso", "huevo"],
  "tiempo_disponible": "30 minutos",
  "restricciones": ["sin gluten"],
  "presupuesto": "bajo",
  "preferencias": "italiana"
}
```

**Respuesta:**
```json
{
  "recomendaciones": "Te recomiendo: ...",
  "fuentes_consultadas": 3,
  "filtros_aplicados": {...}
}
```

---

### POST `/chat`
Chat directo con CookAI

**Body:**
```json
{
  "mensaje": "¿Qué puedo hacer con tomate y cebolla?"
}
```

**Respuesta:**
```json
{
  "respuesta": "Con tomate y cebolla puedes...",
  "contexto_usado": true
}
```

---

## 💡 Ejemplos de Uso

### Ejemplo 1: Búsqueda Simple

```bash
curl -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "ingredientes": ["pasta", "tomate"],
    "tiempo_disponible": "20 minutos",
    "presupuesto": "bajo"
  }'
```

### Ejemplo 2: Subir Receta

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@recetas.pdf"
```

### Ejemplo 3: Chat

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"mensaje": "Soy vegetariano, ¿qué recetas me recomiendas?"}'
```

---

## 🔧 Configuración Avanzada

### Cambiar Modelo de LLM

En `app/llm.py`:
```python
self.model = "gpt-4"  # Más potente pero más caro
# o
self.model = "gpt-3.5-turbo"  # Más barato
```

### Ajustar Temperatura (Creatividad)

```python
self.temperature = 0.3  # Más determinista
# o
self.temperature = 1.0  # Más creativo
```

### Cambiar Número de Resultados RAG

En `app/main.py`:
```python
resultados_rag = rag_system.search(query, top_k=10)  # Buscar 10 en lugar de 5
```

---

## 🧹 Limpiar la Base de Datos

Si quieres empezar de cero:

```bash
python -c "from app.rag import RAGSystem; rag = RAGSystem(); rag.clear_database()"
```

---

## 🐛 Troubleshooting

### ❌ Error: "OPENAI_API_KEY no configurada"
- Verifica que existe el archivo `.env` en la raíz
- Comprueba que tiene `OPENAI_API_KEY=tu_clave_real`
- Sin comillas, sin espacios

### ❌ Error: "Connection refused 0.0.0.0:8000"
- Verifica que el puerto 8000 no está ocupado
- Cambia el puerto en `main.py`: `uvicorn.run(..., port=8001)`

### ❌ ChromaDB vacío
- Sube recetas primero usando `/upload`
- O procesa automáticamente `data/recetas_ejemplo.txt`

### ❌ Respuestas genéricas de OpenAI
- Verifica tu API key es válida
- Comprueba que tienes saldo en tu cuenta
- Aumenta el `max_tokens` en `llm.py`

---

## � Git & Compartir el Proyecto

### ✅ Lo que SÍ se sube a GitHub/GitLab

```
cookai/
├── app/
│   ├── main.py
│   ├── rag.py
│   └── llm.py
├── frontend/
│   └── index.html
├── data/
│   └── recetas_ejemplo.txt
├── .env.example          ← Plantilla sin valores reales
├── .gitignore            ← Ya configurado
├── requirements.txt      ← Dependencias
├── README.md             ← Este archivo
└── iniciar.*             ← Scripts de inicio
```

### ❌ Lo que NO se sube (configurado en .gitignore)

- **venv/** → Entorno virtual (pesa mucho, es local)
- **.env** → API keys (⚠️ SEGURIDAD)
- **__pycache__/** → Archivos compilados de Python
- **chroma_db/** → Base de datos generada localmente
- **data/uploads/** → Archivos subidos por usuarios

### 📋 Checklist antes de compartir

- [ ] `.env` existe con tu API key (NO subir)
- [ ] `.env.example` existe (SÍ subir)
- [ ] `.gitignore` tiene las carpetas sensibles
- [ ] `requirements.txt` actualizado (`pip freeze > requirements.txt`)
- [ ] Todos los `.py` tienen docstrings
- [ ] README tiene instrucciones claras

---

## �📈 Próximos Pasos

- [ ] Integrar autenticación de usuarios
- [ ] Guardar historial de recomendaciones
- [ ] Sistema de ratings (usuario califica la receta)
- [ ] Publicar en la nube (Vercel, Railway, Render)
- [ ] App móvil (React Native, Flutter)
- [ ] Integrar más LLMs (Anthropic, Ollama, local)

---

## 📄 Licencia

Este proyecto es de código abierto. Úsalo libremente.

---

## 🤝 Soporte

Si tienes problemas:
1. Revisa esta documentación
2. Verifica que todas las librerías están instaladas
3. Comprueba que `main.py` está en la carpeta `app/`
4. Ejecuta: `pip list` para ver las versiones

---

**¡Disfruta cocinando con IA! 🍳✨**

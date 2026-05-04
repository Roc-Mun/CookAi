# 🍳 CookAI - Recomendador de Recetas con RAG e IA

CookAI es un asistente culinario inteligente que utiliza **Llama 3 (70B)** a través de **Groq** y una base de datos vectorial **ChromaDB**. El sistema permite buscar recetas personalizadas basadas en lo que tienes en tu despensa y en los documentos que tú mismo subas.

## 📋 Características Principales

- 🧠 **IA de Alta Potencia:** Utiliza el modelo `llama3-70b-8192` para respuestas precisas.
- 📂 **Memoria Propia (RAG):** El sistema "lee" tus PDFs, TXTs y DOCXs para sugerir recetas basadas en tus propios archivos.
- ⚡ **Velocidad Ultra:** Gracias a la infraestructura de Groq, las respuestas son casi instantáneas.
- 🎨 **Interfaz Moderna:** Sistema de carga de archivos intuitivo y visualización de recetas profesional.

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
| :--- | :--- |
| **LLM** | Groq (Llama 3 70B) |
| **Backend** | FastAPI |
| **Vector DB** | ChromaDB |
| **Embeddings** | HuggingFace (Local) |
| **Frontend** | HTML5 / JavaScript / CSS3 |

---

## 🚀 Configuración e Instalación

### 1. Clonar y Preparar Entorno
```bash
git clone [https://github.com/Roc-Mun/CookAi.git](https://github.com/Roc-Mun/CookAi.git)
cd CookAi
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 2. Configurar la API Key 🔑

**¡Importante!** Sin este paso, el motor de Inteligencia Artificial no podrá procesar las recetas ni generar recomendaciones.

1.  **Crear el archivo de configuración:**
    En tu terminal, ejecuta el siguiente comando para crear tu archivo local de secretos:

    ```bash
    cp .env.example .env    # En macOS o Linux
    copy .env.example .env  # En Windows
    ```

2.  **Obtener tu clave de Groq:**
    * Ve a [Groq Cloud Console](https://console.groq.com/keys).
    * Inicia sesión o regístrate.
    * Haz clic en **"Create API Key"**.
    * Asígnale un nombre (ej. `CookAI`) y copia la clave generada (debe empezar por `gsk_`).

3.  **Vincular la clave:**
    Abre el archivo `.env` en VS Code y pega tu clave de la siguiente forma:
    ```env
    GROQ_API_KEY=gsk_tu_clave_aqui_de_48_caracteres
    ```
    
> ⚠️ Seguridad: Nunca compartas tu archivo .env. Ya está configurado en el .gitignore para tu protección.

### 3. Instalar Dependencias 📦

Asegúrate de tener el entorno virtual activo y ejecuta:

```bash
pip install -r requirements.txt
```

---
# 🎯 Cómo Usar

# Opción 1: Iniciar el Servidor
Desde la carpeta raíz del proyecto:

```bash
python -m app.main
```

El servidor estará en: http://localhost:8000 | Docs: http://localhost:8000/docs

### Opción 2: Interfaz Web

1. Abre `frontend/index.html` en tu navegador
2. Interactúa con las 3 pestañas:
   - 🔍 **Recomendador**: Obtén recomendaciones personalizadas
   - 📤 **Subir Recetas**: Añade tus propias recetas
   - 💬 **Chat**: Pregunta directamente a CookAI

---

## 📚 Endpoints de la API

El servidor utiliza **FastAPI** y expone los siguientes servicios para la comunicación entre el frontend y la IA:

### 🟢 GET `/status`
Verifica la salud del sistema, la inicialización de **ChromaDB** y la conexión con el motor de **Groq**.
* **Respuesta:** `{ "rag_inicializado": true, "api_key_configurada": true, ... }`

### 🔵 POST `/upload`
Permite subir archivos para alimentar la base de datos de conocimientos (RAG).
* **Formatos soportados:** PDF, TXT, DOCX.
* **Body:** `multipart/form-data` con el campo `file`.

### 🟠 POST `/recommend`
Genera las primeras 3 recomendaciones basadas en el perfil e ingredientes del usuario.
* **Body (JSON):**
    ```json
    {
      "ingredientes": ["atún", "pasta"],
      "tiempo_disponible": "20 min",
      "presupuesto": "bajo",
      "preferencias": "saludable"
    }
    ```

### 🟣 POST `/recommend_more`
**(Nuevo)** Genera una receta adicional evitando duplicar las que ya se muestran en la interfaz.
* **Body (JSON):**
    ```json
    {
      "ingredientes": ["atún", "pasta"],
      "recetas_vistas": ["Texto completo de la receta 1...", "Receta 2..."]
    }
    ```

### 💬 POST `/chat`
Consulta directa a **CookAI** para resolver dudas culinarias, sustitución de ingredientes o técnicas.
* **Body (JSON):**
    ```json
    {
      "mensaje": "¿Cómo se hace una salsa bechamel sin grumos?"
    }
    ```


---

## 🔧 Configuración Avanzada

### Ajustar el Modelo LLM y Creatividad

En app/llm.py puedes modificar el comportamiento de la IA:

- self.model: Cambiar entre versiones de "Llama3-70b-8192" para máxima calidad.

- self.temperature = 0.2  # Recetas más precisas.
o
- self.temperature = 0.8  # Sugerencias más creativas.

---

## 🧹 Limpiar la Base de Datos

Si deseas borrar todas las recetas subidas y empezar de cero ejecuta:

```bash
python -c "from app.rag import RAGSystem; rag = RAGSystem(); rag.clear_database()"
```

---

## 🐛 Troubleshooting

### ❌ Error: IA no responde:

Revisa que tu clave en el .env sea correcta y que el nombre de la variable coincida con lo que pide el código (GROQ_API_KEY u OPENAI_API_KEY).

### ❌ Error al subir archhivos:

Verifica que el archivo no esté abierto en otro programa y que sea un formato compatible.

### ❌ Error: "Connection refused":

El servidor no está corriendo. Ejecuta python -m app.main y verifica que no haya otro programa usando el puerto 8000.

---

## 💾 Git y Colaboración

### ✅ Lo que SÍ se sincroniza con GitHub
El repositorio contiene únicamente la lógica y estructura necesaria para que el proyecto funcione en cualquier entorno:

```text
cookai/
├── app/
│   ├── main.py           # Endpoints de FastAPI
│   ├── rag.py            # Lógica de búsqueda vectorial
│   └── llm.py            # Cliente de Groq (Llama 3)
├── frontend/
│   └── index.html        # Interfaz de usuario (HTML/JS/CSS)
├── data/
│   └── recetas_ejemplo.txt
├── .env.example          # Plantilla de configuración (Sin datos sensibles)
├── .gitignore            # Reglas de exclusión de Git
├── requirements.txt      # Listado de librerías de Python
└── README.md             # Documentación del proyecto
```

### ❌ Lo que NO se sube (Protegido por .gitignore)

Por seguridad y eficiencia, Git ignora los siguientes archivos:

- venv/: Entorno virtual (se debe recrear localmente).

- .env: Archivo con tu API Key real (⚠️ NUNCA subir).

- __pycache__/: Archivos temporales de ejecución de Python.

- chroma_db/: Tu base de datos vectorial local.

- data/uploads/: Archivos privados que hayas subido para probar.

### 📋 Checklist de seguridad

- [ ] ¿El archivo .env está fuera de GitHub?

- [ ] ¿Añadiste la clave en .env siguiendo el formato de .env.example?

- [ ] ¿Instalaste las dependencias con pip install -r requirements.txt?

---

## 🚀 Próximos Pasos

- [ ] Autenticación: Login para que cada usuario tenga sus propias recetas.

- [ ] Historial: Guardar las recetas generadas anteriormente.

- [ ] Exportación: Botón para descargar recetas en PDF.

- [x] Mejora de UI: Implementar feedback visual en la carga de archivos (Logrado ✨).

---

## 📄 Licencia

Este proyecto es de código abierto. Úsalo libremente.

---

## 🤝 Soporte y contacto

Si encuentras algún error o tienes dudas:

- Revisa que el servidor esté corriendo en el puerto 8000.
- Verifica que tu clave de Groq tenga saldo/cuota disponible.
- Asegúrate de que main.py se ejecute desde la raíz con python -m app.main.

---
Desarrollado para hacer tu cocina más inteligente. ¡Disfruta cocinando con CookAI! 🍳✨

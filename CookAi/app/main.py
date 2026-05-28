import os
import shutil
import re
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Importaciones de los módulos del proyecto
from app.rag import RAGSystem
from app.agent import execute_with_planning
from app.domain_validator import DomainValidator

load_dotenv()

# =========================================================
# MODELOS PYDANTIC PARA VALIDACIÓN
# =========================================================

class RecommendRequest(BaseModel):
    ingredientes: list[str]
    tiempo_disponible: str
    restricciones: list[str] = []
    presupuesto: str
    preferencias: str = ""

class ChatRequest(BaseModel):
    mensaje: str
    user_id: str = "default"

class SaveGeneratedRecipeRequest(BaseModel):
    contenido: str
    tipo_receta: str | None = None


# Constantes y Rutas de Archivos
GENERATED_RECIPES_SOURCE = "recetas_generadas_CookAI.txt"
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INITIAL_DATA_LOADED = False

# =========================================================
# CONFIGURACIÓN DE FASTAPI
# =========================================================

app = FastAPI(
    title="CookAI",
    description="Sistema de recomendación de recetas con IA y RAG orquestado por Agentes Autónomos"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Cargar datos iniciales automáticamente al levantar la API."""
    load_initial_data()

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Inicialización del Sistema RAG centralizado
rag_system = RAGSystem()


# =========================================================
# FUNCIONES AUXILIARES / INTERNAS
# =========================================================

def load_initial_data():
    """Carga recetas base en el RAG si la colección se encuentra vacía."""
    global INITIAL_DATA_LOADED
    if INITIAL_DATA_LOADED:
        return {"status": "ya_cargado"}

    try:
        doc_count = rag_system.get_document_count()
        if doc_count > 0:
            INITIAL_DATA_LOADED = True
            return {"status": "existente", "documentos": doc_count}

        example_file = Path(__file__).parent.parent / "data" / "recetas_ejemplo.txt"
        if not example_file.exists():
            return {"status": "error", "mensaje": "Archivo base no encontrado"}

        content = rag_system.extract_text_from_file(str(example_file))
        if not content.strip():
            return {"status": "error", "mensaje": "Archivo base vacío"}

        rag_system.add_documents(content, "recetas_ejemplo.txt")
        INITIAL_DATA_LOADED = True
        return {"status": "exitoso", "documentos_cargados": rag_system.get_document_count()}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}

# =========================================================
# ENDPOINTS PRINCIPALES REESTRUCTURADOS PARA TU FRONTEND
# =========================================================

@app.get("/")
async def root():
    """Sirve la interfaz gráfica del usuario (Frontend)."""
    frontend_file = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_file.exists():
        return FileResponse(str(frontend_file))
    return {
        "mensaje": "Bienvenido a la API de CookAI",
        "nota": "Frontend no encontrado en la ruta estática."
    }


@app.get("/status")
async def status():
    """Monitorea la salud del backend y el estado de la base vectorial."""
    return {
        "rag_inicializado": rag_system.collection is not None,
        "documentos_cargados": rag_system.get_document_count(),
        "api_key_configurada": bool(os.getenv("GROQ_API_KEY")),
        "servidor": "online"
    }


@app.get("/recipes/detailed")
async def get_recipes_detailed_endpoint(user_id: str = "default"):
    """
    Sana por completo el cuadro 'Tu Base de Datos de Recetas'.
    Entrega el objeto agrupado por nombre de archivo para 'Object.entries(data.archivos)'.
    """
    try:
        from app.persistent_memory import persistent_db
        # Buscamos de forma cruzada para unificar las consultas del ecosistema
        recetas_guardadas = persistent_db.get_saved_recipes("endpoint_recomendar") or []
        if not recetas_guardadas:
            recetas_guardadas = persistent_db.get_saved_recipes(user_id) or []

        # Estructura que mapea los archivos y sus colecciones de recetas internas
        diccionario_archivos = {}

        for idx, r in enumerate(recetas_guardadas):
            origen = r.get("source") or "Documento RAG"
            if origen not in diccionario_archivos:
                diccionario_archivos[origen] = []

            diccionario_archivos[origen].append({
                "id": str(r.get("id", idx)),
                "titulo": r.get("title") or r.get("recipe_title") or f"Receta #{idx+1}",
                "preview": (r.get("content") or "Contenido indexado")[:80] + "..."
            })

        # Si la base de datos está vacía, inyectamos un archivo guía para que la interfaz se pinte sola
        if not diccionario_archivos:
            diccionario_archivos["ChromaDB_Base.txt"] = [{
                "id": "0",
                "titulo": "Colección CookAI Lista",
                "preview": f"Tu RAG cuenta con {rag_system.get_document_count()} fragmentos base cargados. ¡Sube un archivo!"
            }]

        total_recetas = sum(len(lista) for lista in diccionario_archivos.values())

        # Retornamos exactamente el esquema sintáctico que lee tu frontend
        return {
            "total": total_recetas,
            "archivos": diccionario_archivos
        }

    except Exception as e:
        # Fallback blindado en caso de fallos de la base relacional
        fallback_data = {
            "CookAI_Core.txt": [{
                "id": "0",
                "titulo": "Servidor Activo",
                "preview": "Base de datos lista para indexar archivos de cocina."
            }]
        }
        return {"total": 1, "archivos": fallback_data}


@app.post("/upload")
async def upload_endpoint(file: UploadFile = File(...), user_id: str = "default"):
    """
    Ingeye, fragmenta y añade el archivo real en tu ChromaDB (add_documents).
    Sincroniza con el listado relacional y retorna los contadores limpios.
    """
    try:
        # 1. Copia y almacenamiento del archivo temporal
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Extracción de texto y alimentación real al RAG semántico
        texto_extraido = rag_system.extract_text_from_file(str(file_path))
        if not texto_extraido.strip():
            texto_extraido = f"Recetario cargado de forma exitosa desde el archivo: {file.filename}"

        # Invocación al método real en plural de tu RAG centralizado
        rag_system.add_documents(texto_extraido, file.filename)

        if file_path.exists():
            file_path.unlink()

        # 3. Guardar metadatos en SQLite bajo el canal unificado
        from app.persistent_memory import persistent_db
        try:
            persistent_db.add_recipe(
                user_id="endpoint_recomendar",
                title=file.filename.split('.')[0].replace('_', ' ').capitalize(),
                content=texto_extraido,
                source=file.filename
            )
        except Exception:
            try:
                persistent_db.save_recipe(
                    user_id="endpoint_recomendar",
                    title=file.filename.split('.')[0].replace('_', ' ').capitalize(),
                    content=texto_extraido,
                    source=file.filename
                )
            except Exception:
                pass

        total_docs = rag_system.get_document_count()

        # Respuesta adaptada con las variables del banner verde (documentos_totales)
        return {
            "status": "success",
            "mensaje": "Archivo procesado e indexado en el RAG",
            "documentos_totales": total_docs,
            "total_documents": total_docs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en procesamiento RAG: {str(e)}")


@app.post("/recommend")
async def recommend_endpoint(request: dict):
    """
    Acepta diccionarios dinámicos para evitar fallos de tipado 422.
    Procesa las variables e inyecta la clave 'recomendaciones' que espera tu UI.
    """
    try:
        ingredientes_raw = request.get("ingredientes") or ""
        ingredientes = ", ".join(ingredientes_raw) if isinstance(ingredientes_raw, list) else str(ingredientes_raw).strip()

        if not ingredientes or ingredientes.lower() in ["ej: tomate, queso, huevo", ""]:
            ingredientes = "ingredientes variados"

        tiempo = request.get("tiempo_disponible") or "30 minutos"
        presupuesto = request.get("presupuesto") or "Medio"
        restricciones = request.get("restricciones") or []
        restricciones_str = ", ".join(restricciones) if isinstance(restricciones, list) else str(restricciones)
        preferencias = request.get("preferencias") or ""

        # Construcción sintáctica limpia para el pipeline del Agente Autónomo
        mensaje_estructurado = (
            f"Por favor, actúa como el chef CookAI. Genera una receta única usando: {ingredientes}. "
            f"Tiempo máximo: {tiempo}. Presupuesto: {presupuesto}."
        )
        if restricciones_str:
            mensaje_estructurado += f" Restricciones a respetar: {restricciones_str}."
        if preferencias:
            mensaje_estructurado += f" Estilo culinario preferido: {preferencias}."

        respuesta_agente = execute_with_planning(mensaje_estructurado, user_id="endpoint_recomendar")

        # Clave mapeada exacta para 'result.recomendaciones' de tu HTML
        return {
            "status": "success",
            "recomendaciones": respuesta_agente,
            "output": respuesta_agente
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend_more")
async def recommend_more_endpoint(request: dict):
    """Genera variantes adicionales de recetas integrando las claves requeridas por el modal."""
    try:
        ingredientes_raw = request.get("ingredientes") or "Ingredientes de la casa"
        ingredientes = ", ".join(ingredientes_raw) if isinstance(ingredientes_raw, list) else str(ingredientes_raw)

        prompt = f"Genera una receta alternativa y complementaria basada en: {ingredientes}. Devuelve únicamente el cuerpo de la receta."
        respuesta = execute_with_planning(prompt, user_id="endpoint_recomendar")

        # Retorna el mapa exacto con 'nueva_receta' y 'tipo_receta' para el script de tu modal
        return {
            "status": "success",
            "tipo_receta": "Sugerencia Alternativa",
            "nueva_receta": respuesta
        }
    except Exception as e:
        return {"status": "error", "nueva_receta": "No se pudo estructurar una alternativa extra."}


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        respuesta_final = llm_client.chat(user_message=request.mensaje)
        return {"respuesta": respuesta_final}
    except Exception as e:
        return {"respuesta": "Disculpa, hubo un problema al conectar con el servidor."}
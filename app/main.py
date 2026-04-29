from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import shutil
from pathlib import Path
import re

#Cambio línea de código agregando app.
from app.rag import RAGSystem
from app.llm import LLMClient
from app.ingredient_match import bloque_analisis_para_prompt, es_consulta_sustitucion
from pydantic import BaseModel

load_dotenv()

# Modelos Pydantic para validación
class RecommendRequest(BaseModel):
    ingredientes: list[str]
    tiempo_disponible: str
    restricciones: list[str] = []
    presupuesto: str
    preferencias: str = ""

class ChatRequest(BaseModel):
    mensaje: str

class MoreRecipesRequest(BaseModel):
    recetas_vistas: list[str] = []
    ingredientes: list[str]


class SaveGeneratedRecipeRequest(BaseModel):
    contenido: str
    tipo_receta: str | None = None


# Archivo lógico agrupado en la UI para todas las recetas guardadas desde "Generar más"
GENERATED_RECIPES_SOURCE = "recetas_generadas_CookAI.txt"


def _parse_tipo_y_cuerpo_receta_generada(raw: str) -> tuple[str, str]:
    """Separa la línea TIPO: del resto (texto a guardar y mostrar)."""
    text = (raw or "").strip()
    if not text:
        return "Receta generada", ""
    lines = text.split("\n")
    first = lines[0].strip()
    if first.upper().startswith("TIPO:"):
        tipo = first.split(":", 1)[1].strip() or "Receta generada"
        body = "\n".join(lines[1:]).strip()
        return tipo, body
    return "Receta generada", text


def _titulo_desde_contenido_receta(content: str, metadata: dict) -> str:
    """Título para listado: formato === RECETA ===, N) TÍTULO, o metadata."""
    tipo_meta = (metadata or {}).get("tipo_receta") or ""
    titulo = "Sin título"
    for line in content.split("\n"):
        line_st = line.strip()
        if not line_st:
            continue
        if "===" in line_st and "RECETA" in line_st.upper():
            titulo = line_st.replace("=", "").strip()
            break
        m = re.match(r"^\d+\)\s*(.+)$", line_st)
        if m:
            titulo = m.group(1).strip()
            break
    if tipo_meta and titulo != "Sin título":
        return f"[{tipo_meta}] {titulo}"
    if tipo_meta:
        return f"[{tipo_meta}] Receta generada"
    return titulo


app = FastAPI(title="CookAI", description="Sistema de recomendación de recetas con IA y RAG")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Evento de startup para cargar datos iniciales
@app.on_event("startup")
async def startup_event():
    """Cargar datos iniciales al iniciar la aplicación"""
    load_initial_data()

# Montar archivos estáticos (frontend)
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Inicializar sistemas
rag_system = RAGSystem()
llm_client = LLMClient()

# Crear carpeta de uploads si no existe
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Flag para controlar carga inicial
INITIAL_DATA_LOADED = False

def load_initial_data():
    """Cargar recetas de ejemplo en la base de datos si está vacía"""
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
            return {"status": "error", "mensaje": "Archivo no encontrado"}
        
        content = rag_system.extract_text_from_file(str(example_file))
        if not content.strip():
            return {"status": "error", "mensaje": "Archivo vacío"}
        
        rag_system.add_documents(content, "recetas_ejemplo.txt")
        INITIAL_DATA_LOADED = True
        
        final_count = rag_system.get_document_count()
        return {"status": "exitoso", "documentos_cargados": final_count}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}


@app.get("/")
async def root():
    """Servir el frontend HTML"""
    frontend_file = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_file.exists():
        return FileResponse(str(frontend_file))
    return {
        "mensaje": "Bienvenido a CookAI",
        "descripcion": "Sistema inteligente de recomendación de recetas con IA",
        "nota": "Frontend no encontrado en frontend/index.html"
    }


@app.get("/status")
async def status():
    """Verificar estado del sistema RAG"""
    return {
        "rag_inicializado": rag_system.collection is not None,
        "documentos_cargados": rag_system.get_document_count(),
        "api_key_configurada": bool(os.getenv("OPENAI_API_KEY")),
        "servidor": "online"
    }


@app.get("/init")
async def initialize_database():
    """
    Inicializar la base de datos cargando recetas de ejemplo
    Puede ejecutarse más de una vez (solo carga si está vacía)
    """
    result = load_initial_data()
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["mensaje"])
    
    return result


@app.post("/upload")
async def upload_recipe_file(file: UploadFile = File(...)):
    """
    Subir archivos de recetas (PDF, TXT, Word)
    Se procesan y se agregan a la base vectorial
    """
    try:
        # Validar tipo de archivo
        allowed_extensions = {".pdf", ".txt", ".docx", ".doc"}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Formato no permitido. Use: {', '.join(allowed_extensions)}"
            )
        
        # Guardar archivo
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Procesar archivo y añadir a RAG
        content = rag_system.extract_text_from_file(str(file_path))
        rag_system.add_documents(content, file.filename)
        
        return {
            "mensaje": "Archivo subido exitosamente",
            "archivo": file.filename,
            "documentos_totales": rag_system.get_document_count()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")


@app.post("/recommend")
async def get_recommendations(request: RecommendRequest):
    """
    Obtener recomendaciones de recetas personalizadas
    
    Body esperado:
    {
        "ingredientes": ["tomate", "queso", "huevo"],
        "tiempo_disponible": "30 minutos",
        "restricciones": ["sin gluten"],
        "presupuesto": "bajo",
        "preferencias": "italiana"
    }
    """
    try:
        # Validar que hay ingredientes
        if not request.ingredientes or len(request.ingredientes) == 0:
            raise HTTPException(status_code=400, detail="Debes proporcionar al menos un ingrediente")
        
        # Limpiar ingredientes vacíos
        ingredientes = [i.strip() for i in request.ingredientes if i.strip()]
        
        # Validar API key
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="API key de Groq no configurada. Por favor, añade tu clave en .env")
        
        query = f"recetas con {', '.join(ingredientes)} {request.preferencias}".strip()
        chunks = rag_system.search_chunks(query, top_k=5)
        if chunks:
            resultados_rag = "\n---\n".join(
                [f"Fuente: {c['source']}\n{c['text']}" for c in chunks]
            )
            analisis_ing = bloque_analisis_para_prompt(ingredientes, chunks)
        else:
            resultados_rag = rag_system.search(query, top_k=5)
            analisis_ing = ""
        
        # Generar recomendación con LLM
        prompt = f"""
        === RECETAS EN TU BASE DE DATOS PERSONAL (RAG) ===
        {resultados_rag}
        
        === COINCIDENCIA INGREDIENTES (automático; no inventes otras cifras) ===
        {analisis_ing or "—"}
        
        === TUS PREFERENCIAS HOY ===
        - Ingredientes disponibles: {', '.join(ingredientes)}
        - Tiempo disponible: {request.tiempo_disponible}
        - Restricciones: {', '.join(request.restricciones) if request.restricciones else 'ninguna'}
        - Presupuesto: {request.presupuesto}
        - Preferencias: {request.preferencias}
        
        === INSTRUCCIONES ===
        Solo recetas de la base RAG arriba. Usa el bloque COINCIDENCIA: si nivel bajo/medio, advierte que pocos ingredientes de la lista del usuario aparecen en esa receta; si alto, prioriza y resume cuántos coinciden y qué líneas de ingredientes faltan según ese bloque.
        Recomienda hasta 3 recetas (prioriza mayor coincidencia).
        
        Formato:
        X) NOMBRE DE LA RECETA
        
        [Instrucciones de preparación]
        
        [Por qué según tu historial específico]
        """
        
        recomendacion = llm_client.generate_response(prompt)
        
        return {
            "recomendaciones": recomendacion,
            "fuentes_consultadas": len(chunks) if chunks else 0,
            "filtros_aplicados": {
                "ingredientes": ingredientes,
                "tiempo": request.tiempo_disponible,
                "restricciones": request.restricciones,
                "presupuesto": request.presupuesto
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar recomendación: {str(e)}")


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat directo con el asistente de CookAI
    Body: {"mensaje": "¿Qué puedo hacer con tomate y cebolla?"}
    """
    try:
        # Validar API key
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="API key de Groq no configurada")
        
        contexto = rag_system.search(request.mensaje, top_k=3)
        aviso_sub = ""
        if es_consulta_sustitucion(request.mensaje):
            aviso_sub = "\n(Sustituciones: prioriza RAG; alternativas concretas pueden ser conocimiento general del modelo — indica una frase breve de que esa parte no sale solo de sus archivos.)\n"
        
        # Generar respuesta
        prompt = f"""
        === RECETAS EN BASE DE DATOS DEL USUARIO (RAG) ===
        {contexto}
        
        === PREGUNTA DEL USUARIO ===
        {request.mensaje}
        {aviso_sub}
        === INSTRUCCIONES ===
        Responde basándote principalmente en las recetas RAG arriba; no te desvíes de ellas.
        Si pregunta sobre sustituciones, ancla la receta en su BD y luego sugiere alternativas coherentes.
        Si no hay contexto útil en su BD, dilo y sugiere agregar recetas.
        """
        
        respuesta = llm_client.generate_response(prompt)
        
        return {
            "respuesta": respuesta,
            "contexto_usado": bool(contexto)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en chat: {str(e)}")
    

@app.get("/recipes")
async def get_recipes_list():
    """
    Obtener historial de recetas cargadas en la BD
    """
    try:
        doc_count = rag_system.get_document_count()
        sample_search = rag_system.collection.get()
        
        return {
            "total_recetas": doc_count,
            "recetas_cargadas": sample_search.get("metadatas", []) if sample_search else [],
            "mensaje": f"Total: {doc_count} recetas en tu base de datos"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/recipes/detailed")
async def get_recipes_detailed():
    """
    Obtener recetas detalladas agrupadas por archivo con títulos
    """
    try:
        all_docs = rag_system.collection.get()
        
        if not all_docs["ids"]:
            return {"archivos": [], "total": 0}
        
        # Agrupar por source
        archivos = {}
        for doc_id, content, metadata in zip(all_docs["ids"], all_docs["documents"], all_docs["metadatas"]):
            source = metadata.get("source", "Sin nombre")
            
            if source not in archivos:
                archivos[source] = []
            
            titulo = _titulo_desde_contenido_receta(content, metadata or {})
            
            archivos[source].append({
                "id": doc_id,
                "titulo": titulo,
                "preview": content[:100].replace("\n", " ") + "..."
            })
        
        return {
            "archivos": archivos,
            "total": len(all_docs["ids"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.delete("/recipes/item")
async def delete_recipe_item(item_id: str = None):
    """
    Eliminar una receta específica por su chunk ID
    Query param: ?item_id=doc_123
    """
    try:
        if not item_id:
            raise HTTPException(status_code=400, detail="Especifica el item_id")
        
        # Verificar que existe
        doc = rag_system.collection.get(ids=[item_id])
        if not doc["ids"]:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        
        # Eliminar
        rag_system.collection.delete(ids=[item_id])
        
        return {
            "mensaje": "Receta eliminada",
            "item_id": item_id,
            "documentos_restantes": rag_system.get_document_count()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.delete("/recipes")
async def delete_recipe(source: str = None):
    """
    Eliminar recetas por nombre de archivo
    Query param: ?source=nombre_archivo.txt
    """
    try:
        if not source:
            raise HTTPException(status_code=400, detail="Especifica el archivo a eliminar")
        
        all_docs = rag_system.collection.get()
        ids_to_delete = [
            doc_id for doc_id, meta in zip(all_docs["ids"], all_docs["metadatas"])
            if meta.get("source") == source
        ]
        
        if not ids_to_delete:
            raise HTTPException(status_code=404, detail=f"No encontrado: {source}")
        
        rag_system.collection.delete(ids=ids_to_delete)
        
        return {
            "mensaje": "Eliminado exitosamente",
            "archivo": source,
            "documentos_restantes": rag_system.get_document_count()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/recommend_more")
async def get_one_more(request: MoreRecipesRequest):
    """
    Generar una receta adicional siguiendo el formato limpio y sin repeticiones
    """
    try:
        # Validar API key
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="API key de Groq no configurada")
        
        # Validar ingredientes
        if not request.ingredientes or len(request.ingredientes) == 0:
            raise HTTPException(status_code=400, detail="Debes proporcionar al menos un ingrediente")
        
        prompt = f"""
        Eres CookAI. El usuario ya vio estas recetas: {request.recetas_vistas}.
        Basado en los ingredientes {', '.join(request.ingredientes)}, genera UNA SOLA receta nueva.
        
        REGLAS DE FORMATO (SÍGUELAS AL PIE DE LA LETRA):
        0. La PRIMERA línea debe ser exactamente: TIPO: <categoría breve en español> (ej. postre, ensalada, plato principal, sopa, desayuno).
        1. Línea en blanco.
        2. Luego el título numerado: X) NOMBRE DE LA RECETA (en MAYÚSCULAS).
        3. Línea en blanco.
        4. Instrucciones de preparación, sin introducciones como "Aquí tienes...".
        5. Línea en blanco y un comentario breve final sobre por qué elegiste la receta.
        """
        
        raw = llm_client.generate_response(prompt)
        tipo_receta, nueva_receta = _parse_tipo_y_cuerpo_receta_generada(raw)
        
        return {
            "tipo_receta": tipo_receta,
            "nueva_receta": nueva_receta,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar más: {str(e)}")


@app.post("/recipes/save_generated")
async def save_generated_recipe(request: SaveGeneratedRecipeRequest):
    """
    Persiste en ChromaDB una receta generada por el usuario tras confirmar en la UI.
    """
    try:
        contenido = (request.contenido or "").strip()
        if not contenido:
            raise HTTPException(status_code=400, detail="No hay contenido para guardar")
        tipo = (request.tipo_receta or "").strip() or None
        extra = {"tipo_receta": tipo} if tipo else {}
        doc_id = rag_system.add_single_recipe_document(
            contenido, GENERATED_RECIPES_SOURCE, extra_metadata=extra or None
        )
        return {
            "mensaje": "Receta guardada en tu base de datos",
            "item_id": doc_id,
            "source": GENERATED_RECIPES_SOURCE,
            "documentos_totales": rag_system.get_document_count(),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

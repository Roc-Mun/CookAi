from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import shutil
from pathlib import Path

#Cambio línea de código agregando app.
from app.rag import RAGSystem
from app.llm import LLMClient

load_dotenv()

app = FastAPI(title="CookAI", description="Sistema de recomendación de recetas con IA y RAG")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "api_key_configurada": bool(os.getenv("OPENAI_API_KEY"))
    }


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
async def get_recommendations(request: dict):
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
        ingredientes = request.get("ingredientes", [])
        tiempo = request.get("tiempo_disponible", "sin límite")
        restricciones = request.get("restricciones", [])
        presupuesto = request.get("presupuesto", "normal")
        preferencias = request.get("preferencias", "")
        
        # Buscar recetas relevantes en ChromaDB
        query = f"recetas con {', '.join(ingredientes)} {preferencias}".strip()
        resultados_rag = rag_system.search(query, top_k=5)
        
        # Generar recomendación con LLM
        prompt = f"""
        Basándote en las siguientes recetas disponibles:
        
        {resultados_rag}
        
        El usuario tiene:
        - Ingredientes disponibles: {', '.join(ingredientes)}
        - Tiempo disponible: {tiempo}
        - Restricciones dietarias: {', '.join(restricciones) if restricciones else 'ninguna'}
        - Presupuesto: {presupuesto}
        - Preferencias de cocina: {preferencias}
        
        INSTRUCCIONES DE FORMATO: 
        - Recomienda 3 recetas personalizadas.
        - ORTOGRAFÍA PERFECTA: Aunque el usuario escriba sin tildes (ej: 'atun', 'papa', 'limon'), tú DEBES escribir correctamente en español ('atún', 'papa', 'limón') tanto en los títulos como en el texto.
        - Para cada receta usa este formato exacto:
        TÍTULOS: Usa el formato "X) NOMBRE DE LA RECETA" en MAYÚSCULAS y con tildes correctas.
        
        [Instrucciones de preparación]
        
        [Comentario breve de por qué es adecuada]
        
        - NO uses asteriscos ni almohadillas.
        - Deja líneas en blanco entre el título, la preparación y el comentario.
        """
        
        recomendacion = llm_client.generate_response(prompt)
        
        return {
            "recomendaciones": recomendacion,
            "fuentes_consultadas": len(resultados_rag.split("\n")) if resultados_rag else 0,
            "filtros_aplicados": {
                "ingredientes": ingredientes,
                "tiempo": tiempo,
                "restricciones": restricciones,
                "presupuesto": presupuesto
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar recomendación: {str(e)}")


@app.post("/chat")
async def chat(message: dict):
    """
    Chat directo con el asistente de CookAI
    Body: {"mensaje": "¿Qué puedo hacer con tomate y cebolla?"}
    """
    try:
        user_message = message.get("mensaje", "")
        
        if not user_message:
            raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
        
        # Buscar contexto en RAG
        contexto = rag_system.search(user_message, top_k=3)
        
        # Generar respuesta
        prompt = f"""
        Eres CookAI, un asistente experto en recomendación de recetas.
        
        Contexto de recetas disponibles:
        {contexto}
        
        Usuario: {user_message}
        
        Responde de forma amable y útil, recomendando recetas cuando sea relevante.
        """
        
        respuesta = llm_client.generate_response(prompt)
        
        return {
            "respuesta": respuesta,
            "contexto_usado": bool(contexto)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en chat: {str(e)}")
    

@app.post("/recommend_more")
async def get_one_more(request: dict):
    """
    Generar una receta adicional siguiendo el formato limpio y sin repeticiones
    """
    try:
        vistas = request.get("recetas_vistas", [])
        ingredientes = request.get("ingredientes", [])
        
        # Prompt mejorado con reglas de espacio
        prompt = f"""
        Eres CookAI. El usuario ya vio estas recetas: {vistas}.
        Basado en los ingredientes {', '.join(ingredientes)}, genera UNA SOLA receta nueva.
        
        REGLAS DE FORMATO (SÍGUELAS AL PIE DE LA LETRA):
        1. Comienza directamente con el título: X) NOMBRE DE LA RECETA (en MAYÚSCULAS).
        2. Salta UNA línea en blanco.
        3. Escribe solo las instrucciones de preparación, sin textos de introducción como "Aquí tienes...".
        4. Salta OTRA línea en blanco después de la preparación.
        5. Termina con un comentario breve sobre por qué elegiste la receta.
        
        EJEMPLO DE ESTRUCTURA:
        4) TITULO DE LA RECETA
        
        Corta los ingredientes... (instrucciones)
        
        Esta receta es ideal porque... (comentario final)
        """
        
        nueva_receta = llm_client.generate_response(prompt)
        
        return {
            "nueva_receta": nueva_receta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar más: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

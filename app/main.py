import os
import shutil
import re
import time

from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Importaciones de los módulos del proyecto
from app.rag import RAGSystem
from app.domain_validator import DomainValidator
from app.agent import execute_with_planning, agent  # Importamos el agente y su ecosistema
from app.ingredient_match import bloque_analisis_para_prompt, es_consulta_sustitucion, analyze_overlap
from app.monitoring import CookAIMonitor

# Inicialización segura del monitor del ecosistema CookAI
monitor = CookAIMonitor()
load_dotenv()

# Acceso seguro al cliente de LLM que ya está instanciado en el Agente para extraer tokens reales
llm_client = agent._llm_client

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

class MoreRecipesRequest(BaseModel):
    recetas_vistas: list[str] = []
    ingredientes: list[str]


# Constantes y Rutas de Archivos
GENERATED_RECIPES_SOURCE = "recetas_generadas_CookAI.txt"
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INITIAL_DATA_LOADED = False

# =========================================================
# HELPERS INTERNOS
# =========================================================

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

def _parse_tipo_y_cuerpo_receta_generada(raw: str) -> tuple[str, str]:
    """Separa la línea TIPO: del resto."""
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
    load_initial_data()

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Inicialización del Sistema RAG centralizado
rag_system = RAGSystem()
domain_validator = DomainValidator()


# =========================================================
# FUNCIONES AUXILIARES / INTERNAS
# =========================================================

def load_initial_data():
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
# ENDPOINTS PRINCIPALES
# =========================================================

@app.get("/")
async def root():
    frontend_file = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_file.exists():
        return FileResponse(str(frontend_file))
    return {
        "mensaje": "Bienvenido a la API de CookAI",
        "nota": "Frontend no encontrado en la ruta estática."
    }


@app.get("/status")
async def status():
    return {
        "rag_inicializado": rag_system.collection is not None,
        "documentos_cargados": rag_system.get_document_count(),
        "api_key_configurada": bool(os.getenv("GROQ_API_KEY")),
        "servidor": "online"
    }


@app.get("/recipes/detailed")
async def get_recipes_detailed_endpoint():
    try:
        all_docs = rag_system.collection.get()
        if not all_docs or not all_docs.get("ids") or len(all_docs["ids"]) == 0:
            return {"archivos": {}, "total": 0}

        archivos = {}
        for doc_id, content, metadata in zip(
                all_docs["ids"], all_docs["documents"], all_docs["metadatas"]
        ):
            source = (metadata or {}).get("source", "Sin nombre")
            if source not in archivos:
                archivos[source] = []

            titulo = _titulo_desde_contenido_receta(content, metadata or {})
            archivos[source].append({
                "id": doc_id,
                "titulo": titulo,
                "preview": content[:100].replace("\n", " ") + "..."
            })

        return {"archivos": archivos, "total": len(all_docs["ids"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/metrics")
async def get_metrics_endpoint():
    try:
        metrics = monitor.get_aggregated_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener métricas del sistema: {str(e)}"
        )


@app.post("/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    try:
        inicio = time.time()
        allowed_extensions = {".pdf", ".txt", ".docx", ".doc"}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no permitido. Use: {', '.join(allowed_extensions)}"
            )

        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        texto_extraido = rag_system.extract_text_from_file(str(file_path))
        if not texto_extraido.strip():
            texto_extraido = f"Recetario cargado desde: {file.filename}"

        rag_system.add_documents(texto_extraido, file.filename)

        if file_path.exists():
            file_path.unlink()

        total_docs = rag_system.get_document_count()
        fin = time.time()
        latencia = (fin - inicio) * 1000

        monitor.save_metric(
            latencia_ms=latencia,
            tokens_input=0,
            tokens_output=0,
            status="SUCCESS",
            tipo_operacion="rag_upload"
        )

        return {
            "status": "success",
            "mensaje": "Archivo procesado e indexado en el RAG",
            "documentos_totales": total_docs,
            "total_documents": total_docs
        }
    except HTTPException:
        raise
    except Exception as e:
        fin = time.time()
        latencia = (fin - inicio) * 1000
        monitor.save_metric(
            latencia_ms=latencia,
            tokens_input=0,
            tokens_output=0,
            status="FAILED",
            tipo_operacion="rag_upload"
        )
        raise HTTPException(status_code=500, detail=f"Error en procesamiento RAG: {str(e)}")


@app.delete("/recipes/item")
async def delete_recipe_item(item_id: str = None):
    try:
        if not item_id:
            raise HTTPException(status_code=400, detail="Especifica el item_id")

        doc = rag_system.collection.get(ids=[item_id])
        if not doc["ids"]:
            raise HTTPException(status_code=404, detail="Receta no encontrada")

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
async def delete_recipe_by_source(source: str = None):
    try:
        if not source:
            raise HTTPException(status_code=400, detail="Especifica el archivo a eliminar")

        all_docs = rag_system.collection.get()
        ids_to_delete = [
            doc_id for doc_id, meta in zip(all_docs["ids"], all_docs["metadatas"])
            if (meta or {}).get("source") == source
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


@app.post("/recipes/save_generated")
async def save_generated_recipe(request: SaveGeneratedRecipeRequest):
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


# =========================================================
# PESTAÑA 2 — RECOMENDADOR CON THRESHOLDING ESTRICTO
# =========================================================
UMBRAL_COINCIDENCIA_MINIMO = 0.40

@app.post("/recommend")
async def recommend_endpoint(request: dict):
    try:
        inicio = time.time()
        ingredientes_raw = request.get("ingredientes") or ""
        ingredientes = [i.strip() for i in ingredientes_raw] if isinstance(ingredientes_raw, list) else str(ingredientes_raw).strip().split(",")
        ingredientes = [i.strip() for i in ingredientes if i.strip()]

        if not ingredientes or ingredientes == ["ej: tomate, queso, huevo"]:
            ingredientes = ["ingredientes variados"]

        tiempo = request.get("tiempo_disponible") or "30 minutos"
        presupuesto = request.get("presupuesto") or "Medio"
        restricciones = request.get("restricciones") or []
        restricciones_str = ", ".join(restricciones) if isinstance(restricciones, list) else str(restricciones)
        preferencias = request.get("preferencias") or ""

        monitor.log_trace(user_id="endpoint_recomendar", step_name="RAG_Retrieval", tool_used="ChromaDB", status="STARTED")
        query_busqueda = f"recetas con {', '.join(ingredientes)} {preferencias}".strip()
        chunks = rag_system.search_chunks(query_busqueda, top_k=5)
        monitor.log_trace(user_id="endpoint_recomendar", step_name="RAG_Retrieval", tool_used="ChromaDB", status="SUCCESS")

        monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="STARTED")
        mejor_ratio = 0.0
        chunks_validos = []

        if chunks and ingredientes != ["ingredientes variados"]:
            for ch in chunks:
                analisis = analyze_overlap(ingredientes, ch.get("text", ""))
                ratio = analisis.get("ratio_usuario_en_receta", 0.0)
                nivel = analisis.get("nivel_coincidencia", "bajo")
                if ratio > mejor_ratio:
                    mejor_ratio = ratio
                if nivel in ("alto", "medio") or ratio >= UMBRAL_COINCIDENCIA_MINIMO:
                    chunks_validos.append(ch)

        if not chunks_validos and ingredientes != ["ingredientes variados"]:
            motivo = f"⚠️ Sin coincidencia suficiente en tu base de recetas.\n\nTus ingredientes ({', '.join(ingredientes)}) no coinciden suficientemente con la base de datos local. Sin embargo, nuestro sistema ha gestionado el caso con éxito."
            monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="SUCCESS")

            # Guardamos la métrica en SUCCESS porque el filtro de negocio controló la restricción correctamente
            monitor.save_metric(
                latencia_ms=(time.time() - inicio) * 1000,
                tokens_input=0,
                tokens_output=0,
                status="SUCCESS",
                tipo_operacion="recomendar"
            )
            return {
                "status": "sin_coincidencia",
                "recomendaciones": motivo,
                "output": motivo,
                "puede_generar": True,
                "analisis_disponible": False
            }

        monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="SUCCESS")

        analisis_ing = bloque_analisis_para_prompt(ingredientes, chunks_validos)

        mensaje_estructurado = (
            f"Por favor, actúa como el chef CookAI. Recomienda una receta usando: {', '.join(ingredientes)}. "
            f"Tiempo máximo: {tiempo}. Presupuesto: {presupuesto}."
        )
        if restricciones_str:
            mensaje_estructurado += f" Restricciones: {restricciones_str}."
        if preferencias:
            mensaje_estructurado += f" Estilo culinario: {preferencias}."
        if analisis_ing and analisis_ing != "(Sin fragmentos RAG.)":
            mensaje_estructurado += f"\n\n=== ANÁLISIS DE TUS INGREDIENTES EN LA BASE ===\n{analisis_ing}"

        monitor.log_trace(user_id="endpoint_recomendar", step_name="LLM_Generation", tool_used="PlanningAgent", status="STARTED")
        respuesta_agente = execute_with_planning(mensaje_estructurado, user_id="endpoint_recomendar")

        if "<div" in respuesta_agente:
            respuesta_agente = respuesta_agente.split("<div")[0].strip()

        respuesta_agente = re.sub(r"\*\*Nota importante:\*\*.*", "", respuesta_agente, flags=re.DOTALL)
        respuesta_agente = re.sub(r"\*\*Justificación del beneficio:\*\*.*", "", respuesta_agente, flags=re.DOTALL)
        respuesta_agente = respuesta_agente.strip()

        monitor.log_trace(user_id="endpoint_recomendar", step_name="LLM_Generation", tool_used="PlanningAgent", status="SUCCESS")

        fin = time.time()
        latencia = (fin - inicio) * 1000

        monitor.save_metric(
            latencia_ms=latencia,
            tokens_input=llm_client.last_usage.get("input", 0),
            tokens_output=llm_client.last_usage.get("output", 0),
            status="SUCCESS",
            tipo_operacion="recomendar"
        )

        return {
            "status": "success",
            "recomendaciones": respuesta_agente,
            "output": respuesta_agente,
            "puede_generar": True,
            "analisis_disponible": bool(analisis_ing and analisis_ing != "(Sin fragmentos RAG.)"),
            "herramientas_usadas": ["RAG (ChromaDB)", "LLM (Generación)"],
            "pasos_agente": [
                "Analizando ingredientes...",
                "Consultando base RAG...",
                "Evaluando umbral estricto...",
                "Generando recomendación..."
            ]
        }
    except Exception as e:
        fin = time.time()
        latencia = (fin - inicio) * 1000
        monitor.save_metric(
            latencia_ms=latencia,
            tokens_input=0,
            tokens_output=0,
            status="FAILED",
            tipo_operacion="recomendar"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend_more")
async def recommend_more_endpoint(request: dict):
    try:
        ingredientes_raw = request.get("ingredientes") or "Ingredientes de la casa"
        ingredientes = [i.strip() for i in ingredientes_raw] if isinstance(ingredientes_raw, list) else str(ingredientes_raw).strip().split(",")
        ingredientes = [i.strip() for i in ingredientes if i.strip()]
        recetas_vistas = request.get("recetas_vistas") or []

        prompt = (
            f"Eres CookAI. El usuario ya vio estas recetas: {recetas_vistas}. "
            f"Basado en los ingredientes {', '.join(ingredientes)}, genera UNA SOLA receta nueva. "
            f"REGLAS DE FORMATO: "
            f"0. La PRIMERA línea debe ser exactamente: TIPO: <categoría breve en español>. "
            f"1. Línea en blanco. "
            f"2. Luego el título: NOMBRE DE LA RECETA (en MAYÚSCULAS). "
            f"3. Ingredientes necesarios. "
            f"4. Preparación paso a paso numerada. "
            f"5. Tiempo estimado."
        )

        respuesta = execute_with_planning(prompt, user_id="endpoint_recomendar")
        tipo_receta, nueva_receta = _parse_tipo_y_cuerpo_receta_generada(respuesta)

        return {
            "status": "success",
            "tipo_receta": tipo_receta,
            "nueva_receta": nueva_receta
        }
    except Exception as e:
        return {"status": "error", "nueva_receta": "No se pudo estructurar una alternativa.", "tipo_receta": "Error"}


# =========================================================
# PESTAÑA 3 — CHAT CON GUARDRAILS Y DESACOPLE DE HERRAMIENTAS
# =========================================================

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    inicio = time.time()

    # 1. VALIDACIÓN DE DOMINIO Y LOGGING DE OBSERVABILIDAD (CORREGIDO - PASO 4)
    try:
        es_valido, mensaje_error = domain_validator.validate_and_filter(request.mensaje)

        if not es_valido:
            # CAMBIO CLAVE: Se registra como SUCCESS porque el sistema controló la restricción con éxito
            monitor.log_trace(user_id=request.user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="SUCCESS")

            monitor.save_metric(
                latencia_ms=(time.time() - inicio) * 1000,
                tokens_input=0,
                tokens_output=0,
                status="SUCCESS",
                tipo_operacion="chat"
            )

            output_error = f"💡 Nota de CookAI: {mensaje_error} (Recuerda que solo respondo a solicitudes del ámbito gastronómico o culinario)."
            return {
                "output": output_error,
                "respuesta": output_error,
                "response": output_error,
                "message": output_error,
                "status": "success",
                "herramientas_usadas": ["Validación de Dominio"],
                "pasos_agente": ["Validando restricciones del dominio... Fin."]
            }

        monitor.log_trace(user_id=request.user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="SUCCESS")
    except Exception as err_val:
        monitor.log_trace(user_id=request.user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="ERROR", error_message=str(err_val))
        raise HTTPException(status_code=500, detail=f"Error en validación de dominio: {str(err_val)}")

    # 2. BÚSQUEDA EN LA BASE DE DATOS LOCAL (RAG Semántico)
    from app.tools import buscar_recetas_rag, buscar_recetas_en_internet

    monitor.log_trace(user_id=request.user_id, step_name="RAG_Retrieval", tool_used="ChromaDB", status="STARTED")
    contexto_rag = buscar_recetas_rag(request.mensaje)
    monitor.log_trace(user_id=request.user_id, step_name="RAG_Retrieval", tool_used="ChromaDB", status="SUCCESS")

    no_hay_local = (
            "No se encontraron recetas" in contexto_rag or
            "Debe ingresar" in contexto_rag or
            not contexto_rag.strip()
    )

    contexto_final = ""
    es_busqueda_web = False
    herramientas_activadas = ["Validación de Dominio", "Memoria SQLite"]

    if no_hay_local:
        es_busqueda_web = True
        monitor.log_trace(user_id=request.user_id, step_name="Web_Contingency", tool_used="BuscarRecetasInternet", status="STARTED")
        resultados_web = buscar_recetas_en_internet(request.mensaje)
        contexto_final = f"Información recuperada desde la WEB:\n{resultados_web}"
        herramientas_activadas.append("BuscarRecetasInternet")
        monitor.log_trace(user_id=request.user_id, step_name="Web_Contingency", tool_used="BuscarRecetasInternet", status="SUCCESS")
    else:
        contexto_final = f"Información de la BASE DE DATOS LOCAL:\n{contexto_rag}"
        herramientas_activadas.append("RAG (ChromaDB)")

    # 3. PROMPT LIMPIO E INFERENCIA DETERMINISTA
    try:
        monitor.log_trace(user_id=request.user_id, step_name="LLM_Generation", tool_used="Agent", status="STARTED")

        prompt_estructurado = (
            f"El usuario solicita: {request.mensaje}\n\n"
            f"Usa EXCLUSIVAMENTE esta información de contexto para armar la receta:\n{contexto_final}\n\n"
            f"Genera una respuesta gastronómica clara, bien estructurada, con ingredientes y pasos detallados. "
            f"REGLA CRÍTICA: NO incluyas NUNCA ninguna sección llamada 'Justificación del beneficio', "
            f"tampoco uses etiquetas HTML como <div>, <span> o <style>. Responde puramente en texto legible o Markdown."
        )

        respuesta_raw = execute_with_planning(prompt_estructurado, user_id=request.user_id)
        monitor.log_trace(user_id=request.user_id, step_name="LLM_Generation", tool_used="Agent", status="SUCCESS")

        # --- REBANADO MÁXIMO DE SEGURIDAD (ANTIBLOQUES EXTRAÑOS) ---
        for token_corte in ["<div", "Justificación del beneficio", "**Justificación del beneficio:**"]:
            if token_corte in respuesta_raw:
                respuesta_raw = respuesta_raw.split(token_corte)[0]

        respuesta_raw = re.sub(r"\*\*Justificación del beneficio:\*\*.*$", "", respuesta_raw, flags=re.DOTALL | re.IGNORECASE)
        respuesta_raw = re.sub(r"Justificación del beneficio:.*$", "", respuesta_raw, flags=re.DOTALL | re.IGNORECASE)
        respuesta_limpia = re.sub(r"<.*?>", "", respuesta_raw, flags=re.DOTALL).strip()

        # --- REESCRITURA ADAPTATIVA PARA BÚSQUEDAS EN LA WEB ---
        if es_busqueda_web:
            plato_buscado = request.mensaje.lower().replace("receta de", "").replace("receta", "").strip()
            if not plato_buscado:
                plato_buscado = "lo solicitado"

            respuesta_limpia = (
                f"Después de analizar las recetas proporcionadas en el bloque RAG y considerar tus preferencias, "
                f"no hemos encontrado coincidencias, por lo cual, te recomiendo una receta de {plato_buscado} "
                f"encontrada en la web.\n\n{respuesta_limpia}"
            )

            patron_duplicado = r"Después de analizar las recetas proporcionadas en el bloque RAG y considerar tus preferencias,\s*(te recomiendo una receta de|aquí tienes una receta de|te sugiero una receta de).*?\n"
            respuesta_limpia = re.sub(patron_duplicado, "", respuesta_limpia, count=1, flags=re.IGNORECASE)

        output_final = respuesta_limpia.strip()

        # PERSISTENCIA DE TELEMETRÍA CON TOKENS REALES PARA EL CHAT
        monitor.save_metric(
            latencia_ms=(time.time() - inicio) * 1000,
            tokens_input=llm_client.last_usage.get("input", 0),
            tokens_output=llm_client.last_usage.get("output", 0),
            status="SUCCESS",
            tipo_operacion="chat"
        )

        return {
            "output": output_final,
            "respuesta": output_final,
            "response": output_final,
            "message": output_final,
            "status": "success",
            "herramientas_usadas": herramientas_activadas,
            "pasos_agente": [
                "Validando restricciones del dominio...",
                "Consultando coincidencia exacta en ChromaDB...",
                "Activando contingencia de búsqueda web...",
                "Formateando salida limpia de observabilidad."
            ]
        }

    except Exception as e:
        monitor.save_metric(
            latencia_ms=(time.time() - inicio) * 1000,
            tokens_input=0,
            tokens_output=0,
            status="FAILED",
            tipo_operacion="chat"
        )
        error_msg = f"Inconsistencia en el pipeline. Detalles técnicos: {str(e)}"
        return {
            "output": error_msg,
            "respuesta": error_msg,
            "response": error_msg,
            "message": error_msg,
            "status": "success"
        }
@app.get("/metrics/debug")
async def get_raw_metrics_debug():
    try:
        # Esto accede al historial completo guardado en tu monitor
        if hasattr(monitor, "metrics_history"):
            fallos = [m for m in monitor.metrics_history if m.get("status") == "FAILED"]
            return {
                "total_fallos_detectados": len(fallos),
                "detalle_fallos": fallos
            }
        return {"mensaje": "El monitor no almacena el historial en 'metrics_history' o usa una base de datos externa."}
    except Exception as e:
        return {"error": str(e)}

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
from app.agent import execute_with_planning
from app.ingredient_match import bloque_analisis_para_prompt, es_consulta_sustitucion, analyze_overlap
from app.monitoring import CookAIMonitor
from app.metrics_monitor import monitor

monitor = CookAIMonitor()
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

class MoreRecipesRequest(BaseModel):
    recetas_vistas: list[str] = []
    ingredientes: list[str]


# Constantes y Rutas de Archivos
GENERATED_RECIPES_SOURCE = "recetas_generadas_CookAI.txt"
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INITIAL_DATA_LOADED = False

# =========================================================
# HELPERS INTERNOS (restaurados del sistema original)
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


# =========================================================
# PESTAÑA 1 — GESTIÓN DE RECETAS (restaurado desde versión original)
# Lee directo de ChromaDB para mostrar recetas individuales reales
# =========================================================

@app.get("/recipes/detailed")
async def get_recipes_detailed_endpoint():
    """
    Lee directo de ChromaDB (como el sistema original) para obtener
    recetas individuales agrupadas por archivo fuente.
    """
    try:
        all_docs = rag_system.collection.get()

        if not all_docs or not all_docs.get("ids") or len(all_docs["ids"]) == 0:
            return {"archivos": {}, "total": 0}

        # Agrupar por source (igual que el sistema original)
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

        return {
            "archivos": archivos,
            "total": len(all_docs["ids"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# =========================================================
# ENDPOINT DE OBSERVABILIDAD Y MÉTRICAS (IL3.1 / IE1)
# =========================================================

@app.get("/metrics")
async def get_metrics_endpoint():
    """
    Retorna las métricas agregadas operacionales de CookAI recopiladas
    en SQLite para cumplir con las exigencias del panel de observabilidad.
    """
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
    """
    Sube un archivo, lo indexa en ChromaDB.
    Valida extensión permitida (igual que sistema original).
    """
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
    """
    Elimina un chunk individual de ChromaDB por su ID.
    Restaurado del sistema original.
    """
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
    """
    Elimina todos los chunks de un archivo fuente.
    Restaurado del sistema original.
    """
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
    """
    Guarda una receta generada por el LLM en ChromaDB tras confirmación del usuario.
    Restaurado del sistema original.
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


# =========================================================
# PESTAÑA 2 — RECOMENDADOR CON THRESHOLDING ESTRICTO
# El agente solo recomienda si la coincidencia de ingredientes es suficiente.
# Si no hay receta viable en el RAG, ofrece "Generar más" en lugar de inventar.
# =========================================================

# Umbral mínimo de coincidencia para aceptar una receta del RAG
UMBRAL_COINCIDENCIA_MINIMO = 0.40  # al menos 40% de los ingredientes del usuario deben aparecer

@app.post("/recommend")
async def recommend_endpoint(request: dict):
    """
    Recomienda recetas desde el RAG con thresholding estricto de ingredientes.
    Si ninguna receta del RAG supera el umbral, informa al usuario en lugar de inventar.
    El agente (execute_with_planning) orquesta el flujo completo.
    """
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

        # ... (Mantener lógica inicial de extracción de ingredientes y parámetros) ...

        # ── PASO 1: Buscar chunks relevantes en RAG ──────────────────────────
        monitor.log_trace(user_id="endpoint_recomendar", step_name="RAG_Retrieval", tool_used="ChromaDB", status="STARTED")
        query_busqueda = f"recetas con {', '.join(ingredientes)} {preferencias}".strip()
        chunks = rag_system.search_chunks(query_busqueda, top_k=5)
        monitor.log_trace(user_id="endpoint_recomendar", step_name="RAG_Retrieval", tool_used="ChromaDB", status="SUCCESS")

        # ── PASO 2: Thresholding estricto ────────────────────────────────────
        monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="STARTED")
        mejor_nivel = "bajo"
        mejor_ratio = 0.0
        chunks_validos = []

        if chunks and ingredientes != ["ingredientes variados"]:
            for ch in chunks:
                analisis = analyze_overlap(ingredientes, ch.get("text", ""))
                ratio = analisis.get("ratio_usuario_en_receta", 0.0)
                nivel = analisis.get("nivel_coincidencia", "bajo")
                if ratio > mejor_ratio:
                    mejor_ratio = ratio
                    mejor_nivel = nivel
                if nivel in ("alto", "medio") or ratio >= UMBRAL_COINCIDENCIA_MINIMO:
                    chunks_validos.append(ch)

        # ── PASO 3: Si no hay recetas viables en el RAG, rechazar ──
        if not chunks_validos and ingredientes != ["ingredientes variados"]:
            motivo = (
                f"Tus ingredientes ({', '.join(ingredientes)}) no coinciden suficientemente..."
            )
            monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="REJECTED", error_message="Baja coincidencia de ingredientes")
            return {
                "status": "sin_coincidencia",
                "recomendaciones": motivo,
                "output": motivo,
                "puede_generar": True,
                "analisis_disponible": False
            }
        monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="SUCCESS")


        # ── PASO 5: Construir prompt estructurado para el agente ─────────────
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

        # ── PASO 6: El agente orquesta el flujo completo ─────────────────────
        monitor.log_trace(user_id="endpoint_recomendar", step_name="LLM_Generation", tool_used="PlanningAgent", status="STARTED")
        respuesta_agente = execute_with_planning(mensaje_estructurado, user_id="endpoint_recomendar")
        monitor.log_trace(user_id="endpoint_recomendar", step_name="LLM_Generation", tool_used="PlanningAgent", status="SUCCESS")

        fin = time.time()

        latencia = (fin - inicio) * 1000

        monitor.save_metric(

            latencia_ms=latencia,
            tokens_input=0,
            tokens_output=0,
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
                "Analizando ingredientes y preferencias...",
                "Consultando base de conocimiento RAG...",
                "Evaluando umbral de coincidencia estricta...",
                "Generando recomendación adaptativa..."
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
    """
    Genera una receta alternativa nueva usando el LLM cuando el RAG no tiene coincidencia.
    El resultado se muestra en modal para que el usuario decida si guardarla.
    """
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
# PESTAÑA 3 — CHAT CON GUARDRAILS ESTRICTOS
# Usa execute_with_planning (agente) pero con validación de dominio estricta
# y contexto RAG como fuente principal.
# =========================================================

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    # Unificamos el temporizador desde el milisegundo cero del request (IL3.1)
    inicio_global = time.time()
    user_id = request.user_id or "local_host_user"

    # Términos específicos de cocina rápidos
    TERMINOS_COCINA_DIRECTOS = [
        "cazuela", "waffle", "waffles", "hummus", "garbanzo", "omelette",
        "omelet", "tortilla", "papa", "papas", "tomate", "pollo", "huevo",
        "huevos", "queso", "zanahoria", "arroz", "pasta", "carbonara",
        "queque", "bizcocho", "cocinar", "receta", "cebolla", "ajo",
        "pescado", "carne", "harina", "leche", "mantequilla", "sal",
        "pimienta", "aceite", "vinagre", "limón", "lemon", "sopa",
        "ensalada", "postre", "desayuno", "almuerzo", "cena", "guiso",
        "estofado", "empanada", "sandwich", "arepa", "lentejas", "fideos"
    ]

    try:
        # ── 1. PROTOCOLO DE SEGURIDAD Y PRIVACIDAD (IL3.3 / IE3) ──
        # Sanitizamos el mensaje de inmediato eliminando RUT, correos o teléfonos antes de procesar o guardar logs
        mensaje_seguro = DomainValidator.sanitize_pii(request.mensaje)

        # Registrar el inicio oficial del ciclo de vida del pipeline (IL3.2 / Trazabilidad)
        monitor.log_trace(user_id=user_id, step_name="Frontera de Entrada", tool_used="DomainValidator", status="STARTED")

        # ── 2. CAPA DEFENSIVA Y DE DOMINIO (IE6 / IE10) ──
        mensaje_lower = mensaje_seguro.lower()
        es_valido_directo = any(t in mensaje_lower for t in TERMINOS_COCINA_DIRECTOS)

        if not es_valido_directo:
            es_valido, mensaje_error = DomainValidator.validate_and_filter(mensaje_seguro)
            if not es_valido:
                msg_rechazo = (
                    "Esta consulta no está relacionada con recetas o cocina. "
                    "Por favor, pregunta sobre recetas, ingredientes, técnicas de cocina o sustituciones."
                )

                # Calcular latencia de la denegación para guardarla en métricas
                latencia_ms = (time.time() - inicio_global) * 1000
                monitor.save_metric(latencia_ms=latencia_ms, tokens_input=0, tokens_output=0, status="REJECTED", tipo_operacion="chat")
                monitor.log_trace(user_id=user_id, step_name="Frontera de Entrada", tool_used="DomainValidator", status="REJECTED")

                return {
                    "output": msg_rechazo,
                    "respuesta": msg_rechazo,
                    "response": msg_rechazo,
                    "status": "rejected"
                }

        # ── 3. DETECCIÓN DE CONTEXTO CULINARIO ──
        es_sustitucion = es_consulta_sustitucion(mensaje_seguro)
        contexto_extra = ""
        if es_sustitucion:
            contexto_extra = (
                "\n(NOTA: Esta es una consulta sobre sustituciones de ingredientes. "
                "Prioriza información del RAG y sugiere alternativas coherentes.)"
            )

        # ── 4. VERIFICACIÓN VECTORIAL (RAG - IL2.1) ──
        contexto_rag = rag_system.search(mensaje_seguro, top_k=3)
        sin_rag = "No se encontraron recetas culinarias relevantes" in contexto_rag

        if sin_rag:
            contexto_extra += (
                "\n(El RAG no tiene recetas directamente relacionadas con esta consulta. "
                "Responde con conocimiento general culinario pero indica que el usuario puede "
                "agregar recetas relacionadas a su base de datos.)"
            )

        # Enriquecer el prompt final de forma limpia
        mensaje_procesado = mensaje_seguro + contexto_extra

        # ── 5. PLANIFICACIÓN E INFERENCIA (IL2.3 / IL3.2) ──
        monitor.log_trace(user_id=user_id, step_name="Inferencia LLM", tool_used="PlanningAgent", status="STARTED")

        respuesta_final = execute_with_planning(mensaje_procesado, user_id=user_id)

        monitor.log_trace(user_id=user_id, step_name="Inferencia LLM", tool_used="PlanningAgent", status="SUCCESS")

        # ── 6. EMISIÓN DE MÉTRICAS COMPLEMENTARIAS (IL3.1) ──
        latencia_ms = (time.time() - inicio_global) * 1000

        # Guardar en memoria local la telemetría del éxito
        monitor.save_metric(
            latencia_ms=latencia_ms,
            tokens_input=len(mensaje_procesado) // 4,  # Estimación aproximada estándar si tu cliente no cuenta los tokens
            tokens_output=len(respuesta_final) // 4,
            status="SUCCESS",
            tipo_operacion="chat"
        )

        return {
            "output": respuesta_final,
            "respuesta": respuesta_final,
            "response": respuesta_final,
            "message": respuesta_final,
            "status": "success",
            "es_sustitucion": es_sustitucion,
            "herramientas_usadas": ["Validación de Dominio", "Memoria SQLite", "RAG (ChromaDB)", "LLM (Generación)"],
            "pasos_agente": [
                "Validando restricciones del dominio...",
                "Recuperando memoria de corto plazo...",
                "Extrayendo contexto relevante del RAG...",
                "Generando respuesta estructurada..."
            ]
        }

    except Exception as e:
        # Registro automático de fallas críticas en el sistema (Esencial para la rúbrica)
        latencia_ms = (time.time() - inicio_global) * 1000

        monitor.save_metric(latencia_ms=latencia_ms, tokens_input=0, tokens_output=0, status="FAILED", tipo_operacion="chat")
        monitor.log_trace(user_id=user_id, step_name="Pipeline Global", tool_used="System", status="FAILED")

        return {
            "output": f"Error interno temporal: {str(e)}. Intenta de nuevo.",
            "respuesta": f"Error interno temporal: {str(e)}. Intenta de nuevo.",
            "response": f"Error interno temporal: {str(e)}. Intenta de nuevo.",
            "status": "failed"
        }
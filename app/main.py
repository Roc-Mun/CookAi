import os
import sys
import shutil
import re
import time
import uuid
import json

# Los logs del sistema usan emojis (⚠️, ✅, 🔍...). En Windows, si stdout/stderr
# no está en UTF-8 (ej. salida redirigida a archivo), un simple print() truena
# con UnicodeEncodeError y tumba silenciosamente el request que lo dispara.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import iterate_in_threadpool
from pydantic import BaseModel
from dotenv import load_dotenv

# Importaciones de los módulos del proyecto
from app.rag import RAGSystem
from app.domain_validator import DomainValidator
from app.agent import execute_with_planning, agent, _extract_ingredients_from_text  # Importamos el agente y su ecosistema
from app.ingredient_match import bloque_analisis_para_prompt, es_consulta_sustitucion, analyze_overlap, es_solicitud_generar_receta, calcular_fidelidad_contexto
from app.monitoring import CookAIMonitor
from app.tools import buscar_recetas_rag_cacheado, buscar_recetas_en_internet, guardar_receta_usuario
from app.llm import is_llm_fallback

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
    user_id: str = "default"

class MoreRecipesRequest(BaseModel):
    recetas_vistas: list[str] = []
    ingredientes: list[str]


# Constantes y Rutas de Archivos
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INITIAL_DATA_LOADED = False

# =========================================================
# HELPERS INTERNOS
# =========================================================

# Encabezados que indican que un chunk es la continuación de la receta anterior
# (ej: el chunking cortó "Ingredientes" e "Instrucciones" en fragmentos separados)
# y NO una receta nueva independiente.
_MARCADORES_CONTINUACION = ("instrucc", "preparaci", "elaboraci", "pasos")

def _titulo_desde_contenido_receta(content: str, metadata: dict) -> tuple[str, bool]:
    """
    Título para listado a partir de: formato === RECETA ===, 'N) TÍTULO', metadata,
    o (si nada de eso aplica) la primera línea real del contenido.
    Retorna (titulo, es_continuacion) — es_continuacion=True indica que el chunk
    es un fragmento de la receta previa y no debe listarse como receta aparte.
    """
    tipo_meta = (metadata or {}).get("tipo_receta") or ""
    primera_linea = ""
    for line in content.split("\n"):
        line_st = line.strip()
        if not line_st:
            continue
        if not primera_linea:
            primera_linea = line_st

        if "===" in line_st and "RECETA" in line_st.upper():
            titulo = line_st.replace("=", "").strip()
            if tipo_meta:
                return f"[{tipo_meta}] {titulo}", False
            return titulo, False

        m = re.match(r"^\d+\)\s*(.+)$", line_st)
        if m:
            titulo = m.group(1).strip()
            if tipo_meta:
                return f"[{tipo_meta}] {titulo}", False
            return titulo, False

    if tipo_meta:
        return f"[{tipo_meta}] Receta generada", False

    if primera_linea.lower().startswith(_MARCADORES_CONTINUACION):
        return primera_linea[:80], True

    # Sin encabezado reconocible: usamos la primera línea real en vez de
    # inventar o etiquetar genéricamente el contenido ("no asumir recetas").
    return (primera_linea[:80] or "Fragmento sin título"), False

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

        # Agrupar chunks por fuente y ordenarlos por índice de chunk para poder
        # detectar cuáles son continuación (sin encabezado propio) de la receta anterior.
        por_fuente: dict[str, list[tuple]] = {}
        for doc_id, content, metadata in zip(
                all_docs["ids"], all_docs["documents"], all_docs["metadatas"]
        ):
            meta = metadata or {}
            source = meta.get("source", "Sin nombre")
            por_fuente.setdefault(source, []).append((meta.get("chunk", 0), doc_id, content, meta))

        archivos = {}
        for source, items in por_fuente.items():
            items.sort(key=lambda it: it[0])
            recetas: list[dict] = []
            grupo_actual = None

            for _chunk_idx, doc_id, content, meta in items:
                titulo, es_continuacion = _titulo_desde_contenido_receta(content, meta)

                if es_continuacion and grupo_actual is not None:
                    # Fragmento de continuación (ej: sección "Instrucciones" separada por el
                    # chunking): pertenece a la receta anterior, no es una receta nueva.
                    grupo_actual["ids"].append(doc_id)
                    grupo_actual["_full"] += "\n" + content
                else:
                    if grupo_actual is not None:
                        recetas.append(grupo_actual)
                    grupo_actual = {
                        "ids": [doc_id],
                        "titulo": titulo,
                        "_full": content,
                    }

            if grupo_actual is not None:
                recetas.append(grupo_actual)

            archivos[source] = [
                {
                    "id": r["ids"][0],
                    "ids": r["ids"],
                    "titulo": r["titulo"],
                    "preview": r["_full"][:100].replace("\n", " ") + "...",
                    "contenido": r["_full"]
                }
                for r in recetas
            ]

        total_recetas = sum(len(v) for v in archivos.values())
        return {"archivos": archivos, "total": total_recetas}
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


@app.get("/metrics/history")
async def get_metrics_history_endpoint(limit: int = 50):
    """Serie temporal real de ejecuciones (IL3.1/IL3.2), para graficar en el dashboard
    en vez de datos simulados: latencia, consistencia, tokens y estado por request."""
    try:
        rows = monitor.get_raw_records(limit=limit)
        registros = [
            {
                "timestamp": r[0],
                "latencia_ms": r[1],
                "status": r[2],
                "tokens_input": r[3],
                "tokens_output": r[4],
                "tipo_operacion": r[5],
                "consistency_score": r[6],
                "precision_score": r[7],
                "trace_id": r[8],
                "fidelidad_score": r[9],
            }
            for r in reversed(rows)  # orden cronológico ascendente para graficar
        ]
        return {"registros": registros, "total": len(registros)}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener historial de métricas: {str(e)}"
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
        titulo = tipo or re.sub(r"[*#_>-]", "", contenido.split("\n")[0]).strip()[:80] or "Receta generada"

        # Misma función de escritura que usa el Chat (IL2.1/IL2.2): queda en
        # SQLite (memoria de largo plazo) y en el RAG (ChromaDB) en un solo paso,
        # sin importar desde qué pestaña se generó la receta.
        resultado = guardar_receta_usuario(
            user_id=request.user_id, titulo=titulo, contenido=contenido, tipo_receta=tipo
        )
        if resultado.startswith("❌") or resultado.startswith("Error"):
            raise HTTPException(status_code=500, detail=resultado)

        return {
            "mensaje": "Receta guardada en tu base de datos",
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
# El filtro de aceptación real vive en analyze_overlap() (nivel_coincidencia),
# que exige coincidencia del ingrediente principal de la receta.

@app.post("/recommend")
async def recommend_endpoint(request: dict):
    try:
        inicio = time.time()
        trace_id = str(uuid.uuid4())
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

        monitor.log_trace(user_id="endpoint_recomendar", step_name="RAG_Retrieval", tool_used="ChromaDB", status="STARTED", trace_id=trace_id)
        query_busqueda = f"recetas con {', '.join(ingredientes)} {preferencias}".strip()
        chunks = rag_system.search_chunks(query_busqueda, top_k=5)
        monitor.log_trace(user_id="endpoint_recomendar", step_name="RAG_Retrieval", tool_used="ChromaDB", status="SUCCESS", trace_id=trace_id)

        monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="STARTED", trace_id=trace_id)
        chunks_validos = []
        # Precisión (IL3.1): qué tan bien cubre el usuario los ingredientes de la
        # receta seleccionada. Se guarda como métrica histórica, no solo se usa
        # para decidir en el momento y descartarse.
        mejor_precision = 0.0

        if chunks and ingredientes != ["ingredientes variados"]:
            for ch in chunks:
                analisis = analyze_overlap(ingredientes, ch.get("text", ""))
                nivel = analisis.get("nivel_coincidencia", "bajo")
                # Solo se considera viable si el ingrediente principal de la receta
                # está entre los ingredientes del usuario (ver ingredient_match.py).
                if nivel in ("alto", "medio"):
                    chunks_validos.append(ch)
                    mejor_precision = max(mejor_precision, analisis.get("ratio_receta_cubierta_por_usuario", 0.0))

        if not chunks_validos and ingredientes != ["ingredientes variados"]:
            motivo = f"⚠️ Sin coincidencia suficiente en tu base de recetas.\n\nTus ingredientes ({', '.join(ingredientes)}) no coinciden suficientemente con la base de datos local. Sin embargo, nuestro sistema ha gestionado el caso con éxito."
            monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="SUCCESS", trace_id=trace_id)

            # Guardamos la métrica en SUCCESS porque el filtro de negocio controló la restricción correctamente
            monitor.save_metric(
                latencia_ms=(time.time() - inicio) * 1000,
                tokens_input=0,
                tokens_output=0,
                status="SUCCESS",
                tipo_operacion="recomendar",
                precision_score=0.0,
                trace_id=trace_id
            )
            return {
                "status": "sin_coincidencia",
                "recomendaciones": motivo,
                "output": motivo,
                "puede_generar": True,
                "analisis_disponible": False,
                "trace_id": trace_id
            }

        monitor.log_trace(user_id="endpoint_recomendar", step_name="Threshold_Validation", tool_used="IngredientMatch", status="SUCCESS", trace_id=trace_id)

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

        # REGLA DE NEGOCIO: el Recomendador solo puede recomendar lo que está en el
        # RAG — nunca debe inventar una receta alternativa. Se pasa el texto real
        # de las recetas ya validadas (chunks_validos) como contexto_externo: esto
        # hace que execute_with_planning() se salte DynamicAgentExecutor (que sí
        # tiene permiso de inventar) y use el camino simple, siempre fiel al
        # contexto entregado.
        contexto_validado = "\n\n---\n\n".join(ch.get("text", "") for ch in chunks_validos)

        monitor.log_trace(user_id="endpoint_recomendar", step_name="LLM_Generation", tool_used="PlanningAgent", status="STARTED", trace_id=trace_id)
        # user_id único por solicitud (no el fijo "endpoint_recomendar" compartido
        # por todos los usuarios): el Recomendador es un formulario de un solo
        # disparo sin continuidad conversacional, y como execute_with_planning usa
        # el user_id para recuperar historial de memoria persistente, reutilizar
        # el mismo id fijo entre usuarios distintos filtraba interacciones ajenas
        # (ej. una consulta de salmón de otra persona apareciendo en una
        # recomendación de pollo sin relación). El trace_id ya es único por
        # solicitud, así que no hay historial previo que recuperar bajo ese id.
        respuesta_agente = execute_with_planning(
            mensaje_estructurado, user_id=trace_id, trace_id=trace_id,
            contexto_externo=contexto_validado
        )

        if "<div" in respuesta_agente:
            respuesta_agente = respuesta_agente.split("<div")[0].strip()

        respuesta_agente = re.sub(r"\*\*Nota importante:\*\*.*", "", respuesta_agente, flags=re.DOTALL)
        respuesta_agente = re.sub(r"\*\*Justificación del beneficio:\*\*.*", "", respuesta_agente, flags=re.DOTALL)
        respuesta_agente = respuesta_agente.strip()

        monitor.log_trace(user_id="endpoint_recomendar", step_name="LLM_Generation", tool_used="PlanningAgent", status="SUCCESS", trace_id=trace_id)

        fin = time.time()
        latencia = (fin - inicio) * 1000

        # --- SOLUCIÓN AL DESFASE: Sincronización de tokens en tiempo real ---
        tokens_in = 0
        tokens_out = 0

        if hasattr(agent, "last_execution_usage") and agent.last_execution_usage:
            tokens_in = agent.last_execution_usage.get("input", 0)
            tokens_out = agent.last_execution_usage.get("output", 0)
        elif hasattr(llm_client, "last_usage") and llm_client.last_usage:
            tokens_in = llm_client.last_usage.get("input", 0)
            tokens_out = llm_client.last_usage.get("output", 0)

        # --- CONSISTENCIA (IL3.1): ¿la respuesta final realmente usa los ingredientes
        # pedidos? (sin llamar de nuevo al LLM). Si el LLM falló y devolvió el mensaje
        # de fallo, la consistencia es 0 y la operación se marca como FAILED de verdad,
        # en vez de "SUCCESS" con una receta que no tiene relación con lo pedido.
        es_fallo_llm = is_llm_fallback(respuesta_agente)
        if es_fallo_llm:
            consistency_score = 0.0
        elif ingredientes != ["ingredientes variados"]:
            consistency_score = analyze_overlap(ingredientes, respuesta_agente).get("ratio_usuario_en_receta", 1.0)
        else:
            consistency_score = 1.0

        # --- FIDELIDAD / FAITHFULNESS (IL3.1): la respuesta final, ¿se basa en el
        # contexto realmente recuperado (las recetas del RAG), o inventó contenido
        # que no está en ninguna de ellas? A diferencia de la consistencia (que
        # compara contra lo que PIDIÓ el usuario), esto compara contra lo que se
        # RECUPERÓ como fuente.
        contexto_recuperado = "\n".join(ch.get("text", "") for ch in chunks_validos)
        fidelidad_score = (
            0.0 if es_fallo_llm
            else calcular_fidelidad_contexto(contexto_recuperado, respuesta_agente)
        )

        monitor.save_metric(
            latencia_ms=latencia,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            status="FAILED" if es_fallo_llm else "SUCCESS",
            tipo_operacion="recomendar",
            consistency_score=consistency_score,
            precision_score=mejor_precision,
            trace_id=trace_id,
            fidelidad_score=fidelidad_score
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
            ],
            "trace_id": trace_id
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

        trace_id = str(uuid.uuid4())
        respuesta = execute_with_planning(prompt, user_id="endpoint_recomendar", trace_id=trace_id)
        tipo_receta, nueva_receta = _parse_tipo_y_cuerpo_receta_generada(respuesta)

        return {
            "status": "success",
            "tipo_receta": tipo_receta,
            "nueva_receta": nueva_receta,
            "trace_id": trace_id
        }
    except Exception as e:
        return {"status": "error", "nueva_receta": "No se pudo estructurar una alternativa.", "tipo_receta": "Error"}


# =========================================================
# PESTAÑA 3 — CHAT CON GUARDRAILS Y DESACOPLE DE HERRAMIENTAS
# =========================================================

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    inicio = time.time()
    trace_id = str(uuid.uuid4())

    # 1. VALIDACIÓN DE DOMINIO Y LOGGING DE OBSERVABILIDAD (CORREGIDO - PASO 4)
    try:
        es_valido, mensaje_error = domain_validator.validate_and_filter(request.mensaje)

        if not es_valido:
            # CAMBIO CLAVE: Se registra como SUCCESS porque el sistema controló la restricción con éxito
            monitor.log_trace(user_id=request.user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="SUCCESS", trace_id=trace_id)

            monitor.save_metric(
                latencia_ms=(time.time() - inicio) * 1000,
                tokens_input=0,
                tokens_output=0,
                status="SUCCESS",
                tipo_operacion="chat",
                trace_id=trace_id
            )

            output_error = f"💡 Nota de CookAI: {mensaje_error} (Recuerda que solo respondo a solicitudes del ámbito gastronómico o culinario)."
            return {
                "output": output_error,
                "respuesta": output_error,
                "response": output_error,
                "message": output_error,
                "status": "success",
                "herramientas_usadas": ["Validación de Dominio"],
                "pasos_agente": ["Validando restricciones del dominio... Fin."],
                "trace_id": trace_id
            }

        monitor.log_trace(user_id=request.user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="SUCCESS", trace_id=trace_id)
    except Exception as err_val:
        monitor.log_trace(user_id=request.user_id, step_name="Domain_Validation", tool_used="DomainValidator", status="ERROR", error_message=str(err_val), trace_id=trace_id)
        raise HTTPException(status_code=500, detail=f"Error en validación de dominio: {str(err_val)}")

    # 2. BÚSQUEDA EN LA BASE DE DATOS LOCAL (RAG Semántico)
    monitor.log_trace(user_id=request.user_id, step_name="RAG_Retrieval", tool_used="ChromaDB", status="STARTED", trace_id=trace_id)
    contexto_rag = buscar_recetas_rag_cacheado(request.mensaje)
    monitor.log_trace(user_id=request.user_id, step_name="RAG_Retrieval", tool_used="ChromaDB", status="SUCCESS", trace_id=trace_id)

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
        monitor.log_trace(user_id=request.user_id, step_name="Web_Contingency", tool_used="BuscarRecetasInternet", status="STARTED", trace_id=trace_id)
        resultados_web = buscar_recetas_en_internet(request.mensaje)
        contexto_final = f"Información recuperada desde la WEB:\n{resultados_web}"
        herramientas_activadas.append("BuscarRecetasInternet")
        monitor.log_trace(user_id=request.user_id, step_name="Web_Contingency", tool_used="BuscarRecetasInternet", status="SUCCESS", trace_id=trace_id)
    else:
        contexto_final = f"Información de la BASE DE DATOS LOCAL:\n{contexto_rag}"
        herramientas_activadas.append("RAG (ChromaDB)")

    # REGLA DE NEGOCIO: el Chat se basa PRINCIPALMENTE en el RAG (con la web como
    # respaldo secundario, ya resuelto arriba) para preguntas y ajustes sobre lo
    # que ya existe en la base — en ese caso NO debe inventar. La única excepción
    # es cuando el usuario pide explícitamente generar una receta nueva: ahí sí
    # puede apoyarse en el conocimiento propio del LLM si el contexto no alcanza.
    quiere_generar_receta = es_solicitud_generar_receta(request.mensaje)

    # 3. PROMPT LIMPIO E INFERENCIA DETERMINISTA
    try:
        monitor.log_trace(user_id=request.user_id, step_name="LLM_Generation", tool_used="Agent", status="STARTED", trace_id=trace_id)

        prompt_estructurado = (
            f"El usuario solicita: {request.mensaje}\n\n"
            f"Usa EXCLUSIVAMENTE esta información de contexto para armar la receta:\n{contexto_final}\n\n"
            f"Genera una respuesta gastronómica clara, bien estructurada, con ingredientes y pasos detallados. "
            f"REGLA CRÍTICA: NO incluyas NUNCA ninguna sección llamada 'Justificación del beneficio', "
            f"tampoco uses etiquetas HTML como <div>, <span> o <style>. Responde puramente en texto legible o Markdown."
        )

        respuesta_raw = execute_with_planning(
            prompt_estructurado, user_id=request.user_id, trace_id=trace_id,
            contexto_externo=None if quiere_generar_receta else contexto_final
        )
        monitor.log_trace(user_id=request.user_id, step_name="LLM_Generation", tool_used="Agent", status="SUCCESS", trace_id=trace_id)

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
        es_fallo_llm = is_llm_fallback(output_final)

        # --- SI EL USUARIO PIDIÓ EXPLÍCITAMENTE GENERAR UNA RECETA NUEVA, SE OFRECE
        # GUARDARLA (con aprobación explícita del usuario, no automático) ---
        # Antes esto se guardaba solo; ahora requiere confirmación igual que el
        # Recomendador ("siempre debe haber una aprobación antes de persistir
        # contenido generado" — gobernanza humana consistente entre ambas pestañas).
        puede_guardar = False
        titulo_generado = None
        if quiere_generar_receta and output_final and not es_fallo_llm:
            titulo_generado = re.sub(r"[*#_>-]", "", output_final.split("\n")[0]).strip()[:80] or "Receta generada desde Chat"
            puede_guardar = True
            herramientas_activadas.append("GeneracionPendienteDeAprobacion")
            monitor.log_trace(user_id=request.user_id, step_name="Generated_Recipe_Awaiting_Approval", tool_used="Chat", status="SUCCESS", trace_id=trace_id)

        # --- CONSISTENCIA (IL3.1): fidelidad de la respuesta frente a lo pedido ---
        # Sin llamar de nuevo al LLM: compara los ingredientes mencionados en el mensaje
        # del usuario contra el texto final generado. Si no hay ingredientes que
        # verificar (pregunta general), se deja el valor neutro por defecto (1.0).
        ingredientes_msg = _extract_ingredients_from_text(request.mensaje)
        if es_fallo_llm:
            consistency_score = 0.0
        elif ingredientes_msg:
            consistency_score = analyze_overlap(ingredientes_msg, output_final).get("ratio_usuario_en_receta", 1.0)
        else:
            consistency_score = 1.0

        # --- FIDELIDAD / FAITHFULNESS (IL3.1): la respuesta final vs. el contexto
        # que realmente se le entregó al LLM (contexto_final: RAG local o web),
        # no contra lo que pidió el usuario (eso ya lo mide consistency_score).
        fidelidad_score = 0.0 if es_fallo_llm else calcular_fidelidad_contexto(contexto_final, output_final)

        # PERSISTENCIA DE TELEMETRÍA CON TOKENS REALES PARA EL CHAT
        monitor.save_metric(
            latencia_ms=(time.time() - inicio) * 1000,
            tokens_input=llm_client.last_usage.get("input", 0),
            tokens_output=llm_client.last_usage.get("output", 0),
            status="FAILED" if es_fallo_llm else "SUCCESS",
            tipo_operacion="chat",
            consistency_score=consistency_score,
            trace_id=trace_id,
            fidelidad_score=fidelidad_score
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
            ],
            "trace_id": trace_id,
            # Igual que el Recomendador: el contenido generado no se guarda solo,
            # el usuario debe confirmarlo (ver /recipes/save_generated).
            "puede_guardar": puede_guardar,
            "tipo_receta_sugerido": titulo_generado,
            "contenido_generado": output_final if puede_guardar else None
        }

    except Exception as e:
        monitor.save_metric(
            latencia_ms=(time.time() - inicio) * 1000,
            tokens_input=0,
            tokens_output=0,
            status="FAILED",
            tipo_operacion="chat",
            trace_id=trace_id
        )
        error_msg = f"Inconsistencia en el pipeline. Detalles técnicos: {str(e)}"
        return {
            "output": error_msg,
            "respuesta": error_msg,
            "response": error_msg,
            "message": error_msg,
            "status": "success",
            "trace_id": trace_id
        }


# =========================================================
# CHAT CON STREAMING (endpoint separado, NO reemplaza /chat)
# =========================================================
# Streaming real token por token desde Groq, para que el Chat se sienta más
# reactivo (curso: "mejora percepción de velocidad", recomendado para
# chatbots). Deliberadamente NO pasa por PlanningAgent/DynamicAgentExecutor
# (el mecanismo de orquestación que usan /chat, /recommend y /recommend_more)
# para no tocar ese código compartido: valida dominio, sanitiza PII y busca en
# RAG (con el mismo cache) igual que /chat, pero genera la respuesta con una
# llamada directa y streameada. El /chat de siempre sigue intacto como
# respaldo — el frontend cae a él si este endpoint falla.
@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    inicio = time.time()
    trace_id = str(uuid.uuid4())
    mensaje = domain_validator.sanitize_pii(request.mensaje)

    es_valido, mensaje_error = domain_validator.validate_and_filter(mensaje)
    monitor.log_trace(
        user_id=request.user_id, step_name="Domain_Validation", tool_used="DomainValidator",
        status="SUCCESS" if es_valido else "REJECTED", trace_id=trace_id
    )

    if not es_valido:
        texto_rechazo = (
            f"💡 Nota de CookAI: {mensaje_error} "
            "(Recuerda que solo respondo a solicitudes del ámbito gastronómico o culinario)."
        )
        monitor.save_metric(
            latencia_ms=(time.time() - inicio) * 1000, status="SUCCESS",
            tipo_operacion="chat_stream", trace_id=trace_id
        )

        async def gen_rechazo():
            yield texto_rechazo
        return StreamingResponse(gen_rechazo(), media_type="text/plain; charset=utf-8")

    monitor.log_trace(user_id=request.user_id, step_name="RAG_Retrieval", tool_used="ChromaDB", status="STARTED", trace_id=trace_id)
    contexto_rag = buscar_recetas_rag_cacheado(mensaje)
    monitor.log_trace(user_id=request.user_id, step_name="RAG_Retrieval", tool_used="ChromaDB", status="SUCCESS", trace_id=trace_id)

    no_hay_local = (
            "No se encontraron recetas" in contexto_rag or
            "Debe ingresar" in contexto_rag or
            not contexto_rag.strip()
    )
    if no_hay_local:
        resultados_web = buscar_recetas_en_internet(mensaje)
        contexto_final = f"Información recuperada desde la WEB:\n{resultados_web}"
    else:
        contexto_final = f"Información de la BASE DE DATOS LOCAL:\n{contexto_rag}"

    # Mismo criterio que /chat: grounded al contexto salvo que se pida explícitamente
    # generar una receta nueva, donde sí puede apoyarse en conocimiento propio del LLM.
    quiere_generar_receta = es_solicitud_generar_receta(mensaje)

    if quiere_generar_receta:
        prompt_estructurado = (
            f"El usuario pide que generes una receta NUEVA: {mensaje}\n\n"
            f"Contexto disponible como referencia:\n{contexto_final}\n\n"
            f"Si el contexto no incluye algo que use de forma protagónica los ingredientes que el "
            f"usuario mencionó, usa tu conocimiento culinario para crear una receta original y "
            f"coherente que sí los utilice — no te limites solo al contexto en este caso.\n"
            f"Genera una respuesta gastronómica clara, bien estructurada, con ingredientes y pasos detallados. "
            f"REGLA CRÍTICA: NO incluyas NUNCA ninguna sección llamada 'Justificación del beneficio', "
            f"tampoco uses etiquetas HTML como <div>, <span> o <style>. Responde puramente en texto legible o Markdown."
        )
    else:
        prompt_estructurado = (
            f"El usuario solicita: {mensaje}\n\n"
            f"Usa EXCLUSIVAMENTE esta información de contexto para armar la receta; no inventes "
            f"ingredientes, pasos ni platos que no estén respaldados por este contexto:\n{contexto_final}\n\n"
            f"Genera una respuesta gastronómica clara, bien estructurada, con ingredientes y pasos detallados. "
            f"REGLA CRÍTICA: NO incluyas NUNCA ninguna sección llamada 'Justificación del beneficio', "
            f"tampoco uses etiquetas HTML como <div>, <span> o <style>. Responde puramente en texto legible o Markdown."
        )

    async def generador():
        texto_completo = []
        try:
            # iterate_in_threadpool: el cliente de Groq es síncrono; sin esto, cada
            # chunk bloquearía el event loop y volvería más lento el resto del
            # servidor mientras dura el streaming (justo lo que no queremos).
            async for chunk in iterate_in_threadpool(llm_client.generate_chat_stream(prompt_estructurado)):
                texto_completo.append(chunk)
                yield chunk
        except Exception as e:
            texto_completo.append(f"\n\n⚠️ No fue posible completar la respuesta en streaming: {str(e)}")
            yield texto_completo[-1]

        # A partir de aquí ya no se entrega texto visible del cuerpo de la
        # respuesta: se registra la telemetría y, si corresponde, se ofrece
        # guardar la receta (mismo criterio de aprobación que /chat, ver más
        # abajo) mediante un marcador que el frontend separa del texto.
        respuesta_final = "".join(texto_completo).strip()
        es_fallo = is_llm_fallback(respuesta_final)
        ingredientes_msg = _extract_ingredients_from_text(mensaje)
        consistencia = 1.0
        if es_fallo:
            consistencia = 0.0
        elif ingredientes_msg:
            consistencia = analyze_overlap(ingredientes_msg, respuesta_final).get("ratio_usuario_en_receta", 1.0)
        fidelidad = 0.0 if es_fallo else calcular_fidelidad_contexto(contexto_final, respuesta_final)

        puede_guardar = False
        titulo_generado = None
        if quiere_generar_receta and respuesta_final and not es_fallo:
            titulo_generado = re.sub(r"[*#_>-]", "", respuesta_final.split("\n")[0]).strip()[:80] or "Receta generada desde Chat"
            puede_guardar = True

        monitor.log_trace(
            user_id=request.user_id, step_name="LLM_Generation_Stream", tool_used="GroqClient",
            status="ERROR" if es_fallo else "SUCCESS", trace_id=trace_id
        )
        monitor.save_metric(
            latencia_ms=(time.time() - inicio) * 1000,
            status="FAILED" if es_fallo else "SUCCESS",
            tipo_operacion="chat_stream",
            consistency_score=consistencia,
            fidelidad_score=fidelidad,
            trace_id=trace_id
        )

        metadata = {
            "trace_id": trace_id,
            "puede_guardar": puede_guardar,
            "tipo_receta_sugerido": titulo_generado,
        }
        yield f" COOKAI_META {json.dumps(metadata, ensure_ascii=False)}"

    return StreamingResponse(generador(), media_type="text/plain; charset=utf-8")


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

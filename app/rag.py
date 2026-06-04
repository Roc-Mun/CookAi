"""
CookAI - Sistema RAG (Retrieval-Augmented Generation) Centralizado
Cumple estrictamente con el Indicador de Logro IL2.1 (Construcción de agentes 
funcionales que integran herramientas de consulta mediante bases vectoriales).
"""

import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import PyPDF2
import uuid
from typing import Optional


class RAGSystem:
    """
    Gestiona el almacenamiento, fragmentación (chunking) y búsqueda semántica 
    de recetas de cocina dentro de la base de datos vectorial ChromaDB.
    """

    def __init__(self, persist_dir: str = "data/chroma_db"):
        """
        Inicializa la base de datos vectorial y configura el espacio métrico.
        
        Args:
            persist_dir: Ruta donde se guardará físicamente la base sqlite/vectorial.
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.parent.mkdir(parents=True, exist_ok=True)

        # Crear cliente persistente oficial
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

        # IL2.1 - Configuración explícita de función de embeddings para evitar fallos de red remota
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()

        # Crear o acceder a la colección configurando la distancia coseno para recetas
        self.collection = self.client.get_or_create_collection(
            name="recetas_cookai",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embedding_function
        )

    def add_documents(self, content: str, source: str):
        """
        Herramienta de Escritura/Ingesta: Divide un texto masivo en fragmentos semánticos
        y los indexa en la base vectorial con identificadores inmunes a colisiones.
        """
        text_clean = (content or "").strip()
        if not text_clean:
            print(f"⚠️ Contenido vacío omitido para la fuente: {source}")
            return

        # Fragmentación controlada del texto
        chunks = self._split_text(text_clean)

        for i, chunk in enumerate(chunks):
            # IL2.1 - Evitamos usar contadores locales en RAM. Generamos IDs hash únicos basados en la fuente y el chunk
            unique_id = f"doc_{hash(source + str(i))}_{uuid.uuid4().hex[:8]}"

            self.collection.add(
                documents=[chunk],
                metadatas=[{
                    "source": source,
                    "chunk": i,
                    "type": "receta_base"
                }],
                ids=[unique_id]
            )

        print(f"✅ {len(chunks)} chunks de '{source}' añadidos e indexados en ChromaDB.")

    def add_single_recipe_document(
            self, content: str, source: str, extra_metadata: Optional[dict] = None
    ) -> str:
        """
        Añade una receta generada completa como un único bloque semántico,
        permitiendo la retroalimentación continua del sistema.
        """
        text = (content or "").strip()
        if not text:
            raise ValueError("El contenido de la receta está vacío.")

        doc_id = f"doc_gen_{uuid.uuid4().hex}"
        meta = {"source": source, "chunk": 0, "type": "receta_generada"}

        if extra_metadata:
            for k, v in extra_metadata.items():
                if v is not None and v != "":
                    meta[str(k)] = str(v)

        self.collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id],
        )
        print(f"✅ Receta generada guardada exitosamente en el RAG ({doc_id})")
        return doc_id

    def search_chunks(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Herramienta de Consulta: Realiza búsquedas por similitud vectorial.
        Retorna estructuras de diccionarios limpias listas para el análisis de ingredientes.
        """
        if not self.collection or not query.strip():
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
            )

            if not results.get("documents") or not results["documents"][0]:
                return []

            # Mapear los arreglos paralelos que entrega ChromaDB en objetos legibles
            mapped_results = []
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                metadata_safe = meta if meta else {}
                mapped_results.append({
                    "source": metadata_safe.get("source", "Desconocida"),
                    "text": doc
                })
            return mapped_results

        except Exception as e:
            print(f"❌ Error en la consulta semántica RAG: {e}")
            return []

    def search(self, query: str, top_k: int = 5) -> str:
        """
        Consulta simplificada que unifica los fragmentos vectoriales en una sola string.
        Utilizado principalmente para inyectarse directamente en los prompts.
        """
        chunks = self.search_chunks(query, top_k)
        if not chunks:
            return "No se encontraron recetas culinarias relevantes en la base de conocimiento."

        return "\n\n---\n\n".join(
            [f"Fuente: {c['source']}\n{c['text']}" for c in chunks]
        )

    def _split_text(self, text: str, chunk_size: int = 600) -> list[str]:
        """
        Divide de forma inteligente el texto respetando los saltos de línea dobles
        para no cortar los ingredientes o pasos a la mitad.
        """
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para_clean = para.strip()
            if not para_clean:
                continue

            if len(current_chunk) + len(para_clean) < chunk_size:
                current_chunk += para_clean + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para_clean + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return [c for c in chunks if c]

    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extractor multipropósito de archivos de datos (Txt, Pdf, Docx).
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"El archivo especificado no existe: {file_path}")

        suffix = path_obj.suffix.lower()
        if suffix == ".txt":
            with open(path_obj, "r", encoding="utf-8") as f:
                return f.read()
        elif suffix == ".pdf":
            return self._extract_pdf(path_obj)
        elif suffix in [".docx", ".doc"]:
            return self._extract_docx(path_obj)
        else:
            raise ValueError(f"Extensión de archivo culinario no soportada: {suffix}")

    def _extract_pdf(self, file_path: Path) -> str:
        """Extrae el contenido de texto plano desde archivos PDF."""
        try:
            text = []
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text.append(extracted)
            return "\n".join(text)
        except Exception as e:
            print(f"⚠️ Error al leer el documento PDF: {e}")
            return ""

    def _extract_docx(self, file_path: Path) -> str:
        """Extrae el contenido de texto plano desde archivos de Microsoft Word."""
        try:
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text])
        except ImportError:
            print("⚠️ Advertencia: Instale 'python-docx' para leer archivos Word.")
            return ""
        except Exception as e:
            print(f"⚠️ Error al leer el documento DOCX: {e}")
            return ""

    def get_document_count(self) -> int:
        """Retorna la cardinalidad exacta de la colección vectorial."""
        try:
            return self.collection.count()
        except Exception:
            return 0

    def clear_database(self):
        """Elimina de forma segura la colección actual y la recrea vacía."""
        try:
            self.client.delete_collection(name="recetas_cookai")
        except Exception:
            pass  # Evitar caídas si la colección no existía

        self.collection = self.client.get_or_create_collection(
            name="recetas_cookai",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embedding_function
        )
        print("🗑️ Base de datos vectorial limpiada y reconfigurada con éxito.")
import chromadb
from pathlib import Path
import PyPDF2
import re
from typing import Optional


class RAGSystem:
    """
    Sistema RAG (Retrieval-Augmented Generation) con ChromaDB.
    Gestiona almacenamiento y búsqueda de recetas en base vectorial.
    """
    
    def __init__(self, persist_dir: str = "../data/chroma_db"):
        """
        Inicializar ChromaDB para almacenar recetas.
        
        Args:
            persist_dir: Directorio para persistencia de datos
        """
        self.persist_dir = persist_dir
        
        # Crear cliente de ChromaDB
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # Crear o acceder a colección
        self.collection = self.client.get_or_create_collection(
            name="recetas",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.doc_counter = 0
    
    
    def add_documents(self, content: str, source: str):
        """
        Añadir documentos a la base vectorial.
        Divide el contenido en párrafos y los indexa.
        
        Args:
            content: Texto de las recetas
            source: Nombre del archivo o fuente
        """
        # Dividir contenido en párrafos (chunks)
        chunks = self._split_text(content)
        
        for i, chunk in enumerate(chunks):
            self.doc_counter += 1
            
            self.collection.add(
                documents=[chunk],
                metadatas=[{
                    "source": source,
                    "chunk": i,
                    "type": "receta"
                }],
                ids=[f"doc_{self.doc_counter}"]
            )
        
        print(f"✅ {len(chunks)} chunks de '{source}' añadidos a ChromaDB")
    
    
    def search(self, query: str, top_k: int = 5) -> str:
        """
        Buscar recetas relevantes según una consulta.
        
        Args:
            query: Pregunta o búsqueda del usuario
            top_k: Número de resultados a retornar
        
        Returns:
            Texto con las recetas más relevantes encontradas
        """
        if not self.collection:
            return "No hay recetas cargadas en el sistema."
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            if not results["documents"] or not results["documents"][0]:
                return "No se encontraron recetas relevantes."
            
            # Combinar resultados
            recetas = "\n---\n".join([
                f"Fuente: {meta['source']}\n{doc}"
                for doc, meta in zip(
                    results["documents"][0],
                    results["metadatas"][0]
                )
            ])
            
            return recetas
        
        except Exception as e:
            print(f"❌ Error en búsqueda RAG: {e}")
            return "Error al buscar en la base de datos."
    
    
    def _split_text(self, text: str, chunk_size: int = 500) -> list:
        """
        Dividir texto en chunks para mejor procesamiento.
        
        Args:
            text: Texto a dividir
            chunk_size: Tamaño aproximado de cada chunk
        
        Returns:
            Lista de chunks
        """
        # Dividir por párrafos primero
        paragraphs = text.split("\n\n")
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [c for c in chunks if c]  # Filtrar vacíos
    
    
    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extraer texto de diferentes formatos de archivo.
        
        Args:
            file_path: Ruta del archivo
        
        Returns:
            Texto extraído
        """
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        
        elif file_path.suffix.lower() == ".pdf":
            return self._extract_pdf(file_path)
        
        elif file_path.suffix.lower() in [".docx", ".doc"]:
            return self._extract_docx(file_path)
        
        else:
            raise ValueError(f"Formato no soportado: {file_path.suffix}")
    
    
    def _extract_pdf(self, file_path: Path) -> str:
        """Extraer texto de PDF"""
        try:
            text = ""
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"⚠️ Error leyendo PDF: {e}")
            return ""
    
    
    def _extract_docx(self, file_path: Path) -> str:
        """Extraer texto de DOCX"""
        try:
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs])
        except ImportError:
            print("⚠️ Instala: pip install python-docx")
            return ""
        except Exception as e:
            print(f"⚠️ Error leyendo DOCX: {e}")
            return ""
    
    
    def get_document_count(self) -> int:
        """Obtener número de documentos indexados"""
        try:
            return self.collection.count()
        except:
            return 0
    
    
    def clear_database(self):
        """Limpiar la base de datos (usar con cuidado)"""
        self.client.delete_collection(name="recetas")
        self.collection = self.client.get_or_create_collection(
            name="recetas",
            metadata={"hnsw:space": "cosine"}
        )
        print("🗑️ Base de datos limpiada")

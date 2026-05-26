"""
Sistema de Memoria Persistente (Largo Plazo) - IL2.2
Almacena historial de conversaciones y preferencias del usuario entre sesiones.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib


class PersistentMemoryDB:
    """
    Base de datos SQLite para memoria persistente del agente.
    Cumple IL2.2: Memoria de largo plazo con continuidad entre sesiones.
    """
    
    def __init__(self, db_path: str = "data/agent_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()
    
    def _initialize_db(self):
        """Crear tablas si no existen"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de conversaciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                summary TEXT,
                context_embeddings TEXT
            )
        """)
        
        # Tabla de mensajes en conversaciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # Tabla de preferencias del usuario
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                dietary_restrictions TEXT,
                favorite_cuisines TEXT,
                disliked_ingredients TEXT,
                cooking_time_preference TEXT,
                budget_preference TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de recetas guardadas/seleccionadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                recipe_title TEXT NOT NULL,
                recipe_content TEXT NOT NULL,
                source TEXT,
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                rating INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    def store_conversation(self, user_id: str, messages: List[tuple]) -> str:
        """
        Guardar una conversación completa.
        
        Args:
            user_id: ID del usuario
            messages: Lista de tuplas (role, content)
        
        Returns:
            ID de la conversación guardada
        """
        conv_id = hashlib.md5(f"{user_id}{datetime.now()}".encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO conversations (id, user_id) VALUES (?, ?)",
            (conv_id, user_id)
        )
        
        for role, content in messages:
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conv_id, role, content)
            )
        
        conn.commit()
        conn.close()
        
        return conv_id
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Recuperar últimas N conversaciones del usuario.
        
        Args:
            user_id: ID del usuario
            limit: Número de conversaciones a recuperar
        
        Returns:
            Lista de conversaciones con sus mensajes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM conversations 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (user_id, limit))
        
        conv_ids = cursor.fetchall()
        conversations = []
        
        for (conv_id,) in conv_ids:
            cursor.execute("""
                SELECT role, content, timestamp FROM messages 
                WHERE conversation_id = ? 
                ORDER BY timestamp
            """, (conv_id,))
            
            messages = [
                {"role": role, "content": content, "timestamp": ts}
                for role, content, ts in cursor.fetchall()
            ]
            
            conversations.append({
                "conv_id": conv_id,
                "messages": messages
            })
        
        conn.close()
        return conversations
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """
        Actualizar preferencias del usuario aprendidas del contexto.
        Cumple IL2.2: Aprendizaje entre sesiones.
        
        Args:
            user_id: ID del usuario
            preferences: Dict con claves de preferencias
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO user_preferences 
               (user_id, dietary_restrictions, favorite_cuisines, disliked_ingredients, 
                cooking_time_preference, budget_preference) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                json.dumps(preferences.get("dietary_restrictions", [])),
                json.dumps(preferences.get("favorite_cuisines", [])),
                json.dumps(preferences.get("disliked_ingredients", [])),
                preferences.get("cooking_time_preference", ""),
                preferences.get("budget_preference", "")
            )
        )
        
        conn.commit()
        conn.close()
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Recuperar preferencias guardadas del usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT dietary_restrictions, favorite_cuisines, disliked_ingredients, "
            "cooking_time_preference, budget_preference FROM user_preferences WHERE user_id = ?",
            (user_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "dietary_restrictions": json.loads(row[0] or "[]"),
            "favorite_cuisines": json.loads(row[1] or "[]"),
            "disliked_ingredients": json.loads(row[2] or "[]"),
            "cooking_time_preference": row[3],
            "budget_preference": row[4]
        }
    
    def save_recipe(self, user_id: str, recipe_title: str, recipe_content: str, 
                    source: str = "manual", rating: int = 0):
        """
        Guardar receta seleccionada por el usuario.
        Cumple IL2.1: Herramienta de ESCRITURA.
        
        Args:
            user_id: ID del usuario
            recipe_title: Título de la receta
            recipe_content: Contenido completo
            source: Fuente de la receta
            rating: Calificación 1-5
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO saved_recipes 
               (user_id, recipe_title, recipe_content, source, rating) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, recipe_title, recipe_content, source, rating)
        )
        
        conn.commit()
        conn.close()
    
    def get_saved_recipes(self, user_id: str) -> List[Dict[str, Any]]:
        """Recuperar recetas guardadas del usuario"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT id, recipe_title, recipe_content, source, rating, saved_at 
               FROM saved_recipes 
               WHERE user_id = ? 
               ORDER BY saved_at DESC""",
            (user_id,)
        )
        
        recipes = [
            {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "source": row[3],
                "rating": row[4],
                "saved_at": row[5]
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return recipes

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import hashlib


class PersistentMemoryDB:
    """
    Base de datos relacional liviana para la memoria de largo plazo del agente.
    Evita la pérdida de datos ante reinicios del servicio web (FastAPI).
    """

    def __init__(self, db_path: str = "data/agent_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        """Inicializa las tablas relacionales si no existen en el disco."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Tabla de conversaciones de largo plazo
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS conversations (
                                                                    id TEXT PRIMARY KEY,
                                                                    user_id TEXT NOT NULL,
                                                                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                                                    summary TEXT
                       )
                       """)

        # 2. Historial de mensajes individuales
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

        # 3. Perfil de Preferencias del Usuario (Base para la personalización adaptativa IL2.3)
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

        # 4. Repositorio de Recetas Guardadas (Herramienta de escritura IL2.1)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS saved_recipes (
                                                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                    user_id TEXT NOT NULL,
                                                                    recipe_title TEXT NOT NULL,
                                                                    recipe_content TEXT NOT NULL,
                                                                    source TEXT,
                                                                    saved_at DATETIME DEFAULT CURRENT_TIMESTAMP
                       )
                       """)

        conn.commit()
        conn.close()

    def store_conversation(self, user_id: str, messages: List[tuple]) -> str:
        """
        Registra un bloque de interacciones asociándolos a un ID único de sesión histórica.
        """
        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S%f")
        conv_id = hashlib.md5(f"{user_id}_{timestamp_str}".encode()).hexdigest()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO conversations (id, user_id) VALUES (?, ?)",
                (conv_id, user_id)
            )

            for role, content in messages:
                cursor.execute(
                    "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                    (conv_id, role.strip().lower(), content.strip())
                )
            conn.commit()
        except sqlite3.Error as e:
            print(f"[SQLite Error en store_conversation]: {e}")
            conn.rollback()
        finally:
            conn.close()

        return conv_id

    def get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recupera el registro histórico de las últimas N interacciones del usuario.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        conversations = []

        try:
            cursor.execute("""
                           SELECT id FROM conversations
                           WHERE user_id = ?
                           ORDER BY timestamp DESC
                               LIMIT ?
                           """, (user_id, limit))

            conv_rows = cursor.fetchall()

            for (conv_id,) in conv_rows:
                cursor.execute("""
                               SELECT role, content FROM messages
                               WHERE conversation_id = ?
                               ORDER BY timestamp ASC
                               """, (conv_id,))

                messages = [
                    {"role": role, "content": content}
                    for role, content in cursor.fetchall()
                ]

                conversations.append({
                    "conv_id": conv_id,
                    "messages": messages
                })
        except sqlite3.Error as e:
            print(f"[SQLite Error en get_conversation_history]: {e}")
        finally:
            conn.close()

        return conversations

    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """
        Herramienta de Escritura Adaptativa: Actualiza los gustos y restricciones
        del usuario en su perfil histórico (IL2.3).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            dietary = json.dumps(preferences.get("dietary_restrictions", []))
            cuisines = json.dumps(preferences.get("favorite_cuisines", []))
            disliked = json.dumps(preferences.get("disliked_ingredients", []))

            cursor.execute(
                """INSERT OR REPLACE INTO user_preferences 
                   (user_id, dietary_restrictions, favorite_cuisines, disliked_ingredients, 
                    cooking_time_preference, budget_preference, last_updated) 
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    user_id,
                    dietary,
                    cuisines,
                    disliked,
                    preferences.get("cooking_time_preference", ""),
                    preferences.get("budget_preference", "")
                )
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"[SQLite Error en update_user_preferences]: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Recupera las preferencias del usuario. Si es nuevo, inicializa
        un diccionario con estructuras vacías seguras para evitar excepciones.
        """
        default_pref = {
            "dietary_restrictions": [],
            "favorite_cuisines": [],
            "disliked_ingredients": [],
            "cooking_time_preference": "",
            "budget_preference": ""
        }

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """SELECT dietary_restrictions, favorite_cuisines, disliked_ingredients,
                          cooking_time_preference, budget_preference
                   FROM user_preferences WHERE user_id = ?""", (user_id,)
            )
            row = cursor.fetchone()

            if row:
                return {
                    "dietary_restrictions": json.loads(row[0]) if row[0] else [],
                    "favorite_cuisines": json.loads(row[1]) if row[1] else [],
                    "disliked_ingredients": json.loads(row[2]) if row[2] else [],
                    "cooking_time_preference": row[3] or "",
                    "budget_preference": row[4] or ""
                }
        except sqlite3.Error as e:
            print(f"[SQLite Error en get_user_preferences]: {e}")
        finally:
            conn.close()

        return default_pref

    # =========================================================
    # COMPLEMENTOS DE ESCRITURA Y CONSULTA REQUERIDOS (IL2.1)
    # =========================================================

    def save_recipe(self, user_id: str, recipe_title: str, recipe_content: str, source: Optional[str] = "Generada por CookAI") -> bool:
        """
        Herramienta de Escritura Explícita (IL2.1): Guarda una estructura de receta
        en la libreta personal relacional del usuario.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        success = False

        try:
            cursor.execute(
                """INSERT INTO saved_recipes (user_id, recipe_title, recipe_content, source)
                   VALUES (?, ?, ?, ?)""",
                (user_id, recipe_title.strip(), recipe_content.strip(), source)
            )
            conn.commit()
            success = True
        except sqlite3.Error as e:
            print(f"[SQLite Error en save_recipe]: {e}")
            conn.rollback()
        finally:
            conn.close()

        return success

    def get_saved_recipes(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Herramienta de Consulta de Datos Guardados: Recupera todas las recetas
        que el usuario ha guardado en sus sesiones históricas.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        recipes = []

        try:
            cursor.execute(
                """SELECT id, recipe_title, recipe_content, source, saved_at
                   FROM saved_recipes WHERE user_id = ?
                   ORDER BY saved_at DESC""", (user_id,)
            )

            for row in cursor.fetchall():
                recipes.append({
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "source": row[3],
                    "saved_at": row[4]
                })
        except sqlite3.Error as e:
            print(f"[SQLite Error en get_saved_recipes]: {e}")
        finally:
            conn.close()

        return recipes


# Instancia global por defecto para importaciones limpias en el toolkit
persistent_db = PersistentMemoryDB()
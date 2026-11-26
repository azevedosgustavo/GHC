"""SQLite persistence for conversations and provider model catalogs."""
import json
import os
import sqlite3
import time

from .auth import CONFIG_DIR

DB_FILE = os.path.join(CONFIG_DIR, "ghc.sqlite3")
LEGACY_FILE = os.path.join(CONFIG_DIR, "chats.json")
GITHUB = "github-copilot"


class Store:
    def __init__(self, path=DB_FILE, legacy=LEGACY_FILE):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, provider TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0, messages TEXT NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS models (
                provider TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
                metadata TEXT NOT NULL, PRIMARY KEY (provider, id)
            );
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(conversations)")}
        if "files" not in columns:
            with self.db:
                self.db.execute("ALTER TABLE conversations ADD COLUMN files TEXT NOT NULL DEFAULT '[]'")
        try:
            self._import_legacy(legacy)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            self.db.close()
            raise

    def _import_legacy(self, path):
        if self.db.execute("SELECT value FROM metadata WHERE key='legacy_imported'").fetchone():
            return
        chats = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                chats = json.load(f)
            if not isinstance(chats, list):
                raise ValueError("Histórico antigo inválido; o arquivo original foi preservado.")
            if any(not isinstance(chat, dict) or not isinstance(chat.get("id"), str) or
                   not isinstance(chat.get("title"), str) or not isinstance(chat.get("messages"), list)
                   for chat in chats):
                raise ValueError("Conversa antiga inválida; o arquivo original foi preservado.")
            if len({chat["id"] for chat in chats}) != len(chats):
                raise ValueError("Conversas antigas têm identificadores repetidos; arquivo preservado.")
        with self.db:
            for chat in chats:
                self._write_chat(chat)
            self.db.execute("INSERT INTO metadata VALUES ('legacy_imported', '1')")

    def _write_chat(self, chat):
        self.db.execute(
            "INSERT OR REPLACE INTO conversations (id, title, provider, archived, messages, updated, files) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chat["id"], chat["title"], chat.get("provider", GITHUB), int(chat.get("archived", False)),
             json.dumps(chat["messages"], ensure_ascii=False), chat.get("updated", time.time()),
             json.dumps(chat.get("files", []), ensure_ascii=False)))

    def save_chat(self, chat):
        if chat.get("temporary"):
            raise ValueError("Conversas temporárias não podem ser salvas no banco.")
        with self.db:
            self._write_chat(chat)

    def chats(self):
        rows = self.db.execute("SELECT id, title, provider, archived, messages, updated, files "
                               "FROM conversations ORDER BY updated DESC").fetchall()
        return [{"id": row[0], "title": row[1], "provider": row[2],
                 "archived": bool(row[3]), "messages": json.loads(row[4]),
                 "updated": row[5], "files": json.loads(row[6]), "temporary": False} for row in rows]

    def delete_chat(self, chat_id):
        with self.db:
            self.db.execute("DELETE FROM conversations WHERE id = ?", (chat_id,))

    def replace_models(self, provider, models):
        if not models:
            raise ValueError("O serviço não retornou modelos de chat.")
        with self.db:
            self.db.execute("DELETE FROM models WHERE provider = ?", (provider,))
            self.db.executemany("INSERT INTO models (provider, id, name, metadata) VALUES (?, ?, ?, ?)",
                                [(provider, m["id"], m["name"], json.dumps(m, ensure_ascii=False))
                                 for m in models])

    def models(self, provider):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT metadata FROM models WHERE provider = ? ORDER BY name COLLATE NOCASE", (provider,))]

    def close(self):
        self.db.close()

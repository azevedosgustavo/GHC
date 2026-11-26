"""User preferences; existing theme settings are retained."""
import json
import os

from .auth import CONFIG_DIR

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
DEFAULTS = {"theme": "system", "permission": "chat", "model": "Automático (GHC)",
            "instructions": "", "context_chars": 0, "browser": "",
            "menu_font_size": 10, "chat_font_size": 10,
            "files_dir": os.path.join(CONFIG_DIR, "files"), "skills": []}


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULTS)
    if not isinstance(data, dict):
        raise ValueError("Arquivo de configurações inválido.")
    result = dict(DEFAULTS)
    result.update(data)
    return result


def save_settings(settings):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False)
    os.replace(tmp, SETTINGS_FILE)

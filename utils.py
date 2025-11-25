import json
import os

MACRO_FILE = "macros.json"

def load_macros():
    if os.path.exists(MACRO_FILE):
        with open(MACRO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_macros(data):
    with open(MACRO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

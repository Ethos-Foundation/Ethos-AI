"""Preferências da janela (pet ligado, posição do pet, voz ligada), em preferencias_ethos.json."""

import json
import os

ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preferencias_ethos.json")
PADRAO = {"pet": True, "voz": True, "pet_x": None, "pet_y": None, "sarcasmo": None}


def carregar():
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            return {**PADRAO, **json.load(f)}
    except (OSError, ValueError):
        return dict(PADRAO)


def salvar(prefs):
    try:
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except OSError:
        pass

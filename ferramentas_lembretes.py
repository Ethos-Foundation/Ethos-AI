"""Ferramentas de lembrete para a Ethos (o modelo chama; quem calcula a data é o código)."""

import datetime as dt
import re

import lembretes
import tempo
from texto import Falha

_AJUDA_QUANDO = Falha("Não entendi quando. Diga, por exemplo, 'daqui a 20 minutos', 'amanhã às 9h' "
                 "ou 'toda segunda às 8h'.")


def criar_lembrete(texto, quando):
    texto = (texto or "").strip()
    if not texto:
        return Falha("Preciso saber do que lembrar.")
    r = tempo.interpretar_quando(quando or "")
    if r is None and re.match(r"\d{4}-\d{2}-\d{2}", (quando or "").strip()):
        try:
            r = tempo.Resultado(dt.datetime.fromisoformat(quando.strip()), None, [])
        except ValueError:
            r = None
    if r is None:
        return _AJUDA_QUANDO
    item = lembretes.adicionar(texto, r.quando, r.repetir)
    extra = f" (repete {tempo.descrever_repeticao(r.repetir, r.quando)})" if r.repetir else ""
    return f"Lembrete #{item['id']} criado para {tempo.descrever(r.quando)}{extra}: {texto}."


def _linha(item):
    q = dt.datetime.fromisoformat(item["quando"])
    rep = f", repete {tempo.descrever_repeticao(item['repetir'], q)}" if item.get("repetir") else ""
    return f"#{item['id']} {item['texto']} ({tempo.descrever(q)}{rep})"


def listar_lembretes():
    itens = lembretes.listar()
    if not itens:
        return "Não há nenhum lembrete agendado."
    return "Lembretes: " + "; ".join(_linha(i) for i in itens) + "."


def cancelar_lembrete(referencia=""):
    ref = (referencia or "").strip().lower().lstrip("#")
    if ref in ("todos", "todas", "tudo"):
        return f"Cancelei {lembretes.limpar()} lembrete(s)."
    itens = lembretes.listar()
    if ref.isdigit():
        return (f"Lembrete #{ref} cancelado." if lembretes.cancelar(int(ref))
                else f"Não achei o lembrete #{ref}.")
    achados = [i for i in itens if ref and ref in i["texto"].lower()]
    if len(achados) == 1:
        lembretes.cancelar(achados[0]["id"])
        return f"Cancelei o lembrete: {achados[0]['texto']}."
    if not itens:
        return "Não há nenhum lembrete agendado."
    return "Qual deles? " + "; ".join(_linha(i) for i in (achados or itens)) + "."


FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "criar_lembrete",
        "description": "Cria um lembrete que a Ethos vai FALAR no horário. Use quando o usuário pedir para ser lembrado/avisado de algo.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string", "description": "do que lembrar, ex.: 'tomar água'"},
            "quando": {"type": "string", "description": "quando, em português natural: 'daqui a 20 minutos', 'amanhã às 9h', 'toda segunda às 8h'"}},
            "required": ["texto", "quando"]}}},
    {"type": "function", "function": {
        "name": "listar_lembretes",
        "description": "Lista os lembretes agendados.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "cancelar_lembrete",
        "description": "Cancela um lembrete pelo número, por um trecho do texto, ou 'todos'.",
        "parameters": {"type": "object", "properties": {
            "referencia": {"type": "string", "description": "número, trecho do texto, ou 'todos'"}},
            "required": ["referencia"]}}},
]

_FUNCOES = {"criar_lembrete": criar_lembrete, "listar_lembretes": listar_lembretes,
            "cancelar_lembrete": cancelar_lembrete}


def executar(nome, args):
    if nome not in _FUNCOES:
        return None
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return Falha(f"Erro ao executar {nome}: {erro}")

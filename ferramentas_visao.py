"""Ferramenta de visão para a Ethos: olhar a tela do usuário."""

import visao


def ver_tela(pergunta=""):
    return visao.olhar_tela(pergunta)


FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "ver_tela",
        "description": ("Tira uma captura da tela do usuário e a analisa com um modelo de visão. Use quando ele "
                        "pedir para olhar/ver/ler a tela, ou perguntar algo sobre o que está aparecendo nela "
                        "(erro, código, página aberta). Demora alguns segundos."),
        "parameters": {"type": "object", "properties": {
            "pergunta": {"type": "string", "description": "o que o usuário quer saber sobre a tela"}},
            "required": []}}},
]

_FUNCOES = {"ver_tela": ver_tela}


def executar(nome, args):
    if nome not in _FUNCOES:
        return None
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return f"Erro ao executar {nome}: {erro}"

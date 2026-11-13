"""
Ferramentas da Ethos AI que fazem coisas no seu computador:
abrir música no YouTube e abrir/criar arquivos no VS Code.

Precisa do comando "code" disponível no terminal (vem com o VS Code,
em Configurações > "Adicionar ao PATH" na instalação, ou reinstale
marcando essa opção).
"""

import os
import subprocess
import webbrowser
from urllib.parse import quote

import config


def abrir_musica_youtube(busca):
    """Abre a pesquisa dessa música/artista no YouTube, no navegador."""
    url = f"https://www.youtube.com/results?search_query={quote(busca)}"
    webbrowser.open(url)
    return f"Abri a pesquisa de '{busca}' no YouTube."


def abrir_site(url_ou_nome):
    """Abre um site. Aceita atalhos para alguns sites comuns."""
    atalhos = {
        "youtube": "https://youtube.com", "google": "https://google.com",
        "spotify": "https://open.spotify.com", "gmail": "https://mail.google.com",
        "github": "https://github.com",
    }
    url = atalhos.get(url_ou_nome.lower().strip(), url_ou_nome)
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Abri {url}."


def abrir_vscode(caminho=None):
    """Abre uma pasta ou arquivo no VS Code. Sem caminho, abre uma janela nova."""
    try:
        subprocess.Popen(["code", caminho] if caminho else ["code", "-n"], shell=True)
        return f"Abri o VS Code{' em ' + caminho if caminho else ''}."
    except FileNotFoundError:
        return ("Não encontrei o comando 'code'. No VS Code, aperte Ctrl+Shift+P, "
                "digite 'Shell Command: Install code command in PATH' e tente de novo.")


def caminho_seguro(caminho):
    """Garante que o arquivo fique dentro da pasta de projetos da Ethos e que
    nada já existente seja sobrescrito (se existir, vira nome_2.ext, nome_3.ext...)."""
    base = os.path.abspath(config.PASTA_PROJETOS)
    os.makedirs(base, exist_ok=True)
    bruto = caminho if os.path.isabs(caminho) else os.path.join(base, caminho)
    alvo = os.path.abspath(bruto)
    try:
        dentro = os.path.commonpath([alvo, base]) == base
    except ValueError:      # outro disco no Windows
        dentro = False
    if not dentro:
        alvo = os.path.join(base, os.path.basename(caminho) or "arquivo.txt")
    raiz, ext = os.path.splitext(alvo)
    n = 2
    while os.path.exists(alvo):
        alvo = f"{raiz}_{n}{ext}"
        n += 1
    return alvo


def criar_arquivo_codigo(caminho, conteudo):
    """Cria um arquivo na pasta de projetos da Ethos e abre no VS Code."""
    try:
        alvo = caminho_seguro(caminho)
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        with open(alvo, "w", encoding="utf-8") as f:
            f.write(conteudo)
        subprocess.Popen(["code", alvo], shell=True)
        return f"Criei e abri '{alvo}' no VS Code."
    except Exception as erro:
        return f"Não consegui criar o arquivo: {erro}"


FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "abrir_musica_youtube",
        "description": "Abre no navegador a pesquisa de uma música ou artista no YouTube.",
        "parameters": {"type": "object", "properties": {
            "busca": {"type": "string", "description": "nome da música e/ou artista"}},
            "required": ["busca"]}}},
    {"type": "function", "function": {
        "name": "abrir_site",
        "description": "Abre um site no navegador (YouTube, Google, Spotify, Gmail, GitHub ou qualquer URL).",
        "parameters": {"type": "object", "properties": {
            "url_ou_nome": {"type": "string"}}, "required": ["url_ou_nome"]}}},
    {"type": "function", "function": {
        "name": "abrir_vscode",
        "description": "Abre uma pasta ou arquivo no VS Code.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "caminho da pasta/arquivo; opcional"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "criar_arquivo_codigo",
        "description": "Cria um arquivo de código com o conteúdo dado e abre no VS Code.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "nome do arquivo, ex.: 'teste.py' (é salvo na pasta de projetos da Ethos)"},
            "conteudo": {"type": "string"}},
            "required": ["caminho", "conteudo"]}}},
]

_FUNCOES = {
    "abrir_musica_youtube": abrir_musica_youtube, "abrir_site": abrir_site,
    "abrir_vscode": abrir_vscode, "criar_arquivo_codigo": criar_arquivo_codigo,
}


def executar(nome, args):
    if nome not in _FUNCOES:
        return None
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return f"Erro ao executar {nome}: {erro}"

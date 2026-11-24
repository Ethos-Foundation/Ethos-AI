"""
Ferramentas da Ethos que fazem coisas no seu computador: abrir sites, músicas, pastas e o
VS Code, e criar/salvar arquivos em qualquer pasta (com apelidos como 'documentos',
'área de trabalho', 'downloads').

Precisa do comando "code" no terminal para abrir no VS Code (Ctrl+Shift+P no VS Code >
"Shell Command: Install 'code' command in PATH").
"""

import os
import subprocess
import time
import webbrowser
from urllib.parse import quote

import config
from texto import Falha

# A janela da Ethos se registra aqui para "recuar" antes de abrirmos algo (senão o navegador
# abre atrás dela e parece que não abriu). Recebe nada, devolve nada.
ao_abrir = None
# Arquivos criados pela própria Ethos nesta execução (podem ser reescritos; os demais, nunca).
_criados = set()


def _antes_de_abrir():
    if ao_abrir:
        try:
            ao_abrir()
            time.sleep(0.4)       # dá tempo da janela recuar
        except Exception:
            pass


# ----------------------------------------------------------------- pastas
def _pasta_conhecida(nome):
    """Pasta do Windows (Desktop, Documentos...) já considerando OneDrive."""
    chaves = {"area de trabalho": "Desktop", "documentos": "Personal", "imagens": "My Pictures",
              "musicas": "My Music", "videos": "My Video",
              "downloads": "{374DE290-123F-4565-9164-39C4925E467B}"}
    casa = os.path.expanduser("~")
    padrao = {"area de trabalho": "Desktop", "documentos": "Documents", "downloads": "Downloads",
              "imagens": "Pictures", "musicas": "Music", "videos": "Videos"}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as chave:
            caminho = os.path.expandvars(winreg.QueryValueEx(chave, chaves[nome])[0])
            if os.path.isdir(caminho):
                return caminho
    except Exception:
        pass
    for base in (casa, os.path.join(casa, "OneDrive")):
        caminho = os.path.join(base, padrao[nome])
        if os.path.isdir(caminho):
            return caminho
    return None


def resolver_destino(destino):
    """Transforma 'documentos', 'area de trabalho', 'C:\\\\...' ou o nome de uma pasta no
    caminho real. Devolve None se não achar. Sem destino, usa a pasta de projetos da Ethos."""
    destino = (destino or "").strip().strip("\"'")
    if not destino or destino.lower() == "projetos":
        os.makedirs(config.PASTA_PROJETOS, exist_ok=True)
        return config.PASTA_PROJETOS
    if os.path.isabs(destino):
        return destino if os.path.isdir(destino) or not os.path.exists(destino) else None
    alias = destino.lower()
    if alias in ("area de trabalho", "documentos", "downloads", "imagens", "musicas", "videos"):
        return _pasta_conhecida(alias)
    # nome de pasta: procura (até 3 níveis) na área de trabalho, documentos e na pasta pessoal
    bases = [p for p in (_pasta_conhecida("area de trabalho"), _pasta_conhecida("documentos"),
                         os.path.expanduser("~")) if p]
    for base in bases:
        raiz_nivel = base.rstrip("\\/").count(os.sep)
        for atual, subpastas, _ in os.walk(base):
            subpastas[:] = [d for d in subpastas if not d.startswith(".") and d.lower() not in ("appdata", "node_modules")]
            if atual.count(os.sep) - raiz_nivel >= 3:
                subpastas[:] = []
            for d in subpastas:
                if d.lower() == alias:
                    return os.path.join(atual, d)
    return None


def caminho_para_novo_arquivo(nome, destino=""):
    """Caminho final de um arquivo novo. Nunca sobrescreve algo que não foi a Ethos que criou
    nesta execução (nesse caso vira nome_2.ext). Devolve (caminho, None) ou (None, mensagem)."""
    nome = os.path.basename((nome or "").strip()) or "ethos_conteudo.txt"
    pasta = resolver_destino(destino)
    if pasta is None:
        return None, f"Não encontrei a pasta '{destino}'."
    alvo = os.path.join(pasta, nome)
    if alvo in _criados:
        return alvo, None
    raiz, ext = os.path.splitext(alvo)
    n = 2
    while os.path.exists(alvo):
        alvo = f"{raiz}_{n}{ext}"
        n += 1
    return alvo, None


def salvar_arquivo(nome, conteudo, destino="", abrir=True):
    """Grava um arquivo (e abre no VS Code). Recusa conteúdo vazio: nada de arquivo em branco."""
    if not (conteudo or "").strip():
        return Falha("O conteúdo do arquivo veio vazio, então não criei nada.")
    alvo, erro = caminho_para_novo_arquivo(nome, destino)
    if erro:
        return Falha(erro)
    try:
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        with open(alvo, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except Exception as erro_io:
        return Falha(f"Não consegui salvar o arquivo: {erro_io}")
    _criados.add(alvo)
    if abrir:
        _antes_de_abrir()
        try:
            subprocess.Popen(["code", alvo], shell=True)
        except Exception:
            pass
    return f"Arquivo salvo em {alvo}."


def criar_arquivo_codigo(caminho, conteudo):
    """Chamada pelo modelo: salva um arquivo (por nome ou caminho) e abre no VS Code."""
    caminho = (caminho or "").strip()
    pasta, nome = (os.path.dirname(caminho), os.path.basename(caminho)) if os.path.isabs(caminho) else ("", caminho)
    return salvar_arquivo(nome, conteudo, pasta)


# ------------------------------------------------------------------ abrir
def abrir_pasta(destino=""):
    pasta = resolver_destino(destino)
    if not pasta or not os.path.isdir(pasta):
        return Falha(f"Não encontrei a pasta '{destino}'.")
    _antes_de_abrir()
    try:
        os.startfile(pasta)
    except AttributeError:                      # fora do Windows
        subprocess.Popen(["xdg-open", pasta])
    return f"Abri a pasta {pasta}."


def abrir_musica_youtube(busca):
    """Abre a pesquisa dessa música/artista no YouTube, no navegador."""
    _antes_de_abrir()
    webbrowser.open(f"https://www.youtube.com/results?search_query={quote(busca)}")
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
    _antes_de_abrir()
    webbrowser.open(url)
    return f"Abri {url}."


def abrir_vscode(caminho=None):
    """Abre uma pasta ou arquivo no VS Code. Sem caminho, abre uma janela nova."""
    _antes_de_abrir()
    try:
        subprocess.Popen(["code", caminho] if caminho else ["code", "-n"], shell=True)
        return f"Abri o VS Code{' em ' + caminho if caminho else ''}."
    except FileNotFoundError:
        return Falha("Não encontrei o comando 'code'. No VS Code, aperte Ctrl+Shift+P, "
                     "digite 'Shell Command: Install code command in PATH' e tente de novo.")


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
        "name": "abrir_pasta",
        "description": "Abre uma pasta no Explorador de Arquivos: 'documentos', 'downloads', 'area de trabalho', "
                       "um caminho completo ou o nome de uma pasta.",
        "parameters": {"type": "object", "properties": {
            "destino": {"type": "string"}}, "required": ["destino"]}}},
    {"type": "function", "function": {
        "name": "abrir_vscode",
        "description": "Abre uma pasta ou arquivo no VS Code.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "caminho da pasta/arquivo; opcional"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "criar_arquivo_codigo",
        "description": ("Cria UM arquivo com o conteúdo COMPLETO e abre no VS Code. Chame uma única vez por arquivo, "
                        "sempre com o conteúdo preenchido (nunca vazio)."),
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "nome do arquivo, ex.: 'teste.py', ou caminho completo"},
            "conteudo": {"type": "string", "description": "o conteúdo inteiro do arquivo"}},
            "required": ["caminho", "conteudo"]}}},
]

_FUNCOES = {
    "abrir_musica_youtube": abrir_musica_youtube, "abrir_site": abrir_site, "abrir_pasta": abrir_pasta,
    "abrir_vscode": abrir_vscode, "criar_arquivo_codigo": criar_arquivo_codigo,
}


def executar(nome, args):
    if nome not in _FUNCOES:
        return None
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return Falha(f"Erro ao executar {nome}: {erro}")

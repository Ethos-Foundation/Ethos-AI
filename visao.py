"""
Visão da Ethos: captura a tela e pede a um modelo de visão do Ollama para descrevê-la.
Tudo local: a imagem só vai para o Ollama, na sua máquina.

A captura roda num processo separado porque, no Windows com escala de tela (125%, 150%),
um programa sem "DPI awareness" captura só um pedaço da tela. O processo filho se declara
DPI-aware sozinho, sem mexer no tamanho da janela da Ethos.
"""

import io
import os
import subprocess
import sys
import tempfile

import config
from texto import Falha

# A janela registra aqui uma função(nome_do_evento): 'capturando' | 'capturada'
ao_evento = None

PROMPT_VISAO = (
    "Você descreve capturas de tela para um assistente de voz. Responda em português do "
    "Brasil, de forma objetiva, em no máximo uns 120 palavras e sem formatação. Diga qual "
    "programa ou site está aberto e o que o usuário parece estar fazendo. Se houver erros, "
    "mensagens ou textos importantes, cite-os fielmente. Responda diretamente ao pedido do "
    "usuário sobre a tela."
)


def _capturar_direto(max_lado, todas_as_telas):
    from PIL import ImageGrab
    imagem = ImageGrab.grab(all_screens=todas_as_telas).convert("RGB")
    imagem.thumbnail((max_lado, max_lado))          # só reduz, mantém a proporção
    buffer = io.BytesIO()
    imagem.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def capturar_tela(max_lado=None):
    """Devolve a tela como bytes JPEG (reduzida). Tenta o processo filho; se falhar, captura direto."""
    max_lado = max_lado or config.VISAO_MAX_LADO
    todas = config.VISAO_TODAS_AS_TELAS
    arquivo = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    arquivo.close()
    try:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--capturar", arquivo.name,
             str(max_lado), "1" if todas else "0"],
            timeout=20, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode == 0 and os.path.getsize(arquivo.name) > 0:
            with open(arquivo.name, "rb") as f:
                return f.read()
    except Exception:
        pass
    finally:
        try:
            os.remove(arquivo.name)
        except OSError:
            pass
    return _capturar_direto(max_lado, todas)


def analisar_imagem(jpeg, pergunta="", modelo=None):
    """Manda a imagem ao modelo de visão e devolve a descrição (ou uma mensagem de erro clara)."""
    import ollama
    import texto

    modelo = modelo or config.MODELO_VISAO
    pedido = (pergunta or "").strip() or "Descreva o que está na tela."
    mensagens = [{"role": "system", "content": PROMPT_VISAO},
                 {"role": "user", "content": pedido, "images": [jpeg]}]
    opcoes = {"temperature": 0.2, "num_ctx": config.VISAO_NUM_CTX, "num_predict": config.VISAO_MAX_TOKENS}
    try:
        try:
            resposta = ollama.chat(model=modelo, messages=mensagens, think=False,
                                   keep_alive=config.VISAO_KEEP_ALIVE, options=opcoes)
        except Exception as erro:
            if "think" not in str(erro).lower():
                raise
            # alguns modelos não aceitam o parâmetro 'think': tenta sem ele
            resposta = ollama.chat(model=modelo, messages=mensagens,
                                   keep_alive=config.VISAO_KEEP_ALIVE, options=opcoes)
    except Exception as erro:
        t = str(erro).lower()
        if "not found" in t:
            return Falha(f"O modelo de visão {modelo} não está instalado. Rode no terminal: ollama pull {modelo}")
        if any(p in t for p in ("connect", "10061", "refused")):
            return Falha("Não consegui falar com o Ollama para olhar a tela. Ele está aberto?")
        return Falha(f"Não consegui analisar a tela: {erro}")
    descricao = texto.remover_pensamento(resposta["message"]["content"] or "")
    return descricao[:1800] or Falha("O modelo de visão não devolveu nenhuma descrição.")


def _evento(nome):
    if ao_evento:
        try:
            ao_evento(nome)
        except Exception:
            pass


def olhar_tela(pergunta=""):
    """Captura a tela agora e a analisa. Avisa a janela quando captura (som e status), para você
    saber que já pode voltar ao que estava fazendo."""
    try:
        _evento("capturando")
        jpeg = capturar_tela()
        _evento("capturada")
    except ImportError:
        return Falha("Falta a biblioteca Pillow para capturar a tela. Rode: pip install Pillow")
    except Exception as erro:
        return Falha(f"Não consegui capturar a tela: {erro}")
    return analisar_imagem(jpeg, pergunta)


# --- modo "processo filho": python visao.py --capturar <arquivo> <max_lado> <todas 0|1>
def _main_captura(destino, max_lado, todas):
    if os.name == "nt":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    with open(destino, "wb") as f:
        f.write(_capturar_direto(int(max_lado), todas == "1"))


if __name__ == "__main__" and len(sys.argv) >= 5 and sys.argv[1] == "--capturar":
    _main_captura(*sys.argv[2:5])

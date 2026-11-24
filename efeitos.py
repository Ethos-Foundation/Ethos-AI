"""
Efeitos sonoros da Ethos, gerados por código (um sintetizador pequeno): bips e bops de IA.
Para usar sons SEUS, ponha arquivos .wav na pasta `sons/` com o nome do efeito
(ativar.wav, concluir.wav, alerta.wav, erro.wav, captura.wav, ligar.wav, desligar.wav, tique_a.wav, tique_b.wav):
um arquivo com o nome certo substitui o som gerado.
"""

import os
import wave

import numpy as np

import config

TAXA = 44100
PASTA_SONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sons")
_cache = {}


# ------------------------------------------------------------- peças básicas
def _t(dur):
    return np.arange(int(TAXA * dur)) / TAXA


def _envelope(n, ataque=0.004, decai=12.0):
    i = np.arange(n)
    env = np.minimum(1.0, i / (TAXA * ataque)) * np.exp(-decai * i / TAXA)
    fim = min(n, int(TAXA * 0.006))
    if fim:
        env[-fim:] *= np.linspace(1, 0, fim)          # sem estalo no final
    return env


def _fm(freq, dur, razao=2.0, indice=3.0, decai=14.0):
    """Tom metálico de sintetizador (modulação de frequência)."""
    t = _t(dur)
    mod = indice * np.exp(-decai * 0.5 * t) * np.sin(2 * np.pi * freq * razao * t)
    return np.sin(2 * np.pi * freq * t + mod) * _envelope(len(t), decai=decai)


def _varredura(f0, f1, dur, pesos=(1.0, 0.35, 0.12), decai=5.0):
    t = _t(dur)
    freq = f0 * (f1 / f0) ** (t / dur)                 # sobe/desce de forma exponencial
    fase = 2 * np.pi * np.cumsum(freq) / TAXA
    onda = sum(p * np.sin((h + 1) * fase) for h, p in enumerate(pesos))
    return onda * _envelope(len(t), ataque=0.01, decai=decai)


def _ruido(dur, decai=60.0):
    rng = np.random.default_rng(7)                     # fixo: o som é sempre o mesmo
    return rng.uniform(-1, 1, int(TAXA * dur)) * _envelope(int(TAXA * dur), ataque=0.001, decai=decai)


def _pausa(dur):
    return np.zeros(int(TAXA * dur))


def _eco(x, repeticoes=((0.11, 0.32), (0.22, 0.16))):
    saida = np.zeros(len(x) + int(TAXA * max(a for a, _ in repeticoes)))
    saida[:len(x)] += x
    for atraso, ganho in repeticoes:
        d = int(TAXA * atraso)
        saida[d:d + len(x)] += ganho * x
    return saida


def _final(x, pico=0.32):
    x = np.asarray(x, dtype=np.float64)
    x = x / (np.max(np.abs(x)) + 1e-9) * pico * config.VOLUME_EFEITOS
    return x.astype(np.float32)


# ------------------------------------------------------------ estilo futurista
def _futurista():
    j = np.concatenate
    return {
        "ativar":   _eco(j([_fm(880, .07), _pausa(.015), _fm(1320, .1, indice=2.5)])),
        "concluir": _eco(j([_fm(1320, .07), _pausa(.015), _fm(740, .12, indice=2.0)])),
        "alerta":   _eco(j([_fm(784, .11), _fm(1047, .11), _fm(1568, .22, indice=2.0, decai=8)]),
                         ((0.16, 0.4), (0.32, 0.22), (0.48, 0.1))),
        "erro":     _eco(j([_varredura(260, 150, .16, pesos=(1, .8, .5)), _pausa(.04),
                            _varredura(240, 120, .24, pesos=(1, .8, .5))])),
        "captura":  _eco(j([_ruido(.035), _varredura(2400, 700, .09, pesos=(1, .2)), _pausa(.02),
                            _fm(1760, .06, indice=1.5)]), ((0.12, 0.25),)),
        "ligar":    _eco(j([_varredura(300, 1500, .26), _fm(1760, .1, indice=2.0)])),
        "desligar": _eco(j([_fm(1320, .07), _varredura(1200, 260, .3)])),
        "tique_a":  _fm(1900, .035, indice=1.2, decai=60) * 0.35,
        "tique_b":  _fm(2400, .035, indice=1.2, decai=60) * 0.35,
    }


# --------------------------------------------------------------- estilo clássico
def _classico():
    return {
        "ativar":   _varredura(880, 1320, .14, pesos=(1,), decai=4),
        "concluir": _varredura(1320, 880, .12, pesos=(1,), decai=4),
        "alerta":   np.concatenate([_varredura(880, 1320, .14, pesos=(1,), decai=4), _pausa(.05),
                                    _varredura(1320, 1760, .2, pesos=(1,), decai=4)]),
        "erro":     _varredura(300, 180, .3, pesos=(1,), decai=4),
        "captura":  np.concatenate([_ruido(.03), _varredura(1500, 900, .06, pesos=(1,), decai=4)]),
        "ligar":    _varredura(500, 1400, .2, pesos=(1,), decai=4),
        "desligar": _varredura(1400, 500, .2, pesos=(1,), decai=4),
        "tique_a":  _fm(1600, .03, indice=0.5, decai=60) * 0.25,
        "tique_b":  _fm(2000, .03, indice=0.5, decai=60) * 0.25,
    }


NOMES = ["ativar", "concluir", "alerta", "erro", "captura", "ligar", "desligar", "tique_a", "tique_b"]


def _carregar_wav(caminho):
    with wave.open(caminho, "rb") as w:
        canais, largura, taxa = w.getnchannels(), w.getsampwidth(), w.getframerate()
        dados = w.readframes(w.getnframes())
    if largura != 2:
        raise ValueError("só WAV de 16 bits")
    audio = np.frombuffer(dados, dtype=np.int16).astype(np.float32) / 32768.0
    if canais > 1:
        audio = audio.reshape(-1, canais).mean(axis=1)
    return audio * config.VOLUME_EFEITOS, taxa


def som(nome):
    """(áudio float32, taxa) do efeito: o WAV seu em sons/, se existir; senão o gerado."""
    if nome in _cache:
        return _cache[nome]
    caminho = os.path.join(PASTA_SONS, f"{nome}.wav")
    resultado = None
    if os.path.exists(caminho):
        try:
            resultado = _carregar_wav(caminho)
        except Exception as erro:
            print(f"⚠ não consegui usar {caminho}: {erro}. Usando o som gerado.")
    if resultado is None:
        estilo = _classico if config.ESTILO_SONS == "classico" else _futurista
        gerados = estilo()
        if nome not in gerados:
            raise KeyError(nome)
        resultado = (_final(gerados[nome], pico=0.12 if nome.startswith("tique") else 0.32), TAXA)
    _cache[nome] = resultado
    return resultado


def tocar(nome):
    """Toca o efeito e espera terminar. Nomes desconhecidos são ignorados."""
    import sounddevice as sd
    try:
        audio, taxa = som(nome)
    except KeyError:
        return
    sd.play(audio, taxa)
    sd.wait()

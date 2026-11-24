"""
Ethos AI - voz: ouvir (faster-whisper) e falar (Piper).
Aqui não há lógica de conversa; isso fica em cerebro.py.

Vozes (rode NA MESMA PASTA deste arquivo, uma vez cada):
    python -m piper.download_voices pt_BR-faber-medium
"""

import io
import os
import queue
import threading
import time
import wave

import numpy as np
import sounddevice as sd

import config
import efeitos
import memoria
from segmentador import SegmentadorFala
from texto import corrigir_texto, parece_alucinacao

PASTA = os.path.dirname(os.path.abspath(__file__))

# ---------------------------- CARREGAMENTO ----------------------------
# Whisper e vozes só são carregados quando precisam (ou quando a GUI chama
# carregar() em segundo plano na abertura), para a janela abrir na hora.
_whisper = None
_vozes_prontas = False
_kokoro = None
vozes = {}
_trava_whisper = threading.Lock()   # travas SEPARADAS: a voz não espera o Whisper
_trava_vozes = threading.Lock()


def _registrar_dlls_nvidia():
    """No Windows, o pip instala o cuBLAS/cuDNN em site-packages/nvidia/*/bin.
    Avisamos o Python onde estão para o Whisper achar a GPU."""
    if os.name != "nt":
        return
    try:
        import nvidia
    except ImportError:
        return
    for base in list(nvidia.__path__):
        try:
            subpastas = os.listdir(base)
        except OSError:
            continue
        for sub in subpastas:
            pasta = os.path.join(base, sub, "bin")
            if os.path.isdir(pasta):
                os.add_dll_directory(pasta)
                os.environ["PATH"] = pasta + os.pathsep + os.environ.get("PATH", "")


def _criar_whisper():
    """Tenta o modelo configurado (GPU) e, se algo falhar, o plano B (CPU)."""
    from faster_whisper import WhisperModel
    tentativas = [(config.MODELO_WHISPER, config.WHISPER_DEVICE, config.WHISPER_COMPUTE)]
    if tentativas[0] != tuple(config.WHISPER_FALLBACK):
        tentativas.append(tuple(config.WHISPER_FALLBACK))
    ultimo_erro = None
    for modelo, dispositivo, compute in tentativas:
        try:
            if dispositivo == "cuda":
                _registrar_dlls_nvidia()
            w = WhisperModel(modelo, device=dispositivo, compute_type=compute)
            # Aquecimento: força o carregamento das bibliotecas CUDA agora, e não no
            # meio da sua primeira frase (e revela na hora se a GPU não está funcionando).
            list(w.transcribe(np.zeros(config.TAXA, dtype=np.float32),
                              language="pt", vad_filter=False)[0])
            print(f"Whisper pronto: {modelo} em {dispositivo} ({compute})")
            return w
        except Exception as erro:
            print(f"⚠ Whisper {modelo} em {dispositivo} não funcionou: {erro}")
            ultimo_erro = erro
    raise RuntimeError(f"Não consegui carregar o reconhecimento de voz: {ultimo_erro}")


def carregar_whisper():
    global _whisper
    if _whisper is not None:
        return
    with _trava_whisper:
        if _whisper is None:
            print("Carregando reconhecimento de voz...")
            _whisper = _criar_whisper()


def carregar_vozes():
    global _vozes_prontas, _kokoro
    if _vozes_prontas:
        return
    with _trava_vozes:
        if _vozes_prontas:
            return
        from piper import PiperVoice

        print("Carregando vozes...")
        for idioma, arquivo in config.ARQUIVOS_VOZ.items():
            caminho = os.path.join(PASTA, arquivo)
            if os.path.exists(caminho):
                vozes[idioma] = PiperVoice.load(caminho)
            else:
                print(f"⚠ Voz '{arquivo}' não encontrada. Baixe com: "
                      f"python -m piper.download_voices {arquivo.replace('.onnx', '')}")
        if "pt" not in vozes:
            raise RuntimeError("A voz em português é obrigatória. Baixe-a "
                               "(python -m piper.download_voices pt_BR-faber-medium) e abra de novo.")
        _tentar_kokoro()
        _vozes_prontas = True


def _tentar_kokoro():
    """Carrega o Kokoro se existir e se o MOTOR_VOZ pedir (ou para o testar_vozes.py)."""
    global _kokoro
    modelo, vozes_bin = (os.path.join(PASTA, n) for n in ("kokoro-v1.0.onnx", "voices-v1.0.bin"))
    if not (os.path.exists(modelo) and os.path.exists(vozes_bin)):
        if config.MOTOR_VOZ == "kokoro":
            print("⚠ Kokoro pedido, mas faltam kokoro-v1.0.onnx / voices-v1.0.bin na pasta. Usando Piper.")
        return
    try:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(modelo, vozes_bin)
    except Exception as erro:
        print(f"⚠ Não consegui carregar o Kokoro ({erro}). Usando Piper.")


def whisper_pronto():
    return _whisper is not None


def carregar():
    carregar_vozes()      # rápido: primeiro, para ela já poder falar
    carregar_whisper()    # lento (baixa/carrega o modelo na 1ª vez)


# ------------------------------- OUVIR --------------------------------
def _gravar_ate_silencio(espera_maxima=config.ESPERA_MAXIMA,
                         gravacao_maxima=config.GRAVACAO_MAXIMA, verificar_parar=None):
    """Grava do microfone até você ficar em silêncio (ou os limites baterem).
    Devolve o áudio (numpy array) ou None se ninguém falou / foi pedido para parar.
    verificar_parar: função chamada a cada pedaço; se retornar True, interrompe."""
    blocos = []
    falou = False
    silencio = 0.0
    total = 0.0
    passo = 0.1  # lê o microfone em pedaços de 0,1 s

    with sd.InputStream(samplerate=config.TAXA, channels=1, dtype="float32") as mic:
        while True:
            if verificar_parar is not None and verificar_parar():
                return None
            bloco, _ = mic.read(int(config.TAXA * passo))
            blocos.append(bloco)
            total += passo
            volume = float(np.sqrt(np.mean(bloco**2)))

            if volume > config.LIMITE_VOLUME:
                falou = True
                silencio = 0.0
            elif falou:
                silencio += passo
                if silencio >= config.SILENCIO_FINAL:
                    break

            if not falou and total >= espera_maxima:
                return None  # ninguém falou
            if total >= gravacao_maxima:
                break

    return np.concatenate(blocos).flatten()


def _transcrever(audio, idioma_forcado=None):
    """Transcreve um áudio já gravado. Devolve (texto_corrigido, idioma)."""
    carregar_whisper()
    inicio = time.time()
    segmentos, info = _whisper.transcribe(
        audio,
        language=idioma_forcado or config.IDIOMA_VOZ,   # fixo em português: mais preciso
        initial_prompt=config.VOCABULARIO,
        vad_filter=True,
    )
    frase = " ".join(s.text.strip() for s in segmentos).strip()
    print(f"⏱ transcrição: {time.time() - inicio:.1f}s")
    idioma = "pt"
    return corrigir_texto(frase, memoria.memoria.get("correcoes")), idioma


def ouvir(idioma_esperado=None, verificar_parar=None):
    """Grava até você ficar em silêncio e transcreve. Retorna (texto, idioma)."""
    print("🎤 Ouvindo... (fale agora)")
    audio = _gravar_ate_silencio(verificar_parar=verificar_parar)
    if audio is None:
        return "", "pt"
    return _transcrever(audio, idioma_esperado)


def escutar_fala(verificar_parar):
    """Fica com o microfone aberto até você falar e terminar. Devolve o áudio, ou
    None se verificar_parar() virou True antes disso. Não grava nada enquanto a
    Ethos fala (quem chama só chama esta função quando ela já terminou)."""
    segmentador = SegmentadorFala()
    passo = 0.1
    with sd.InputStream(samplerate=config.TAXA, channels=1, dtype="float32") as mic:
        while not verificar_parar():
            bloco, _ = mic.read(int(config.TAXA * passo))
            audio = segmentador.alimentar(bloco.flatten())
            if audio is not None:
                return audio
    return None


def ouvir_uma_fala(idioma_esperado=None, verificar_parar=lambda: False):
    """Modo conversa contínua: espera você falar e devolve (texto, idioma).
    Devolve ("", "pt") se mandaram parar, se foi ruído ou se o Whisper alucinou."""
    audio = escutar_fala(verificar_parar)
    if audio is None:
        return "", "pt"
    frase, idioma = _transcrever(audio, idioma_esperado)
    if parece_alucinacao(frase):
        print(f"(ignorado, parece ruído: {frase!r})")
        return "", idioma
    return frase, idioma


# ------------------------------- FALAR --------------------------------
def aplicar_efeito_jarvis(audio_int16, taxa):
    """Deixa a voz com cara de sistema: eco curto e discreto + leve compressão."""
    x = audio_int16.astype(np.float32)
    x = x / (np.max(np.abs(x)) + 1e-9)
    if config.EFEITO_VOZ <= 0:
        return (x * 0.9).astype(np.float32)
    saida = x.copy()
    for atraso_s, ganho in ((0.035, 0.22), (0.09, 0.10)):
        d = int(atraso_s * taxa)
        saida[d:] += config.EFEITO_VOZ * ganho * x[:-d]
    saida = np.tanh(1.4 * saida) / np.tanh(1.4)  # compressão suave
    return (saida * 0.9).astype(np.float32)


def _sintetizar_kokoro(frase, idioma, voz=None):
    nome, lang = config.VOZ_KOKORO[idioma]
    amostras, taxa = _kokoro.create(frase, voice=voz or nome,
                                    speed=config.VELOCIDADE_KOKORO, lang=lang)
    return np.asarray(amostras, dtype=np.float32), taxa


def _sintetizar_piper(frase, idioma):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as arquivo:
        vozes[idioma].synthesize_wav(frase, arquivo)
    buffer.seek(0)
    with wave.open(buffer, "rb") as arquivo:
        taxa = arquivo.getframerate()
        audio = np.frombuffer(arquivo.readframes(arquivo.getnframes()), dtype=np.int16)
    return audio, taxa


def sintetizar(frase, idioma="pt", motor=None, voz_kokoro=None):
    """Texto -> (áudio float32 com efeito, taxa). Não toca nada.
    `motor` ("piper"/"kokoro") força um motor (usado pelo testar_vozes.py);
    sem ele vale o MOTOR_VOZ, com volta automática para o Piper se o Kokoro faltar."""
    import re
    carregar_vozes()
    explicito = motor is not None
    motor = motor or config.MOTOR_VOZ
    if idioma not in vozes:
        idioma = "pt"
    if idioma == "pt":
        for escrita, som in config.PRONUNCIAS_PT.items():
            frase = re.sub(rf"\b{re.escape(escrita)}\b", som, frase, flags=re.IGNORECASE)

    if motor == "kokoro" and _kokoro is None and explicito:
        raise RuntimeError("Kokoro não está disponível (faltam os arquivos ou o pacote kokoro-onnx).")
    if motor == "kokoro" and _kokoro is not None and idioma in config.VOZ_KOKORO:
        audio, taxa = _sintetizar_kokoro(frase, idioma, voz_kokoro)
    else:
        audio, taxa = _sintetizar_piper(frase, idioma)
    return aplicar_efeito_jarvis(audio, taxa), taxa


def falar(frase, idioma="pt"):
    """Fala uma frase e espera terminar (usado para avisos curtos)."""
    audio, taxa = sintetizar(frase, idioma)
    sd.play(audio, taxa)
    sd.wait()


class Locutor:
    """Fala frases em sequência, em linha de montagem: enquanto uma frase toca,
    a próxima já está sendo sintetizada (some a pausa entre as frases).

        loc = Locutor("pt", ao_comecar=callback)
        loc.dizer("Primeira frase.")
        loc.dizer("Segunda frase.")
        loc.terminar()   # espera tudo ser falado
    """

    def __init__(self, idioma="pt", ao_comecar=None):
        self.idioma = idioma
        self.ao_comecar = ao_comecar          # chamado quando o 1º áudio começa a tocar
        self.cortado = False                  # True depois de cortar(): descarta o resto
        self._frases = queue.Queue()
        self._audios = queue.Queue(maxsize=2)
        self._sintese = threading.Thread(target=self._loop_sintese, daemon=True)
        self._toque = threading.Thread(target=self._loop_toque, daemon=True)
        self._sintese.start()
        self._toque.start()

    def dizer(self, frase):
        if not self.cortado and frase and frase.strip():
            self._frases.put(frase)

    def cortar(self):
        """Interrompe a fala na hora e descarta as frases que faltavam."""
        self.cortado = True
        sd.stop()

    def terminar(self):
        self._frases.put(None)
        self._sintese.join()
        self._toque.join()

    def _loop_sintese(self):
        while True:
            frase = self._frases.get()
            if frase is None:
                self._audios.put(None)
                return
            if self.cortado:
                continue
            try:
                self._audios.put(sintetizar(frase, self.idioma))
            except Exception as erro:
                print(f"⚠ erro ao sintetizar voz: {erro}")

    def _loop_toque(self):
        primeiro = True
        while True:
            item = self._audios.get()
            if item is None:
                return
            if self.cortado:
                continue
            if primeiro:
                primeiro = False
                if self.ao_comecar:
                    self.ao_comecar()
            try:
                sd.play(item[0], item[1])
                sd.wait()
            except Exception as erro:
                print(f"⚠ erro ao tocar áudio: {erro}")


# ------------------------------ SONS ----------------------------------
def tocar_efeito(nome):
    """Efeitos sonoros (veja efeitos.py): ativar, concluir, alerta, erro, captura, ligar, desligar."""
    try:
        efeitos.tocar(nome)
    except Exception as erro:
        print(f"⚠ não consegui tocar o efeito '{nome}': {erro}")


# Tique sutil de "processando" enquanto a IA pensa. Para antes da fala começar
# e nunca toca durante a gravação (para o microfone não captar).
_processando = threading.Event()


def _loop_processando():
    alternar = True
    while _processando.is_set():
        tocar_efeito("tique_a" if alternar else "tique_b")
        alternar = not alternar
        time.sleep(0.7)


def iniciar_som_processando():
    if not config.SOM_PROCESSANDO or _processando.is_set():
        return
    _processando.set()
    threading.Thread(target=_loop_processando, daemon=True).start()


def parar_som_processando():
    _processando.clear()

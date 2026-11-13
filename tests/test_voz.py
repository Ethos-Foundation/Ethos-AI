"""Testa o carregamento (GPU com plano B) e a escolha do motor de voz, com
bibliotecas FALSAS. Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))

import config  # noqa: E402
import ethos_ai_voz as voz  # noqa: E402


class WhisperFalso:
    criados = []
    falha_em = ()                                  # dispositivos que "dão erro"

    bloqueio = None                                # Event: simula download lento

    def __init__(self, modelo, device, compute_type):
        if WhisperFalso.bloqueio is not None:
            WhisperFalso.bloqueio.wait(5)
        if device in WhisperFalso.falha_em:
            raise RuntimeError(f"cublas64_12.dll not found ({device})")
        self.args = (modelo, device, compute_type)
        WhisperFalso.criados.append(self.args)

    def transcribe(self, audio, **kw):
        return iter([]), types.SimpleNamespace(language="pt")


class PiperFalso:
    @staticmethod
    def load(caminho):
        return PiperFalso()

    def synthesize_wav(self, frase, arquivo):
        arquivo.setnchannels(1); arquivo.setsampwidth(2); arquivo.setframerate(22050)
        arquivo.writeframes((np.ones(2205) * 1000).astype(np.int16).tobytes())


class KokoroFalso:
    def create(self, frase, voice, speed, lang):
        self.ultimo = (voice, lang)
        return np.ones(2400, dtype=np.float32) * 0.1, 24000


class TestVoz(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for nome in ("pt.onnx", "en.onnx"):
            open(os.path.join(self.tmp.name, nome), "w").close()
        fw = types.ModuleType("faster_whisper"); fw.WhisperModel = WhisperFalso
        pp = types.ModuleType("piper"); pp.PiperVoice = PiperFalso
        for p in (mock.patch.dict(sys.modules, {"faster_whisper": fw, "piper": pp}),
                  mock.patch.object(voz, "PASTA", self.tmp.name),
                  mock.patch.object(config, "ARQUIVOS_VOZ", {"pt": "pt.onnx", "en": "en.onnx"}),
                  mock.patch.object(config, "MODELO_WHISPER", "large-v3-turbo"),
                  mock.patch.object(config, "WHISPER_DEVICE", "cuda"),
                  mock.patch.object(config, "WHISPER_COMPUTE", "int8_float16"),
                  mock.patch.object(config, "WHISPER_FALLBACK", ("small", "cpu", "int8"))):
            p.start(); self.addCleanup(p.stop)
        voz._whisper, voz._vozes_prontas, voz._kokoro = None, False, None
        voz.vozes.clear()
        WhisperFalso.criados.clear(); WhisperFalso.falha_em = (); WhisperFalso.bloqueio = None
        self.addCleanup(self.tmp.cleanup)

    def test_gpu_funciona(self):
        voz.carregar_whisper()
        self.assertEqual(WhisperFalso.criados, [("large-v3-turbo", "cuda", "int8_float16")])

    def test_gpu_falha_cai_para_cpu(self):
        WhisperFalso.falha_em = ("cuda",)
        voz.carregar_whisper()
        self.assertEqual(WhisperFalso.criados, [("small", "cpu", "int8")])

    def test_tudo_falha_da_erro_claro(self):
        WhisperFalso.falha_em = ("cuda", "cpu")
        with self.assertRaises(RuntimeError):
            voz.carregar_whisper()

    def test_sem_kokoro_usa_piper(self):
        with mock.patch.object(config, "MOTOR_VOZ", "kokoro"):
            audio, taxa = voz.sintetizar("olá", "pt")
        self.assertEqual(taxa, 22050)

    def test_kokoro_explicito_sem_arquivos_avisa(self):
        with self.assertRaises(RuntimeError):
            voz.sintetizar("olá", "pt", motor="kokoro")

    def test_kokoro_quando_disponivel(self):
        voz.carregar_vozes()
        voz._kokoro = KokoroFalso()
        with mock.patch.object(config, "MOTOR_VOZ", "kokoro"):
            audio, taxa = voz.sintetizar("olá", "pt")
        self.assertEqual(taxa, 24000)
        self.assertEqual(voz._kokoro.ultimo, ("pf_dora", "pt-br"))
        self.assertTrue(np.isfinite(audio).all())

    def test_voz_kokoro_escolhida_manualmente(self):
        voz.carregar_vozes()
        voz._kokoro = KokoroFalso()
        voz.sintetizar("olá", "pt", motor="kokoro", voz_kokoro="pm_alex")
        self.assertEqual(voz._kokoro.ultimo[0], "pm_alex")

    def test_voz_fala_mesmo_com_whisper_ainda_carregando(self):
        WhisperFalso.bloqueio = threading.Event()
        t = threading.Thread(target=voz.carregar_whisper, daemon=True)
        t.start()
        try:
            audio, taxa = voz.sintetizar("olá", "pt")      # não pode ficar esperando o download
            self.assertEqual(taxa, 22050)
            self.assertFalse(voz.whisper_pronto())
        finally:
            WhisperFalso.bloqueio.set(); t.join(5)
        self.assertTrue(voz.whisper_pronto())

    def test_vozes_nao_esperam_o_whisper(self):
        voz.carregar_vozes()
        self.assertIsNone(voz._whisper)


if __name__ == "__main__":
    unittest.main()

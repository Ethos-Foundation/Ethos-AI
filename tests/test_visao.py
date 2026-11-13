"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _nome in ("ollama", "requests"):
    try:
        __import__(_nome)
    except ImportError:
        sys.modules[_nome] = types.ModuleType(_nome)

import cerebro  # noqa: E402
import config  # noqa: E402
import ferramentas_visao  # noqa: E402
import memoria  # noqa: E402
import visao  # noqa: E402

JPEG = b"\xff\xd8fake-jpeg"


def resposta(txt):
    return {"message": {"content": txt}}


class TestAnalisar(unittest.TestCase):
    def test_envia_a_imagem_e_limpa_a_resposta(self):
        chamadas = []

        def chat(**kw):
            chamadas.append(kw)
            return resposta("<think>hmm</think>Você está no VS Code com um erro de sintaxe.")

        with mock.patch.object(sys.modules["ollama"], "chat", chat, create=True):
            r = visao.analisar_imagem(JPEG, "o que há de errado?")
        self.assertEqual(r, "Você está no VS Code com um erro de sintaxe.")
        usuario = chamadas[0]["messages"][-1]
        self.assertEqual(usuario["images"], [JPEG])
        self.assertIn("o que há de errado?", usuario["content"])
        self.assertEqual(chamadas[0]["model"], config.MODELO_VISAO)
        self.assertEqual(chamadas[0]["keep_alive"], config.VISAO_KEEP_ALIVE)

    def test_tenta_sem_think_se_o_modelo_nao_aceita(self):
        chamadas = []

        def chat(**kw):
            chamadas.append("think" in kw)
            if "think" in kw:
                raise RuntimeError("model does not support thinking")
            return resposta("Uma página de texto.")

        with mock.patch.object(sys.modules["ollama"], "chat", chat, create=True):
            self.assertEqual(visao.analisar_imagem(JPEG), "Uma página de texto.")
        self.assertEqual(chamadas, [True, False])

    def test_modelo_nao_instalado_diz_o_que_fazer(self):
        def chat(**kw):
            raise RuntimeError("model 'qwen3-vl:4b' not found")

        with mock.patch.object(sys.modules["ollama"], "chat", chat, create=True):
            r = visao.analisar_imagem(JPEG, modelo="qwen3-vl:4b")
        self.assertIn("ollama pull qwen3-vl:4b", r)

    def test_ollama_fechado(self):
        def chat(**kw):
            raise ConnectionError("[WinError 10061] recusada")

        with mock.patch.object(sys.modules["ollama"], "chat", chat, create=True):
            self.assertIn("Ollama", visao.analisar_imagem(JPEG))

    def test_resposta_vazia(self):
        with mock.patch.object(sys.modules["ollama"], "chat", lambda **kw: resposta(""), create=True):
            self.assertIn("não devolveu", visao.analisar_imagem(JPEG))

    def test_olhar_tela_captura_e_analisa(self):
        with mock.patch.object(visao, "capturar_tela", lambda: JPEG), \
             mock.patch.object(sys.modules["ollama"], "chat", lambda **kw: resposta("ok"), create=True):
            self.assertEqual(ferramentas_visao.executar("ver_tela", {"pergunta": "x"}), "ok")

    def test_sem_pillow_avisa(self):
        def falha():
            raise ImportError("PIL")
        with mock.patch.object(visao, "capturar_tela", falha):
            self.assertIn("pip install Pillow", visao.olhar_tela())


@unittest.skipUnless(shutil.which("xvfb-run"), "precisa do xvfb-run (tela virtual) para capturar de verdade")
class TestCapturaReal(unittest.TestCase):
    def test_processo_filho_gera_um_jpeg_reduzido(self):
        from PIL import Image
        destino = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
        try:
            proc = subprocess.run(
                ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable,
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "visao.py"),
                 "--capturar", destino, "1280", "0"], capture_output=True, timeout=60)
            if proc.returncode != 0:
                self.skipTest(f"captura indisponível neste ambiente: {proc.stderr.decode()[-200:]}")
            imagem = Image.open(destino)
            self.assertEqual(imagem.format, "JPEG")
            self.assertLessEqual(max(imagem.size), 1280)
        finally:
            os.remove(destino)


class TestComandoNoCerebro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(memoria, "ARQUIVO", os.path.join(self.tmp.name, "m.json")),
                  mock.patch.object(config, "MEMORIA_AUTOMATICA", False),
                  mock.patch.object(config, "PROB_GIRIA", 0.0),
                  mock.patch.object(config, "PROB_INVENTAR_GIRIA", 0.0)):
            p.start(); self.addCleanup(p.stop)
        cerebro.trocar_modo("conversa")

    def test_avisa_antes_e_depois_descreve(self):
        executadas = []

        def chat(**kw):
            yield {"message": {"content": "Pelo visto você está no VS Code.", "tool_calls": None}}

        with mock.patch.object(sys.modules["ollama"], "chat", chat, create=True), \
             mock.patch.object(cerebro, "executar_ferramenta",
                               lambda n, a: executadas.append((n, dict(a))) or "VS Code com erro."):
            pedacos = list(cerebro.conversar("olha minha tela"))
        self.assertEqual(pedacos[0], "Um instante, vou olhar. ")           # fala antes de demorar
        self.assertEqual(executadas, [("ver_tela", {"pergunta": "olha minha tela"})])
        self.assertIn("VS Code", "".join(pedacos))


if __name__ == "__main__":
    unittest.main()

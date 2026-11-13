"""Teste de fumaça da janela com tkinter FALSO: pega erros de nome/lógica no chat e no pet.
(Não vê problemas visuais: isso só abrindo a janela de verdade.)
Rode na pasta do projeto:  python -m unittest discover tests -v"""

import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def tk_falso():
    tk = mock.MagicMock(name="tkinter")
    texto = mock.MagicMock(name="Text")
    texto.yview.return_value = (0.0, 1.0)
    texto.get.return_value = ""
    tk.Text.side_effect = lambda *a, **k: texto
    tk.Tk.return_value.winfo_screenwidth.return_value = 1920
    tk.Tk.return_value.winfo_screenheight.return_value = 1080
    tk.Tk.return_value.state.return_value = "normal"
    tk.Canvas.return_value.bbox.return_value = (0, 0, 100, 30)
    tk.TclError = type("TclError", (Exception,), {})
    tk._texto = texto
    return tk


class TestGuiFumaca(unittest.TestCase):
    def setUp(self):
        self.tk = tk_falso()
        modulos = {"tkinter": self.tk, "tkinter.ttk": mock.MagicMock(), "sounddevice": mock.MagicMock()}
        for nome in ("ollama", "requests"):
            try:
                __import__(nome)
            except ImportError:
                modulos[nome] = types.ModuleType(nome)
        patcher = mock.patch.dict(sys.modules, modulos)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        import memoria, preferencias
        import ethos_ai_gui as gui
        for p in (mock.patch.object(gui, "ARQUIVO_CHAT", os.path.join(self.tmp.name, "chat.json")),
                  mock.patch.object(preferencias, "ARQUIVO", os.path.join(self.tmp.name, "prefs.json")),
                  mock.patch.object(memoria, "ARQUIVO", os.path.join(self.tmp.name, "mem.json")),
                  mock.patch.dict(memoria.memoria, {"correcoes": {}}, clear=False)):
            p.start(); self.addCleanup(p.stop)
        self.gui, self.memoria = gui, memoria
        self.app = gui.App(self.tk.Tk())

    def test_conversa_completa_no_chat(self):
        a = self.app
        a._tratar({"usuario": "faz um código"})
        for t in ("Pronto, ", "está na tela."):
            a._tratar({"token": t})
        a._tratar({"conteudo": "x = a * b"})
        a._tratar({"fim": True})
        self.assertEqual([i["papel"] for i in a.registro], ["usuario", "ethos"])
        self.assertEqual(a.registro[1]["texto"], "Pronto, está na tela.")
        self.assertEqual(a.registro[1]["codigo"], "x = a * b")
        salvo = json.load(open(self.gui.ARQUIVO_CHAT, encoding="utf-8"))
        self.assertEqual(len(salvo), 2)
        self.assertFalse(a.bolha)

    def test_fim_sem_resposta_nao_quebra(self):
        self.app._tratar({"fim": True})
        self.app._tratar({"estado": "espera", "continuo": False, "fim": True})

    def test_erro_vira_linha_de_sistema(self):
        self.app._tratar({"voce": "Não consegui falar com o Ollama. Ele está aberto?"})
        self.assertEqual(self.app.registro, [])   # avisos do sistema não entram no histórico

    def test_historico_e_recarregado(self):
        self.app._tratar({"usuario": "oi"})
        self.app._tratar({"token": "olá"})
        self.app._tratar({"fim": True})
        app2 = self.gui.App(self.tk.Tk())
        self.assertEqual(len(app2.registro), 2)

    def test_comando_corrigir(self):
        self.tk._texto.get.return_value = "/corrigir e maio = e-mail"
        self.app.enviar_entrada()
        self.assertEqual(self.memoria.memoria["correcoes"].get("e maio"), "e-mail")

    def test_fechar_janela_com_pet_so_esconde(self):
        self.app.pet.ativo = True
        self.app.ao_fechar()
        self.app.raiz.withdraw.assert_called()
        self.app.raiz.destroy.assert_not_called()

    def test_fechar_janela_sem_pet_encerra(self):
        self.app.pet.ativo = False
        self.app.ao_fechar()
        self.app.raiz.destroy.assert_called()

    def test_balao_do_pet_recebe_a_resposta(self):
        with mock.patch.object(self.app.pet, "mostrar_fala") as m:
            self.app._tratar({"usuario": "oi"})
            self.app._tratar({"token": "Boa noite, meu caro."})
            self.app._tratar({"fim": True})
        m.assert_called_once_with("Boa noite, meu caro.")

    def test_pet_clique_e_arrasto(self):
        pet = self.app.pet
        pet.orq = mock.MagicMock()
        pet.janela.winfo_x.return_value, pet.janela.winfo_y.return_value = 50, 60
        e = types.SimpleNamespace(x_root=100, y_root=100)
        pet._apertou(e); pet._soltou(e)                       # clique parado
        pet.orq.ao_clicar.assert_called_once()
        pet.orq.reset_mock()
        pet._apertou(e); pet._arrastou(types.SimpleNamespace(x_root=160, y_root=140)); pet._soltou(e)
        pet.orq.ao_clicar.assert_not_called()                 # arrastar não liga o microfone

    def test_pet_balao_e_animacao(self):
        pet = self.app.pet
        pet.mostrar_fala("texto " * 60)                       # longo: é truncado
        self.assertLessEqual(len(pet.fala), 150)
        pet._animar()


if __name__ == "__main__":
    unittest.main()

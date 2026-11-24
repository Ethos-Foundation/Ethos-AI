"""Testa o fluxo completo (cérebro + orquestrador) com voz e modelo FALSOS.
Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _nome in ("ollama", "requests"):          # só para rodar sem as bibliotecas instaladas
    try:
        __import__(_nome)
    except ImportError:
        sys.modules[_nome] = types.ModuleType(_nome)

import cerebro  # noqa: E402
import config  # noqa: E402
import memoria  # noqa: E402
from orquestrador import Orquestrador  # noqa: E402


class LocutorFalso:
    instancias = []

    def __init__(self, idioma="pt", ao_comecar=None):
        self.frases, self.cortado, self.ao_comecar = [], False, ao_comecar
        LocutorFalso.instancias.append(self)

    def dizer(self, frase):
        if not self.cortado:
            self.frases.append(frase)
            if len(self.frases) == 1 and self.ao_comecar:
                self.ao_comecar()

    def cortar(self):
        self.cortado = True

    def terminar(self):
        pass


class VozFalsa:
    Locutor = LocutorFalso

    def __init__(self):
        self.falado, self.escutas = [], []

    def whisper_pronto(self): return True
    def iniciar_som_processando(self): pass
    def parar_som_processando(self): pass
    def tocar_efeito(self, nome): pass
    def falar(self, frase, idioma="pt"): self.falado.append(frase)

    def ouvir_uma_fala(self, idioma_esperado=None, verificar_parar=lambda: False):
        return self.escutas.pop(0) if self.escutas else ("", "pt")


def modelo_falso(*pedacos):
    def chat(**kw):
        for p in pedacos:
            yield {"message": {"content": p, "tool_calls": None}}
    return chat


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for p in (mock.patch.object(memoria, "ARQUIVO", os.path.join(self.tmp.name, "m.json")),
                  mock.patch.object(config, "MEMORIA_AUTOMATICA", False),
                  mock.patch.object(config, "PROB_GIRIA", 0.0),
                  mock.patch.object(config, "PROB_INVENTAR_GIRIA", 0.0),
                  mock.patch.object(config, "PAUSA_POS_FALA", 0.0)):
            p.start(); self.addCleanup(p.stop)
        cerebro.trocar_modo("conversa")
        LocutorFalso.instancias.clear()
        self.msgs = []
        self.voz = VozFalsa()
        self.orq = Orquestrador(lambda **m: self.msgs.append(m), self.voz)

    def tearDown(self):
        self.tmp.cleanup()

    def tela(self):
        return "".join(m.get("token", "") for m in self.msgs)


class TestResponder(Base):
    def test_fala_frase_a_frase_sem_emoji(self):
        with mock.patch.object(cerebro.ollama, "chat", modelo_falso(
                "Ora, que surpresa 😀 você aqui. ", "Vamos ao que interessa, então."), create=True):
            self.orq.responder("oi", "pt")
        loc = LocutorFalso.instancias[0]
        self.assertEqual(loc.frases, ["Ora, que surpresa  você aqui.", "Vamos ao que interessa, então."])
        self.assertNotIn("😀", self.tela())
        self.assertIn({"estado": "falando"}, self.msgs)

    def test_conteudo_vai_para_a_aba(self):
        with mock.patch.object(cerebro.ollama, "chat", modelo_falso("Pronto, está na tela.---CONTEUDO---\n", "x = a * b"), create=True):
            self.orq.responder("faz um código", "pt")
        conteudo = "".join(m.get("conteudo", "") for m in self.msgs)
        self.assertIn("x = a * b", conteudo)
        self.assertEqual(LocutorFalso.instancias[0].frases, ["Pronto, está na tela."])

    def test_interrupcao_para_de_gerar(self):
        consumidos = []

        def chat(**kw):
            for i in range(50):
                consumidos.append(i)
                if i == 3:
                    self.orq.interromper_fala()
                yield {"message": {"content": f"palavra{i} ", "tool_calls": None}}

        with mock.patch.object(cerebro.ollama, "chat", chat, create=True):
            self.orq.responder("conta uma história longa", "pt")
        self.assertLess(len(consumidos), 10)


class TestAindaCarregando(Base):
    def test_avisa_em_vez_de_ficar_mudo(self):
        self.voz.whisper_pronto = lambda: False
        self.orq.tarefa("ouvir", None)
        self.assertTrue(any("carregando" in m.get("voce", "") for m in self.msgs))
        self.orq.alternar_conversa()
        self.assertFalse(self.orq.conversa_ativa.is_set())


class TestHistoricoComFerramentas(Base):
    def test_comando_claro_executa_a_ferramenta_e_fica_no_historico(self):
        executadas = []
        envios = []

        def chat(**kw):
            envios.append(kw["messages"])
            yield {"message": {"content": "Aberto, como pedido.", "tool_calls": None}}

        with mock.patch.object(cerebro.ollama, "chat", chat, create=True), \
             mock.patch.object(cerebro, "executar_ferramenta", lambda n, a: executadas.append((n, dict(a))) or "Abri o YouTube."):
            "".join(cerebro.conversar("abre o youtube"))
            "".join(cerebro.conversar("e agora abre o google"))
        self.assertEqual(executadas, [("abrir_site", {"url_ou_nome": "youtube"}),
                                      ("abrir_site", {"url_ou_nome": "google"})])
        # na 2ª pergunta o modelo enxerga a chamada de ferramenta do 1º turno
        papeis = [m["role"] for m in envios[1]]
        self.assertIn("tool", papeis)
        self.assertTrue(any(m.get("tool_calls") for m in envios[1] if m["role"] == "assistant"))

    def test_historico_limpo_para_o_curador_continua_so_texto(self):
        with mock.patch.object(cerebro.ollama, "chat", modelo_falso("Certo."), create=True):
            "".join(cerebro.conversar("oi"))
        self.assertEqual([m["role"] for m in cerebro.estado["historico"]], ["user", "assistant"])


class TestAvisoDeLembrete(Base):
    ITEM = {"id": 1, "texto": "tomar água", "quando": "2026-11-05T14:00:00", "repetir": None}

    def setUp(self):
        super().setUp()
        self.efeitos = []
        self.voz.tocar_efeito = lambda n: self.efeitos.append(n)

    def test_fala_o_aviso_quando_livre(self):
        self.orq.anunciar(self.ITEM)
        for _ in range(50):
            if LocutorFalso.instancias: break
            time.sleep(0.05)
        time.sleep(0.1)
        self.assertIn("tomar água", " ".join(LocutorFalso.instancias[0].frases))
        self.assertIn("alerta", self.efeitos)
        self.assertIn("tomar água", self.tela())
        self.assertFalse(self.orq.ocupado.locked())

    def test_com_voz_muda_so_mostra_e_toca_o_som(self):
        self.orq.falar_respostas = False
        self.orq.anunciar(self.ITEM)
        time.sleep(0.3)
        self.assertEqual(LocutorFalso.instancias, [])
        self.assertIn("tomar água", self.tela())
        self.assertIn("alerta", self.efeitos)

    def test_espera_ela_terminar_de_falar(self):
        self.orq.ocupado.acquire()                       # ela está ocupada
        self.orq.anunciar(self.ITEM)
        time.sleep(0.3)
        self.assertEqual(LocutorFalso.instancias, [])    # ainda não falou
        self.orq.ocupado.release()
        for _ in range(50):
            if LocutorFalso.instancias: break
            time.sleep(0.05)
        self.assertEqual(len(LocutorFalso.instancias), 1)

    def test_na_conversa_continua_o_laco_avisa(self):
        chamadas = []
        original = self.voz.ouvir_uma_fala

        def ouvir(**kw):
            chamadas.append(1)
            if len(chamadas) == 1:
                self.orq.anunciar(self.ITEM)             # chega um lembrete enquanto ela escuta
                self.assertTrue(kw["verificar_parar"]())  # e a escuta é interrompida para avisar
            else:
                self.orq.conversa_ativa.clear()
            return original(**kw)
        self.voz.ouvir_uma_fala = ouvir
        self.orq.conversa_ativa.set()
        self.orq.loop_conversa()
        self.assertEqual(len(LocutorFalso.instancias), 1)
        self.assertIn("tomar água", " ".join(LocutorFalso.instancias[0].frases))


class TestLigacoesDaFase1(Base):
    def setUp(self):
        super().setUp()
        self.efeitos = []
        self.voz.tocar_efeito = lambda n: self.efeitos.append(n)

    def test_abrir_algo_faz_a_janela_recuar(self):
        import ferramentas_sistema
        ferramentas_sistema.ao_abrir()
        self.assertIn({"recuar": True}, self.msgs)

    def test_ver_tela_da_retorno_ao_usuario(self):
        import visao
        with mock.patch.object(time, "sleep"):
            visao.ao_evento("capturando")
            visao.ao_evento("capturada")
        self.assertIn({"estado": "olhando", "recuar": True}, self.msgs)           # recua e mostra o status
        self.assertEqual(self.efeitos, ["captura"])                                  # som de "clique"
        self.assertTrue(any("Capturei a tela" in m.get("voce", "") for m in self.msgs))

    def test_avisos_do_sistema_aparecem_depois_da_resposta(self):
        cerebro.estado["avisos"].append("Arquivo salvo em C:\\x\\a.py.")
        with mock.patch.object(cerebro.ollama, "chat", modelo_falso("Pronto."), create=True):
            self.orq.responder("oi", "pt")
        indice_fim = self.msgs.index({"fim": True})
        self.assertIn({"voce": "Arquivo salvo em C:\\x\\a.py."}, self.msgs[indice_fim:])

    def test_erro_toca_o_som_de_erro(self):
        def chat(**kw):
            raise ConnectionError("recusada")
            yield
        with mock.patch.object(cerebro.ollama, "chat", chat, create=True):
            self.orq.tarefa("texto", "oi")
        self.assertIn("erro", self.efeitos)

    def test_conversa_continua_toca_ligar_e_desligar(self):
        original = self.voz.ouvir_uma_fala

        def ouvir(**kw):
            self.orq.conversa_ativa.clear()
            return original(**kw)
        self.voz.ouvir_uma_fala = ouvir
        self.orq.conversa_ativa.set()
        self.orq.loop_conversa()
        self.assertEqual(self.efeitos[0], "ligar")
        self.assertEqual(self.efeitos[-1], "desligar")


class TestSemVoz(Base):
    def test_chat_so_de_texto_nao_cria_locutor(self):
        self.orq.falar_respostas = False
        with mock.patch.object(cerebro.ollama, "chat", modelo_falso("Resposta só escrita."), create=True):
            self.orq.responder("oi", "pt")
        self.assertEqual(LocutorFalso.instancias, [])
        self.assertIn("Resposta só escrita.", self.tela())
        self.assertIn({"fim": True}, self.msgs)

    def test_clique_no_pet_liga_o_microfone(self):
        chamadas = []
        self.orq.acao = lambda a, d: chamadas.append(a)
        self.orq.ao_clicar()
        self.assertEqual(chamadas, ["ouvir"])

    def test_clique_no_pet_corta_a_fala(self):
        self.orq.locutor_atual = LocutorFalso()
        self.orq.ao_clicar()
        self.assertTrue(self.orq.locutor_atual.cortado)


class TestErros(Base):
    def test_ollama_fechado_vira_frase_clara(self):
        def chat(**kw):
            raise ConnectionError("[WinError 10061] conexão recusada")
            yield
        with mock.patch.object(cerebro.ollama, "chat", chat, create=True):
            self.orq.tarefa("texto", "oi")
        self.assertTrue(any("Ollama" in m.get("voce", "") for m in self.msgs))
        self.assertTrue(any("Ollama" in f for f in self.voz.falado))
        self.assertFalse(self.orq.ocupado.locked())          # não trava depois do erro


class TestConversaContinua(Base):
    def test_ouve_responde_e_desliga(self):
        self.voz.escutas = [("que dia é hoje", "pt")]
        original = self.voz.ouvir_uma_fala

        def ouvir(**kw):
            r = original(**kw)
            if r[0] == "":                      # 2ª rodada: o usuário desliga
                self.orq.conversa_ativa.clear()
            return r
        self.voz.ouvir_uma_fala = ouvir
        self.orq.conversa_ativa.set()
        with mock.patch.object(cerebro.ollama, "chat", modelo_falso("não usado"), create=True):
            self.orq.loop_conversa()
        self.assertTrue(any(m.get("usuario") == "que dia é hoje" for m in self.msgs))
        self.assertIn({"continuo": True}, self.msgs)
        self.assertIn({"estado": "espera", "continuo": False, "fim": True}, self.msgs)
        self.assertFalse(self.orq.ocupado.locked())


if __name__ == "__main__":
    unittest.main()

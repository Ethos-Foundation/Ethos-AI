"""Testes da Fase 1: arquivos, erros de ferramenta, tela sem memória, sarcasmo, curador, sons, vigia.
Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import struct
import sys
import tempfile
import time
import types
import unittest
import wave
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _nome in ("ollama", "requests"):
    try:
        __import__(_nome)
    except ImportError:
        sys.modules[_nome] = types.ModuleType(_nome)

import cerebro  # noqa: E402
import config  # noqa: E402
import efeitos  # noqa: E402
import ferramentas_sistema as fs  # noqa: E402
import memoria  # noqa: E402
import registro  # noqa: E402
import texto  # noqa: E402


def modelo(*rodadas):
    """Modelo falso: cada chamada devolve a próxima 'rodada' (lista de pedaços de texto ou tool_calls)."""
    chamadas = []

    def chat(**kw):
        chamadas.append(kw)
        rodada = rodadas[min(len(chamadas) - 1, len(rodadas) - 1)]
        for item in rodada:
            if isinstance(item, str):
                yield {"message": {"content": item, "tool_calls": None}}
            else:
                yield {"message": {"content": "", "tool_calls": [{"function": item}]}}
    chat.chamadas = chamadas
    return chat


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = os.path.realpath(os.path.join(self.tmp.name, "projetos"))
        os.makedirs(self.pasta)
        for p in (mock.patch.object(memoria, "ARQUIVO", os.path.join(self.tmp.name, "m.json")),
                  mock.patch.dict(memoria.memoria, {"fatos": {}, "girias": {}, "dialeto": {}, "correcoes": {},
                                                    "tarefas": [], "eventos": []}, clear=True),
                  mock.patch.object(config, "MEMORIA_AUTOMATICA", False),
                  mock.patch.object(config, "PROB_GIRIA", 0.0),
                  mock.patch.object(config, "PROB_INVENTAR_GIRIA", 0.0),
                  mock.patch.object(config, "PASTA_PROJETOS", self.pasta),
                  mock.patch.object(fs, "ao_abrir", None),
                  mock.patch.object(fs, "_criados", set()),
                  mock.patch.object(fs.subprocess, "Popen")):
            p.start(); self.addCleanup(p.stop)
        cerebro.trocar_modo("conversa")
        cerebro.estado["ultimo_conteudo"], cerebro.estado["avisos"] = "", []
        self.addCleanup(lambda: cerebro.definir_sarcasmo(1))

    def rodar(self, pergunta, chat):
        with mock.patch.object(sys.modules["ollama"], "chat", chat, create=True):
            return "".join(cerebro.conversar(pergunta))


class TestErrosSemReescrever(Base):
    def test_falha_de_comando_claro_nao_chama_o_modelo(self):
        chat = modelo(["não deveria ser usado"])
        r = self.rodar("abre a pasta fantasma", chat)
        self.assertEqual(r, "Não encontrei a pasta 'fantasma'.")
        self.assertEqual(chat.chamadas, [])

    def test_falha_de_ferramenta_chamada_pelo_modelo_e_mostrada_como_e(self):
        chat = modelo([{"name": "criar_arquivo_codigo", "arguments": {"caminho": "x.py", "conteudo": ""}}],
                      ["Criei o arquivo com sucesso!"])
        r = self.rodar("faz um arquivo", chat)
        self.assertIn("veio vazio", r)
        self.assertNotIn("sucesso", r)
        self.assertEqual(len(chat.chamadas), 1)                 # sem 2ª rodada para o modelo "enfeitar"
        self.assertEqual(os.listdir(self.pasta), [])

    def test_ver_tela_com_modelo_ausente_mostra_o_comando(self):
        falha = texto.Falha("O modelo de visão qwen3-vl:4b não está instalado. Rode no terminal: ollama pull qwen3-vl:4b")
        chat = modelo(["Tá tudo bem, o Ethos não vê a tela"])
        with mock.patch.object(cerebro, "executar_ferramenta", lambda n, a: falha):
            r = self.rodar("olha minha tela", chat)
        self.assertTrue(r.endswith("ollama pull qwen3-vl:4b"))
        self.assertNotIn("Tá tudo bem", r)
        self.assertEqual(chat.chamadas, [])


class TestTelaSemMemoria(Base):
    def test_pedido_de_tela_nao_leva_a_memoria(self):
        memoria.memoria["fatos"]["reuniao"] = "professor Stefan amanhã"
        chat = modelo(["A tela mostra um editor."])
        with mock.patch.object(cerebro, "executar_ferramenta", lambda n, a: "Editor de código aberto."):
            self.rodar("olha minha tela", chat)
        ultimo_usuario = [m for m in chat.chamadas[0]["messages"] if m["role"] == "user"][-1]["content"]
        self.assertNotIn("Stefan", ultimo_usuario)
        self.assertNotIn("Contexto interno", ultimo_usuario)

    def test_conversa_normal_continua_com_memoria(self):
        memoria.memoria["fatos"]["curso"] = "engenharia"
        chat = modelo(["Oi."])
        self.rodar("oi, tudo bem?", chat)
        self.assertIn("engenharia", [m for m in chat.chamadas[0]["messages"] if m["role"] == "user"][-1]["content"])


class TestArquivos(Base):
    def test_criar_arquivo_ethos_gera_o_conteudo_e_grava_uma_vez(self):
        chat = modelo(["Pronto, já fiz.---CONTEUDO---\n```python\nprint('oi')\n```"])
        r = self.rodar("cria um arquivo ola.py com um hello world", chat)
        self.assertEqual(os.listdir(self.pasta), ["ola.py"])
        self.assertEqual(open(os.path.join(self.pasta, "ola.py"), encoding="utf-8").read(), "print('oi')\n")
        self.assertIsNone(chat.chamadas[0]["tools"])              # o modelo não recebe ferramentas: sem chamada dupla
        self.assertTrue(any("Arquivo salvo" in a for a in cerebro.pegar_avisos()))
        self.assertIn("---CONTEUDO---", r)

    def test_salvar_o_que_acabou_de_escrever_em_outra_pasta(self):
        self.rodar("escreve um poema curto", modelo(["Pronto.---CONTEUDO---\nRosas são vermelhas"]))
        destino = os.path.join(self.pasta, "docs")
        os.makedirs(destino)
        chat = modelo(["Salvo, meu caro."])
        with mock.patch.object(fs, "_pasta_conhecida", lambda n: self.pasta if n == "area de trabalho" else None), \
             mock.patch.object(fs.os.path, "expanduser", lambda p: self.pasta):
            self.rodar("salva isso como poema.txt na pasta docs", chat)
        self.assertEqual(open(os.path.join(destino, "poema.txt"), encoding="utf-8").read(), "Rosas são vermelhas\n")

    def test_salvar_sem_nada_para_salvar(self):
        r = self.rodar("salva isso como x.txt", modelo(["Salvo."]))
        self.assertIn("Não tenho nenhum conteúdo", r)

    def test_criar_em_pasta_inexistente(self):
        with mock.patch.object(fs, "_pasta_conhecida", lambda n: None), \
             mock.patch.object(fs.os.path, "expanduser", lambda p: self.tmp.name):
            chat = modelo(["x"])
            r = self.rodar("cria um arquivo a.py na pasta fantasma", chat)
        self.assertIn("Não encontrei a pasta", r)
        self.assertEqual(chat.chamadas, [])


class TestSarcasmo(Base):
    def test_niveis_mudam_o_prompt(self):
        cerebro.definir_sarcasmo(0)
        p0 = cerebro.MODOS["conversa"]["prompt"]
        cerebro.definir_sarcasmo(3)
        p3 = cerebro.MODOS["conversa"]["prompt"]
        self.assertIn("Sem sarcasmo", p0)
        self.assertIn("sarcástica", p3)
        self.assertNotEqual(p0, p3)

    def test_limites(self):
        self.assertEqual(cerebro.definir_sarcasmo(99), 3)
        self.assertEqual(cerebro.definir_sarcasmo(-5), 0)

    def test_padrao_e_leve(self):
        self.assertEqual(config.NIVEL_SARCASMO, 1)


class TestCuradorSemDuplicatas(Base):
    def test_dez_reunioes_repetidas_viram_uma(self):
        dados = {"eventos": [{"texto": "Reunião com o professor Stefan amanhã", "data": "2026-11-05"}]}
        anotados = [cerebro.aplicar_curadoria(dados) for _ in range(10)]
        self.assertEqual(sum(len(a) for a in anotados), 1)
        self.assertEqual(len(memoria.memoria["eventos"]), 1)

    def test_evento_muito_curto_e_ignorado(self):
        self.assertEqual(cerebro.aplicar_curadoria({"eventos": [{"texto": "reunião", "data": ""}]}), [])

    def test_fato_igual_com_outra_chave_nao_duplica(self):
        cerebro.aplicar_curadoria({"fatos": [{"chave": "curso", "valor": "Engenharia Elétrica"}]})
        self.assertEqual(cerebro.aplicar_curadoria({"fatos": [{"chave": "graduação", "valor": "engenharia eletrica."}]}), [])

    def test_dialeto_dela_e_anotado(self):
        self.assertEqual(cerebro.aplicar_curadoria({"dialeto": [{"termo": "quebra-lógica", "significado": "coisa sem sentido"}]}),
                         ["expressão dela: quebra-lógica"])


class TestMemoriaGerenciamento(Base):
    def test_adicionar_editar_remover(self):
        self.assertTrue(memoria.adicionar_item("fato", "time", "Sport")[0])
        self.assertFalse(memoria.adicionar_item("evento", "ontem", "algo")[0])        # data inválida
        self.assertTrue(memoria.adicionar_item("evento", "2026-11-20", "Prova de física")[0])
        self.assertTrue(memoria.editar_item("fato", "time", "time do coração", "Sport Recife")[0])
        self.assertEqual(memoria.memoria["fatos"], {"time do coração": "Sport Recife"})
        self.assertTrue(memoria.remover_item("evento", 0))
        self.assertEqual(memoria.memoria["eventos"], [])

    def test_editar_evento_mantem_a_ordem(self):
        memoria.adicionar_item("evento", "2026-11-01", "primeiro evento aqui")
        memoria.adicionar_item("evento", "2026-12-01", "segundo evento aqui")
        memoria.editar_item("evento", 0, "2027-01-01", "primeiro evento movido")
        self.assertEqual([e["texto"] for e in memoria.memoria["eventos"]], ["segundo evento aqui", "primeiro evento movido"])

    def test_remover_duplicados_do_que_ja_esta_la(self):
        for _ in range(5):
            memoria.adicionar_item("evento", "2026-11-05", "Reunião com o professor Stefan")
        memoria.adicionar_item("fato", "a", "Gosto de café")
        memoria.adicionar_item("fato", "b", "gosto de cafe")
        r = memoria.remover_duplicados()
        self.assertEqual((r["eventos"], r["fatos"]), (4, 1))

    def test_listar_tudo_traz_todos_os_tipos(self):
        memoria.adicionar_item("fato", "a", "b"); memoria.adicionar_item("giria", "tipo", "mais ou menos")
        memoria.adicionar_item("dialeto", "x", "y"); memoria.adicionar_item("correcao", "e maio", "e-mail")
        memoria.adicionar_item("tarefa", "pendente", "estudar")
        self.assertEqual({i["tipo"] for i in memoria.listar_tudo()}, {"fato", "giria", "dialeto", "correcao", "tarefa"})


class TestEfeitos(unittest.TestCase):
    def setUp(self):
        efeitos._cache.clear()
        self.addCleanup(efeitos._cache.clear)

    def test_todos_os_sons_dos_dois_estilos_sao_validos(self):
        for estilo in ("futurista", "classico"):
            with mock.patch.object(config, "ESTILO_SONS", estilo):
                efeitos._cache.clear()
                for nome in efeitos.NOMES:
                    audio, taxa = efeitos.som(nome)
                    self.assertTrue(np.isfinite(audio).all(), (estilo, nome))
                    self.assertTrue(0 < np.max(np.abs(audio)) <= 1.0, (estilo, nome))
                    self.assertTrue(0.02 < len(audio) / taxa < 1.5, (estilo, nome))

    def test_wav_do_usuario_substitui_o_som(self):
        with tempfile.TemporaryDirectory() as pasta:
            with wave.open(os.path.join(pasta, "alerta.wav"), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
                w.writeframes(struct.pack("<2205h", *([8000] * 2205)))
            with mock.patch.object(efeitos, "PASTA_SONS", pasta):
                audio, taxa = efeitos.som("alerta")
        self.assertEqual(taxa, 22050)
        self.assertEqual(len(audio), 2205)

    def test_wav_ruim_cai_para_o_gerado(self):
        with tempfile.TemporaryDirectory() as pasta:
            open(os.path.join(pasta, "erro.wav"), "wb").write(b"isso nao e um wav")
            with mock.patch.object(efeitos, "PASTA_SONS", pasta):
                audio, taxa = efeitos.som("erro")
        self.assertEqual(taxa, efeitos.TAXA)

    def test_nome_desconhecido_nao_quebra(self):
        with mock.patch.dict(sys.modules, {"sounddevice": mock.MagicMock()}):
            efeitos.tocar("nao_existe")


class TestVigia(unittest.TestCase):
    def test_avisa_uma_vez_quando_trava_e_rearma_depois(self):
        avisos = []
        v = registro.VigiaDeTravamento(limite=0.2, ao_travar=avisos.append)
        v.verificar()
        self.assertEqual(avisos, [])
        time.sleep(0.3)
        v.verificar(); v.verificar()
        self.assertEqual(len(avisos), 1)
        v.batida(); v.verificar()
        time.sleep(0.3)
        v.verificar()
        self.assertEqual(len(avisos), 2)

    def test_resumo_corta_texto_longo(self):
        self.assertEqual(len(registro.resumo("a" * 500, 50)), 50)


if __name__ == "__main__":
    unittest.main()

"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import datetime as dt
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ferramentas_lembretes as fl  # noqa: E402
import lembretes  # noqa: E402

AGORA = dt.datetime(2026, 11, 5, 14, 0, 0)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(lembretes, "ARQUIVO", os.path.join(self.tmp.name, "l.json"))
        p.start(); self.addCleanup(p.stop)


class TestArmazenamento(Base):
    def test_adicionar_listar_cancelar(self):
        a = lembretes.adicionar("a", AGORA + dt.timedelta(hours=2))
        b = lembretes.adicionar("b", AGORA + dt.timedelta(hours=1))
        self.assertEqual([i["texto"] for i in lembretes.listar()], ["b", "a"])    # por horário
        self.assertTrue(lembretes.cancelar(a["id"]))
        self.assertFalse(lembretes.cancelar(999))
        self.assertEqual([i["id"] for i in lembretes.listar()], [b["id"]])

    def test_arquivo_corrompido_nao_quebra(self):
        open(lembretes.ARQUIVO, "w").write("{lixo")
        self.assertEqual(lembretes.listar(), [])
        lembretes.adicionar("x", AGORA)
        self.assertEqual(len(lembretes.listar()), 1)

    def test_vencidos_e_concluir(self):
        passado = lembretes.adicionar("já passou", AGORA - dt.timedelta(minutes=1))
        lembretes.adicionar("futuro", AGORA + dt.timedelta(hours=1))
        self.assertEqual([i["texto"] for i in lembretes.vencidos(AGORA)], ["já passou"])
        lembretes.concluir(passado, AGORA)
        self.assertEqual([i["texto"] for i in lembretes.listar()], ["futuro"])

    def test_repetido_vai_para_a_proxima(self):
        d = lembretes.adicionar("diário", AGORA - dt.timedelta(days=3, hours=1), "diario")
        lembretes.concluir(d, AGORA)
        proximo = dt.datetime.fromisoformat(lembretes.listar()[0]["quando"])
        self.assertGreater(proximo, AGORA)
        self.assertLessEqual(proximo - AGORA, dt.timedelta(days=1))
        s = lembretes.adicionar("semanal", AGORA - dt.timedelta(hours=1), "semanal")
        lembretes.concluir(s, AGORA)
        q = [dt.datetime.fromisoformat(i["quando"]) for i in lembretes.listar() if i["texto"] == "semanal"][0]
        self.assertEqual(q, AGORA - dt.timedelta(hours=1) + dt.timedelta(days=7))


class TestAgendador(Base):
    def rodar(self, relogio):
        avisos = []
        ag = lembretes.Agendador(lambda item, atrasado: avisos.append((item["texto"], atrasado)),
                                 agora=lambda: relogio[0])
        return ag, avisos

    def test_avisa_na_hora_e_so_uma_vez(self):
        relogio = [AGORA]
        ag, avisos = self.rodar(relogio)
        lembretes.adicionar("água", AGORA + dt.timedelta(minutes=5))
        ag.verificar()
        self.assertEqual(avisos, [])
        relogio[0] = AGORA + dt.timedelta(minutes=5, seconds=1)
        ag.verificar(); ag.verificar()
        self.assertEqual(avisos, [("água", False)])

    def test_atrasado_avisa_como_atrasado(self):
        relogio = [AGORA]
        ag, avisos = self.rodar(relogio)
        lembretes.adicionar("remédio", AGORA - dt.timedelta(hours=2))
        ag.verificar()
        self.assertEqual(avisos, [("remédio", True)])

    def test_repetido_muito_antigo_e_pulado(self):
        relogio = [AGORA]
        ag, avisos = self.rodar(relogio)
        lembretes.adicionar("academia", AGORA - dt.timedelta(days=2), "diario")
        ag.verificar()
        self.assertEqual(avisos, [])
        self.assertEqual(len(lembretes.listar()), 1)          # mas continua agendado

    def test_erro_no_aviso_nao_trava_o_agendador(self):
        def falha(item, atrasado): raise RuntimeError("boom")
        ag = lembretes.Agendador(falha, agora=lambda: AGORA)
        lembretes.adicionar("x", AGORA - dt.timedelta(seconds=5))
        ag.verificar()
        self.assertEqual(lembretes.listar(), [])


class TestFerramentas(Base):
    def test_criar_com_frase_natural(self):
        r = fl.criar_lembrete("tomar água", "daqui a 20 minutos")
        self.assertIn("daqui a 20 minutos", r)
        self.assertEqual(lembretes.listar()[0]["texto"], "tomar água")

    def test_criar_recorrente(self):
        self.assertIn("repete toda segunda-feira", fl.criar_lembrete("reunião", "toda segunda às 9h"))

    def test_criar_com_data_iso(self):
        self.assertIn("criado", fl.criar_lembrete("x", "2030-01-02T10:00:00"))

    def test_quando_invalido(self):
        self.assertIn("Não entendi quando", fl.criar_lembrete("x", "qualquer hora"))
        self.assertEqual(lembretes.listar(), [])

    def test_listar_e_cancelar(self):
        self.assertIn("nenhum", fl.listar_lembretes())
        fl.criar_lembrete("tomar água", "em 10 minutos")
        fl.criar_lembrete("ligar pro João", "em 30 minutos")
        self.assertIn("tomar água", fl.listar_lembretes())
        self.assertIn("Cancelei o lembrete: tomar água", fl.cancelar_lembrete("água"))
        self.assertIn("#2 cancelado", fl.cancelar_lembrete("#2"))
        fl.criar_lembrete("a", "em 5 minutos"); fl.criar_lembrete("b", "em 6 minutos")
        self.assertIn("Qual deles?", fl.cancelar_lembrete("lembrete"))
        self.assertIn("Cancelei 2", fl.cancelar_lembrete("todos"))


if __name__ == "__main__":
    unittest.main()

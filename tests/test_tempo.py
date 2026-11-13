"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempo  # noqa: E402

AGORA = dt.datetime(2026, 11, 5, 14, 0, 0)   # quinta-feira, 14:00


def quando(frase):
    r = tempo.interpretar_quando(frase, AGORA)
    return (r.quando.strftime("%Y-%m-%d %H:%M"), r.repetir) if r else None


class TestInterpretar(unittest.TestCase):
    def test_relativo(self):
        self.assertEqual(quando("em 20 minutos"), ("2026-11-05 14:20", None))
        self.assertEqual(quando("daqui a meia hora"), ("2026-11-05 14:30", None))
        self.assertEqual(quando("em duas horas"), ("2026-11-05 16:00", None))
        self.assertEqual(quando("em 1 hora e meia"), ("2026-11-05 15:30", None))
        self.assertEqual(quando("daqui a 2 dias"), ("2026-11-07 14:00", None))

    def test_hora_do_dia(self):
        self.assertEqual(quando("hoje às 18h"), ("2026-11-05 18:00", None))
        self.assertEqual(quando("às 15:30"), ("2026-11-05 15:30", None))
        self.assertEqual(quando("às 17 e meia"), ("2026-11-05 17:30", None))
        self.assertEqual(quando("hoje à noite"), ("2026-11-05 20:00", None))

    def test_hora_ja_passada(self):
        self.assertEqual(quando("às 3"), ("2026-11-05 15:00", None))       # versão da tarde
        self.assertEqual(quando("às 9"), ("2026-11-06 09:00", None))       # amanhã
        self.assertEqual(quando("às 8 da manhã"), ("2026-11-06 08:00", None))
        self.assertEqual(quando("meio-dia"), ("2026-11-06 12:00", None))

    def test_dias(self):
        self.assertEqual(quando("amanhã às 9h"), ("2026-11-06 09:00", None))
        self.assertEqual(quando("amanhã às 9 da noite"), ("2026-11-06 21:00", None))
        self.assertEqual(quando("amanhã de manhã"), ("2026-11-06 09:00", None))
        self.assertEqual(quando("depois de amanhã"), ("2026-11-07 09:00", None))
        self.assertEqual(quando("na sexta às 10h"), ("2026-11-06 10:00", None))
        self.assertEqual(quando("segunda às 8"), ("2026-11-09 08:00", None))
        self.assertEqual(quando("dia 20 às 9h"), ("2026-11-20 09:00", None))
        self.assertEqual(quando("dia 2"), ("2026-12-02 09:00", None))

    def test_repeticao(self):
        self.assertEqual(quando("todo dia às 8h"), ("2026-11-06 08:00", "diario"))
        self.assertEqual(quando("todos os dias às 22h"), ("2026-11-05 22:00", "diario"))
        self.assertEqual(quando("toda segunda às 9h"), ("2026-11-09 09:00", "semanal"))
        self.assertEqual(quando("todo sábado às 10h"), ("2026-11-07 10:00", "semanal"))

    def test_sem_tempo(self):
        self.assertIsNone(quando("comprar pão"))
        self.assertIsNone(quando("às 25h"))


class TestDescrever(unittest.TestCase):
    def test_formas(self):
        d = lambda **kw: tempo.descrever(AGORA + dt.timedelta(**kw), AGORA)
        self.assertEqual(d(minutes=20), "daqui a 20 minutos")
        self.assertEqual(d(seconds=30), "daqui a 30 segundos")
        self.assertEqual(d(hours=2, minutes=30), "daqui a 2 horas e 30 minutos")
        self.assertEqual(d(hours=10), "amanhã às 00:00")
        self.assertEqual(d(days=1, hours=-5), "amanhã às 09:00")
        self.assertEqual(d(days=3), "domingo às 14:00")
        self.assertEqual(d(days=15), "20/11 às 14:00")


class TestExtrair(unittest.TestCase):
    def ex(self, frase):
        return tempo.extrair_lembrete(frase, AGORA)

    def test_relativo(self):
        self.assertEqual(self.ex("me lembra em 20 minutos de tomar água")[0], "tomar água")

    def test_preserva_maiusculas(self):
        self.assertEqual(self.ex("Me lembra amanhã às 9h de ligar para o João")[0], "ligar para o João")

    def test_tira_artigo_do_comeco(self):
        self.assertEqual(self.ex("toda segunda às 8h me lembra da reunião")[0], "reunião")

    def test_tempo_no_fim(self):
        self.assertEqual(self.ex("me lembra de ligar pro João amanhã às 9")[0], "ligar pro João")

    def test_criar_lembrete_com_dois_pontos(self):
        self.assertEqual(self.ex("cria um lembrete para sexta às 10h: reunião com o time")[0], "reunião com o time")

    def test_avisa_que(self):
        self.assertEqual(self.ex("me avisa daqui a 5 minutos que o macarrão está pronto")[0], "o macarrão está pronto")

    def test_expressao_serve_de_novo(self):
        texto, expr = self.ex("me lembra amanhã às 9h de ligar para o João")
        self.assertEqual(quando(expr), ("2026-11-06 09:00", None))

    def test_sem_tempo_ou_sem_assunto(self):
        self.assertIsNone(self.ex("me lembra de comprar pão"))
        self.assertIsNone(self.ex("me lembra em 20 minutos"))


if __name__ == "__main__":
    unittest.main()

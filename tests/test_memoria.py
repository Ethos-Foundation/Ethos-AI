"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import memoria  # noqa: E402


class TestMemoria(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.p1 = mock.patch.object(memoria, "ARQUIVO", os.path.join(self.dir.name, "m.json"))
        self.p2 = mock.patch.dict(memoria.memoria, {
            "fatos": {}, "girias": {}, "dialeto": {}, "tarefas": [], "eventos": []}, clear=True)
        self.p1.start(); self.p2.start()

    def tearDown(self):
        self.p1.stop(); self.p2.stop(); self.dir.cleanup()

    def test_giria_nao_aparece_sempre(self):
        memoria.aprender_giria("tipo assim", "mais ou menos")
        with mock.patch.object(config, "PROB_GIRIA", 0.2):
            usos = sum(memoria.sortear_giria() is not None for _ in range(2000))
        self.assertTrue(250 < usos < 550, usos)   # ~20% de 2000

    def test_sem_giria_nao_sorteia(self):
        with mock.patch.object(config, "PROB_GIRIA", 1.0):
            self.assertIsNone(memoria.sortear_giria())

    def test_dialeto_proprio_entra_no_sorteio(self):
        memoria.aprender_dialeto("quebra-lógica", "coisa que desafia o bom senso")
        with mock.patch.object(config, "PROB_GIRIA", 1.0):
            self.assertEqual(memoria.sortear_giria()[0], "dialeto")

    def test_contexto_pequeno_leva_todos_os_fatos(self):
        memoria.salvar_fato("curso", "engenharia")
        memoria.salvar_fato("time", "Sport")
        ctx = " ".join(memoria.contexto_para("oi"))
        self.assertIn("curso: engenharia", ctx)
        self.assertIn("time: Sport", ctx)

    def test_contexto_grande_filtra_por_relevancia(self):
        for i in range(30):
            memoria.salvar_fato(f"coisa{i}", f"valor{i}")
        memoria.memoria["fatos"] = {"cachorro": "chama Thor", **memoria.memoria["fatos"]}
        ctx = " ".join(memoria.contexto_para("como está o cachorro?"))
        self.assertIn("cachorro: chama Thor", ctx)
        self.assertLessEqual(ctx.count("; ") , config.MAX_FATOS_CONTEXTO)

    def test_arquivo_antigo_sem_dialeto_carrega(self):
        import json
        with open(memoria.ARQUIVO, "w", encoding="utf-8") as f:
            json.dump({"fatos": {"a": "b"}, "girias": {}, "tarefas": [], "eventos": []}, f)
        self.assertIn("dialeto", memoria.carregar())


if __name__ == "__main__":
    unittest.main()

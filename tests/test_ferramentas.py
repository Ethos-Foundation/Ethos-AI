"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import ferramentas_sistema as fs  # noqa: E402


class TestCaminhoSeguro(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.base = os.path.realpath(self.dir.name)
        self.p = mock.patch.object(config, "PASTA_PROJETOS", self.base)
        self.p.start()

    def tearDown(self):
        self.p.stop(); self.dir.cleanup()

    def test_nome_simples_vai_para_a_pasta(self):
        self.assertEqual(fs.caminho_seguro("teste.py"), os.path.join(self.base, "teste.py"))

    def test_caminho_fora_e_redirecionado(self):
        fora = os.path.join(os.path.dirname(self.base), "outro", "importante.txt")
        self.assertEqual(fs.caminho_seguro(fora), os.path.join(self.base, "importante.txt"))

    def test_nunca_sobrescreve(self):
        open(os.path.join(self.base, "a.py"), "w").close()
        self.assertEqual(fs.caminho_seguro("a.py"), os.path.join(self.base, "a_2.py"))
        open(os.path.join(self.base, "a_2.py"), "w").close()
        self.assertEqual(fs.caminho_seguro("a.py"), os.path.join(self.base, "a_3.py"))

    def test_subir_pastas_nao_escapa(self):
        r = fs.caminho_seguro("../../fora.py")
        self.assertTrue(r.startswith(self.base))


if __name__ == "__main__":
    unittest.main()

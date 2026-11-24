"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import ferramentas_sistema as fs  # noqa: E402
from texto import Falha  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)
        for p in (mock.patch.object(config, "PASTA_PROJETOS", self.base),
                  mock.patch.object(fs, "ao_abrir", None),
                  mock.patch.object(fs, "_criados", set()),
                  mock.patch.object(fs.subprocess, "Popen")):
            p.start(); self.addCleanup(p.stop)


class TestDestino(Base):
    def test_sem_destino_usa_pasta_de_projetos(self):
        self.assertEqual(fs.resolver_destino(""), self.base)
        self.assertEqual(fs.resolver_destino("projetos"), self.base)

    def test_caminho_completo(self):
        pasta = os.path.join(self.base, "x")
        os.makedirs(pasta)
        self.assertEqual(fs.resolver_destino(pasta), pasta)

    def test_apelido_usa_a_pasta_conhecida(self):
        with mock.patch.object(fs, "_pasta_conhecida", lambda n: os.path.join(self.base, n)):
            self.assertEqual(fs.resolver_destino("documentos"), os.path.join(self.base, "documentos"))

    def test_nome_de_pasta_e_procurado(self):
        alvo = os.path.join(self.base, "Faculdade", "Calculo")
        os.makedirs(alvo)
        with mock.patch.object(fs, "_pasta_conhecida", lambda n: self.base if n == "area de trabalho" else None), \
             mock.patch.object(fs.os.path, "expanduser", lambda p: self.base):
            self.assertEqual(fs.resolver_destino("calculo"), alvo)

    def test_pasta_inexistente(self):
        with mock.patch.object(fs, "_pasta_conhecida", lambda n: None), \
             mock.patch.object(fs.os.path, "expanduser", lambda p: self.base):
            self.assertIsNone(fs.resolver_destino("nao_existe_mesmo"))


class TestSalvar(Base):
    def test_salva_e_abre_no_vscode(self):
        r = fs.salvar_arquivo("teste.py", "print(1)\n")
        self.assertIn("Arquivo salvo", r)
        self.assertEqual(open(os.path.join(self.base, "teste.py"), encoding="utf-8").read(), "print(1)\n")
        fs.subprocess.Popen.assert_called_once()

    def test_nunca_cria_arquivo_em_branco(self):
        for vazio in ("", "   \n"):
            r = fs.salvar_arquivo("branco.py", vazio)
            self.assertIsInstance(r, Falha)
        self.assertEqual(os.listdir(self.base), [])

    def test_nao_sobrescreve_arquivo_que_ja_existia(self):
        open(os.path.join(self.base, "a.py"), "w").write("meu codigo")
        fs.salvar_arquivo("a.py", "novo\n")
        self.assertEqual(open(os.path.join(self.base, "a.py")).read(), "meu codigo")
        self.assertTrue(os.path.exists(os.path.join(self.base, "a_2.py")))

    def test_chamada_repetida_da_ethos_reescreve_o_mesmo_arquivo(self):
        """O bug dos dois arquivos: o modelo chamando a ferramenta duas vezes não cria nome_2."""
        fs.salvar_arquivo("fib.py", "v1\n")
        fs.salvar_arquivo("fib.py", "v2 completo\n")
        self.assertEqual(sorted(os.listdir(self.base)), ["fib.py"])
        self.assertEqual(open(os.path.join(self.base, "fib.py")).read(), "v2 completo\n")

    def test_pasta_inexistente_da_falha(self):
        with mock.patch.object(fs, "_pasta_conhecida", lambda n: None), \
             mock.patch.object(fs.os.path, "expanduser", lambda p: self.base):
            self.assertIsInstance(fs.salvar_arquivo("x.py", "a\n", "pasta_fantasma"), Falha)

    def test_ferramenta_do_modelo_com_conteudo_vazio_falha(self):
        self.assertIsInstance(fs.executar("criar_arquivo_codigo", {"caminho": "x.py", "conteudo": ""}), Falha)
        self.assertEqual(os.listdir(self.base), [])

    def test_recua_a_janela_antes_de_abrir_vscode(self):
        chamadas = []
        with mock.patch.object(fs, "ao_abrir", lambda: chamadas.append(1)), mock.patch.object(fs.time, "sleep"):
            fs.salvar_arquivo("y.py", "1\n")
        self.assertEqual(chamadas, [1])


class TestAbrir(Base):
    def test_abrir_pasta(self):
        with mock.patch.object(fs.os, "startfile", create=True) as abrir:
            self.assertIn("Abri a pasta", fs.abrir_pasta(""))
            abrir.assert_called_once_with(self.base)

    def test_abrir_pasta_inexistente(self):
        with mock.patch.object(fs, "_pasta_conhecida", lambda n: None), \
             mock.patch.object(fs.os.path, "expanduser", lambda p: self.base):
            self.assertIsInstance(fs.abrir_pasta("fantasma"), Falha)

    def test_abrir_site_recua_a_janela_primeiro(self):
        ordem = []
        with mock.patch.object(fs, "ao_abrir", lambda: ordem.append("recuou")), mock.patch.object(fs.time, "sleep"), \
             mock.patch.object(fs.webbrowser, "open", lambda u: ordem.append("abriu")):
            fs.abrir_site("youtube")
        self.assertEqual(ordem, ["recuou", "abriu"])


if __name__ == "__main__":
    unittest.main()

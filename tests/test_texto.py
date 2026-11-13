"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import texto  # noqa: E402


def rotear(pedacos):
    r = texto.RoteadorResposta()
    eventos = []
    for p in pedacos:
        eventos += r.alimentar(p)
    eventos += r.finalizar()
    return eventos


def por_tipo(eventos, tipo):
    return [t for tp, t in eventos if tp == tipo]


class TestFrases(unittest.TestCase):
    def test_corta_frase_longa(self):
        frases, resto = texto.extrair_frases("Olá, tudo bem com você? Estou ótimo. E")
        self.assertEqual(frases, ["Olá, tudo bem com você?"])
        self.assertEqual(resto, "Estou ótimo. E")

    def test_frase_curta_espera_mais(self):
        frases, resto = texto.extrair_frases("Oi. ")
        self.assertEqual(frases, [])
        self.assertEqual(resto, "Oi. ")


class TestHorario(unittest.TestCase):
    def test_detecta(self):
        for p in ("que horas são?", "Qual é a hora", "que dia é hoje", "qual a data de hoje"):
            self.assertTrue(texto.eh_pergunta_de_horario(p), p)

    def test_ignora(self):
        self.assertFalse(texto.eh_pergunta_de_horario("me conta uma piada"))


class TestCorrecao(unittest.TestCase):
    def test_ethos(self):
        self.assertEqual(texto.corrigir_texto("oi etos, tudo bem?"), "oi Ethos, tudo bem?")

    def test_email(self):
        self.assertEqual(texto.corrigir_texto("lê meus e maios"), "lê meus e-mails")
        self.assertEqual(texto.corrigir_texto("tem e maio novo?"), "tem e-mail novo?")

    def test_extras_do_usuario_valem(self):
        self.assertEqual(texto.corrigir_texto("abre o vi esco di", {"vi esco di": "VS Code"}), "abre o VS Code")


class TestComandos(unittest.TestCase):
    def cmd(self, frase):
        return texto.detectar_comando(frase)

    def test_youtube(self):
        self.assertEqual(self.cmd("Toca Imagine Dragons no YouTube."), ("abrir_musica_youtube", {"busca": "imagine dragons"}))
        self.assertEqual(self.cmd("coloca a música lo-fi no youtube"), ("abrir_musica_youtube", {"busca": "lo-fi"}))

    def test_abrir_site(self):
        self.assertEqual(self.cmd("Abre o YouTube"), ("abrir_site", {"url_ou_nome": "youtube"}))
        self.assertEqual(self.cmd("abre o site do github, por favor"), ("abrir_site", {"url_ou_nome": "github"}))
        self.assertEqual(self.cmd("abre o gmail"), ("abrir_site", {"url_ou_nome": "gmail"}))

    def test_vscode(self):
        self.assertEqual(self.cmd("abre o VS Code"), ("abrir_vscode", {}))

    def test_emails(self):
        self.assertEqual(self.cmd("lê meus e-mails"), ("ler_emails_recentes", {}))
        self.assertEqual(self.cmd("tem e-mail não lido?"), ("ler_emails_recentes", {"apenas_nao_lidos": True}))
        self.assertEqual(self.cmd("procura e-mail da Maria"), ("buscar_emails", {"termo": "maria"}))

    def test_ver_tela(self):
        for f in ("olha minha tela", "o que tem na minha tela?", "me diz o que você vê na tela",
                  "lê o erro que apareceu na minha tela", "dá uma olhada na tela"):
            nome, args = self.cmd(f)
            self.assertEqual(nome, "ver_tela", f)
            self.assertTrue(args["pergunta"])

    def test_tela_sem_ser_pedido_de_visao(self):
        for f in ("coloca em tela cheia", "a tela do meu celular quebrou", "me lembra de olhar a tela às 9h"):
            self.assertNotEqual((self.cmd(f) or ("",))[0], "ver_tela", f)

    def test_lembretes(self):
        nome, args = self.cmd("me lembra em 20 minutos de tomar água")
        self.assertEqual((nome, args["texto"]), ("criar_lembrete", "tomar água"))
        self.assertIn("20 minutos", args["quando"])
        self.assertEqual(self.cmd("quais são meus lembretes?"), ("listar_lembretes", {}))
        self.assertEqual(self.cmd("cancela o lembrete de tomar água"), ("cancelar_lembrete", {"referencia": "tomar água"}))
        self.assertEqual(self.cmd("cancela todos os lembretes"), ("cancelar_lembrete", {"referencia": "todos"}))

    def test_lembrete_de_email_nao_vira_leitura_de_email(self):
        nome, args = self.cmd("me lembra amanhã às 9h de ler o e-mail do chefe")
        self.assertEqual(nome, "criar_lembrete")

    def test_lembra_sem_horario_vai_para_o_modelo(self):
        self.assertIsNone(self.cmd("me lembra de comprar pão"))
        self.assertIsNone(self.cmd("você lembra do meu nome?"))

    def test_nao_dispara_quando_nao_deve(self):
        for f in ("me conta uma piada", "manda um e-mail para o João", "o que é o youtube?",
                  "que horas são", "toca uma música pra mim"):
            self.assertIsNone(self.cmd(f), f)


class TestMensagemErro(unittest.TestCase):
    def test_ollama_fechado(self):
        self.assertIn("Ollama", texto.mensagem_de_erro(ConnectionError("[WinError 10061] recusou")))

    def test_modelo_ausente(self):
        m = texto.mensagem_de_erro(Exception("model 'x' not found"), "x")
        self.assertIn("ollama pull x", m)

    def test_generico(self):
        self.assertIn("boom", texto.mensagem_de_erro(Exception("boom")))


class TestLimpeza(unittest.TestCase):
    def test_remove_emoji_e_asterisco(self):
        self.assertEqual(texto.limpar_fala("Olá 😄 *sorri* tudo bem? 👍🏽✨"), "Olá  sorri tudo bem? ")

    def test_preserva_acentos_e_pontuacao(self):
        s = "Não é à toa, né? Três — ok… (sim)."
        self.assertEqual(texto.limpar_fala(s), s)

    def test_roteador_limpa_emoji_na_fala(self):
        ev = rotear(list("Que ótimo 😀 meu caro, vamos nessa!"))
        self.assertNotIn("😀", "".join(por_tipo(ev, "tela")))
        self.assertNotIn("😀", " ".join(por_tipo(ev, "frase")))

    def test_conteudo_preserva_asterisco_de_codigo(self):
        ev = rotear(["Pronto.---CONTEUDO---\nx = a * b"])
        self.assertIn("a * b", "".join(por_tipo(ev, "conteudo")))


class TestJson(unittest.TestCase):
    def test_json_limpo(self):
        self.assertEqual(texto.extrair_json('{"a": 1}'), {"a": 1})

    def test_json_com_lixo(self):
        self.assertEqual(texto.extrair_json('Claro!\n```json\n{"a": [1]}\n```'), {"a": [1]})

    def test_json_invalido(self):
        self.assertIsNone(texto.extrair_json("sem json"))
        self.assertIsNone(texto.extrair_json("{quebrado"))


class TestAlucinacao(unittest.TestCase):
    def test_detecta(self):
        for f in ("", ".", "Legendas pela comunidade Amara.org", "Thanks for watching!"):
            self.assertTrue(texto.parece_alucinacao(f), f)

    def test_fala_normal_passa(self):
        for f in ("Obrigado.", "Que horas são?", "Sim"):
            self.assertFalse(texto.parece_alucinacao(f), f)


class TestRemoverPensamento(unittest.TestCase):
    def test_par_completo(self):
        self.assertEqual(texto.remover_pensamento("<think>blá</think>\n\nResposta"), "Resposta")

    def test_tag_de_fecho_solta(self):
        self.assertEqual(texto.remover_pensamento("raciocínio em inglês...</think>Resposta"), "Resposta")

    def test_sem_pensamento(self):
        self.assertEqual(texto.remover_pensamento("  Só a resposta.  "), "Só a resposta.")


class TestFiltroPensamento(unittest.TestCase):
    def rodar(self, pedacos):
        f = texto.FiltroPensamento()
        return "".join(f.alimentar(p) for p in pedacos) + f.finalizar()

    def test_texto_normal_passa(self):
        self.assertEqual(self.rodar(["Olá", ", mundo"]), "Olá, mundo")

    def test_remove_think(self):
        self.assertEqual(self.rodar(["<thi", "nk>blá blá</th", "ink>\n\nResposta"]), "Resposta")

    def test_menor_que_legitimo(self):
        self.assertEqual(self.rodar(["<b>oi</b>"]), "<b>oi</b>")

    def test_resposta_curta_nao_some(self):
        self.assertEqual(self.rodar(["<"]), "<")


class TestRoteador(unittest.TestCase):
    def test_conteudo_separado_char_a_char(self):
        entrada = "Olá, tudo bem? Eu sou a Ethos. ---CONTEUDO---\nprint(1)"
        ev = rotear(list(entrada))
        self.assertEqual(por_tipo(ev, "frase"), ["Olá, tudo bem? Eu sou a Ethos."])
        self.assertEqual("".join(por_tipo(ev, "conteudo")), "print(1)")
        self.assertNotIn("---", "".join(por_tipo(ev, "tela")))

    def test_conteudo_em_pedaco_unico(self):
        ev = rotear(["Pronto, já fiz.---CONTEUDO---\ncódigo aqui"])
        self.assertEqual(por_tipo(ev, "frase"), ["Pronto, já fiz."])
        self.assertEqual("".join(por_tipo(ev, "conteudo")), "código aqui")

    def test_dica_nao_e_falada(self):
        entrada = "Nice to meet you! How are you today? Dica: diga 'I am fine'."
        for pedacos in ([entrada], list(entrada)):
            ev = rotear(pedacos)
            falado = " ".join(por_tipo(ev, "frase"))
            self.assertIn("How are you today?", falado)
            self.assertNotIn("Dica", falado)
            self.assertNotIn("fine", falado)
            self.assertIn("Dica:", "".join(por_tipo(ev, "tela")))

    def test_resposta_curta_sem_pontuacao_final(self):
        ev = rotear(["Claro", ", pode ", "falar"])
        self.assertEqual(por_tipo(ev, "frase"), ["Claro, pode falar"])

    def test_nada_se_perde_na_tela(self):
        entrada = "Dia D de Dica sem dois pontos. Fim."
        ev = rotear(list(entrada))
        self.assertEqual("".join(por_tipo(ev, "tela")), entrada)

    def test_varias_frases_em_streaming(self):
        entrada = "Esta é a primeira frase completa. Esta é a segunda frase completa. Fim"
        ev = rotear(list(entrada))
        self.assertEqual(por_tipo(ev, "frase"), [
            "Esta é a primeira frase completa.",
            "Esta é a segunda frase completa.",
            "Fim",
        ])


if __name__ == "__main__":
    unittest.main()

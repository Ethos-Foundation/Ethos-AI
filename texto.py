"""
Funções de texto puras da Ethos AI (sem áudio, sem Ollama, sem janela).
Ficam num módulo à parte para poderem ser testadas sozinhas (tests/test_texto.py).
"""

import json
import re

import config

MARCA_CONTEUDO = "---CONTEUDO---"
MARCA_DICA = "Dica:"


def extrair_frases(buffer, minimo=None):
    """Devolve (frases_completas, resto_do_texto). Uma frase só é liberada
    quando já tem pelo menos `minimo` caracteres, para a fala não sair picada."""
    minimo = config.MIN_FRASE if minimo is None else minimo
    frases = []
    while True:
        for m in re.finditer(r"[.!?…]+\s|\n", buffer):
            if m.end() >= minimo:
                frase = buffer[:m.end()].strip()
                if frase:
                    frases.append(frase)
                buffer = buffer[m.end():]
                break
        else:
            return frases, buffer


def corrigir_texto(frase, extras=None):
    """Troca palavras que o Whisper costuma errar (ex.: 'etos' -> 'Ethos').
    `extras` são correções ensinadas pelo usuário (guardadas na memória)."""
    correcoes = {**config.CORRECOES_OUVIDO, **(extras or {})}
    for errado in sorted(correcoes, key=len, reverse=True):   # frases longas primeiro
        frase = re.sub(rf"\b{re.escape(errado)}\b", correcoes[errado], frase, flags=re.IGNORECASE)
    return frase


def mensagem_de_erro(erro, modelo=""):
    """Traduz erros técnicos em uma frase clara (e curta o bastante para ser falada)."""
    t = str(erro).lower()
    if "not found" in t and "model" in t:
        return f"O modelo {modelo} não está instalado. Rode ollama pull {modelo} no terminal."
    if any(p in t for p in ("connect", "10061", "refused", "failed to establish")):
        return "Não consegui falar com o Ollama. Ele está aberto?"
    return f"Tive um problema aqui: {erro}"


_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\uFE0F\u200D\u20E3]+")


def limpar_fala(trecho):
    """Tira emojis e asteriscos do texto falado/mostrado (o modelo pequeno às
    vezes ignora a instrução de não usá-los)."""
    return _EMOJI.sub("", trecho).replace("*", "")


def extrair_json(conteudo):
    """Pega o primeiro objeto JSON de um texto (tolera lixo antes/depois). None se falhar."""
    inicio, fim = conteudo.find("{"), conteudo.rfind("}")
    if inicio == -1 or fim <= inicio:
        return None
    try:
        dados = json.loads(conteudo[inicio:fim + 1])
    except ValueError:
        return None
    return dados if isinstance(dados, dict) else None


_PADRAO_HORARIO = re.compile(
    r"(que horas|que hora|horas s[aã]o|qual (é |e )?a hora|hora (é|e) agora"
    r"|que dia (é|e) hoje|qual (é |e )?a data|data de hoje)",
    re.IGNORECASE,
)


def eh_pergunta_de_horario(pergunta):
    """True se for pergunta de hora/data (respondida direto pelo relógio)."""
    return bool(_PADRAO_HORARIO.search(pergunta))


_ALUCINACOES = (
    "legendas pela comunidade amara.org", "amara.org", "thanks for watching",
    "thank you for watching", "inscreva-se no canal", "obrigado por assistir",
)


def parece_alucinacao(frase):
    """O Whisper às vezes 'escuta' frases de vídeos no meio de ruído/silêncio.
    Devolve True se a transcrição for vazia, curta demais ou uma dessas frases."""
    limpa = re.sub(r"[^\w\s.\-]", "", frase.lower()).strip(" .-")
    return len(limpa) < 2 or any(a in limpa for a in _ALUCINACOES)


_SITES = "youtube|google|spotify|gmail|github"


def detectar_comando(pergunta):
    """Reconhece pedidos CLAROS de ferramenta e devolve (nome, argumentos), ou None.
    Esses comandos são executados com certeza, antes de o modelo responder (o modelo
    pequeno às vezes só 'diz' que fez, sem fazer)."""
    bruto = pergunta
    p = re.sub(r"\s+", " ", pergunta.lower()).strip(" .!?,")

    if re.search(r"\blembretes?\b|\b(?:lembra|lembre|lembrar|avisa|avise|avisar)\b", p):
        import tempo
        if re.search(r"\b(?:cancela|cancele|cancelar|apaga|apague|apagar|remove|remova|remover|tira|tire|exclui|exclua)\b.*\blembretes?\b", p):
            m = re.search(r"\blembretes?\b\s*(.*)$", p)
            resto = re.sub(r"^(?:de|do|da|sobre|n[uú]mero|#)\s*", "", m.group(1).strip()).strip()
            return "cancelar_lembrete", {"referencia": "todos" if re.search(r"\btodos\b", p) else resto}
        if re.search(r"\b(?:quais|lista|listar|mostra|mostrar|ver|tenho|tem)\b.*\blembretes?\b", p):
            return "listar_lembretes", {}
        achado = tempo.extrair_lembrete(bruto)
        if achado:
            return "criar_lembrete", {"texto": achado[0], "quando": achado[1]}

    m = re.search(r"\b(?:toca|toque|tocar|coloca|coloque|bota|bote|p[oõ]e|pesquisa|procura|busca)\s+"
                  r"(.+?)\s+(?:no|do|pelo|na)\s+youtube\b", p)
    if m:
        busca = re.sub(r"^(?:a |o |um |uma )?(?:m[uú]sica|som|v[ií]deo|clipe)(?: de| do| da)? ", "", m.group(1)).strip()
        if busca:
            return "abrir_musica_youtube", {"busca": busca}

    if (re.search(r"\b(?:minha|nossa|essa|esta|dessa|desta|nessa|nesta|na|a)\s+tela\b", p)
            and not re.search(r"tela cheia|e-?mails?", p)
            and re.search(r"\b(?:olha|olhe|olhar|v[eê]|ver|enxerga|l[eê]|ler|analisa|analise|analisar|descreve|descreva"
                          r"|confere|checa|observa|espia)\b|o que (?:tem|est[aá]|aparece|h[aá]|t[aá])"
                          r"|d[aá] uma (?:olhada|espiada)|tira um print", p)):
        return "ver_tela", {"pergunta": bruto.strip()}

    m = re.search(rf"\babr(?:e|a|ir)\s+(?:o |a )?(?:site (?:do |da |de )?)?({_SITES})\b", p)
    if m:
        return "abrir_site", {"url_ou_nome": m.group(1)}

    if re.search(r"\babr(?:e|a|ir)\s+(?:o )?(?:vs ?code|visual studio code)\b", p):
        return "abrir_vscode", {}

    if re.search(r"\be-?mails?\b|caixa de entrada", p) and not re.search(
            r"\b(?:envia|enviar|manda|mandar|escreve|escrever|responde|responder|apaga|apagar)\b", p):
        m = re.search(r"\b(?:procura|procure|busca|busque|acha|ache|encontra|encontre)\b.*?\be-?mails?\b"
                      r".*?\b(?:de|da|do|sobre|com|dos|das)\s+(.+)$", p)
        if m:
            return "buscar_emails", {"termo": m.group(1).strip()}
        if re.search(r"n[aã]o lid", p):
            return "ler_emails_recentes", {"apenas_nao_lidos": True}
        if re.search(r"\b(?:l[eê]|ler|mostra|mostre|v[eê]|ver|checa|checar|confere|olha|olhe|tem|chegou|novos?)\b", p):
            return "ler_emails_recentes", {}
    return None


def remover_pensamento(conteudo):
    """Para respostas COMPLETAS (sem streaming): tira <think>...</think> e, se sobrar só
    um '</think>' solto (bug conhecido do Ollama), descarta tudo antes dele."""
    conteudo = re.sub(r"<think>.*?</think>", "", conteudo, flags=re.DOTALL)
    if "</think>" in conteudo:
        conteudo = conteudo.rsplit("</think>", 1)[1]
    return conteudo.strip()


class FiltroPensamento:
    """Descarta um bloco <think>...</think> no INÍCIO da resposta, em streaming.
    Só segura texto se a resposta começar com '<'; senão, libera tudo na hora.
    (Rede de segurança: o modelo instruct não deveria gerar isso.)"""

    _ABERTURA, _FECHO = "<think>", "</think>"

    def __init__(self):
        self._buf = ""
        self._modo = "decidindo"   # decidindo -> pensando -> livre

    def alimentar(self, pedaco):
        if self._modo == "livre":
            return pedaco
        self._buf += pedaco
        if self._modo == "decidindo":
            inicio = self._buf.lstrip()
            if not inicio:
                return ""
            if inicio.startswith(self._ABERTURA):
                self._modo = "pensando"
            elif self._ABERTURA.startswith(inicio):
                return ""          # ainda pode virar "<think>"
            else:
                self._modo = "livre"
                saida, self._buf = self._buf, ""
                return saida
        if self._modo == "pensando":
            if self._FECHO in self._buf:
                resto = self._buf.split(self._FECHO, 1)[1]
                self._buf, self._modo = "", "livre"
                return resto.lstrip()
        return ""

    def finalizar(self):
        """Libera o que sobrou retido (só acontece com respostas muito curtas)."""
        if self._modo == "decidindo":
            saida, self._buf = self._buf, ""
            return saida
        return ""


class RoteadorResposta:
    """Recebe a resposta do modelo pedaço a pedaço e decide o destino de cada trecho.

    Eventos devolvidos, como tuplas (tipo, texto):
      "tela"     -> mostrar na área principal
      "frase"    -> uma frase pronta para ser FALADA
      "conteudo" -> texto para a aba Conteúdo (depois de '---CONTEUDO---')

    Texto depois de 'Dica:' aparece na tela mas não é falado.
    """

    def __init__(self):
        self.pendente = ""     # recebido, mas pode conter começo de marcador
        self.fala_buf = ""     # texto que ainda não virou frase falável
        self.modo = "fala"     # fala | dica | conteudo
        self._conteudo_comecou = False

    def _marcadores(self):
        return (MARCA_CONTEUDO,) if self.modo == "dica" else (MARCA_CONTEUDO, MARCA_DICA)

    def _primeiro_marcador(self):
        melhor = None
        for m in self._marcadores():
            pos = self.pendente.find(m)
            if pos != -1 and (melhor is None or pos < melhor[0]):
                melhor = (pos, m)
        return melhor

    def _tamanho_retido(self):
        """Quantos caracteres do fim podem ser o começo de um marcador."""
        marcadores = self._marcadores()
        maximo = min(len(self.pendente), max(len(m) for m in marcadores) - 1)
        for k in range(maximo, 0, -1):
            sufixo = self.pendente[-k:]
            if any(m.startswith(sufixo) for m in marcadores):
                return k
        return 0

    def _emitir(self, trecho):
        trecho = limpar_fala(trecho)
        if not trecho:
            return []
        eventos = [("tela", trecho)]
        if self.modo == "fala":
            self.fala_buf += trecho
            frases, self.fala_buf = extrair_frases(self.fala_buf)
            eventos += [("frase", f) for f in frases]
        return eventos

    def _fechar_fala(self):
        resto, self.fala_buf = self.fala_buf.strip(), ""
        return [("frase", resto)] if resto else []

    def _conteudo(self, pedaco):
        """Texto da aba Conteúdo; ignora quebras de linha logo após o marcador."""
        if not self._conteudo_comecou:
            pedaco = pedaco.lstrip("\n")
            if not pedaco:
                return []
            self._conteudo_comecou = True
        return [("conteudo", pedaco)]

    def alimentar(self, pedaco):
        if self.modo == "conteudo":
            return self._conteudo(pedaco)
        self.pendente += pedaco
        eventos = []
        while True:
            achou = self._primeiro_marcador()
            if achou is None:
                break
            pos, marcador = achou
            eventos += self._emitir(self.pendente[:pos])
            self.pendente = self.pendente[pos + len(marcador):]
            eventos += self._fechar_fala()
            if marcador == MARCA_CONTEUDO:
                self.modo = "conteudo"
                resto, self.pendente = self.pendente, ""
                return eventos + self._conteudo(resto)
            self.modo = "dica"
            eventos.append(("tela", MARCA_DICA))
        retido = self._tamanho_retido()
        corte = len(self.pendente) - retido
        eventos += self._emitir(self.pendente[:corte])
        self.pendente = self.pendente[corte:]
        return eventos

    def finalizar(self):
        """Chamar no fim da resposta: libera o que ficou retido."""
        eventos = []
        if self.modo != "conteudo":
            eventos += self._emitir(self.pendente)
            eventos += self._fechar_fala()
        self.pendente = ""
        return eventos

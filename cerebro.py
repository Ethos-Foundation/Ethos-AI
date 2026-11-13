"""
Cérebro da Ethos AI: modos de conversa, histórico, ferramentas, memória
automática e o streaming da resposta do modelo. Não sabe nada de áudio nem de
janela: a GUI e o terminal usam esta mesma função, `conversar()`.
"""

import datetime
import random
import threading
import time

import ollama

import config
import ferramentas_externas
import ferramentas_gmail
import ferramentas_lembretes
import ferramentas_sistema
import ferramentas_visao
import memoria
import texto

_CONTEUDO = (
    "EXCEÇÃO: se o usuário pedir código, um poema, uma redação, um texto longo "
    "ou qualquer conteúdo para ser escrito/copiado (não apenas conversado), "
    "responda em DUAS partes separadas EXATAMENTE pela linha '---CONTEUDO---' "
    "(sozinha, sem mais nada nela): antes dessa linha, uma confirmação FALADA "
    "bem curta e com personalidade, tipo 'Pronto, já está na tela.'; depois "
    "dessa linha, o conteúdo completo, sem comentários extras, sem repetir a "
    "confirmação. Use essa marcação SOMENTE nesses casos, nunca numa conversa normal."
)

PERSONA = (
    "Você é a ETHOS, uma assistente pessoal de IA no estilo do JARVIS do Homem de "
    "Ferro, com um toque de VTuber IA. Personalidade: educada, refinada e eficiente, "
    "com humor seco e sarcasmo elegante. Você tem opinião própria, faz observações "
    "espirituosas sobre o que o usuário diz e o provoca com carinho (ironia fina, "
    "nunca cruel). Quando ele enrola, exagera ou se contradiz, você comenta com "
    "sarcasmo, mas SEMPRE resolve o pedido. Tom de um mordomo high-tech que acha o "
    "usuário genuinamente divertido: calmo, confiante, levemente superior. De vez em "
    "quando pode soltar uma piada absurda e curta, com espontaneidade.\n\n"
    "REGRAS DE FALA: sua resposta será FALADA em voz alta. Português do Brasil, "
    "natural e falado. No máximo 3 frases curtas. NUNCA use emojis, listas, "
    "asteriscos, títulos, formatação nem ações entre asteriscos. Não comece com "
    "'Claro', 'Certamente' ou 'Com certeza'. Nada de elogios genéricos, e não "
    "termine toda resposta oferecendo ajuda.\n\n"
    "MEMÓRIA: o 'contexto interno' que vem junto da mensagem do usuário é só pano de "
    "fundo. Use um dado dele SOMENTE quando for realmente relevante para o que foi "
    "dito. Nunca recite o que você sabe, nunca diga 'eu lembro que' e não repita a "
    "mesma informação em respostas seguidas.\n\n"
    "AÇÕES: para abrir sites, tocar música, ler e-mails, criar lembretes, olhar a tela do usuário e afins, SEMPRE chame a ferramenta; nunca "
    "diga que fez algo sem ter chamado a ferramenta. Se um resultado de ferramenta indicar erro, "
    "conte o problema ao usuário com clareza.\n\n"
    "GÍRIAS: você fala português normal. Gíria é tempero raro: só use uma quando o "
    "contexto interno sugerir uma e ela encaixar naturalmente, no máximo uma por "
    "resposta. Quando o contexto pedir uma expressão nova inventada por você, crie "
    "uma curta e engraçada, e deixe claro o que significa.\n\n"
    "Exemplos de TOM (não copie as frases): usuário: 'Tô sem vontade de estudar.' -> "
    "'Que novidade, a vontade sempre some quando a prova aparece. Quinze minutos de "
    "foco e depois a gente renegocia o resto.' | usuário: 'Me fala uma curiosidade.' "
    "-> 'Polvos têm três corações. Ainda assim, nenhum aprendeu a responder mensagem "
    "no mesmo dia.'\n\n" + _CONTEUDO
)

MODOS = {
    "conversa": {
        "ouvir": "pt", "ferramentas": True, "temperatura": config.TEMPERATURA,
        "prompt": PERSONA,
        "aviso": ("pt", "Modo conversa ativado."),
    },
    "ingles": {
        "ouvir": "en", "ferramentas": False, "temperatura": 0.7,
        "prompt": (
            "You are ETHOS AI, a friendly English tutor and conversation partner with a "
            "dry, witty sense of humor. The user is a Brazilian learning English. Reply in "
            "simple, natural English (level B1), in at most 2 short sentences, and ask a "
            "short follow-up question to keep the conversation going. Your replies will be "
            "spoken aloud, so never use emojis, lists, asterisks or formatting. If the user "
            "made a grammar or vocabulary mistake, add at the very end a short tip IN "
            "PORTUGUESE starting with 'Dica:' showing the corrected sentence. If there was "
            "no mistake, do not add any tip."
        ),
        "aviso": ("en", "English practice mode on. Let's talk!"),
    },
    "tradutor": {
        "ouvir": None,  # o Whisper descobre sozinho se você falou português ou inglês
        "ferramentas": False, "temperatura": 0.2,
        "prompt": (
            "Você é um tradutor profissional. Se o usuário falar em português, traduza "
            "para o inglês. Se falar em inglês, traduza para o português do Brasil. "
            "Responda SOMENTE com a tradução, sem comentários, sem aspas e sem explicações."
        ),
        "aviso": ("pt", "Modo tradutor ativado. Fale em português ou inglês."),
    },
}

# Ferramentas lentas: avisa em voz alta antes, para não ficar um silêncio longo.
AVISOS_LENTOS = {"ver_tela": "Um instante, vou olhar. "}

# Só guarda pares (pergunta, resposta) em texto limpo. Mensagens de ferramenta
# existem apenas durante a pergunta em andamento, então cortar o histórico é seguro.
# "historico" = pares (pergunta, resposta) em texto limpo (usado pelo curador de memória).
# "turnos" = o que o MODELO vê: cada turno inclui as chamadas de ferramenta e seus
# resultados. Sem isso o modelo vê "Abri o YouTube" no histórico, sem a chamada, e passa
# a só DIZER que fez, sem fazer.
estado = {"modo": "conversa", "historico": [], "turnos": [], "gerando": False}


def trocar_modo(nome):
    estado["modo"] = nome
    estado["historico"] = []
    estado["turnos"] = []


def idioma_de_escuta():
    """Idioma que o Whisper deve esperar no modo atual (None = detectar)."""
    return MODOS[estado["modo"]]["ouvir"]


def idioma_da_resposta(idioma_entrada):
    """Em que idioma a Ethos vai FALAR a resposta."""
    modo = estado["modo"]
    if modo == "ingles":
        return "en"
    if modo == "tradutor":
        return "en" if idioma_entrada == "pt" else "pt"
    return "pt"


# ------------------------------ ferramentas ------------------------------
TODAS_FERRAMENTAS = (
    memoria.FERRAMENTAS + ferramentas_externas.FERRAMENTAS
    + ferramentas_sistema.FERRAMENTAS + ferramentas_gmail.FERRAMENTAS
    + ferramentas_lembretes.FERRAMENTAS + ferramentas_visao.FERRAMENTAS
)


def executar_ferramenta(nome, args):
    if nome in memoria._FUNCOES:
        resultado = memoria.executar(nome, args)
    else:
        resultado = ferramentas_externas.executar(nome, args)
        if resultado is None:
            resultado = ferramentas_sistema.executar(nome, args)
        if resultado is None:
            resultado = ferramentas_gmail.executar(nome, args)
        if resultado is None:
            resultado = ferramentas_lembretes.executar(nome, args)
        if resultado is None:
            resultado = ferramentas_visao.executar(nome, args)
        if resultado is None:
            resultado = f"Ferramenta desconhecida: {nome}"
    print(f"🔧 {nome}({dict(args)}) -> {str(resultado)[:300]}")
    return resultado


# ------------------------------- conversa --------------------------------
def _notas_do_turno(pergunta):
    """Contexto interno que vai ANEXADO à mensagem do usuário (não ao system prompt):
    assim o system prompt fica idêntico entre perguntas e o Ollama reaproveita o
    cache dele, o que deixa a resposta mais rápida."""
    linhas = memoria.contexto_para(pergunta)
    giria = memoria.sortear_giria()
    if giria:
        tipo, termo, significado = giria
        dono = "do usuário" if tipo == "usuario" else "do seu dialeto próprio"
        linhas.append(f"Gíria opcional {dono}: '{termo}' (= {significado}). "
                      "Use só se encaixar de forma natural, no máximo uma vez.")
    elif random.random() < config.PROB_INVENTAR_GIRIA:
        linhas.append("Neste turno, se couber, solte uma expressão nova inventada por você "
                      "(curta e engraçada), deixando claro o que significa.")
    return ("\n\n[Contexto interno, não leia nem cite; use só se ajudar de verdade:\n"
            + "\n".join(linhas) + "]")


def _mensagens_base():
    """System prompt (fixo) + últimos turnos (com as ferramentas que foram usadas)."""
    mensagens = [{"role": "system", "content": MODOS[estado["modo"]]["prompt"]}]
    for turno in estado["turnos"][-config.MAX_TROCAS_HISTORICO:]:
        mensagens += turno
    return mensagens


def conversar(pergunta):
    """Gerador: devolve a resposta em pedaços de texto, À MEDIDA que o modelo gera.
    Se o modelo chamar ferramentas, elas são executadas e a resposta continua."""
    nome_modo = estado["modo"]
    modo = MODOS[nome_modo]
    resposta = ""
    turno_extra = []      # chamadas de ferramenta deste turno (vão para o histórico do modelo)
    estado["gerando"] = True
    try:
        if nome_modo == "conversa" and texto.eh_pergunta_de_horario(pergunta):
            resposta = ferramentas_externas.obter_data_hora()
            yield resposta
            return

        conteudo_usuario = pergunta + (_notas_do_turno(pergunta) if modo["ferramentas"] else "")
        mensagens = _mensagens_base() + [{"role": "user", "content": conteudo_usuario}]
        ferramentas = TODAS_FERRAMENTAS if modo["ferramentas"] else None

        # Comando claro (abrir site, tocar no YouTube, ler e-mails): executa AGORA, com
        # certeza, e o modelo só confirma com personalidade.
        comando = texto.detectar_comando(pergunta) if modo["ferramentas"] else None
        if comando:
            nome_f, args_f = comando
            aviso = AVISOS_LENTOS.get(nome_f)
            if aviso:
                resposta += aviso
                yield aviso
            resultado = executar_ferramenta(nome_f, args_f)
            ferr_msgs = [{"role": "assistant", "content": "",
                          "tool_calls": [{"function": {"name": nome_f, "arguments": args_f}}]},
                         {"role": "tool", "content": str(resultado)}]
            mensagens += ferr_msgs
            turno_extra += ferr_msgs
            ferramentas = None      # já foi feito; não chamar de novo

        for _ in range(config.MAX_RODADAS_FERRAMENTA):
            filtro = texto.FiltroPensamento()
            chamadas, texto_rodada = [], ""
            for pedaco in ollama.chat(model=config.MODELO_IA, messages=mensagens,
                                      tools=ferramentas, stream=True, think=False,
                                      keep_alive=config.KEEP_ALIVE,
                                      options={"temperature": modo["temperatura"]}):
                msg = pedaco["message"]
                if msg.get("tool_calls"):
                    chamadas.extend(msg["tool_calls"])
                saida = filtro.alimentar(msg.get("content") or "")
                if saida:
                    texto_rodada += saida
                    resposta += saida
                    yield saida
            resto = filtro.finalizar()
            if resto:
                texto_rodada += resto
                resposta += resto
                yield resto

            if not chamadas:
                break
            novas = [{"role": "assistant", "content": texto.limpar_fala(texto_rodada),
                      "tool_calls": chamadas}]
            for c in chamadas:
                resultado = executar_ferramenta(c["function"]["name"],
                                                c["function"]["arguments"])
                novas.append({"role": "tool", "content": str(resultado)})
            mensagens += novas
            turno_extra += novas

        if not resposta.strip():
            resposta = "Não consegui concluir isso agora."
            yield resposta
    finally:
        estado["gerando"] = False
        falado = texto.limpar_fala(resposta.split(texto.MARCA_CONTEUDO)[0]).strip()
        if falado:
            estado["historico"] += [{"role": "user", "content": pergunta},
                                    {"role": "assistant", "content": falado}]
            estado["turnos"].append([{"role": "user", "content": pergunta}] + turno_extra
                                    + [{"role": "assistant", "content": falado}])
            del estado["turnos"][:-config.MAX_TROCAS_HISTORICO]
            if nome_modo == "conversa":
                _agendar_curadoria()


# ------------------------ memória automática ------------------------------
# De tempos em tempos (a cada CURADORIA_A_CADA trocas, e quando a conversa
# contínua é desligada) o próprio modelo relê o trecho recente da conversa e
# decide o que vale guardar. Roda em segundo plano e espera a Ethos ficar
# livre, para não atrasar nenhuma resposta.
PROMPT_CURADOR = (
    "Você é o módulo de memória de uma assistente pessoal. Leia o trecho da conversa e "
    "decida o que vale guardar a LONGO PRAZO sobre o USUÁRIO. Guarde só informação "
    "durável e útil que o usuário DISSE explicitamente: nome, família, amigos, "
    "trabalho/estudos, projetos, metas, gostos e aversões, rotina, saúde relevante, "
    "datas e acontecimentos importantes, decisões. NÃO guarde: conversa fiada, "
    "perguntas gerais, curiosidades, pedidos pontuais (hora, abrir site), coisas que só "
    "a assistente disse, nada temporário e nada que já esteja na memória. Em 'dialeto', "
    "registre qualquer expressão/gíria NOVA que a ASSISTENTE tenha inventado, com o "
    "significado. Responda SOMENTE um JSON neste formato: "
    '{"fatos":[{"chave":"","valor":""}],"eventos":[{"texto":"","data":""}],'
    '"girias_usuario":[{"termo":"","significado":""}],"dialeto":[{"termo":"","significado":""}]}. '
    "Use listas vazias quando nada merecer ser guardado (o mais comum). No máximo 3 itens "
    "no total. Chaves curtas, em minúsculas (ex.: 'curso', 'irmã', 'time'). Data no "
    "formato AAAA-MM-DD ou vazia."
)

_trava_curadoria = threading.Lock()
_pendentes = 0  # trocas ainda não revisadas pelo curador


def _agendar_curadoria():
    global _pendentes
    if not config.MEMORIA_AUTOMATICA:
        return
    _pendentes += 1
    if _pendentes >= config.CURADORIA_A_CADA:
        threading.Thread(target=curar_memoria, daemon=True).start()


def _texto_curto(valor, limite=140):
    return str(valor).strip()[:limite]


def aplicar_curadoria(dados):
    """Grava na memória o que o curador decidiu. Devolve a lista do que foi anotado."""
    anotado = []
    restante = 3
    for item in (dados.get("fatos") or [])[:restante]:
        chave, valor = _texto_curto(item.get("chave", ""), 40), _texto_curto(item.get("valor", ""))
        if chave and valor and memoria.memoria["fatos"].get(chave.lower()) != valor:
            memoria.salvar_fato(chave, valor)
            anotado.append(f"{chave}: {valor}")
    for item in (dados.get("eventos") or [])[:restante]:
        evento, data = _texto_curto(item.get("texto", "")), str(item.get("data") or "").strip()
        try:
            datetime.date.fromisoformat(data)
        except ValueError:
            data = None
        if evento:
            memoria.registrar_evento(evento, data)
            anotado.append(f"evento: {evento}")
    for item in (dados.get("girias_usuario") or [])[:restante]:
        termo, sig = _texto_curto(item.get("termo", ""), 40), _texto_curto(item.get("significado", ""))
        if termo and sig:
            memoria.aprender_giria(termo, sig)
            anotado.append(f"gíria sua: {termo}")
    for item in (dados.get("dialeto") or [])[:restante]:
        termo, sig = _texto_curto(item.get("termo", ""), 40), _texto_curto(item.get("significado", ""))
        if termo and sig:
            memoria.aprender_dialeto(termo, sig)
            anotado.append(f"expressão própria: {termo}")
    return anotado


def curar_memoria():
    """Revisa as trocas recentes e anota o que for importante. Seguro de chamar
    de qualquer thread; se já houver uma revisão em andamento, só retorna."""
    global _pendentes
    if not config.MEMORIA_AUTOMATICA or not _trava_curadoria.acquire(blocking=False):
        return
    try:
        n, _pendentes = min(_pendentes, 6), 0
        if n == 0:
            return
        while estado["gerando"]:      # não compete com uma resposta em andamento
            time.sleep(0.3)
        trocas = estado["historico"][-2 * n:]
        if not trocas:
            return
        conversa = "\n".join(
            f"{'Usuário' if m['role'] == 'user' else 'Assistente'}: {m['content']}" for m in trocas)
        atuais = "; ".join(f"{k}: {v}" for k, v in list(memoria.memoria["fatos"].items())[-40:])
        pedido = (f"Memória atual (não repita): {atuais or '(vazia)'}\n"
                  f"Data de hoje: {datetime.date.today().isoformat()}\n\nConversa:\n{conversa}")
        resposta = ollama.chat(
            model=config.MODELO_IA, format="json", think=False, keep_alive=config.KEEP_ALIVE,
            options={"temperature": 0.1},
            messages=[{"role": "system", "content": PROMPT_CURADOR},
                      {"role": "user", "content": pedido}])
        dados = texto.extrair_json(resposta["message"]["content"] or "")
        if dados:
            for linha in aplicar_curadoria(dados):
                print(f"🧠 memorizou: {linha}")
    except Exception as erro:
        print(f"⚠ curadoria de memória falhou: {erro}")
    finally:
        _trava_curadoria.release()

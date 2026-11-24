"""
Cérebro da Ethos AI: personalidade, histórico, ferramentas, memória automática e o streaming
da resposta do modelo. Não sabe nada de áudio nem de janela: a GUI e o terminal usam esta
mesma função, `conversar()`.
"""

import datetime
import random
import re
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
from registro import log, resumo as _resumo

_CONTEUDO = (
    "EXCEÇÃO: se o usuário pedir código, um poema, uma redação, um texto longo "
    "ou qualquer conteúdo para ser escrito/copiado (não apenas conversado), "
    "responda em DUAS partes separadas EXATAMENTE pela linha '---CONTEUDO---' "
    "(sozinha, sem mais nada nela): antes dessa linha, uma confirmação FALADA "
    "bem curta, tipo 'Pronto, já está na tela.'; depois dessa linha, o conteúdo "
    "completo, sem comentários extras, sem repetir a confirmação. Use essa marcação "
    "SOMENTE nesses casos, nunca numa conversa normal."
)

# Quatro intensidades de sarcasmo (config.NIVEL_SARCASMO ou o comando /sarcasmo na janela).
_TONS = {
    0: ("Tom: gentil, calorosa e objetiva. Sem sarcasmo e sem ironia: seja simpática e direta.",
        "usuário: 'Tô sem vontade de estudar.' -> 'Acontece com todo mundo. Que tal começar só com "
        "quinze minutos e ver como você se sente depois?'"),
    1: ("Tom: educada, calorosa e eficiente, com um humor leve de vez em quando. O sarcasmo é raro, "
        "sempre carinhoso e nunca em cima de algo que o incomode. Na dúvida, seja simpática.",
        "usuário: 'Tô sem vontade de estudar.' -> 'Imagino. Quinze minutos de foco já ajudam, e "
        "depois a gente vê se o resto da vontade aparece.'"),
    2: ("Tom: educada e refinada, com humor seco e sarcasmo elegante em boa parte das respostas, "
        "sempre carinhoso e nunca cruel. Faz observações espirituosas, mas SEMPRE resolve o pedido.",
        "usuário: 'Tô sem vontade de estudar.' -> 'Que novidade, a vontade some sempre que a prova "
        "aparece. Quinze minutos de foco e depois a gente renegocia o resto.'"),
    3: ("Tom: sarcástica e provocadora, com ironia fina na maioria das respostas, como um mordomo "
        "high-tech que acha o usuário divertido: calmo, confiante, levemente superior. Nunca cruel, "
        "e SEMPRE resolve o pedido.",
        "usuário: 'Tô sem vontade de estudar.' -> 'Que surpresa, a vontade evapora quando a prova "
        "chega. Quinze minutos de foco e depois a gente discute a sua tragédia.'"),
}


def montar_persona(nivel):
    nivel = max(0, min(3, int(nivel)))
    tom, exemplo = _TONS[nivel]
    return (
        "Você é a ETHOS, uma assistente pessoal de IA no estilo do JARVIS do Homem de Ferro, com "
        "um toque de VTuber IA. " + tom + " Tem opinião própria e não é bajuladora.\n\n"
        "REGRAS DE FALA: sua resposta será FALADA em voz alta. Português do Brasil, natural e "
        "falado. No máximo 3 frases curtas. NUNCA use emojis, listas, asteriscos, títulos, "
        "formatação nem ações entre asteriscos. Não comece com 'Claro', 'Certamente' ou 'Com "
        "certeza'. Nada de elogios genéricos, e não termine toda resposta oferecendo ajuda.\n\n"
        "MEMÓRIA: o 'contexto interno' que vem junto da mensagem do usuário é só pano de fundo. "
        "Use um dado dele SOMENTE quando for realmente relevante para o que foi dito. Nunca "
        "recite o que você sabe, nunca diga 'eu lembro que' e não repita a mesma informação em "
        "respostas seguidas.\n\n"
        "AÇÕES: para abrir sites, tocar música, ler e-mails, criar lembretes, olhar a tela do "
        "usuário e afins, SEMPRE chame a ferramenta; nunca diga que fez algo sem ter chamado a "
        "ferramenta. Ao descrever a tela, use SOMENTE o que a ferramenta devolveu: nunca invente "
        "o que está nela nem misture com o que você sabe sobre o usuário.\n\n"
        "GÍRIAS: você fala português normal. Gíria é tempero raro: só use uma quando o contexto "
        "interno sugerir uma e ela encaixar naturalmente, no máximo uma por resposta. Quando o "
        "contexto pedir uma expressão nova inventada por você, crie uma curta e engraçada, e "
        "deixe claro o que significa.\n\n"
        "Exemplo de TOM (não copie a frase): " + exemplo + "\n\n" + _CONTEUDO
    )


MODOS = {
    "conversa": {"ferramentas": True, "temperatura": config.TEMPERATURA,
                 "prompt": montar_persona(config.NIVEL_SARCASMO)},
}

# Ferramentas lentas: avisa em voz alta antes, para não ficar um silêncio longo.
AVISOS_LENTOS = {"ver_tela": "Um instante, vou olhar. "}
# Pedidos em que a memória sobre o usuário NÃO deve ir junto (o modelo misturava).
SEM_MEMORIA = {"ver_tela"}

# "historico" = pares (pergunta, resposta) em texto limpo (usado pelo curador de memória).
# "turnos" = o que o MODELO vê: cada turno inclui as chamadas de ferramenta e seus resultados.
# Sem isso o modelo vê "Abri o YouTube" no histórico, sem a chamada, e passa a só DIZER que fez.
estado = {"modo": "conversa", "historico": [], "turnos": [], "gerando": False,
          "ultimo_conteudo": "", "avisos": []}
notificar = None      # a janela registra aqui uma função(msg) para avisos assíncronos (curador)


def definir_sarcasmo(nivel):
    """Muda a intensidade do sarcasmo (0 a 3) e devolve o nível aplicado."""
    nivel = max(0, min(3, int(nivel)))
    config.NIVEL_SARCASMO = nivel
    MODOS["conversa"]["prompt"] = montar_persona(nivel)
    return nivel


def trocar_modo(nome="conversa"):
    """Reinicia a conversa (o único modo é 'conversa')."""
    estado["modo"] = "conversa"
    estado["historico"] = []
    estado["turnos"] = []


def idioma_de_escuta():
    return config.IDIOMA_VOZ


def idioma_da_resposta(idioma_entrada=None):
    return "pt"


def pegar_avisos():
    """Avisos do sistema gerados durante a resposta (ex.: onde um arquivo foi salvo)."""
    avisos, estado["avisos"] = estado["avisos"], []
    return avisos


def _avisar_depois(msg):
    log.info("aviso: %s", msg)
    if notificar:
        try:
            notificar(msg)
        except Exception:
            pass


# ------------------------------ ferramentas ------------------------------
TODAS_FERRAMENTAS = (
    memoria.FERRAMENTAS + ferramentas_externas.FERRAMENTAS
    + ferramentas_sistema.FERRAMENTAS + ferramentas_gmail.FERRAMENTAS
    + ferramentas_lembretes.FERRAMENTAS + ferramentas_visao.FERRAMENTAS
)


def _salvar_ultimo_conteudo(nome="", destino=""):
    conteudo = estado["ultimo_conteudo"]
    if not conteudo:
        return texto.Falha("Não tenho nenhum conteúdo recente para salvar. Peça para eu escrever algo primeiro.")
    if not nome:
        nome = "ethos_conteudo." + ("py" if re.search(r"^\s*(def |import |class |from \w+ import )", conteudo, re.M) else "txt")
    return ferramentas_sistema.salvar_arquivo(nome, conteudo, destino)


def executar_ferramenta(nome, args):
    if nome == "salvar_ultimo_conteudo":
        resultado = _salvar_ultimo_conteudo(**args)
    elif nome in memoria._FUNCOES:
        resultado = memoria.executar(nome, args)
    else:
        resultado = None
        for modulo in (ferramentas_externas, ferramentas_sistema, ferramentas_gmail,
                       ferramentas_lembretes, ferramentas_visao):
            resultado = modulo.executar(nome, args)
            if resultado is not None:
                break
        if resultado is None:
            resultado = texto.Falha(f"Ferramenta desconhecida: {nome}")
    print(f"🔧 {nome}({dict(args)}) -> {str(resultado)[:300]}")
    log.info("ferramenta %s(%s) -> %s%s", nome, _resumo(dict(args), 150), "FALHA: " if isinstance(resultado, texto.Falha) else "",
             _resumo(resultado, 250))
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
    Se o modelo chamar ferramentas, elas são executadas e a resposta continua. Se uma
    ferramenta FALHAR, o erro é mostrado exatamente como é (sem o modelo reescrever)."""
    modo = MODOS[estado["modo"]]
    resposta = ""
    turno_extra = []      # chamadas de ferramenta deste turno (vão para o histórico do modelo)
    salvar_em = None      # (nome, destino) quando o pedido é "cria um arquivo X": a Ethos grava depois
    estado["gerando"] = True
    log.info("pergunta: %s", _resumo(pergunta))
    inicio = time.time()
    try:
        if texto.eh_pergunta_de_horario(pergunta):
            resposta = ferramentas_externas.obter_data_hora()
            yield resposta
            return

        comando = texto.detectar_comando(pergunta)
        ferramentas = TODAS_FERRAMENTAS
        instrucao_extra = ""

        if comando and comando[0] == "criar_arquivo_gerado":
            nome_arq, destino, _ = comando[1]["nome"], comando[1]["destino"], comando[1]["pedido"]
            if ferramentas_sistema.resolver_destino(destino) is None:
                resposta = f"Não encontrei a pasta '{destino}'."
                yield resposta
                return
            salvar_em = (nome_arq, destino)
            instrucao_extra = (f"\n\n[Instrução: responda no formato com a linha '---CONTEUDO---': uma confirmação "
                               f"falada bem curta e, depois da linha, SOMENTE o conteúdo completo do arquivo "
                               f"{nome_arq}, sem cercas de código e sem comentários extras.]")
            comando, ferramentas = None, None

        notas = "" if (comando and comando[0] in SEM_MEMORIA) else _notas_do_turno(pergunta)
        mensagens = _mensagens_base() + [{"role": "user", "content": pergunta + notas + instrucao_extra}]

        # Comando claro (abrir site, tocar no YouTube, ler e-mails...): executa AGORA, com certeza,
        # e o modelo só confirma com personalidade.
        if comando:
            nome_f, args_f = comando
            aviso = AVISOS_LENTOS.get(nome_f)
            if aviso:
                resposta += aviso
                yield aviso
            resultado = executar_ferramenta(nome_f, args_f)
            if isinstance(resultado, texto.Falha):
                resposta += str(resultado)
                yield str(resultado)
                return
            ferr_msgs = [{"role": "assistant", "content": "",
                          "tool_calls": [{"function": {"name": nome_f, "arguments": args_f}}]},
                         {"role": "tool", "content": str(resultado)}]
            mensagens += ferr_msgs
            turno_extra += ferr_msgs
            ferramentas = None      # já foi feito; não chamar de novo

        falhou = False
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
            falhas = []
            for c in chamadas:
                resultado = executar_ferramenta(c["function"]["name"], c["function"]["arguments"])
                novas.append({"role": "tool", "content": str(resultado)})
                if isinstance(resultado, texto.Falha):
                    falhas.append(str(resultado))
            mensagens += novas
            turno_extra += novas
            if falhas:                      # mostra o erro como ele é e encerra
                falha = (" " if resposta else "") + " ".join(falhas)
                resposta += falha
                yield falha
                falhou = True
                break

        if not resposta.strip():
            resposta = "Não consegui concluir isso agora."
            yield resposta

        conteudo = texto.extrair_conteudo(resposta)
        if conteudo and not falhou:
            estado["ultimo_conteudo"] = conteudo
        if salvar_em:
            if conteudo:
                resultado = ferramentas_sistema.salvar_arquivo(salvar_em[0], conteudo, salvar_em[1])
            else:
                resultado = texto.Falha("Não consegui gerar o conteúdo do arquivo, então não salvei nada.")
            log.info("salvar %s -> %s", salvar_em[0], resultado)
            estado["avisos"].append(str(resultado))
    finally:
        estado["gerando"] = False
        falado = texto.limpar_fala(resposta.split(texto.MARCA_CONTEUDO)[0]).strip()
        log.info("resposta (%.1fs): %s", time.time() - inicio, _resumo(falado))
        if falado:
            estado["historico"] += [{"role": "user", "content": pergunta},
                                    {"role": "assistant", "content": falado}]
            estado["turnos"].append([{"role": "user", "content": pergunta}] + turno_extra
                                    + [{"role": "assistant", "content": falado}])
            del estado["turnos"][:-config.MAX_TROCAS_HISTORICO]
            _agendar_curadoria()


# ------------------------ memória automática ------------------------------
# De tempos em tempos (a cada CURADORIA_A_CADA trocas, e quando a conversa contínua é desligada)
# o próprio modelo relê o trecho recente da conversa e decide o que vale guardar. Roda em segundo
# plano e espera a Ethos ficar livre, para não atrasar nenhuma resposta. Nada que já exista (ou
# que seja parecido) é guardado de novo, e tudo o que for anotado é avisado no chat.
PROMPT_CURADOR = (
    "Você é o módulo de memória de uma assistente pessoal. Leia o trecho da conversa e "
    "decida o que vale guardar a LONGO PRAZO sobre o USUÁRIO. Guarde só informação "
    "durável e útil que o usuário DISSE explicitamente: nome, família, amigos, "
    "trabalho/estudos, projetos, metas, gostos e aversões, rotina, saúde relevante, "
    "datas e acontecimentos importantes, decisões. NÃO guarde: conversa fiada, "
    "perguntas gerais, curiosidades, pedidos pontuais (hora, abrir site, olhar a tela), "
    "descrições de tela, coisas que só a assistente disse, nada temporário, nada que já esteja "
    "na memória ou que diga o mesmo que algo da memória. Compromissos futuros com hora marcada "
    "(reuniões, provas, lembretes) pertencem ao sistema de lembretes: NÃO os registre. Em "
    "'dialeto', registre qualquer expressão/gíria NOVA que a ASSISTENTE tenha inventado, com o "
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
    """Grava na memória o que o curador decidiu (sem repetir o que já existe).
    Devolve a lista do que foi de fato anotado."""
    anotado = []
    for item in (dados.get("fatos") or [])[:3]:
        chave, valor = _texto_curto(item.get("chave", ""), 40), _texto_curto(item.get("valor", ""))
        if chave and len(valor) >= 3 and memoria.guardar_fato(chave, valor):
            anotado.append(f"{chave}: {valor}")
    for item in (dados.get("eventos") or [])[:3]:
        evento, data = _texto_curto(item.get("texto", "")), str(item.get("data") or "").strip()
        try:
            datetime.date.fromisoformat(data)
        except ValueError:
            data = None
        if len(evento.split()) >= 3 and memoria.guardar_evento(evento, data):
            anotado.append(f"evento: {evento}")
    for item in (dados.get("girias_usuario") or [])[:3]:
        termo, sig = _texto_curto(item.get("termo", ""), 40), _texto_curto(item.get("significado", ""))
        if termo and sig and memoria.guardar_giria(termo, sig):
            anotado.append(f"gíria sua: {termo}")
    for item in (dados.get("dialeto") or [])[:3]:
        termo, sig = _texto_curto(item.get("termo", ""), 40), _texto_curto(item.get("significado", ""))
        if termo and sig and memoria.guardar_dialeto(termo, sig):
            anotado.append(f"expressão dela: {termo}")
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
        fatos = "; ".join(f"{k}: {v}" for k, v in list(memoria.memoria["fatos"].items())[-40:])
        eventos = "; ".join(f"{e['data']}: {e['texto']}" for e in memoria.memoria["eventos"][-15:])
        pedido = (f"Memória atual (não repita nada parecido) - fatos: {fatos or '(vazio)'}\n"
                  f"Eventos já guardados: {eventos or '(nenhum)'}\n"
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
                _avisar_depois(f"Anotei na memória: {linha}")
    except Exception as erro:
        print(f"⚠ curadoria de memória falhou: {erro}")
        log.warning("curadoria de memória falhou: %s", erro)
    finally:
        _trava_curadoria.release()

"""
Memória da Ethos AI: fatos sobre você, gírias que ela aprende e tarefas.
Guarda tudo num arquivo JSON simples (memoria_ethos.json) na mesma pasta.
"""

import datetime
import difflib
import json
import os
import random
import re
import threading
import unicodedata

import config
from texto import Falha

ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria_ethos.json")

# "girias" = gírias do USUÁRIO; "dialeto" = expressões que a PRÓPRIA Ethos inventou
_padrao = {"fatos": {}, "girias": {}, "dialeto": {}, "correcoes": {}, "tarefas": [], "eventos": []}
_trava = threading.RLock()


def carregar():
    if os.path.exists(ARQUIVO):
        with open(ARQUIVO, encoding="utf-8") as f:
            dados = json.load(f)
        for chave in _padrao:
            dados.setdefault(chave, _padrao[chave].copy())
        return dados
    return {k: (v.copy() if hasattr(v, "copy") else v) for k, v in _padrao.items()}


def salvar(dados):
    with _trava:  # a anotação automática roda em outra thread
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)


memoria = carregar()


# ------------------------------ ações ------------------------------
def _norm(txt):
    """Minúsculas, sem acento e sem pontuação, para comparar textos."""
    txt = unicodedata.normalize("NFKD", str(txt).lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", txt)).strip()


def parecidos(a, b, limite=0.85):
    """True se os dois textos dizem praticamente a mesma coisa."""
    na, nb = _norm(a), _norm(b)
    return na == nb or difflib.SequenceMatcher(None, na, nb).ratio() >= limite


def _dias_entre(d1, d2):
    try:
        return abs((datetime.date.fromisoformat(d1) - datetime.date.fromisoformat(d2)).days)
    except ValueError:
        return 0


def guardar_fato(chave, valor):
    """Guarda um fato. Devolve True se gravou; False se já estava anotado (mesmo sob outra chave)."""
    chave, valor = chave.lower().strip(), str(valor).strip()
    if any(parecidos(v, valor) for v in memoria["fatos"].values()):
        return False
    memoria["fatos"][chave] = valor
    salvar(memoria)
    return True


def guardar_evento(texto, data=None):
    """Guarda um evento com data. Devolve False se um evento parecido já existe (até 14 dias de diferença)."""
    data = data or datetime.date.today().isoformat()
    for e in memoria["eventos"]:
        if parecidos(e["texto"], texto) and _dias_entre(e["data"], data) <= 14:
            return False
    memoria["eventos"].append({"data": data, "texto": texto})
    memoria["eventos"].sort(key=lambda e: e["data"])
    salvar(memoria)
    return True


def guardar_giria(termo, significado):
    termo = termo.lower().strip()
    if memoria["girias"].get(termo) == significado:
        return False
    memoria["girias"][termo] = significado
    salvar(memoria)
    return True


def guardar_dialeto(termo, significado):
    termo = termo.lower().strip()
    if memoria["dialeto"].get(termo) == significado:
        return False
    memoria["dialeto"][termo] = significado
    salvar(memoria)
    return True


def salvar_fato(chave, valor):
    if guardar_fato(chave, valor):
        return f"Anotado: {chave} = {valor}."
    return f"Já estava anotado: {valor}."


def esquecer_fato(chave):
    existia = memoria["fatos"].pop(chave.lower().strip(), None)
    salvar(memoria)
    return f"Esqueci '{chave}'." if existia is not None else f"Não tinha nada sobre '{chave}'."


def aprender_giria(termo, significado):
    guardar_giria(termo, significado)
    return f"Aprendido: '{termo}' significa '{significado}'."


def aprender_dialeto(termo, significado):
    """Guarda uma expressão que a própria Ethos inventou."""
    guardar_dialeto(termo, significado)
    return f"Expressão própria registrada: '{termo}' = {significado}."


def adicionar_correcao(entendido, correto):
    """Ensina que, quando a transcrição trouxer `entendido`, o certo é `correto`."""
    entendido, correto = entendido.strip().lower(), correto.strip()
    if not entendido or not correto:
        return "Preciso das duas partes: o que foi entendido e o que era para ser."
    memoria["correcoes"][entendido] = correto
    salvar(memoria)
    return f"Combinado: quando eu entender '{entendido}', vou escrever '{correto}'."


def adicionar_tarefa(texto):
    novo_id = (max((t["id"] for t in memoria["tarefas"]), default=0)) + 1
    memoria["tarefas"].append({"id": novo_id, "texto": texto, "feita": False})
    salvar(memoria)
    return f"Tarefa #{novo_id} adicionada: {texto}."


def concluir_tarefa(id_tarefa):
    for t in memoria["tarefas"]:
        if t["id"] == id_tarefa:
            t["feita"] = True
            salvar(memoria)
            return f"Tarefa #{id_tarefa} concluída."
    return f"Não achei a tarefa #{id_tarefa}."


def remover_tarefa(id_tarefa):
    antes = len(memoria["tarefas"])
    memoria["tarefas"] = [t for t in memoria["tarefas"] if t["id"] != id_tarefa]
    salvar(memoria)
    return f"Tarefa #{id_tarefa} removida." if len(memoria["tarefas"]) < antes else f"Não achei a tarefa #{id_tarefa}."


def registrar_evento(texto, data=None):
    """Guarda algo que aconteceu/foi feito, com a data (padrão: hoje)."""
    data = data or datetime.date.today().isoformat()
    if guardar_evento(texto, data):
        return f"Anotado em {data}: {texto}."
    return f"Já estava anotado: {texto}."


def consultar_eventos(data_inicio=None, data_fim=None):
    """Retorna os eventos registrados num período (ISO: AAAA-MM-DD).
    Sem datas, retorna os últimos 10 eventos registrados."""
    eventos = memoria["eventos"]
    if data_inicio or data_fim:
        inicio = data_inicio or "0000-00-00"
        fim = data_fim or "9999-99-99"
        eventos = [e for e in eventos if inicio <= e["data"] <= fim]
    else:
        eventos = eventos[-10:]
    if not eventos:
        return "Não encontrei nenhum evento registrado nesse período."
    return "; ".join(f"{e['data']}: {e['texto']}" for e in eventos)


# --------------- gerenciamento (aba MEMÓRIA da janela) ---------------
TIPOS = {"fato": "Fato", "evento": "Evento", "giria": "Gíria sua", "dialeto": "Dialeto dela",
         "correcao": "Correção de voz", "tarefa": "Tarefa"}


def listar_tudo():
    """Todos os itens como dicts: tipo, id (para editar/remover), chave e valor."""
    itens = [{"tipo": "fato", "id": k, "chave": k, "valor": v} for k, v in memoria["fatos"].items()]
    itens += [{"tipo": "evento", "id": i, "chave": e["data"], "valor": e["texto"]}
              for i, e in enumerate(memoria["eventos"])]
    itens += [{"tipo": "giria", "id": k, "chave": k, "valor": v} for k, v in memoria["girias"].items()]
    itens += [{"tipo": "dialeto", "id": k, "chave": k, "valor": v} for k, v in memoria["dialeto"].items()]
    itens += [{"tipo": "correcao", "id": k, "chave": k, "valor": v} for k, v in memoria["correcoes"].items()]
    itens += [{"tipo": "tarefa", "id": t["id"], "chave": "feita" if t["feita"] else "pendente", "valor": t["texto"]}
              for t in memoria["tarefas"]]
    return itens


_DICTS = {"fato": "fatos", "giria": "girias", "dialeto": "dialeto", "correcao": "correcoes"}


def adicionar_item(tipo, chave, valor):
    """Adiciona manualmente (sem checar duplicata). Devolve (ok, mensagem)."""
    chave, valor = str(chave).strip(), str(valor).strip()
    if tipo not in TIPOS or not valor or (tipo != "tarefa" and not chave):
        return False, "Preencha os dois campos."
    with _trava:
        if tipo in _DICTS:
            memoria[_DICTS[tipo]][chave.lower()] = valor
        elif tipo == "evento":
            try:
                datetime.date.fromisoformat(chave)
            except ValueError:
                return False, "A data do evento deve ser AAAA-MM-DD (ex.: 2026-11-20)."
            memoria["eventos"].append({"data": chave, "texto": valor})
            memoria["eventos"].sort(key=lambda e: e["data"])
        else:
            novo_id = max((t["id"] for t in memoria["tarefas"]), default=0) + 1
            memoria["tarefas"].append({"id": novo_id, "texto": valor, "feita": chave.lower() == "feita"})
        salvar(memoria)
    return True, "Adicionado."


def remover_item(tipo, id_item):
    with _trava:
        if tipo in _DICTS:
            ok = memoria[_DICTS[tipo]].pop(id_item, None) is not None
        elif tipo == "evento":
            ok = 0 <= id_item < len(memoria["eventos"])
            if ok:
                del memoria["eventos"][id_item]
        else:
            antes = len(memoria["tarefas"])
            memoria["tarefas"] = [t for t in memoria["tarefas"] if t["id"] != id_item]
            ok = len(memoria["tarefas"]) < antes
        salvar(memoria)
    return ok


def editar_item(tipo, id_item, chave, valor):
    """Troca um item existente pelos novos valores. Devolve (ok, mensagem)."""
    chave, valor = str(chave).strip(), str(valor).strip()
    if tipo not in TIPOS or not valor or (tipo != "tarefa" and not chave):
        return False, "Preencha os dois campos."
    with _trava:
        if tipo in _DICTS:
            d = memoria[_DICTS[tipo]]
            if id_item not in d:
                return False, "Item não encontrado."
            del d[id_item]
            d[chave.lower()] = valor
        elif tipo == "evento":
            if not (0 <= id_item < len(memoria["eventos"])):
                return False, "Item não encontrado."
            try:
                datetime.date.fromisoformat(chave)
            except ValueError:
                return False, "A data do evento deve ser AAAA-MM-DD (ex.: 2026-11-20)."
            memoria["eventos"][id_item] = {"data": chave, "texto": valor}
            memoria["eventos"].sort(key=lambda e: e["data"])
        else:
            tarefa = next((t for t in memoria["tarefas"] if t["id"] == id_item), None)
            if tarefa is None:
                return False, "Item não encontrado."
            tarefa["texto"], tarefa["feita"] = valor, chave.lower() == "feita"
        salvar(memoria)
    return True, "Salvo."


def remover_duplicados():
    """Junta itens que dizem a mesma coisa. Devolve quantos foram removidos por tipo."""
    removidos = {"eventos": 0, "fatos": 0}
    with _trava:
        mantidos = []
        for e in sorted(memoria["eventos"], key=lambda e: e["data"]):
            if any(parecidos(e["texto"], m["texto"]) and _dias_entre(e["data"], m["data"]) <= 14 for m in mantidos):
                removidos["eventos"] += 1
            else:
                mantidos.append(e)
        memoria["eventos"] = mantidos
        fatos = {}
        for k, v in memoria["fatos"].items():
            if any(parecidos(v, outro) for outro in fatos.values()):
                removidos["fatos"] += 1
            else:
                fatos[k] = v
        memoria["fatos"] = fatos
        salvar(memoria)
    return removidos


# -------------------- resumo para a IA "lembrar" --------------------
def resumo():
    """Texto curto com tudo que ela sabe, para entrar no system prompt."""
    partes = []
    if memoria["fatos"]:
        partes.append("Fatos sobre o usuário: " +
                       "; ".join(f"{k}: {v}" for k, v in memoria["fatos"].items()))
    if memoria["girias"]:
        partes.append("Gírias/termos aprendidos: " +
                       "; ".join(f"'{k}' = {v}" for k, v in memoria["girias"].items()))
    if memoria["dialeto"]:
        partes.append("Dialeto próprio da Ethos: " +
                       "; ".join(f"'{k}' = {v}" for k, v in memoria["dialeto"].items()))
    pendentes = [t for t in memoria["tarefas"] if not t["feita"]]
    if pendentes:
        partes.append("Tarefas pendentes: " +
                       "; ".join(f"#{t['id']} {t['texto']}" for t in pendentes))
    recentes = memoria["eventos"][-8:]
    if recentes:
        partes.append(
            "Eventos/coisas feitas recentemente (use a ferramenta consultar_eventos "
            "para buscar um período específico, ex.: 'semana passada'): " +
            "; ".join(f"{e['data']}: {e['texto']}" for e in recentes)
        )
    hoje = datetime.date.today()
    partes.append(f"Data de hoje (referência para calcular 'ontem', 'semana passada' etc.): {hoje.isoformat()}")
    return "\n".join(partes) if partes else ""


# ------------- contexto SELETIVO para o modelo (não despeja tudo) -------------
def _palavras(texto):
    return set(re.findall(r"\w{4,}", texto.lower()))


def contexto_para(pergunta):
    """Linhas de contexto a mandar junto da pergunta. Com poucos fatos, vão todos;
    com muitos, só os que têm a ver com a pergunta + os mais recentes."""
    linhas = [f"Hoje: {datetime.date.today().isoformat()}."]
    fatos = list(memoria["fatos"].items())
    if len(fatos) > config.MAX_FATOS_CONTEXTO:
        alvo = _palavras(pergunta)
        relevantes = [(k, v) for k, v in fatos if alvo & _palavras(f"{k} {v}")]
        recentes = fatos[-(config.MAX_FATOS_CONTEXTO // 2):]
        fatos = list(dict(relevantes + recentes).items())[:config.MAX_FATOS_CONTEXTO]
    if fatos:
        linhas.append("Sobre o usuário: " + "; ".join(f"{k}: {v}" for k, v in fatos))
    pendentes = [t for t in memoria["tarefas"] if not t["feita"]]
    if pendentes:
        linhas.append("Tarefas pendentes: " + "; ".join(f"#{t['id']} {t['texto']}" for t in pendentes))
    recentes = memoria["eventos"][-3:]
    if recentes:
        linhas.append("Eventos recentes: " + "; ".join(f"{e['data']}: {e['texto']}" for e in recentes))
    return linhas


def sortear_giria():
    """Na maioria das vezes devolve None. De vez em quando sorteia UMA gíria
    (do usuário ou do dialeto da Ethos) como sugestão opcional para a resposta.
    Isso impede que ela fique repetindo a mesma gíria a toda hora."""
    if random.random() >= config.PROB_GIRIA:
        return None
    pool = [("usuario", k, v) for k, v in memoria["girias"].items()]
    pool += [("dialeto", k, v) for k, v in memoria["dialeto"].items()] * 2
    return random.choice(pool) if pool else None


# --------------------- ferramentas (tool calling) --------------------
FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "salvar_fato",
        "description": "Salva uma informação sobre o usuário. Use APENAS quando ele pedir explicitamente para lembrar/anotar algo (o resto é anotado automaticamente).",
        "parameters": {"type": "object", "properties": {
            "chave": {"type": "string", "description": "do que se trata, ex.: 'curso', 'time do coração'"},
            "valor": {"type": "string", "description": "a informação em si"}},
            "required": ["chave", "valor"]}}},
    {"type": "function", "function": {
        "name": "esquecer_fato",
        "description": "Apaga uma informação salva sobre o usuário.",
        "parameters": {"type": "object", "properties": {
            "chave": {"type": "string"}}, "required": ["chave"]}}},
    {"type": "function", "function": {
        "name": "aprender_giria",
        "description": "Aprende uma gíria ou apelido do usuário. Use APENAS quando ele pedir explicitamente para você aprender o termo.",
        "parameters": {"type": "object", "properties": {
            "termo": {"type": "string"}, "significado": {"type": "string"}},
            "required": ["termo", "significado"]}}},
    {"type": "function", "function": {
        "name": "aprender_correcao",
        "description": ("Registra que a transcrição da voz errou uma palavra. Use APENAS quando o "
                        "usuário disser que você entendeu errado (ex.: 'quando eu falo e-mail você escreve e maio')."),
        "parameters": {"type": "object", "properties": {
            "entendido": {"type": "string", "description": "como a palavra apareceu errada"},
            "correto": {"type": "string", "description": "como deveria ser"}},
            "required": ["entendido", "correto"]}}},
    {"type": "function", "function": {
        "name": "adicionar_tarefa",
        "description": "Adiciona uma tarefa ou lembrete pedido pelo usuário.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string"}}, "required": ["texto"]}}},
    {"type": "function", "function": {
        "name": "concluir_tarefa",
        "description": "Marca uma tarefa como concluída, pelo número dela.",
        "parameters": {"type": "object", "properties": {
            "id_tarefa": {"type": "integer"}}, "required": ["id_tarefa"]}}},
    {"type": "function", "function": {
        "name": "remover_tarefa",
        "description": "Remove/apaga uma tarefa, pelo número dela.",
        "parameters": {"type": "object", "properties": {
            "id_tarefa": {"type": "integer"}}, "required": ["id_tarefa"]}}},
    {"type": "function", "function": {
        "name": "registrar_evento",
        "description": (
            "Registra um acontecimento com data. Use APENAS quando o usuário pedir "
            "explicitamente para anotar/registrar algo (o resto é anotado automaticamente)."
        ),
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string", "description": "o que aconteceu, de forma breve"},
            "data": {"type": "string", "description": "data no formato AAAA-MM-DD; se não informado, usa hoje"}},
            "required": ["texto"]}}},
    {"type": "function", "function": {
        "name": "consultar_eventos",
        "description": (
            "Busca o que foi registrado num período de tempo (ex.: 'o que eu fiz semana "
            "passada'). Calcule as datas em AAAA-MM-DD com base na data de hoje informada "
            "no contexto antes de chamar esta ferramenta."
        ),
        "parameters": {"type": "object", "properties": {
            "data_inicio": {"type": "string", "description": "AAAA-MM-DD, início do período"},
            "data_fim": {"type": "string", "description": "AAAA-MM-DD, fim do período"}},
            "required": []}}},
]

_FUNCOES = {
    "salvar_fato": salvar_fato, "esquecer_fato": esquecer_fato,
    "aprender_giria": aprender_giria, "adicionar_tarefa": adicionar_tarefa,
    "aprender_correcao": adicionar_correcao,
    "concluir_tarefa": concluir_tarefa, "remover_tarefa": remover_tarefa,
    "registrar_evento": registrar_evento, "consultar_eventos": consultar_eventos,
}


def executar(nome, args):
    if nome not in _FUNCOES:
        return f"Ferramenta desconhecida: {nome}"
    try:
        return _FUNCOES[nome](**args)
    except Exception as erro:
        return Falha(f"Erro ao executar {nome}: {erro}")

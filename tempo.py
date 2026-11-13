"""
Interpretação de datas e horas em português falado: "daqui a 20 minutos",
"amanhã às 9h", "toda segunda às 8h", "dia 20 às 15:30".
Funções puras: recebem `agora`, então dá para testar com qualquer data.
"""

import datetime as dt
import re
from collections import namedtuple

# quando: datetime | repetir: None, "diario" ou "semanal" | spans: trechos da frase que são tempo
Resultado = namedtuple("Resultado", "quando repetir spans")

_NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5,
            "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
            "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50}
_SEMANA = {"segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4,
           "sábado": 5, "sabado": 5, "domingo": 6}
NOMES_DIA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira",
             "sábado", "domingo"]
_PERIODO_PADRAO = {"manha": (9, 0), "tarde": (15, 0), "noite": (20, 0), "madrugada": (5, 0)}
_DIA_SEMANA_RE = r"(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)"


def _num(token):
    return int(token) if token.isdigit() else _NUMEROS.get(token)


def _mascarar(p, span):
    return p[:span[0]] + " " * (span[1] - span[0]) + p[span[1]:]


def _relativo(p):
    m = re.search(r"\b(?:daqui a|daqui|em)\s+meia hora\b", p)
    if m:
        return dt.timedelta(minutes=30), m.span()
    for m in re.finditer(r"\b(?:daqui a|daqui|em)\s+(\d+|[a-zçê]+)\s+horas?\s+e\s+meia\b", p):
        n = _num(m.group(1))
        if n is not None:
            return dt.timedelta(minutes=n * 60 + 30), m.span()
    for m in re.finditer(r"\b(?:daqui a|daqui|em)\s+(\d+|[a-zçê]+)\s+(segundos?|minutos?|horas?|dias?)\b", p):
        n = _num(m.group(1))
        if n is None:
            continue
        unidade = {"seg": "seconds", "min": "minutes", "hor": "hours", "dia": "days"}[m.group(2)[:3]]
        return dt.timedelta(**{unidade: n}), m.span()
    return None


def _repeticao(p):
    m = re.search(r"\b(?:todos os dias|todo dia|diariamente)\b", p)
    if m:
        return "diario", None, m.span()
    m = re.search(rf"\btod[ao]s? (?:as |os )?{_DIA_SEMANA_RE}s?(?:-feiras?)?\b", p)
    if m:
        return "semanal", _SEMANA[m.group(1)], m.span()
    m = re.search(r"\btoda semana\b|\bsemanalmente\b", p)
    if m:
        return "semanal", None, m.span()
    return None


def _dia(p):
    m = re.search(r"\bdepois de amanh[ãa]\b", p)
    if m:
        return "delta", 2, m.span()
    m = re.search(r"\bamanh[ãa]\b", p)
    if m:
        return "delta", 1, m.span()
    m = re.search(r"\bhoje\b", p)
    if m:
        return "delta", 0, m.span()
    for m in re.finditer(r"\bdia (\d{1,2})\b", p):
        if 1 <= int(m.group(1)) <= 31:
            return "mes", int(m.group(1)), m.span()
    m = re.search(r"\b(?:(?:na|no|nesta|neste|esta|este|pr[óo]xima|pr[óo]ximo|para a|para o|pra|pro)\s+)?"
                  rf"{_DIA_SEMANA_RE}(?:-feira)?\b", p)
    if m:
        return "semana", _SEMANA[m.group(1)], m.span()
    return None


def _periodo(p):
    m = re.search(r"\b(?:da|de|[àa]|pela|na|do)\s+(manh[ãa]|tarde|noite|madrugada)\b", p)
    if m:
        nome = "manha" if m.group(1).startswith("manh") else m.group(1)
        return nome, m.span()
    return None


_HORAS = [
    (r"\bmeio[- ]dia\b", lambda m: (12, 0)),
    (r"\bmeia[- ]noite\b", lambda m: (0, 0)),
    (r"\b(\d{1,2})\s*(?:h|horas?)\s+e\s+meia\b", lambda m: (int(m.group(1)), 30)),
    (r"\b[àa]s?\s+(\d{1,2})\s+e\s+meia\b", lambda m: (int(m.group(1)), 30)),
    (r"\b(?:[àa]s?\s+)?(\d{1,2})\s*(?:h|:)\s*(\d{2})\b", lambda m: (int(m.group(1)), int(m.group(2)))),
    (r"\b[àa]s?\s+(\d{1,2})\s*(?:h|horas?)?\b", lambda m: (int(m.group(1)), 0)),
    (r"\b(\d{1,2})\s*(?:h|horas)\b", lambda m: (int(m.group(1)), 0)),
]


def _hora(p):
    for padrao, extrair in _HORAS:
        for m in re.finditer(padrao, p):
            h, mi = extrair(m)
            if 0 <= h <= 23 and 0 <= mi <= 59:
                return h, mi, m.span()
    return None


def interpretar_quando(frase, agora=None):
    """Acha o momento citado na frase. Devolve Resultado(quando, repetir, spans) ou None."""
    agora = (agora or dt.datetime.now()).replace(microsecond=0)
    p = frase.lower()

    rel = _relativo(p)
    if rel:
        return Resultado(agora + rel[0], None, [rel[1]])

    spans, repet, dia_rep = [], None, None
    r = _repeticao(p)
    if r:
        repet, dia_rep, span = r
        spans.append(span)
        p = _mascarar(p, span)
    d = _dia(p)
    if d:
        spans.append(d[2])
        p = _mascarar(p, d[2])
    per = _periodo(p)
    if per:
        spans.append(per[1])
        p = _mascarar(p, per[1])
    hora = _hora(p)
    if hora:
        spans.append(hora[2])
    if not (repet or d or per or hora):
        return None

    if hora:
        h, mi = hora[0], hora[1]
        if per and per[0] in ("tarde", "noite") and h < 12:
            h += 12
    elif per:
        h, mi = _PERIODO_PADRAO[per[0]]
    else:
        h, mi = 9, 0
    hoje = agora.date()

    def com(dia):
        return dt.datetime.combine(dia, dt.time(h, mi))

    def flexivel(dia):
        """Hoje (ou sem dia): se já passou, tenta a versão da tarde ("às 3" = 15h) ou o dia seguinte."""
        q = com(dia)
        if q > agora:
            return q
        if hora and not per and h < 12:
            tarde = q.replace(hour=h + 12) if h + 12 <= 23 else None
            if tarde and agora < tarde <= agora + dt.timedelta(hours=6):
                return tarde
        return q + dt.timedelta(days=1)

    def proxima_semana(wd):
        q = com(hoje + dt.timedelta(days=(wd - hoje.weekday()) % 7))
        return q if q > agora else q + dt.timedelta(days=7)

    if repet == "diario":
        quando = com(hoje)
        if quando <= agora:
            quando += dt.timedelta(days=1)
    elif repet == "semanal":
        quando = proxima_semana(dia_rep if dia_rep is not None else hoje.weekday())
    elif d and d[0] == "delta":
        quando = flexivel(hoje) if d[1] == 0 else com(hoje + dt.timedelta(days=d[1]))
    elif d and d[0] == "semana":
        quando = proxima_semana(d[1])
    elif d and d[0] == "mes":
        try:
            quando = com(dt.date(hoje.year, hoje.month, d[1]))
            if quando <= agora:
                ano, mes = (hoje.year + 1, 1) if hoje.month == 12 else (hoje.year, hoje.month + 1)
                quando = com(dt.date(ano, mes, d[1]))
        except ValueError:
            return None
    else:
        quando = flexivel(hoje)
    return Resultado(quando, repet, spans)


def descrever(quando, agora=None):
    """'daqui a 20 minutos', 'hoje às 15:30', 'amanhã às 09:00', 'sexta-feira às 10:00', '20/11 às 09:00'."""
    agora = (agora or dt.datetime.now()).replace(microsecond=0)
    delta = (quando - agora).total_seconds()
    if 0 <= delta < 3 * 3600:
        if delta < 60:
            return f"daqui a {max(1, round(delta))} segundos"
        minutos = round(delta / 60)
        if minutos == 1:
            return "daqui a 1 minuto"
        if minutos < 60:
            return f"daqui a {minutos} minutos"
        h, m = divmod(minutos, 60)
        return f"daqui a {h} hora{'s' if h > 1 else ''}" + (f" e {m} minutos" if m else "")
    dias = (quando.date() - agora.date()).days
    hora = quando.strftime("%H:%M")
    if dias == 0:
        return f"hoje às {hora}"
    if dias == 1:
        return f"amanhã às {hora}"
    if 1 < dias < 7:
        return f"{NOMES_DIA[quando.weekday()]} às {hora}"
    return f"{quando.strftime('%d/%m')} às {hora}"


def descrever_repeticao(repetir, quando):
    if repetir == "diario":
        return "todo dia"
    if repetir == "semanal":
        nome = NOMES_DIA[quando.weekday()]
        return ("todo " if nome == "sábado" or nome == "domingo" else "toda ") + nome
    return ""


_PREFIXO = re.compile(
    r"^\s*(?:por favor[, ]*|pode |poderia )?(?:"
    r"(?:me )?(?:lembra|lembre|lembrar|avisa|avise|avisar)(?: eu| a mim)?\b"
    r"|(?:cria|crie|criar|faz|fa[cç]a|fazer|adiciona|adicione|coloca|bota|p[oõ]e)\s+(?:um |uma )?lembrete\b"
    r"|n[aã]o me deixa(?:r)? esquecer\b)", re.IGNORECASE)


def extrair_lembrete(frase, agora=None):
    """De 'me lembra amanhã às 9h de ligar pro João' tira (texto, expressão_de_tempo).
    Devolve None se não houver tempo reconhecível ou não houver o que lembrar."""
    r = interpretar_quando(frase, agora)
    if r is None or not r.spans:
        return None
    resto = frase
    for ini, fim in sorted(r.spans, reverse=True):
        resto = resto[:ini] + " " + resto[fim:]
    resto = _PREFIXO.sub("", resto.strip(), count=1)
    resto = re.sub(r"\s+", " ", resto).strip(" ,.:;-!?")
    resto = re.sub(r"^(?:de|do|da|dos|das|que|para|pra)\s+", "", resto, flags=re.IGNORECASE).strip(" ,.:;-!?")
    if not resto:
        return None
    expressao = " ".join(frase[i:f] for i, f in sorted(r.spans))
    return resto, expressao

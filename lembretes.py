"""
Lembretes da Ethos: armazenamento em JSON (sobrevive a reiniciar o app), agendador em
segundo plano e as frases do aviso. Quem FALA o aviso é o orquestrador.
"""

import datetime as dt
import json
import os
import random
import threading

ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lembretes_ethos.json")
_trava = threading.RLock()
ATRASO_AVISADO = 120          # segundos: acima disso o aviso é tratado como "atrasado"
REPETIDO_ANTIGO = 6 * 3600    # lembrete repetido que passou há mais que isso é pulado em silêncio


def _ler():
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except (OSError, ValueError):
        return []


def _gravar(itens):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(itens, f, ensure_ascii=False, indent=1)


def _quando(item):
    return dt.datetime.fromisoformat(item["quando"])


def adicionar(texto, quando, repetir=None):
    with _trava:
        itens = _ler()
        item = {"id": max((i["id"] for i in itens), default=0) + 1, "texto": texto,
                "quando": quando.isoformat(timespec="seconds"), "repetir": repetir}
        itens.append(item)
        _gravar(itens)
        return item


def listar():
    with _trava:
        return sorted(_ler(), key=lambda i: i["quando"])


def cancelar(id_lembrete):
    with _trava:
        itens = _ler()
        restantes = [i for i in itens if i["id"] != id_lembrete]
        _gravar(restantes)
        return len(restantes) < len(itens)


def limpar():
    with _trava:
        n = len(_ler())
        _gravar([])
        return n


def vencidos(agora):
    return [i for i in listar() if _quando(i) <= agora]


def concluir(item, agora=None):
    """Depois de avisar: remove o lembrete, ou (se repete) agenda a próxima vez."""
    agora = (agora or dt.datetime.now()).replace(microsecond=0)
    with _trava:
        itens = _ler()
        for i in itens:
            if i["id"] == item["id"]:
                if i.get("repetir"):
                    passo = dt.timedelta(days=1 if i["repetir"] == "diario" else 7)
                    q = _quando(i)
                    while q <= agora:
                        q += passo
                    i["quando"] = q.isoformat(timespec="seconds")
                else:
                    itens.remove(i)
                break
        _gravar(itens)


# ----------------------------------------------------------- frases do aviso
_FRASES = [
    "Lembrete: {t}.",
    "Perdão pela interrupção, mas você me pediu para avisar: {t}.",
    "Hora do seu lembrete: {t}. Depois não diga que eu não avisei.",
    "Só passando para lembrar: {t}.",
]
_FRASES_ATRASADO = [
    "Você tinha um lembrete para as {h} e eu estava fora do ar. Mas ainda dá tempo: {t}.",
    "Com algum atraso, e sem culpa minha: {t}. Era para as {h}.",
]


def frase_de_lembrete(item, atrasado=False):
    texto = item["texto"].strip().rstrip(".!?")
    modelos = _FRASES_ATRASADO if atrasado else _FRASES
    return random.choice(modelos).format(t=texto, h=_quando(item).strftime("%H:%M"))


# ---------------------------------------------------------------- agendador
class Agendador:
    """Verifica de tempos em tempos se algum lembrete venceu e chama ao_vencer(item, atrasado)."""

    def __init__(self, ao_vencer, intervalo=2.0, agora=None):
        self.ao_vencer, self.intervalo = ao_vencer, intervalo
        self._agora = agora or dt.datetime.now
        self._parar = threading.Event()
        self._thread = None

    def iniciar(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def parar(self):
        self._parar.set()

    def _loop(self):
        while not self._parar.is_set():
            self.verificar()
            self._parar.wait(self.intervalo)

    def verificar(self):
        agora = self._agora().replace(microsecond=0)
        for item in vencidos(agora):
            atraso = (agora - _quando(item)).total_seconds()
            pular = bool(item.get("repetir")) and atraso > REPETIDO_ANTIGO
            try:
                if not pular:
                    self.ao_vencer(item, atraso > ATRASO_AVISADO)
            except Exception as erro:
                print(f"⚠ erro ao avisar o lembrete #{item['id']}: {erro}")
            finally:
                concluir(item, agora)

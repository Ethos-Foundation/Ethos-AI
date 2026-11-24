"""
Registro da Ethos: grava em ethos.log o que ela ouviu, respondeu, quais ferramentas usou, tempos
e erros (para você me mandar o trecho e eu enxergar o que aconteceu). Também vigia a janela:
se ela parar de responder, grava no log o que cada parte do programa estava fazendo naquele momento.

O log fica só no seu computador e é ignorado pelo Git. Contém o que você falou: apague quando quiser.
"""

import faulthandler
import logging
import os
import threading
import time
from logging.handlers import RotatingFileHandler

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(PASTA, "ethos.log")
log = logging.getLogger("ethos")
_arquivo_pilhas = None


def resumo(texto, limite=200):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[:limite - 3] + "..."


def iniciar():
    """Liga o registro em arquivo (chame uma vez, no início do programa)."""
    global _arquivo_pilhas
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    manipulador = RotatingFileHandler(ARQUIVO, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    manipulador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(manipulador)
    log.info("=== Ethos iniciada ===")
    try:                                   # também registra quedas feias (erro dentro de biblioteca)
        _arquivo_pilhas = open(ARQUIVO, "a", encoding="utf-8")
        faulthandler.enable(file=_arquivo_pilhas, all_threads=True)
    except Exception:
        _arquivo_pilhas = None


def ultimas_linhas(quantas=40):
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            return "".join(f.readlines()[-quantas:]).strip() or "(registro vazio)"
    except OSError:
        return "(ainda não há registro)"


def _gravar_pilhas():
    if _arquivo_pilhas is not None:
        faulthandler.dump_traceback(file=_arquivo_pilhas, all_threads=True)
        _arquivo_pilhas.flush()


class VigiaDeTravamento:
    """A janela chama batida() a cada instante. Se parar de chamar por `limite` segundos,
    ao_travar() é chamada (uma vez por travamento) e as pilhas de todas as threads vão para o log."""

    def __init__(self, limite=6.0, intervalo=2.0, ao_travar=None):
        self.limite, self.intervalo = limite, intervalo
        self.ao_travar = ao_travar or self._registrar
        self.ultimo = time.time()
        self._avisado = False

    def batida(self):
        self.ultimo = time.time()

    def _registrar(self, atraso):
        log.error("A janela ficou %.0fs sem responder. O que cada parte estava fazendo:", atraso)
        _gravar_pilhas()

    def verificar(self):
        atraso = time.time() - self.ultimo
        if atraso > self.limite and not self._avisado:
            self._avisado = True
            self.ao_travar(atraso)
        elif atraso <= self.limite:
            self._avisado = False

    def iniciar(self):
        def laco():
            while True:
                time.sleep(self.intervalo)
                self.verificar()
        threading.Thread(target=laco, daemon=True).start()

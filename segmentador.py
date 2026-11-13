"""
Segmentador de fala: recebe blocos de áudio do microfone (0,1 s cada) e devolve
a fala completa quando você termina de falar. Sem microfone, sem Whisper: é só
a lógica de "começou / terminou", por isso dá para testar sozinho.
"""

from collections import deque

import numpy as np

import config


class SegmentadorFala:
    def __init__(self, limite=None, silencio_final=None, fala_minima=None,
                 pre_roll=None, max_fala=None, passo=0.1):
        self.limite = config.LIMITE_VOLUME if limite is None else limite
        silencio_final = config.SILENCIO_CONVERSA if silencio_final is None else silencio_final
        fala_minima = config.FALA_MINIMA if fala_minima is None else fala_minima
        pre_roll = config.PRE_ROLL if pre_roll is None else pre_roll
        max_fala = config.GRAVACAO_MAXIMA if max_fala is None else max_fala
        self._n_silencio = max(1, round(silencio_final / passo))
        self._n_minimo = max(1, round(fala_minima / passo))
        self._n_max = max(1, round(max_fala / passo))
        self._pre = deque(maxlen=max(1, round(pre_roll / passo)))
        self._reset()

    def _reset(self):
        self._blocos, self._falando = [], False
        self._com_voz = self._silencio = 0
        self._pre.clear()

    def alimentar(self, bloco):
        """Devolve o áudio (numpy) da fala completa, ou None se ainda não terminou
        (ou se foi só um ruído curto, que é descartado)."""
        volume = float(np.sqrt(np.mean(bloco ** 2)))
        alto = volume > self.limite
        if not self._falando:
            if not alto:
                self._pre.append(bloco)     # guarda um pouco do começo, para não cortar a 1ª sílaba
                return None
            self._falando = True
            self._blocos = list(self._pre)
            self._pre.clear()
        self._blocos.append(bloco)
        if alto:
            self._com_voz += 1
            self._silencio = 0
        else:
            self._silencio += 1
        if self._silencio >= self._n_silencio or len(self._blocos) >= self._n_max:
            audio = np.concatenate(self._blocos) if self._com_voz >= self._n_minimo else None
            self._reset()
            return audio
        return None

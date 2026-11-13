"""Rode na pasta do projeto:  python -m unittest discover tests -v"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from segmentador import SegmentadorFala  # noqa: E402

SILENCIO = np.zeros(1600, dtype=np.float32)
VOZ = np.full(1600, 0.1, dtype=np.float32)


def rodar(blocos, **kw):
    seg = SegmentadorFala(limite=0.01, silencio_final=1.2, fala_minima=0.3,
                          pre_roll=0.3, max_fala=30, **kw)
    saidas = []
    for i, b in enumerate(blocos):
        r = seg.alimentar(b)
        if r is not None:
            saidas.append((i, r))
    return saidas


class TestSegmentador(unittest.TestCase):
    def test_fala_completa(self):
        saidas = rodar([SILENCIO] * 5 + [VOZ] * 10 + [SILENCIO] * 20)
        self.assertEqual(len(saidas), 1)
        indice, audio = saidas[0]
        self.assertEqual(indice, 5 + 10 + 12 - 1)          # termina após 1,2 s de silêncio
        self.assertEqual(len(audio), 1600 * (3 + 10 + 12))  # 3 de pré-roll + fala + silêncio

    def test_ruido_curto_e_ignorado(self):
        self.assertEqual(rodar([SILENCIO] * 5 + [VOZ] * 2 + [SILENCIO] * 20), [])

    def test_pausa_curta_no_meio_nao_corta(self):
        blocos = [VOZ] * 5 + [SILENCIO] * 5 + [VOZ] * 5 + [SILENCIO] * 15
        self.assertEqual(len(rodar(blocos)), 1)

    def test_duas_falas_seguidas(self):
        blocos = ([VOZ] * 6 + [SILENCIO] * 15) * 2
        self.assertEqual(len(rodar(blocos)), 2)

    def test_limite_maximo(self):
        saidas = rodar([VOZ] * 400)
        self.assertEqual(len(saidas), 1)


if __name__ == "__main__":
    unittest.main()

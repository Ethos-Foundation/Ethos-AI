"""Desenho do orbe (hexágonos concêntricos) da Ethos, usado pela janela e pelo pet."""

import math


def blend(cor_a, cor_b, k):
    """Mistura duas cores #rrggbb (k=0 -> a, k=1 -> b). Simula transparência."""
    a = [int(cor_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(cor_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * k) for x, y in zip(a, b))


ALVO_AMPLITUDE = {"carregando": .3, "espera": .12, "ouvindo": .55, "olhando": .5, "pensando": .3, "falando": .85}


def desenhar(canvas, cx, cy, escala, t, estado, amp, fundo, frente, k_inicial=0, tag="orbe"):
    """Redesenha o orbe (apaga só os itens com a `tag`, então dá para ter outros
    desenhos no mesmo canvas)."""
    canvas.delete(tag)
    vel = 1.4 if estado == "pensando" else .22
    for i in range(6):
        voz = abs(math.sin(t * 6 + i * 1.3)) if estado == "falando" else 1
        r = (62 + i * 28 + math.sin(t * 1.6 + i) * amp * 12 * voz) * escala
        rot = (-1 if i % 2 else 1) * t * vel * (1 + i * .25) + i * .35
        pontos = []
        for j in range(6):
            a = rot + j * math.pi / 3
            pontos += [cx + r * math.cos(a), cy + r * math.sin(a)]
        canvas.create_polygon(pontos, outline=blend(fundo, frente, .8 - i * .12),
                              fill="", width=2 if i == 0 else 1, tags=tag)
    pulso = (.6 + .4 * math.sin(t * 9)) if estado == "falando" else 1
    rc = (20 + amp * 18 * pulso) * escala
    for k in range(k_inicial, 7):   # brilho do núcleo (círculos que vão clareando)
        raio = rc * (2.2 - k * .3)
        canvas.create_oval(cx - raio, cy - raio, cx + raio, cy + raio,
                           fill=blend(fundo, "#ffffff", .08 + k * .15), outline="", tags=tag)

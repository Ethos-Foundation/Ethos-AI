"""
Compara as vozes lado a lado. Rode:  python testar_vozes.py

Piper funciona direto. Para testar o Kokoro (voz mais natural):
  1) pip install kokoro-onnx
  2) baixe kokoro-v1.0.onnx e voices-v1.0.bin (página de releases do projeto
     kokoro-onnx, no GitHub, versão "model-files-v1.0") e coloque nesta pasta.
"""

import time

import sounddevice as sd

import ethos_ai_voz as voz

FRASES = {
    "pt": "Boa noite. Todos os sistemas estão operando normalmente, e eu continuo achando você bastante interessante.",
}

TESTES = [
    ("Piper (atual)", "pt", dict(motor="piper")),
    ("Kokoro pf_dora (feminina)", "pt", dict(motor="kokoro", voz_kokoro="pf_dora")),
    ("Kokoro pm_alex (masculina)", "pt", dict(motor="kokoro", voz_kokoro="pm_alex")),
    ("Kokoro pm_santa (masculina)", "pt", dict(motor="kokoro", voz_kokoro="pm_santa")),
]

for nome, idioma, opcoes in TESTES:
    print(f"\n▶ {nome}")
    try:
        inicio = time.time()
        audio, taxa = voz.sintetizar(FRASES[idioma], idioma, **opcoes)
        gerar, duracao = time.time() - inicio, len(audio) / taxa
        print(f"  gerou {duracao:.1f}s de áudio em {gerar:.1f}s (abaixo de 1.0x do tempo = tempo real)")
        sd.play(audio, taxa)
        sd.wait()
    except Exception as erro:
        print(f"  pulado: {erro}")
print("\nPara usar o Kokoro: em config.py, MOTOR_VOZ = \"kokoro\" e a voz em VOZ_KOKORO.")

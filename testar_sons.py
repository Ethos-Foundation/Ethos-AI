"""
Toca os efeitos sonoros da Ethos, um por vez, para você escolher o estilo.
Rode:  python testar_sons.py            (estilo atual do config.py)
       python testar_sons.py classico   (ou: futurista)
"""

import sys

import config
import efeitos

if len(sys.argv) > 1:
    config.ESTILO_SONS = sys.argv[1]

DESCRICAO = {"ativar": "começou a ouvir você", "concluir": "entendeu o que você disse",
             "alerta": "lembrete", "erro": "algo deu errado", "captura": "tirou print da tela",
             "ligar": "conversa contínua ligada", "desligar": "conversa contínua desligada",
             "tique_a": "processando (1)", "tique_b": "processando (2)"}

print(f"Estilo: {config.ESTILO_SONS}. Aperte ENTER para ouvir cada som (ou escreva 'sair').\n")
for nome in efeitos.NOMES:
    if input(f"▶ {nome}: {DESCRICAO[nome]}  ").strip().lower() == "sair":
        break
    efeitos.tocar(nome)
print("\nPara trocar o estilo: ESTILO_SONS no config.py. Para usar sons seus: arquivos .wav na pasta sons/.")

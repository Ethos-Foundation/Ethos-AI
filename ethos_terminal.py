"""
Ethos AI - modo terminal (sem janela). Rode:  python ethos_terminal.py
"""

import re

import cerebro
import texto
import ethos_ai_voz as voz


def mostrar_ajuda():
    print("  /conversa  bate-papo em português")
    print("  /ingles    treino de inglês (você fala inglês, ela corrige)")
    print("  /tradutor  tradução português <-> inglês")
    print("  ENTER      falar | ou digite o texto | 'sair' encerra\n")


def _despachar(eventos, locutor):
    for tipo, trecho in eventos:
        if tipo == "frase":
            locutor.dizer(trecho)
        else:  # "tela" e "conteudo" aparecem no terminal
            print(trecho, end="", flush=True)


def responder(pergunta, idioma):
    roteador = texto.RoteadorResposta()
    locutor = voz.Locutor(cerebro.idioma_da_resposta(idioma))
    print("ETHOS  > ", end="", flush=True)
    try:
        for pedaco in cerebro.conversar(pergunta):
            _despachar(roteador.alimentar(pedaco), locutor)
        _despachar(roteador.finalizar(), locutor)
    finally:
        locutor.terminar()
    print("\n")


def main():
    cerebro.trocar_modo("conversa")
    print("=" * 58)
    print("  ETHOS AI online.")
    print("=" * 58)
    mostrar_ajuda()
    voz.falar("Ethos AI online. Como posso ajudar?")

    while True:
        entrada = input(f"[{cerebro.estado['modo']}] ENTER para falar (ou digite): ").strip()

        if entrada.lower() in ("sair", "exit", "quit"):
            voz.falar("Encerrando sistemas. Até logo.")
            break

        if entrada.lower() in ("/ajuda", "/help"):
            mostrar_ajuda()
            continue

        if entrada.startswith("/") and entrada[1:].lower() in cerebro.MODOS:
            novo = entrada[1:].lower()
            cerebro.trocar_modo(novo)
            idioma_aviso, frase = cerebro.MODOS[novo]["aviso"]
            print(f"ETHOS  > {frase}\n")
            voz.falar(frase, idioma_aviso)
            continue

        if entrada:
            pergunta = entrada
            idioma = "en" if re.search(r"\b(the|is|are|you|and|what|how)\b", entrada, re.I) else "pt"
            if cerebro.estado["modo"] == "ingles":
                idioma = "en"
        else:
            pergunta, idioma = voz.ouvir(cerebro.idioma_de_escuta())

        if not pergunta:
            print("(não entendi nada, tente de novo)\n")
            continue

        print(f"VOCÊ   > {pergunta}")
        responder(pergunta, idioma)


if __name__ == "__main__":
    main()

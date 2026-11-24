"""
Ethos AI - modo terminal (sem janela). Rode:  python ethos_terminal.py
"""

import cerebro
import registro
import texto
import ethos_ai_voz as voz


def mostrar_ajuda():
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
    for aviso in cerebro.pegar_avisos():
        print(f"[{aviso}]")


def main():
    registro.iniciar()
    cerebro.trocar_modo("conversa")
    print("=" * 58)
    print("  ETHOS AI online.")
    print("=" * 58)
    mostrar_ajuda()
    voz.falar("Ethos AI online. Como posso ajudar?")

    while True:
        entrada = input("ENTER para falar (ou digite): ").strip()

        if entrada.lower() in ("sair", "exit", "quit"):
            voz.falar("Encerrando sistemas. Até logo.")
            break

        if entrada.lower() in ("/ajuda", "/help"):
            mostrar_ajuda()
            continue

        if entrada:
            pergunta, idioma = entrada, "pt"
        else:
            pergunta, idioma = voz.ouvir(cerebro.idioma_de_escuta())

        if not pergunta:
            print("(não entendi nada, tente de novo)\n")
            continue

        print(f"VOCÊ   > {pergunta}")
        responder(pergunta, idioma)


if __name__ == "__main__":
    main()

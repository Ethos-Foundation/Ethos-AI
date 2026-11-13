"""
Compara modelos de visão na SUA máquina: tempo, memória de vídeo e qualidade.
Rode:  python testar_visao.py                 (testa o MODELO_VISAO do config.py e o qwen3-vl:2b)
       python testar_visao.py qwen3-vl:4b     (testa só os modelos que você listar)

Antes: atualize o Ollama (os modelos qwen3-vl exigem a versão 0.12.7 ou mais nova) e baixe
o modelo, por exemplo:  ollama pull qwen3-vl:4b
"""

import sys
import time

import ollama

import config
import visao


def instalados():
    try:
        return {m.model for m in ollama.list().models}
    except Exception as erro:
        raise SystemExit(f"Não consegui falar com o Ollama: {erro}")


def uso_gpu():
    """O que está carregado agora e quanto está na GPU (o que importa nos seus 6 GB)."""
    try:
        modelos = ollama.ps().models
    except Exception:
        return "?"
    partes = []
    for m in modelos or []:
        total, vram = getattr(m, "size", 0) or 0, getattr(m, "size_vram", 0) or 0
        nome = getattr(m, "model", None) or getattr(m, "name", "?")
        partes.append(f"{nome}: {total / 1e9:.1f} GB, {100 * vram / total if total else 0:.0f}% na GPU")
    return "; ".join(partes) or "(nada carregado)"


def tempo_modelo_principal():
    inicio = time.time()
    ollama.chat(model=config.MODELO_IA, messages=[{"role": "user", "content": "Diga olá."}],
                think=False, keep_alive=config.KEEP_ALIVE)
    return time.time() - inicio


def main():
    modelos = sys.argv[1:] or [config.MODELO_VISAO, "qwen3-vl:2b"]
    ja_tem = instalados()
    print("Vou capturar a tela em 5 segundos: deixe aberto o que você quer que ela veja.")
    for i in range(5, 0, -1):
        print(f"  {i}...", end="\r", flush=True)
        time.sleep(1)
    jpeg = visao.capturar_tela()
    with open("captura_teste.jpg", "wb") as f:
        f.write(jpeg)
    print(f"Captura salva em captura_teste.jpg ({len(jpeg) / 1024:.0f} KB): é exatamente o que será enviado.\n")

    for modelo in dict.fromkeys(modelos):
        print("=" * 70)
        print(f"MODELO: {modelo}")
        if modelo not in ja_tem and f"{modelo}:latest" not in ja_tem:
            print(f"  não instalado. Para testar: ollama pull {modelo}\n")
            continue
        for rotulo in ("1ª chamada (inclui carregar o modelo)", "2ª chamada (modelo já carregado)"):
            inicio = time.time()
            texto = visao.analisar_imagem(jpeg, "O que está na minha tela? Seja breve.", modelo=modelo)
            print(f"\n  {rotulo}: {time.time() - inicio:.1f}s")
            print(f"  GPU agora: {uso_gpu()}")
        print("\n  Descrição:\n  " + texto.replace("\n", "\n  "))
        print(f"\n  Voltar a conversar com o modelo principal ({config.MODELO_IA}) levou "
              f"{tempo_modelo_principal():.1f}s")
        print(f"  GPU depois: {uso_gpu()}\n")
    print("Dica: se 'na GPU' ficar abaixo de 100%, o modelo está sendo dividido com a CPU e fica lento.")


if __name__ == "__main__":
    main()

"""
Orquestrador da Ethos AI: o fluxo ouvir -> pensar -> falar, a conversa contínua
e as interrupções. Não sabe nada de janela: fala com a interface por um callback
`ui(**mensagem)` e usa o módulo de voz que for injetado (o real, ou um falso nos testes).

Mensagens enviadas à interface:
  usuario=texto   uma pergunta sua (nova bolha no chat)
  token=texto     pedaço da resposta falada/mostrada
  conteudo=texto  pedaço de conteúdo longo (código, texto) da resposta
  fim=True        a resposta terminou
  voce=texto      aviso do sistema (erro, "carregando...")
  estado=...      espera | ouvindo | pensando | falando
  modo=..., continuo=bool
"""

import queue
import threading
import time

import cerebro
import config
import lembretes
import texto


class LocutorMudo:
    """Faz o papel do Locutor quando a voz está desligada (chat só de texto)."""
    cortado = False

    def dizer(self, frase): pass
    def terminar(self): pass
    def cortar(self): self.cortado = True


class Orquestrador:
    def __init__(self, ui, voz):
        self.ui = ui
        self.voz = voz
        self.ocupado = threading.Lock()       # impede dois pedidos ao mesmo tempo
        self.ouvindo = threading.Event()      # ligado enquanto o microfone grava (fala única)
        self.conversa_ativa = threading.Event()
        self.locutor_atual = None
        self.parar_gravacao_agora = False
        self.falar_respostas = True           # False = chat só de texto
        self.alertas = queue.Queue()          # lembretes vencidos esperando ela ficar livre

    def _whisper_pronto(self):
        """Se o reconhecimento de voz ainda está carregando, avisa em vez de ficar mudo."""
        pronto = getattr(self.voz, "whisper_pronto", lambda: True)()
        if not pronto:
            self.ui(voce="Ainda carregando o reconhecimento de voz, um instante...")
        return pronto

    def _erro(self, erro):
        msg = texto.mensagem_de_erro(erro, config.MODELO_IA)
        print(f"⚠ {erro!r}")
        self.ui(voce=msg)
        if self.falar_respostas:
            try:
                self.voz.falar(msg, "pt")
            except Exception:
                pass

    # ----------------------------- respostas ---------------------------
    def responder(self, pergunta, idioma):
        """Resposta com streaming real: cada frase é falada assim que fica pronta,
        enquanto o modelo ainda gera o resto."""
        self.ui(estado="pensando")
        inicio = time.time()
        marcos = {}

        def ao_comecar_a_falar():
            marcos["fala"] = time.time() - inicio
            self.ui(estado="falando")

        if self.falar_respostas:
            locutor = self.voz.Locutor(cerebro.idioma_da_resposta(idioma), ao_comecar=ao_comecar_a_falar)
        else:
            locutor = LocutorMudo()
        self.locutor_atual = locutor
        roteador = texto.RoteadorResposta()

        def despachar(eventos):
            for tipo, trecho in eventos:
                if tipo == "tela":
                    self.ui(token=trecho)
                elif tipo == "frase":
                    locutor.dizer(trecho)
                elif tipo == "conteudo":
                    self.ui(conteudo=trecho)

        gerador = cerebro.conversar(pergunta)
        self.voz.iniciar_som_processando()
        try:
            for pedaco in gerador:
                if locutor.cortado:       # interrompida: para de gerar também
                    break
                marcos.setdefault("modelo", time.time() - inicio)
                self.voz.parar_som_processando()
                despachar(roteador.alimentar(pedaco))
            despachar(roteador.finalizar())
        finally:
            gerador.close()
            self.voz.parar_som_processando()
            locutor.terminar()
            self.locutor_atual = None
            self.ui(fim=True)

        print(f"⏱ 1º texto do modelo em {marcos.get('modelo', 0):.1f}s, "
              f"fala começou em {marcos.get('fala', 0):.1f}s, total {time.time() - inicio:.1f}s")

    # ------------------------------ lembretes ---------------------------
    def anunciar(self, lembrete, atrasado=False):
        """Chamado pelo agendador (thread dele) quando um lembrete vence."""
        self.alertas.put((lembrete, atrasado))
        if not self.conversa_ativa.is_set():          # na conversa contínua o próprio laço avisa
            threading.Thread(target=self._esvaziar_alertas, daemon=True).start()

    def _esvaziar_alertas(self):
        """Espera ela ficar livre (até 10 min) e fala os avisos pendentes."""
        for _ in range(1200):
            if self.ocupado.acquire(blocking=False):
                break
            if self.conversa_ativa.is_set():
                return
            time.sleep(0.5)
        else:
            return
        try:
            self._falar_alertas_pendentes()
        finally:
            self.ui(estado="espera")
            self.ocupado.release()

    def _falar_alertas_pendentes(self):
        """Quem chama já está com `ocupado`."""
        while True:
            try:
                lembrete, atrasado = self.alertas.get_nowait()
            except queue.Empty:
                return
            self._falar_alerta(lembrete, atrasado)

    def _falar_alerta(self, lembrete, atrasado):
        frase = lembretes.frase_de_lembrete(lembrete, atrasado)
        try:
            self.voz.tocar_efeito("alerta")
        except Exception:
            pass
        self.ui(token=frase, fim=True)                # aparece no chat e no balão do pet
        if not self.falar_respostas:
            return
        locutor = self.voz.Locutor("pt", ao_comecar=lambda: self.ui(estado="falando"))
        self.locutor_atual = locutor
        try:
            locutor.dizer(frase)
        finally:
            locutor.terminar()
            self.locutor_atual = None

    # ---------------------------- interrupções --------------------------
    def interromper_fala(self):
        """Corta a fala na hora (e para de gerar o resto da resposta)."""
        if self.locutor_atual is not None:
            self.locutor_atual.cortar()

    def parar_de_ouvir_agora(self):
        """Corta a gravação em andamento (botão ou atalho, útil em ambiente barulhento)."""
        self.parar_gravacao_agora = True
        threading.Timer(0.4, lambda: setattr(self, "parar_gravacao_agora", False)).start()

    # -------------------------- conversa contínua -----------------------
    def loop_conversa(self):
        """Ouve -> responde -> ouve de novo, até ser desligada. O microfone fica
        FECHADO enquanto ela fala (a caixa do notebook não vira eco)."""
        if not self.ocupado.acquire(blocking=False):
            self.conversa_ativa.clear()
            return
        self.ui(continuo=True)
        try:
            self.voz.tocar_efeito("ativar")
            while self.conversa_ativa.is_set():
                self._falar_alertas_pendentes()
                self.ui(estado="ouvindo")
                pergunta, idioma = self.voz.ouvir_uma_fala(
                    idioma_esperado=cerebro.idioma_de_escuta(),
                    verificar_parar=lambda: (not self.conversa_ativa.is_set()
                                             or not self.alertas.empty()))
                if not self.conversa_ativa.is_set():
                    break
                if not pergunta:
                    continue
                self.ui(usuario=pergunta)
                self.responder(pergunta, idioma)
                time.sleep(config.PAUSA_POS_FALA)
        except Exception as erro:
            self._erro(erro)
        finally:
            self.conversa_ativa.clear()
            self.voz.parar_som_processando()
            self.ui(estado="espera", continuo=False, fim=True)
            self.ocupado.release()
            # fim da conversa: revisa o que sobrou e anota o que for importante
            threading.Thread(target=cerebro.curar_memoria, daemon=True).start()

    def alternar_conversa(self):
        """Liga/desliga a conversa contínua (botão ou atalho)."""
        if self.conversa_ativa.is_set():
            self.conversa_ativa.clear()
            self.interromper_fala()
        elif not self.ocupado.locked() and self._whisper_pronto():
            self.conversa_ativa.set()
            threading.Thread(target=self.loop_conversa, daemon=True).start()

    # ------------------------------ tarefas -----------------------------
    def acao(self, acao, dados):
        threading.Thread(target=self.tarefa, args=(acao, dados), daemon=True).start()

    def tarefa(self, acao, dados):
        if not self.ocupado.acquire(blocking=False):
            return
        try:
            if acao == "ouvir":
                if not self._whisper_pronto():
                    return
                self.ui(estado="ouvindo")
                self.voz.tocar_efeito("ativar")
                self.ouvindo.set()
                try:
                    pergunta, idioma = self.voz.ouvir(
                        idioma_esperado=cerebro.idioma_de_escuta(),
                        verificar_parar=lambda: self.parar_gravacao_agora)
                finally:
                    self.ouvindo.clear()
                if pergunta:
                    self.voz.tocar_efeito("concluir")
            elif acao == "texto":
                pergunta, idioma = dados, "pt"
            elif acao == "modo":
                cerebro.trocar_modo(dados)
                self.ui(modo=dados)
                idioma_aviso, frase = cerebro.MODOS[dados]["aviso"]
                self.ui(voce=frase, estado="falando")
                if self.falar_respostas:
                    self.voz.falar(frase, idioma_aviso)
                return
            else:
                return
            if not pergunta:
                self.ui(voce="(não entendi, tente de novo)")
                return
            self.ui(usuario=pergunta)
            self.responder(pergunta, idioma)
        except Exception as erro:
            self._erro(erro)
        finally:
            self.voz.parar_som_processando()
            self.ui(estado="espera", fim=True)
            self.ocupado.release()

    def ao_apertar_atalho(self):
        """Atalho de falar uma vez (thread do teclado):
        gravando -> para a gravação | livre -> começa | ocupado -> ignora."""
        if self.ouvindo.is_set():
            self.parar_de_ouvir_agora()
        elif not self.ocupado.locked():
            self.acao("ouvir", None)

    def ao_clicar(self):
        """Clique no pet: falando -> corta a fala | gravando -> para de gravar |
        livre -> liga o microfone para uma pergunta."""
        if self.locutor_atual is not None:
            self.interromper_fala()
        else:
            self.ao_apertar_atalho()

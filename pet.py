"""
Pet da Ethos: um orbe pequeno, sem borda, sempre por cima das outras janelas.
  clique        -> liga o microfone para uma pergunta (ou corta a fala, se ela estiver falando)
  arrastar      -> muda de lugar (a posição é lembrada)
  botão direito -> menu (abrir janela, conversa contínua, calar, esconder, sair)
Mostra um balão com o começo da última resposta por alguns segundos.
"""

import time
import tkinter as tk

import orbe

CHAVE = "#010203"        # cor "transparente" (Windows)
FUNDO, FRENTE = "#131418", "#eef0f5"
LARGURA, ALTURA = 230, 280
CENTRO = (LARGURA // 2, 200)
ESCALA = .27
NOMES = {"carregando": "CARREGANDO", "ouvindo": "OUVINDO", "pensando": "PENSANDO", "falando": "FALANDO"}


class Pet:
    def __init__(self, raiz, orq, obter_estado, abrir_janela, sair, prefs, salvar_prefs):
        self.raiz, self.orq, self.obter_estado = raiz, orq, obter_estado
        self.abrir_janela, self.sair = abrir_janela, sair
        self.prefs, self.salvar_prefs = prefs, salvar_prefs
        self.t, self.amp = 0.0, .12
        self.fala, self.fala_ate = "", 0.0
        self.ativo = True

        self.janela = tk.Toplevel(raiz)
        self.janela.overrideredirect(True)
        self.janela.attributes("-topmost", True)
        try:
            self.janela.attributes("-transparentcolor", CHAVE)
            fundo = CHAVE
        except tk.TclError:                    # fora do Windows: fundo sólido
            fundo = FUNDO
        self.janela.configure(bg=fundo)
        self.canvas = tk.Canvas(self.janela, width=LARGURA, height=ALTURA, bg=fundo,
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack()

        x = prefs.get("pet_x")
        y = prefs.get("pet_y")
        if x is None or y is None:
            x = raiz.winfo_screenwidth() - LARGURA - 30
            y = raiz.winfo_screenheight() - ALTURA - 70
        self.janela.geometry(f"{LARGURA}x{ALTURA}+{int(x)}+{int(y)}")

        self.menu = tk.Menu(self.janela, tearoff=0)
        self.menu.add_command(label="Abrir janela", command=self.abrir_janela)
        self.menu.add_command(label="Conversa contínua (liga/desliga)", command=orq.alternar_conversa)
        self.menu.add_command(label="Calar", command=orq.interromper_fala)
        self.menu.add_separator()
        self.menu.add_command(label="Esconder o pet", command=self.esconder_com_seguranca)
        self.menu.add_command(label="Sair da Ethos", command=self.sair)

        self.canvas.bind("<ButtonPress-1>", self._apertou)
        self.canvas.bind("<B1-Motion>", self._arrastou)
        self.canvas.bind("<ButtonRelease-1>", self._soltou)
        self.canvas.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

        self._animar()
        self._manter_no_topo()

    # ---------------------------- mouse ----------------------------
    def _apertou(self, e):
        self._o = (e.x_root, e.y_root)
        self._p = (self.janela.winfo_x(), self.janela.winfo_y())
        self._moveu = False

    def _arrastou(self, e):
        dx, dy = e.x_root - self._o[0], e.y_root - self._o[1]
        if abs(dx) + abs(dy) > 4:
            self._moveu = True
        if self._moveu:
            self.janela.geometry(f"+{self._p[0] + dx}+{self._p[1] + dy}")

    def _soltou(self, _e):
        if self._moveu:
            self.prefs["pet_x"], self.prefs["pet_y"] = self.janela.winfo_x(), self.janela.winfo_y()
            self.salvar_prefs(self.prefs)
        else:
            self.orq.ao_clicar()

    # ------------------------- visibilidade ------------------------
    @property
    def visivel(self):
        return self.ativo

    def mostrar(self):
        self.janela.deiconify()
        self.ativo = True
        self.prefs["pet"] = True
        self.salvar_prefs(self.prefs)

    def esconder(self):
        self.janela.withdraw()
        self.ativo = False
        self.prefs["pet"] = False
        self.salvar_prefs(self.prefs)

    def esconder_com_seguranca(self):
        """Nunca deixa a Ethos sem nenhuma janela visível: abre a principal antes."""
        self.abrir_janela()
        self.esconder()

    # ----------------------------- balão ---------------------------
    def mostrar_fala(self, texto):
        texto = " ".join(texto.split())
        if len(texto) > 150:
            texto = texto[:147].rstrip() + "..."
        self.fala = texto
        self.fala_ate = time.time() + max(5.0, len(texto) * 0.07)
        self._desenhar_balao()

    def _desenhar_balao(self):
        self.canvas.delete("balao")
        if not self.fala or time.time() > self.fala_ate:
            self.fala = ""
            return
        id_texto = self.canvas.create_text(LARGURA // 2, 118, text=self.fala, width=LARGURA - 40,
                                           font=("Segoe UI", 9), fill="#101114", anchor="s", tags="balao")
        x0, y0, x1, y1 = self.canvas.bbox(id_texto)
        fundo = self.canvas.create_rectangle(x0 - 10, y0 - 8, x1 + 10, y1 + 8, fill="#eef0f5",
                                             outline="#7d818c", tags="balao")
        ponta = self.canvas.create_polygon(LARGURA // 2 - 8, y1 + 8, LARGURA // 2 + 8, y1 + 8,
                                           LARGURA // 2, y1 + 18, fill="#eef0f5", outline="#7d818c", tags="balao")
        self.canvas.tag_raise(id_texto)
        self.canvas.tag_lower(ponta)
        self.canvas.tag_lower(fundo)

    # --------------------------- animação --------------------------
    def _animar(self):
        estado = self.obter_estado()
        self.t += 0.033
        self.amp += (orbe.ALVO_AMPLITUDE.get(estado, .12) - self.amp) * .06
        orbe.desenhar(self.canvas, CENTRO[0], CENTRO[1], ESCALA, self.t, estado, self.amp,
                      FUNDO, FRENTE, k_inicial=2)
        self.canvas.delete("status")
        if estado in NOMES:
            self.canvas.create_text(CENTRO[0], ALTURA - 14, text=NOMES[estado], fill=FRENTE,
                                    font=("Segoe UI", 8, "bold"), tags="status")
        if self.fala and time.time() > self.fala_ate:
            self._desenhar_balao()
        self.janela.after(33, self._animar)

    def _manter_no_topo(self):
        """Reafirma 'sempre no topo' de vez em quando, sem forçar a janela para a frente
        (o lift() repetido atrapalhava as outras janelas)."""
        if self.visivel:
            self.janela.attributes("-topmost", True)
        self.janela.after(15000, self._manter_no_topo)

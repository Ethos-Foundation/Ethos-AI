"""
Ethos AI - janela de chat (tkinter, já vem com o Python) + pet no canto da tela.
Aqui só fica o desenho da interface; a lógica de conversa está em orquestrador.py.

Coloque na MESMA pasta dos outros arquivos e rode:
    python ethos_ai_gui.py
"""

import json
import os
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk

import cerebro
import config
import ethos_ai_voz as ethos
import ferramentas_lembretes
import lembretes
import memoria
import orbe
import preferencias
import texto
from orquestrador import Orquestrador
from pet import Pet

BG, PAINEL, FG, DIM, LINHA = "#131418", "#1a1b20", "#eef0f5", "#7d818c", "#2a2c33"
NOMES = {"carregando": "CARREGANDO", "espera": "EM ESPERA", "ouvindo": "OUVINDO",
         "pensando": "PROCESSANDO", "falando": "FALANDO"}
ARQUIVO_CHAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_ethos.json")
MAX_CHAT = 80     # quantas mensagens do histórico visual são lembradas entre aberturas

fila = queue.Queue()          # mensagens das threads de trabalho -> janela


def enviar(**msg):
    fila.put(msg)


orq = Orquestrador(enviar, ethos)   # toda a lógica de conversa vive aqui


def pre_carregar():
    """Carrega vozes e Whisper em segundo plano, com a janela já aberta e avisos na tela."""
    enviar(estado="carregando")
    try:
        enviar(voce="Carregando as vozes...")
        ethos.carregar_vozes()
        enviar(voce="Carregando o reconhecimento de voz (na 1ª vez baixa o modelo e demora)...")
        ethos.carregar_whisper()
        enviar(voce="Pronta. Pode falar ou escrever.")
    except Exception as erro:
        enviar(voce=texto.mensagem_de_erro(erro, config.MODELO_IA))
    enviar(estado="espera")


class App:
    def __init__(self, raiz):
        self.raiz, self.estado, self.amp, self.t = raiz, "espera", 0.1, 0.0
        self.prefs = preferencias.carregar()
        orq.falar_respostas = self.prefs["voz"]
        self.bolha, self.em_codigo = False, False     # há uma resposta da Ethos em andamento?
        self.resposta, self.conteudo = "", ""
        self.registro = self._ler_registro()

        raiz.title("ETHOS AI")
        raiz.configure(bg=BG)
        raiz.geometry("560x820")
        raiz.minsize(440, 560)
        raiz.protocol("WM_DELETE_WINDOW", self.ao_fechar)
        self.tela_cheia = False
        raiz.bind("<F11>", self.alternar_tela_cheia)
        raiz.bind("<Escape>", self.sair_tela_cheia)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        estilo.configure("TNotebook", background=BG, borderwidth=0)
        estilo.configure("TNotebook.Tab", background=BG, foreground=DIM, padding=(16, 8), font=("Segoe UI", 9))
        estilo.map("TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", FG)])

        abas = ttk.Notebook(raiz)
        abas.pack(fill="both", expand=True)
        aba_conversa, aba_ajuda = tk.Frame(abas, bg=BG), tk.Frame(abas, bg=BG)
        abas.add(aba_conversa, text="CONVERSA")
        abas.add(aba_ajuda, text="AJUDA")
        self._montar_conversa(aba_conversa)
        self._montar_ajuda(aba_ajuda)

        for item in self.registro:
            self._mostrar_registro(item)

        self.pet = Pet(raiz, orq, lambda: self.estado, self.abrir_janela, self.sair,
                       self.prefs, preferencias.salvar)
        if not self.prefs["pet"]:
            self.pet.janela.withdraw()
            self.pet.ativo = False
        self._atualizar_botoes()

        self.animar()
        self.ler_fila()

    # ------------------------------------------------------------ layout
    def botao(self, pai, rotulo, comando):
        return tk.Button(pai, text=rotulo, command=comando, bg=BG, fg=FG, activebackground=LINHA,
                         activeforeground=FG, relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=LINHA, padx=10, pady=6, font=("Segoe UI", 9), cursor="hand2")

    def _montar_conversa(self, aba):
        # Controles fixos primeiro (rodapé e topo): sempre visíveis; só o chat do meio encolhe.
        rodape = tk.Frame(aba, bg=BG)
        rodape.pack(side="bottom", fill="x", padx=12, pady=(4, 12))
        linha_botoes = tk.Frame(rodape, bg=BG)
        linha_botoes.pack(side="bottom", fill="x", pady=(8, 0))
        linha_entrada = tk.Frame(rodape, bg=BG)
        linha_entrada.pack(side="bottom", fill="x")

        self.entrada = tk.Text(linha_entrada, height=3, wrap="word", bg=PAINEL, fg=FG, insertbackground=FG,
                               relief="flat", highlightthickness=1, highlightbackground=LINHA,
                               highlightcolor=FG, font=("Segoe UI", 11), padx=8, pady=6)
        self.entrada.pack(side="left", fill="x", expand=True)
        self.entrada.bind("<Return>", self.enviar_entrada)       # Enter envia
        self.entrada.bind("<Shift-Return>", lambda e: None)      # Shift+Enter quebra linha
        self.botao(linha_entrada, "ENVIAR ▸", self.enviar_entrada).pack(side="left", padx=(8, 0), fill="y")

        self.botao_falar = self.botao(linha_botoes, "●  FALAR", lambda: orq.acao("ouvir", None))
        self.botao_falar.pack(side="left", padx=(0, 6))
        self.botao(linha_botoes, "■ PARAR", orq.parar_de_ouvir_agora).pack(side="left", padx=6)
        self.botao_continuo = self.botao(linha_botoes, "∞ CONTÍNUO", orq.alternar_conversa)
        self.botao_continuo.pack(side="left", padx=6)
        self.botao(linha_botoes, "✕ CALAR", orq.interromper_fala).pack(side="left", padx=6)
        self.botao_voz = self.botao(linha_botoes, "VOZ: LIGADA", self.alternar_voz)
        self.botao_voz.pack(side="left", padx=6)

        topo = tk.Frame(aba, bg=BG)
        topo.pack(side="top", fill="x", padx=12, pady=(10, 4))
        self.tela = tk.Canvas(topo, width=110, height=110, bg=BG, highlightthickness=0)
        self.tela.pack(side="left")
        info = tk.Frame(topo, bg=BG)
        info.pack(side="left", fill="x", expand=True, padx=(10, 0))
        tk.Label(info, text="E T H O S   A I", bg=BG, fg=FG, font=("Segoe UI", 12)).pack(anchor="w")
        self.st = tk.Label(info, text="EM ESPERA", bg=BG, fg=DIM, font=("Segoe UI", 9))
        self.st.pack(anchor="w", pady=(0, 6))
        modos = tk.Frame(info, bg=BG)
        modos.pack(anchor="w")
        self.botoes = {}
        for nome, rotulo in (("conversa", "CONVERSA"), ("ingles", "INGLÊS"), ("tradutor", "TRADUTOR")):
            self.botoes[nome] = self.botao(modos, rotulo, lambda n=nome: orq.acao("modo", n))
            self.botoes[nome].pack(side="left", padx=(0, 5))
        self.marcar("conversa")
        extras = tk.Frame(info, bg=BG)
        extras.pack(anchor="w", pady=(6, 0))
        self.botao_pet = self.botao(extras, "PET", self.alternar_pet)
        self.botao_pet.pack(side="left", padx=(0, 5))
        self.botao(extras, "LIMPAR CHAT", self.limpar_chat).pack(side="left", padx=5)

        corpo = tk.Frame(aba, bg=BG)
        corpo.pack(side="top", fill="both", expand=True, padx=12, pady=(4, 4))
        self.chat = tk.Text(corpo, bg=PAINEL, fg=FG, font=("Segoe UI", 11), wrap="word", relief="flat",
                            padx=12, pady=10, state="disabled", cursor="arrow", spacing1=1, spacing3=1,
                            highlightthickness=0)
        rolagem = tk.Scrollbar(corpo, orient="vertical", command=self.chat.yview, bg=BG, troughcolor=BG)
        self.chat.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.chat.pack(side="left", fill="both", expand=True)
        c = self.chat.tag_configure
        c("nome_usuario", foreground=DIM, font=("Segoe UI", 8, "bold"), justify="right", rmargin=8,
          lmargin1=60, lmargin2=60, spacing1=6)
        c("usuario", background="#2b2d36", foreground=FG, justify="right", lmargin1=60, lmargin2=60,
          rmargin=8, spacing1=2, spacing3=2)
        c("nome_ethos", foreground="#8fb4ff", font=("Segoe UI", 8, "bold"), lmargin1=8, lmargin2=8,
          rmargin=60, spacing1=6)
        c("ethos", foreground=FG, lmargin1=8, lmargin2=8, rmargin=60)
        c("codigo", font=("Consolas", 10), background="#0e0f12", foreground="#d6dae6",
          lmargin1=16, lmargin2=16, rmargin=16)
        c("sistema", foreground=DIM, font=("Segoe UI", 9, "italic"), justify="center", spacing1=4, spacing3=4)
        c("espaco", font=("Segoe UI", 5))

    def _montar_ajuda(self, aba):
        canvas = tk.Canvas(aba, bg=BG, highlightthickness=0)
        rolagem = tk.Scrollbar(aba, orient="vertical", command=canvas.yview, bg=BG)
        canvas.configure(yscrollcommand=rolagem.set)
        canvas.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        interior = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=interior, anchor="nw")
        interior.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def titulo(txt):
            tk.Label(interior, text=txt, bg=BG, fg=FG, font=("Segoe UI", 12, "bold"),
                     anchor="w").pack(fill="x", padx=20, pady=(18, 4))

        def item(cmd, explicacao):
            linha = tk.Frame(interior, bg=BG)
            linha.pack(fill="x", padx=20, pady=2)
            tk.Label(linha, text=cmd, bg=BG, fg=FG, font=("Consolas", 10, "bold"), width=20,
                     anchor="w").pack(side="left")
            tk.Label(linha, text=explicacao, bg=BG, fg=DIM, font=("Segoe UI", 10), anchor="w",
                     wraplength=330, justify="left").pack(side="left", fill="x")

        titulo("CONVERSA")
        item("Chat", "Tudo que você e a Ethos dizem aparece aqui, por voz ou texto. Enter envia, "
                     "Shift+Enter quebra linha. Código e textos longos aparecem num bloco com COPIAR.")
        item("VOZ: LIGADA/MUDA", "Liga ou desliga a fala dela (MUDA = só texto).")
        item("LIMPAR CHAT", "Apaga o histórico visual (a memória dela continua).")

        titulo("VOZ E MICROFONE")
        item("● FALAR", "Grava uma pergunta; para sozinho após um instante de silêncio.")
        item("■ PARAR", "Corta a gravação na hora (útil em ambiente barulhento).")
        item("∞ CONTÍNUO", "Conversa sem apertar nada: fale quando quiser; ela responde e volta a ouvir.")
        item("✕ CALAR", "Corta a fala dela na hora.")

        titulo("PET (ORBE NO CANTO DA TELA)")
        item("Clique", "Liga o microfone para uma pergunta. Clicando enquanto ela fala, ela se cala.")
        item("Arrastar", "Muda de lugar; a posição fica salva.")
        item("Botão direito", "Menu: abrir janela, conversa contínua, calar, esconder, sair.")
        item("Fechar a janela (X)", "Com o pet ligado, a Ethos continua rodando no pet. Para sair, use "
                                    "'Sair da Ethos' no menu do pet.")

        titulo("ATALHOS GLOBAIS (funcionam em qualquer programa)")
        item("Ctrl+Alt+E", "Fala uma vez (aperta, fala, ela responde).")
        item("Ctrl+Alt+C", "Liga/desliga a conversa contínua.")
        item("Ctrl+Alt+Q", "Corta a fala dela.")

        titulo("COMANDOS DIGITADOS")
        item("/conversa /ingles /tradutor", "Troca o modo de conversa.")
        item("/memoria", "Mostra tudo que ela guardou.")
        item("/corrigir A = B", "Ensina uma correção de voz. Ex.: /corrigir e maio = e-mail")
        item("/lembretes", "Lista os lembretes agendados.")
        item("/limpar", "Limpa o chat.")
        item("F11 / Esc", "Tela cheia / sair da tela cheia.")

        titulo("O QUE ELA FAZ SOZINHA")
        item("Data e hora", "'Que horas são?', 'que dia é hoje?'")
        item("Abrir coisas", "'Abre o YouTube', 'toca X no YouTube', 'abre o VS Code'.")
        item("Criar arquivos", "'Cria um arquivo teste.py com...' (salvo na pasta EthosProjetos).")
        item("E-mails", "'Lê meus e-mails', 'tem e-mail não lido?', 'procura e-mail da Maria'.")
        item("Ver a tela", "'Olha minha tela', 'o que tem na minha tela?', 'lê o erro que apareceu'. "
                           "Usa um modelo de visão local; o primeiro pedido demora alguns segundos.")
        item("Lembretes", "'Me lembra daqui a 20 minutos de tomar água', 'amanhã às 9h ligar pro João', "
                          "'toda segunda às 8h reunião'. Ela avisa falando. 'Quais são meus lembretes?', "
                          "'cancela o lembrete de água'.")
        item("Memória", "Ela anota sozinha o que for importante; veja com /memoria.")

    # ----------------------------------------------------------- chat
    def _escrever(self, txt, *tags):
        no_fim = self.chat.yview()[1] >= 0.97
        self.chat.config(state="normal")
        self.chat.insert("end", txt, tags)
        self.chat.config(state="disabled")
        if no_fim:
            self.chat.see("end")

    def _copiar(self, conteudo):
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(conteudo)

    def _botao_copiar(self, conteudo):
        botao = self.botao(self.chat, "COPIAR", lambda c=conteudo: self._copiar(c))
        self.chat.config(state="normal")
        self.chat.insert("end", "\n")
        self.chat.window_create("end", window=botao)
        self.chat.insert("end", "\n")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def _novo_usuario(self, txt):
        self._fim(silencioso=True)
        self._escrever("VOCÊ\n", "nome_usuario")
        self._escrever(txt + "\n", "usuario")
        self._escrever("\n", "espaco")
        self._registrar({"papel": "usuario", "texto": txt})

    def _abrir_bolha(self):
        if not self.bolha:
            self.bolha, self.em_codigo = True, False
            self.resposta, self.conteudo = "", ""
            self._escrever("ETHOS\n", "nome_ethos")

    def _token(self, trecho):
        self._abrir_bolha()
        self._escrever(trecho, "ethos")
        self.resposta += trecho

    def _conteudo(self, trecho):
        self._abrir_bolha()
        if not self.em_codigo:
            self.em_codigo = True
            self._escrever("\n\n", "ethos")
        self._escrever(trecho, "codigo")
        self.conteudo += trecho

    def _fim(self, silencioso=False):
        if not self.bolha:
            return
        self.bolha = False
        self._escrever("\n", "ethos")
        if self.conteudo.strip():
            self._botao_copiar(self.conteudo)
        self._escrever("\n", "espaco")
        if self.resposta.strip() or self.conteudo.strip():
            self._registrar({"papel": "ethos", "texto": self.resposta, "codigo": self.conteudo})
        if self.resposta.strip() and not silencioso:
            self.pet.mostrar_fala(self.resposta)

    def _sistema(self, txt):
        self._fim(silencioso=True)
        self._escrever(txt + "\n", "sistema")

    def _mostrar_registro(self, item):
        if item.get("papel") == "usuario":
            self._escrever("VOCÊ\n", "nome_usuario")
            self._escrever(item["texto"] + "\n", "usuario")
        else:
            self._escrever("ETHOS\n", "nome_ethos")
            self._escrever(item.get("texto", ""), "ethos")
            if item.get("codigo"):
                self._escrever("\n\n", "ethos")
                self._escrever(item["codigo"], "codigo")
                self._botao_copiar(item["codigo"])
            self._escrever("\n", "ethos")
        self._escrever("\n", "espaco")

    def _ler_registro(self):
        try:
            with open(ARQUIVO_CHAT, encoding="utf-8") as f:
                return json.load(f)[-MAX_CHAT:]
        except (OSError, ValueError):
            return []

    def _registrar(self, item):
        self.registro = (self.registro + [item])[-MAX_CHAT:]
        self._salvar_registro()

    def _salvar_registro(self):
        try:
            with open(ARQUIVO_CHAT, "w", encoding="utf-8") as f:
                json.dump(self.registro, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def limpar_chat(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.config(state="disabled")
        self.registro = []
        self._salvar_registro()

    # -------------------------------------------------------- entrada
    def enviar_entrada(self, _evento=None):
        txt = self.entrada.get("1.0", "end-1c").strip()
        if not txt:
            return "break"
        self.entrada.delete("1.0", "end")
        baixo = txt.lower()
        if baixo.startswith("/corrigir"):
            errado, _, certo = txt[len("/corrigir"):].partition("=")
            self._sistema(memoria.adicionar_correcao(errado, certo) if errado.strip() and certo.strip()
                          else "Use:  /corrigir como ela entendeu = como deveria ser")
        elif baixo in ("/memoria", "/tarefas"):
            self._sistema(memoria.resumo() or "(nada guardado ainda)")
        elif baixo == "/limpar":
            self.limpar_chat()
        elif baixo == "/lembretes":
            self._sistema(ferramentas_lembretes.listar_lembretes())
        elif baixo in ("/conversa", "/ingles", "/tradutor"):
            orq.acao("modo", baixo[1:])
        else:
            orq.acao("texto", txt)
        return "break"

    # ------------------------------------------------ botões e janela
    def marcar(self, modo):
        for nome, b in self.botoes.items():
            b.config(highlightbackground=FG if nome == modo else LINHA)

    def _atualizar_botoes(self):
        self.botao_voz.config(text="VOZ: LIGADA" if orq.falar_respostas else "VOZ: MUDA",
                              highlightbackground=FG if orq.falar_respostas else LINHA)
        self.botao_pet.config(highlightbackground=FG if self.pet.visivel else LINHA)

    def alternar_voz(self):
        orq.falar_respostas = not orq.falar_respostas
        self.prefs["voz"] = orq.falar_respostas
        preferencias.salvar(self.prefs)
        if not orq.falar_respostas:
            orq.interromper_fala()
        self._atualizar_botoes()

    def alternar_pet(self):
        self.pet.esconder() if self.pet.visivel else self.pet.mostrar()
        self._atualizar_botoes()

    def alternar_tela_cheia(self, _e=None):
        self.tela_cheia = not self.tela_cheia
        self.raiz.attributes("-fullscreen", self.tela_cheia)

    def sair_tela_cheia(self, _e=None):
        if self.tela_cheia:
            self.tela_cheia = False
            self.raiz.attributes("-fullscreen", False)

    def abrir_janela(self):
        self.raiz.deiconify()
        self.raiz.lift()
        self.raiz.focus_force()

    def ao_fechar(self):
        """X da janela: com o pet ligado, só esconde (a Ethos continua no pet)."""
        if self.pet.visivel:
            self.raiz.withdraw()
        else:
            self.sair()

    def sair(self):
        orq.conversa_ativa.clear()
        orq.interromper_fala()
        self.raiz.destroy()

    # ------------------------------------------------ fila e animação
    def _tratar(self, m):
        if "estado" in m:
            self.estado = m["estado"]
            self.st.config(text=NOMES.get(self.estado, ""))
        if m.get("usuario"):
            self._novo_usuario(m["usuario"])
        if m.get("voce"):
            self._sistema(m["voce"])
        if "token" in m:
            self._token(m["token"])
        if "conteudo" in m:
            self._conteudo(m["conteudo"])
        if m.get("fim"):
            self._fim()
        if "modo" in m:
            self.marcar(m["modo"])
        if "continuo" in m:
            self.botao_continuo.config(highlightbackground=FG if m["continuo"] else LINHA,
                                       text="∞ CONTÍNUO: LIGADO" if m["continuo"] else "∞ CONTÍNUO")

    def ler_fila(self):
        try:
            while True:
                try:
                    self._tratar(fila.get_nowait())
                except queue.Empty:
                    break
                except Exception:
                    traceback.print_exc()      # um erro de desenho não pode derrubar a janela
        finally:
            self.raiz.after(50, self.ler_fila)

    def animar(self):
        self.t += 0.033
        self.amp += (orbe.ALVO_AMPLITUDE.get(self.estado, .12) - self.amp) * .06
        if self.raiz.state() != "withdrawn":
            orbe.desenhar(self.tela, 55, 55, .25, self.t, self.estado, self.amp, BG, FG)
        self.raiz.after(33, self.animar)


# ------------------ atalhos de tecla globais (funcionam com outros programas abertos) ------------------
def iniciar_atalho_global():
    from pynput import keyboard
    ouvinte = keyboard.GlobalHotKeys({
        config.HOTKEY_FALAR: orq.ao_apertar_atalho,
        config.HOTKEY_CONVERSA: orq.alternar_conversa,
        config.HOTKEY_INTERROMPER: orq.interromper_fala,
    })
    ouvinte.daemon = True
    ouvinte.start()
    return ouvinte


if __name__ == "__main__":
    cerebro.trocar_modo("conversa")
    raiz = tk.Tk()
    app = App(raiz)
    iniciar_atalho_global()
    threading.Thread(target=pre_carregar, daemon=True).start()
    lembretes.Agendador(orq.anunciar).iniciar()    # avisa os lembretes na hora (e os que passaram com o app fechado)
    # "--segundo-plano" abre só o pet (janela escondida); os atalhos continuam funcionando
    if "--segundo-plano" in sys.argv:
        raiz.withdraw()
        if not app.pet.visivel:
            app.pet.mostrar()
            app._atualizar_botoes()
    raiz.mainloop()

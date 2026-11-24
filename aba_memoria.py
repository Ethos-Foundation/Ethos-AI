"""
Aba MEMÓRIA da janela: ver, adicionar, editar e apagar o que a Ethos sabe (fatos, eventos, gírias,
dialeto dela, correções de voz, tarefas), e remover duplicatas, sem mexer em arquivo JSON.
"""

import tkinter as tk
from tkinter import ttk

import memoria

_ROTULOS = {
    "fato": ("Assunto (ex.: curso)", "Informação (ex.: Engenharia)"),
    "evento": ("Data (AAAA-MM-DD)", "O que aconteceu"),
    "giria": ("Termo", "Significado"),
    "dialeto": ("Expressão dela", "Significado"),
    "correcao": ("Como ela entende (errado)", "Como deveria ser"),
    "tarefa": ("Situação: pendente ou feita", "Tarefa"),
}


class AbaMemoria:
    def __init__(self, aba, botao, cores):
        """`botao(pai, rotulo, comando)` é o criador de botões da janela; `cores` = (BG, PAINEL, FG, DIM, LINHA)."""
        self.aba, self.botao = aba, botao
        self.bg, self.painel, self.fg, self.dim, self.linha = cores
        self._itens = {}                      # iid da linha -> item da memória

        estilo = ttk.Style()
        estilo.configure("Memoria.Treeview", background=self.painel, fieldbackground=self.painel,
                         foreground=self.fg, rowheight=24, borderwidth=0, font=("Segoe UI", 10))
        estilo.configure("Memoria.Treeview.Heading", background=self.bg, foreground=self.dim,
                         font=("Segoe UI", 9, "bold"), relief="flat")
        estilo.map("Memoria.Treeview", background=[("selected", self.linha)], foreground=[("selected", self.fg)])

        topo = tk.Frame(aba, bg=self.bg)
        topo.pack(side="top", fill="x", padx=12, pady=(12, 6))
        tk.Label(topo, text="Mostrar:", bg=self.bg, fg=self.dim, font=("Segoe UI", 9)).pack(side="left")
        self.filtro = tk.StringVar(value="Tudo")
        combo = ttk.Combobox(topo, textvariable=self.filtro, state="readonly", width=16,
                             values=["Tudo"] + list(memoria.TIPOS.values()))
        combo.pack(side="left", padx=(6, 12))
        combo.bind("<<ComboboxSelected>>", lambda e: self.atualizar())
        self.busca = tk.StringVar()
        entrada = tk.Entry(topo, textvariable=self.busca, bg=self.painel, fg=self.fg, insertbackground=self.fg,
                           relief="flat", highlightthickness=1, highlightbackground=self.linha,
                           highlightcolor=self.fg, font=("Segoe UI", 10))
        entrada.pack(side="left", fill="x", expand=True, ipady=3)
        entrada.bind("<KeyRelease>", lambda e: self.atualizar())
        tk.Label(topo, text="buscar", bg=self.bg, fg=self.dim, font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

        rodape = tk.Frame(aba, bg=self.bg)
        rodape.pack(side="bottom", fill="x", padx=12, pady=(6, 12))
        self.status = tk.Label(rodape, text="", bg=self.bg, fg=self.dim, font=("Segoe UI", 9), anchor="w")
        self.status.pack(side="bottom", fill="x", pady=(6, 0))
        botoes = tk.Frame(rodape, bg=self.bg)
        botoes.pack(side="bottom", fill="x")
        for rotulo, comando in (("ADICIONAR", self.adicionar), ("EDITAR", self.editar), ("REMOVER", self.remover),
                                ("REMOVER DUPLICADOS", self.remover_duplicados), ("ATUALIZAR", self.atualizar)):
            self.botao(botoes, rotulo, comando).pack(side="left", padx=(0, 6))

        corpo = tk.Frame(aba, bg=self.bg)
        corpo.pack(side="top", fill="both", expand=True, padx=12)
        self.arvore = ttk.Treeview(corpo, columns=("tipo", "chave", "valor"), show="headings",
                                   style="Memoria.Treeview", selectmode="browse")
        for coluna, titulo, largura in (("tipo", "TIPO", 110), ("chave", "ASSUNTO / DATA", 150), ("valor", "CONTEÚDO", 420)):
            self.arvore.heading(coluna, text=titulo)
            self.arvore.column(coluna, width=largura, anchor="w")
        rolagem = tk.Scrollbar(corpo, orient="vertical", command=self.arvore.yview, bg=self.bg, troughcolor=self.bg)
        self.arvore.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.arvore.pack(side="left", fill="both", expand=True)
        self.arvore.bind("<Double-1>", lambda e: self.editar())
        self.arvore.bind("<Delete>", lambda e: self.remover())
        self.atualizar()

    # ------------------------------------------------------------------
    def _msg(self, texto):
        self.status.config(text=texto)

    def atualizar(self, *_):
        filtro = self.filtro.get()
        busca = self.busca.get().strip().lower()
        self.arvore.delete(*self.arvore.get_children())
        self._itens = {}
        for item in memoria.listar_tudo():
            nome_tipo = memoria.TIPOS[item["tipo"]]
            if filtro not in ("Tudo", nome_tipo):
                continue
            if busca and busca not in f"{item['chave']} {item['valor']}".lower():
                continue
            iid = f"{item['tipo']}:{item['id']}"
            self._itens[iid] = item
            self.arvore.insert("", "end", iid=iid, values=(nome_tipo, item["chave"], item["valor"]))
        self._msg(f"{len(self._itens)} item(ns).")

    def _selecionado(self):
        selecao = self.arvore.selection()
        return self._itens.get(selecao[0]) if selecao else None

    def adicionar(self):
        self._dialogo(None)

    def editar(self):
        item = self._selecionado()
        if item is None:
            self._msg("Selecione um item primeiro.")
            return
        self._dialogo(item)

    def remover(self):
        item = self._selecionado()
        if item is None:
            self._msg("Selecione um item primeiro.")
            return
        memoria.remover_item(item["tipo"], item["id"])
        self.atualizar()
        self._msg(f"Removido: {item['valor'][:60]}")

    def remover_duplicados(self):
        r = memoria.remover_duplicados()
        self.atualizar()
        self._msg(f"Duplicatas removidas: {r['eventos']} evento(s), {r['fatos']} fato(s).")

    # ------------------------------------------------------------------
    def _dialogo(self, item):
        janela = tk.Toplevel(self.aba.winfo_toplevel())
        janela.title("Editar memória" if item else "Adicionar à memória")
        janela.configure(bg=self.bg)
        janela.resizable(False, False)
        nomes = {nome: tipo for tipo, nome in memoria.TIPOS.items()}
        var_tipo = tk.StringVar(value=memoria.TIPOS[item["tipo"]] if item else memoria.TIPOS["fato"])
        combo = ttk.Combobox(janela, textvariable=var_tipo, values=list(memoria.TIPOS.values()),
                             state="disabled" if item else "readonly", width=24)
        combo.grid(row=0, column=0, columnspan=2, padx=14, pady=(14, 8), sticky="we")

        rot1 = tk.Label(janela, bg=self.bg, fg=self.dim, font=("Segoe UI", 9), anchor="w")
        rot2 = tk.Label(janela, bg=self.bg, fg=self.dim, font=("Segoe UI", 9), anchor="w")
        e1 = tk.Entry(janela, width=48, bg=self.painel, fg=self.fg, insertbackground=self.fg, relief="flat",
                      highlightthickness=1, highlightbackground=self.linha, highlightcolor=self.fg)
        e2 = tk.Entry(janela, width=48, bg=self.painel, fg=self.fg, insertbackground=self.fg, relief="flat",
                      highlightthickness=1, highlightbackground=self.linha, highlightcolor=self.fg)
        rot1.grid(row=1, column=0, columnspan=2, padx=14, sticky="we")
        e1.grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 8), ipady=3)
        rot2.grid(row=3, column=0, columnspan=2, padx=14, sticky="we")
        e2.grid(row=4, column=0, columnspan=2, padx=14, pady=(0, 8), ipady=3)
        aviso = tk.Label(janela, text="", bg=self.bg, fg="#ff9a8f", font=("Segoe UI", 9), anchor="w")
        aviso.grid(row=5, column=0, columnspan=2, padx=14, sticky="we")

        def rotular(*_):
            tipo = nomes.get(var_tipo.get(), "fato")
            rot1.config(text=_ROTULOS[tipo][0])
            rot2.config(text=_ROTULOS[tipo][1])

        combo.bind("<<ComboboxSelected>>", rotular)
        rotular()
        if item:
            e1.insert(0, str(item["chave"]))
            e2.insert(0, str(item["valor"]))

        def salvar():
            if item:
                ok, msg = memoria.editar_item(item["tipo"], item["id"], e1.get(), e2.get())
            else:
                ok, msg = memoria.adicionar_item(nomes.get(var_tipo.get(), "fato"), e1.get(), e2.get())
            if ok:
                janela.destroy()
                self.atualizar()
                self._msg(msg)
            else:
                aviso.config(text=msg)

        botoes = tk.Frame(janela, bg=self.bg)
        botoes.grid(row=6, column=0, columnspan=2, pady=(8, 14))
        self.botao(botoes, "SALVAR", salvar).pack(side="left", padx=6)
        self.botao(botoes, "CANCELAR", janela.destroy).pack(side="left", padx=6)
        e1.focus_set()

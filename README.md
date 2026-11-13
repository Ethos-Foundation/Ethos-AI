# Ethos AI

Um assistente pessoal de IA que roda **localmente** no seu computador: conversa por voz de forma contínua, tem personalidade (sarcasmo elegante, estilo JARVIS), lembra do que importa sem você pedir, abre programas e lê seus e-mails. Tudo offline, sem API paga, com modelos abertos.

---

## O que ela faz

- **Conversa contínua por voz:** você liga uma vez e fala quando quiser; ela detecta quando você termina, responde falando (frase por frase, enquanto ainda pensa) e volta a ouvir.
- **Personalidade:** humor seco, opinião própria, sem emojis. Gírias aparecem raramente e ela inventa expressões próprias.
- **Memória automática:** de tempos em tempos ela revisa a conversa e anota sozinha o que for importante (fatos sobre você, eventos, tarefas, gírias). Você também pode pedir ("anota que...", "esquece que...").
- **Modos:** conversa (`/conversa`), professor de inglês (`/ingles`) e tradutor (`/tradutor`).
- **Ferramentas que ela usa sozinha:** hora e data, previsão do tempo, abrir sites e programas, criar arquivos de código, ler e buscar e-mails (somente leitura).
- **Chat com histórico:** a janela é um chat normal (suas mensagens e as dela, por voz ou texto), com bloco de código copiável. O histórico é lembrado entre aberturas.
- **Pet no canto da tela:** um orbe sempre visível; clique nele para falar uma vez com ela.
- **Lembretes com aviso falado:** "me lembra daqui a 20 minutos de tomar água", "amanhã às 9h ligar pro João", "toda segunda às 8h reunião". Ela avisa falando (esperando você terminar de falar com ela), e lembretes que passaram com o app fechado são avisados ao abrir.
- **Ver a tela:** "olha minha tela", "o que tem na minha tela?", "lê o erro que apareceu". Ela captura a tela, um modelo de visão local a descreve e ela comenta. Veja a seção *Ver a tela*.
- **Atalhos globais** que funcionam com qualquer programa em foco.

---

## Requisitos

- **Windows 10/11** (o núcleo funciona em Linux/macOS, mas o atalho `.lnk` é do Windows).
- **Python 3.10+** (testado com 3.13). Marque "Add Python to PATH" na instalação.
- **Ollama** ([ollama.com](https://ollama.com)), aberto em segundo plano.
- **8 GB de RAM** no mínimo (16 GB é mais confortável). Placa NVIDIA recomendada.
- Microfone e caixa de som. Com a caixa do notebook funciona, pois o microfone fica fechado enquanto ela fala.

---

## Instalação

```bash
# 1. Modelos do Ollama
ollama pull qwen3:4b-instruct-2507-q4_K_M

# 2. Bibliotecas (na pasta do projeto)
pip install -r requirements.txt

# 3. Vozes do Piper (ficam na pasta do projeto)
python -m piper.download_voices pt_BR-faber-medium
python -m piper.download_voices en_GB-alan-medium
```

Na primeira execução o Whisper baixa o modelo de reconhecimento de voz (uma vez só; o `large-v3-turbo` tem cerca de 1,6 GB).

**Whisper na GPU (NVIDIA):** o `pip install -r requirements.txt` já traz as bibliotecas CUDA (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, download grande). Ao abrir, o terminal mostra `Whisper pronto: large-v3-turbo em cuda`. Se a GPU falhar, ela volta sozinha para o modelo `small` na CPU (ajustável em `WHISPER_FALLBACK`).

**Voz mais natural (opcional, Kokoro):** `pip install kokoro-onnx`, baixe `kokoro-v1.0.onnx` e `voices-v1.0.bin` (releases do projeto kokoro-onnx no GitHub) para a pasta do projeto e rode `python testar_vozes.py` para comparar com o Piper. Para adotar, ajuste `MOTOR_VOZ` e `VOZ_KOKORO` em `config.py`.

## Como rodar

| Comando | O que faz |
|---|---|
| `python ethos_ai_gui.py` | Interface gráfica (recomendado) |
| `python ethos_ai_gui.py --segundo-plano` | Só o pet (janela escondida); atalhos e voz funcionam |
| `python testar_gmail.py` | Diagnóstico da leitura de e-mails |
| `python testar_visao.py` | Compara modelos de visão: tempo, memória de vídeo e qualidade |
| `python ethos_terminal.py` | Modo terminal, sem janela |
| `python testar_vozes.py` | Toca as vozes lado a lado (Piper x Kokoro) |
| `python criar_atalho.py` | Cria o atalho "Ethos AI" na área de trabalho (Windows) |
| `python -m unittest discover tests` | Roda os testes automáticos |

Abrindo pelo atalho da área de trabalho não aparece terminal; para ver tempos e erros, abra pelo terminal.

---

## Como usar

### Atalhos de teclado (funcionam em qualquer programa)

| Atalho | Ação |
|---|---|
| `Ctrl+Alt+C` | Liga/desliga a **conversa contínua** |
| `Ctrl+Alt+Q` | **Corta a fala** dela na hora |
| `Ctrl+Alt+E` | Fala uma vez só (aperta, fala, ela responde) |

Todos podem ser trocados em `config.py`.

### Pet (orbe no canto da tela)

| Ação | O que faz |
|---|---|
| Clique | Liga o microfone para uma pergunta (se ela estiver falando, corta a fala) |
| Arrastar | Muda de lugar (a posição é lembrada) |
| Botão direito | Menu: abrir janela, conversa contínua, calar, esconder, sair |

Fechar a janela no X só a esconde, e a Ethos continua no pet. Para encerrar de vez, use **Sair da Ethos** no menu do pet. O balão do pet mostra o começo da última resposta por alguns segundos.

### Botões e comandos digitados

`● FALAR`, `■ PARAR`, `∞ CONTÍNUO`, `✕ CALAR`, `VOZ: LIGADA/MUDA` (MUDA = chat só de texto), `PET`, `LIMPAR CHAT` e os modos `CONVERSA / INGLÊS / TRADUTOR`. Enter envia; Shift+Enter quebra linha. Comandos digitados:

| Comando | O que faz |
|---|---|
| `/conversa`, `/ingles`, `/tradutor` | Troca o modo |
| `/memoria` | Mostra tudo que ela guardou |
| `/corrigir e maio = e-mail` | Ensina uma correção de voz (quando o Whisper entende errado) |
| `/lembretes` | Lista os lembretes agendados |
| `/limpar` | Limpa o chat |
| `F11` / `Esc` | Tela cheia / sair da tela cheia |

### Exemplos

- "Que horas são?" / "Qual a previsão do tempo em Lisboa?"
- "Abre o VS Code." / "Toca lo-fi no YouTube."
- "Cria um arquivo chamado teste.py com um hello world." (salvo em `~/EthosProjetos`, nunca sobrescreve)
- "Olha minha tela e me diz o que está errado."
- "Lê meus e-mails." / "Procura e-mail da Maria."
- "Anota que tenho prova dia 20." / "Esquece isso."
- "Me lembra daqui a meia hora de tirar a roupa da máquina." / "Quais são meus lembretes?" / "Cancela o lembrete de água."

---

## Configurações (`config.py`)

Tudo fica num arquivo só. As principais:

| Constante | Para que serve |
|---|---|
| `MODELO_IA` | Modelo de conversa (Ollama) |
| `TEMPERATURA` | Criatividade da personalidade (0.2 sério, 1.0 solto) |
| `MODELO_WHISPER`, `WHISPER_DEVICE` | Reconhecimento de voz e onde roda (`cpu` ou `cuda`) |
| `VOCABULARIO`, `CORRECOES_OUVIDO` | Palavras que o Whisper deve esperar / correções do que ele escreve errado |
| `LIMITE_VOLUME`, `SILENCIO_CONVERSA` | Sensibilidade do microfone e quanto silêncio indica fim da fala |
| `PAUSA_POS_FALA` | Espera após ela falar, antes de ouvir de novo (aumente se ela ouvir a si mesma) |
| `MOTOR_VOZ`, `ARQUIVOS_VOZ`, `VOZ_KOKORO`, `EFEITO_VOZ` | Motor de voz (Piper/Kokoro), arquivos das vozes e eco "Jarvis" |
| `MEMORIA_AUTOMATICA`, `CURADORIA_A_CADA` | Anotação automática e a cada quantas trocas ela revisa |
| `PROB_GIRIA`, `PROB_INVENTAR_GIRIA` | Frequência de gírias e de expressões novas |
| `MODELO_VISAO`, `VISAO_KEEP_ALIVE`, `VISAO_MAX_LADO` | Modelo de visão, quanto tempo fica na GPU e tamanho da captura |
| `HOTKEY_*` | Atalhos de teclado |
| `CIDADE_PADRAO`, `PASTA_PROJETOS` | Cidade do tempo e pasta de arquivos criados |

Para trocar o modelo, escreva o nome de qualquer modelo do `ollama list` em `MODELO_IA`. Modelos `instruct` respondem direto, sem "pensar em voz alta", e são os melhores para voz. Para conferir se roda 100% na GPU: `ollama ps` com o modelo respondendo.

---

## Ver a tela

Ela captura a tela quando você pede e a manda a um **modelo de visão local** (nada sai do seu computador). Ela **não fica vigiando** a tela: só olha sob demanda.

1. Atualize o Ollama (os modelos `qwen3-vl` exigem a versão 0.12.7 ou mais nova) e baixe um modelo: `ollama pull qwen3-vl:4b` (3,3 GB) ou `ollama pull qwen3-vl:2b` (1,9 GB, mais leve).
2. Rode `python testar_visao.py`: ele mostra o tempo, quanto fica na GPU e a descrição de cada modelo, para você escolher. Ajuste `MODELO_VISAO` em `config.py`.
3. Peça: "olha minha tela", "o que tem na minha tela?".

Com 6 GB de VRAM, o modelo de visão e o de conversa não cabem juntos: o Ollama troca um pelo outro, e o primeiro pedido de tela leva alguns segundos a mais (ela avisa "um instante, vou olhar"). O modelo de visão sai da GPU sozinho após `VISAO_KEEP_ALIVE`. Ela vê tudo que estiver na tela, inclusive a própria janela da Ethos; para ela ver outro programa, chame-a pelo atalho de voz ou pelo pet.

---

## Configurar a leitura de e-mails (Gmail)

Esta parte é opcional. Sem ela, o resto funciona normalmente. O acesso é **somente leitura**: a assistente não consegue enviar, apagar ou alterar e-mails.

### Passo 1: criar o projeto no Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com) e entre com a conta Gmail que ela vai ler.
2. Crie um projeto novo (qualquer nome, por exemplo "Ethos AI").

### Passo 2: ativar a Gmail API

1. Vá em **APIs e Serviços > Biblioteca**.
2. Procure por **Gmail API** e clique em **Ativar**.

### Passo 3: configurar a tela de consentimento

1. Vá em **APIs e Serviços > Tela de consentimento OAuth**.
2. Escolha **Externo** e preencha o nome do app e seu e-mail.
3. Em **Escopos**, adicione `https://www.googleapis.com/auth/gmail.readonly`.
4. Em **Usuários de teste**, adicione o seu próprio e-mail.

> Como o app não será publicado, o Google mostra um aviso de "app não verificado" na primeira autorização. Isso é esperado: é o seu próprio app.

### Passo 4: criar a credencial

1. Vá em **APIs e Serviços > Credenciais > Criar credenciais > ID do cliente OAuth**.
2. Tipo: **App para computador**.
3. Baixe o JSON, renomeie para **`credentials.json`** e coloque na pasta do projeto, ao lado do `ethos_ai_gui.py`.

### Passo 5: primeira autorização

Peça à assistente para ler seus e-mails (por exemplo, "lê meus e-mails"). Uma aba do navegador vai abrir pedindo login e autorização. Depois disso, ela salva um arquivo `token.json` e não pede de novo.

> **Nunca compartilhe** `credentials.json` nem `token.json`. Eles são listados no `.gitignore` para não irem ao GitHub.

### Ferramentas de e-mail disponíveis

- `ler_emails_recentes`: lista os últimos e-mails (remetente, assunto e trecho). Aceita filtrar só os não lidos.
- `buscar_emails`: procura e-mails por um termo (nome, empresa, assunto).

---

## Estrutura do projeto

| Arquivo | Função |
|---|---|
| `ethos_ai_gui.py` | Janela de chat (tkinter), atalhos e modo segundo plano. **Comece por aqui.** |
| `pet.py`, `orbe.py` | Pet no canto da tela e o desenho do orbe |
| `preferencias.py` | Preferências da janela (pet, voz, posição) |
| `orquestrador.py` | Fluxo ouvir → pensar → falar, conversa contínua e interrupções |
| `cerebro.py` | Personalidade, modos, histórico, ferramentas, streaming e memória automática |
| `ethos_ai_voz.py` | Ouvir (Whisper) e falar (Piper); carrega sob demanda |
| `texto.py` | Funções de texto puras: frases, filtros, correções, mensagens de erro |
| `segmentador.py` | Detecta quando você começa e termina de falar |
| `lembretes.py`, `tempo.py`, `ferramentas_lembretes.py` | Lembretes: armazenamento e agendador, interpretação de "amanhã às 9h" etc., ferramentas |
| `visao.py`, `ferramentas_visao.py` | Captura da tela e análise com modelo de visão |
| `memoria.py` | Memória persistente (fatos, gírias, dialeto, correções, tarefas, eventos) |
| `ferramentas_externas.py` | Hora, data e previsão do tempo |
| `ferramentas_sistema.py` | Abrir sites/programas, criar arquivos |
| `ferramentas_gmail.py` | Leitura e busca de e-mails |
| `ethos_terminal.py` | Modo terminal |
| `testar_gmail.py`, `testar_vozes.py`, `testar_visao.py` | Diagnósticos |
| `config.py` | Todas as configurações |
| `criar_atalho.py`, `ethos_icone.ico` | Atalho da área de trabalho |
| `tests/` | Testes automáticos |

Criados pelo programa (não vão para o repositório): `memoria_ethos.json`, `lembretes_ethos.json`, `chat_ethos.json`, `preferencias_ethos.json`, `token.json`, os `.onnx` das vozes.

---

## Subir para o GitHub com segurança

O `.gitignore` já protege `credentials.json`, `token.json`, `memoria_ethos.json` e os `.onnx`. Antes de enviar, rode `git status` e confira que nenhum aparece. Se algum já foi enviado antes, apagar não basta (o histórico guarda): troque as credenciais no Google Cloud.

---

## Solução de problemas

**"Não consegui falar com o Ollama"** — abra o aplicativo Ollama e tente de novo.

**Resposta demorando** — `ollama ps` deve mostrar `100% GPU`; feche programas pesados; use um modelo `instruct` menor.

**Ela entende uma palavra errada** — ensine: `/corrigir como ela entendeu = como deveria ser`, ou acrescente em `CORRECOES_OUVIDO` / `VOCABULARIO`.

**Ela responde a si mesma** — aumente `PAUSA_POS_FALA` (ex.: 1.0) ou baixe o volume da caixa.

**Ela dispara com barulho de fundo** — aumente `LIMITE_VOLUME` (ex.: 0.02).

**Ela corta minha fala no meio** — aumente `SILENCIO_CONVERSA` (ex.: 1.0).

**Atalho não responde** — outro programa pode usar a mesma combinação; programas abertos "como administrador" bloqueiam atalhos globais; troque em `config.py`.

**VS Code não abre** — no VS Code, `Ctrl+Shift+P` → *Shell Command: Install 'code' command in PATH*.

**Voz não carrega** — confira se os dois arquivos da voz (`.onnx` e `.onnx.json`) estão na pasta e batem com `ARQUIVOS_VOZ`.

---

## Privacidade

Conversa e reconhecimento de voz acontecem no seu computador. A internet só é usada, e só se você usar, pela previsão do tempo (Open-Meteo) e pelo Gmail. Sua memória fica em `memoria_ethos.json`; apague o arquivo para zerar tudo.

## Licença

Adicione aqui a licença que preferir (por exemplo, MIT) antes de publicar.

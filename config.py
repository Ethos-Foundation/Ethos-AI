"""
Configurações centrais da Ethos AI. Edite aqui; o resto do código lê daqui.
"""

# ======================= MODELO DE CONVERSA (Ollama) =======================
MODELO_IA = "qwen3:4b-instruct-2507-q4_K_M"
KEEP_ALIVE = "30m"            # quanto tempo o modelo fica na memória entre perguntas
MAX_TROCAS_HISTORICO = 8      # quantas trocas (pergunta+resposta) ela lembra na conversa
MAX_RODADAS_FERRAMENTA = 3    # limite de chamadas de ferramenta encadeadas por pergunta

# ======================= RECONHECIMENTO DE VOZ (Whisper) ===================
MODELO_WHISPER = "large-v3-turbo"   # "small" = leve | "large-v3-turbo" = muito mais preciso (GPU)
WHISPER_DEVICE = "cuda"             # "cuda" (placa NVIDIA) ou "cpu"
WHISPER_COMPUTE = "int8_float16"    # GPU: "int8_float16" (economiza VRAM) | CPU: "int8"
# Plano B automático se a GPU falhar (modelo, dispositivo, compute):
WHISPER_FALLBACK = ("small", "cpu", "int8")

IDIOMA_VOZ = "pt"                  # idioma que o Whisper espera ouvir

# Dica de vocabulário para o Whisper: uma frase com as palavras que ele deve esperar
# ouvir (ajuda com termos em inglês ditos com sotaque). Acrescente o que você usa.
VOCABULARIO = ("Conversa em português do Brasil com a assistente Ethos AI. Assuntos comuns: "
               "e-mail, Gmail, YouTube, Spotify, GitHub, Python, VS Code, Windows, Ollama, "
               "Google, WhatsApp, Wi-Fi, Bluetooth, notebook.")

# Correções do que o Whisper escreveu errado -> como deveria ser. Você também pode
# ensinar pela janela:  /corrigir e maio = e-mail
CORRECOES_OUVIDO = {
    "etos": "Ethos", "etus": "Ethos", "ethus": "Ethos", "éthos": "Ethos", "ethós": "Ethos",
    "e maio": "e-mail", "e maios": "e-mails", "e-maio": "e-mail", "emaio": "e-mail",
    "imeio": "e-mail", "imeil": "e-mail", "gmeio": "Gmail", "jimeio": "Gmail",
    "you tube": "YouTube", "iutube": "YouTube",
}

# ======================= MICROFONE =========================================
TAXA = 16000           # o Whisper usa 16 kHz
LIMITE_VOLUME = 0.01   # sensibilidade: se ela não te ouve, diminua (ex.: 0.005)
SILENCIO_FINAL = 1.2   # segundos de silêncio para entender que você terminou
ESPERA_MAXIMA = 8      # segundos esperando você começar a falar
GRAVACAO_MAXIMA = 30   # limite de segurança por fala

# --- Conversa contínua ---
SILENCIO_CONVERSA = 0.8   # segundos de silêncio para considerar que você terminou de falar
FALA_MINIMA = 0.3         # fala mais curta que isso é tratada como ruído e ignorada
PRE_ROLL = 0.3            # segundos guardados ANTES de detectar a voz (não corta o começo)
PAUSA_POS_FALA = 0.5      # espera depois que ela termina de falar, antes de ouvir de novo (eco)

# ======================= VOZ (Piper) =======================================
ARQUIVOS_VOZ = {
    "pt": "pt_BR-faber-medium.onnx",
}

# Como a palavra deve SOAR na voz em português (a tela continua "Ethos").
PRONUNCIAS_PT = {"Ethos": "Étos"}

MOTOR_VOZ = "piper"        # "piper" ou "kokoro" (veja testar_vozes.py)
# Voz do Kokoro: idioma -> (voz, código de idioma). Português do Brasil: pf_dora (feminina),
# pm_alex e pm_santa (masculinas).
VOZ_KOKORO = {"pt": ("pf_dora", "pt-br")}
VELOCIDADE_KOKORO = 1.0
ESTILO_SONS = "futurista"   # "futurista" (bips de IA) ou "classico" (sons simples)
VOLUME_EFEITOS = 1.0        # volume dos efeitos sonoros (0.0 a 1.0+)
EFEITO_VOZ = 1.0          # intensidade do eco "Jarvis" (0 = desligado)
SOM_PROCESSANDO = True    # tique enquanto pensa (desligar no modo conversa contínua)
MIN_FRASE = 20            # tamanho mínimo (caracteres) de um trecho antes de falá-lo

# ======================= INTERFACE =========================================
HOTKEY_FALAR = "<ctrl>+<alt>+e"        # fala uma vez (aperta, fala, responde)
HOTKEY_CONVERSA = "<ctrl>+<alt>+c"     # liga/desliga a conversa contínua
HOTKEY_INTERROMPER = "<ctrl>+<alt>+q"  # corta a fala dela na hora

# ======================= FERRAMENTAS =======================================
# Cidade usada na previsão do tempo quando você não informa nenhuma.
CIDADE_PADRAO = "São Paulo"

# Pasta onde ela pode criar arquivos de código (nunca sobrescreve nada existente).
import os as _os
PASTA_PROJETOS = _os.path.join(_os.path.expanduser("~"), "EthosProjetos")

# ======================= PERSONALIDADE E MEMÓRIA ===========================
NIVEL_SARCASMO = 1           # 0 = sem sarcasmo | 1 = leve | 2 = médio | 3 = alto (comando /sarcasmo na janela)
TEMPERATURA = 0.8             # criatividade da conversa (0.2 = sério, 1.0 = solta)
MEMORIA_AUTOMATICA = True     # ela decide sozinha o que vale anotar
CURADORIA_A_CADA = 3          # a cada quantas trocas ela revisa a conversa para anotar
MAX_FATOS_CONTEXTO = 15       # máximo de fatos sobre você mandados ao modelo por pergunta
PROB_GIRIA = 0.2              # chance, por resposta, de receber uma gíria para usar
PROB_INVENTAR_GIRIA = 0.08    # chance, por resposta, de ser incentivada a inventar uma gíria nova

# ======================= VISÃO (ver a tela) ================================
# Modelo de visão do Ollama (rode: ollama pull qwen3-vl:4b). Veja testar_visao.py para
# comparar os modelos na sua máquina. "qwen3-vl:2b" é mais leve; "qwen3-vl:4b" é mais preciso.
MODELO_VISAO = "qwen3-vl:4b"
VISAO_KEEP_ALIVE = "2m"        # quanto tempo o modelo de visão fica na GPU depois de usado
VISAO_MAX_LADO = 1280          # a captura é reduzida para no máximo isso (pixels) no lado maior
VISAO_NUM_CTX = 4096           # contexto do modelo de visão (menor = menos memória)
VISAO_MAX_TOKENS = 600         # limite do tamanho da descrição
VISAO_TODAS_AS_TELAS = False   # True = captura todos os monitores juntos

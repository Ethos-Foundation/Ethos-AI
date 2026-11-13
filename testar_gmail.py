"""
Diagnóstico do Gmail. Rode na pasta do projeto:  python testar_gmail.py
Mostra exatamente onde está o problema (arquivos, bibliotecas, autorização).
"""

import os
import traceback

import ferramentas_gmail as g

print("Pasta do projeto:", g.PASTA)
for nome, caminho in (("credentials.json", g.ARQUIVO_CREDENCIAIS), ("token.json", g.ARQUIVO_TOKEN)):
    print(f"  {nome}: {'encontrado' if os.path.exists(caminho) else 'NÃO ENCONTRADO'}")

try:
    import google.auth, google_auth_oauthlib, googleapiclient  # noqa: F401
    print("  bibliotecas do Google: ok")
except ImportError as erro:
    print(f"  bibliotecas do Google: FALTANDO ({erro})\n  -> pip install google-auth-oauthlib google-api-python-client")
    raise SystemExit(1)

print("\nTentando ler os 2 e-mails mais recentes (na 1ª vez abre o navegador para autorizar)...\n")
try:
    print(g.ler_emails_recentes(2))
except Exception:
    print("ERRO:\n")
    traceback.print_exc()

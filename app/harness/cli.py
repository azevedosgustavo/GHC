import argparse
import os
import sys

from .agent import run_agent
from .auth import CopilotSession, device_login, load_github_token
from .client import ChatClient

SYSTEM = ("Voce e um assistente de programacao rodando em um harness local. "
          "Use as ferramentas para ler arquivos do workspace quando necessario.")


def run_turn(client, messages, root, out=sys.stdout):
    """Runs the model/tool loop until the model answers without tool calls."""
    def emit(t):
        out.write(t)
        out.flush()

    ok = run_agent(client, messages, root, on_text=emit,
                   on_tool=lambda n, a: out.write("\n[tool] %s %s\n" % (n, a)))
    out.write("\n" if ok else "\n[limite de passos atingido]\n")


def main(argv=None):
    p = argparse.ArgumentParser(prog="harness")
    p.add_argument("--model", default="gpt-4o")
    p.add_argument("--root", default=os.getcwd(), help="workspace acessivel as ferramentas")
    p.add_argument("--login", action="store_true", help="autenticar via device flow e sair")
    p.add_argument("--cli", action="store_true", help="usar o chat no terminal em vez da GUI")
    p.add_argument("--minimized", action="store_true", help="iniciar oculto na bandeja")
    a = p.parse_args(argv)

    if not a.cli and not a.login:
        from .gui import run_gui
        run_gui(a.root, a.model, a.minimized)
        return 0

    if a.login:
        device_login()
        print("Login salvo.")
        return 0
    token = load_github_token()
    if not token:
        print("Sem credenciais; iniciando login.")
        token = device_login()

    client = ChatClient(CopilotSession(token), a.model)

    def fresh():
        return [{"role": "system", "content": SYSTEM}]

    messages = fresh()
    print("Harness (%s) | workspace: %s | /help para comandos" % (a.model, a.root))
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("/exit", "/quit"):
            return 0
        if line == "/clear":
            messages = fresh()
            continue
        if line.startswith("/model "):
            client.model = line.split(None, 1)[1]
            continue
        if line == "/help":
            print("/clear  /model <nome>  /exit")
            continue
        messages.append({"role": "user", "content": line})
        try:
            run_turn(client, messages, a.root)
        except Exception as e:  # keep the REPL alive on network/API errors
            print("\n[erro] %s" % e)

# copilot-harness

Harness de chat para GitHub Copilot em Python 3.8 (último com suporte ao Windows 7 32 bits), sem dependências externas.

## Uso
```
python -m harness --root C:\projeto          # GUI (Tkinter)
python -m harness --cli --root C:\projeto    # terminal
```
GUI: barra lateral com conversas (salvas em `~/.copilot-harness/chats.json`, `Delete` remove), seletor de modelo, pasta de trabalho, streaming, blocos de código; Enter envia, Shift+Enter quebra linha, "Parar" cancela entre passos. Sem token, mostra a tela de login: "Entrar com GitHub" gera o código, copia para a área de transferência e abre o navegador; a GUI conclui sozinha após a autorização. "Sair da conta" na barra lateral volta à tela de login.
Tema: botão "Tema" na barra lateral alterna Sistema → Claro → Escuro (salvo em `~/.copilot-harness/settings.json`). Troca instantânea, sem reiniciar. No Windows com Aero ativo, a cor de destaque segue a cor das janelas do Aero (`DwmGetColorizationColor`) e muda ao vivo quando o usuário a altera ou desliga o Aero (verificado a cada 2 s). "Sistema" segue o modo escuro do Windows 10+; no Windows 7 (sem modo escuro) resulta em claro.
Login persistente: o token fica em `~/.copilot-harness/token.json` e é reutilizado ao reabrir; só pede login de novo se o GitHub o rejeitar (401) ou ao clicar em "Sair da conta".
Bandeja (Windows): fechar a janela (X) oculta o app ao lado do relógio e ele continua rodando; clique no ícone para abrir, botão direito → Abrir/Sair. Um aviso aparece quando uma resposta termina com a janela oculta. Abrir o programa de novo apenas traz a janela existente. `--minimized` inicia oculto.
Comandos do modo terminal: `/clear`, `/model <nome>`, `/exit`. Requer assinatura Copilot.

## Etapas
1. **Atual**: chat com streaming + ferramentas `read_file` e `list_dir` (restritas ao `--root`).
2. **Próxima**: escrita/edição de arquivos e execução de `cmd`/`powershell` — registrar com `@tools.tool(..., mutating=True)` e pedir confirmação no CLI.

Testes: `python -m unittest discover tests`

Nota: a API usada (`copilot_internal`) não é oficialmente documentada e pode mudar.

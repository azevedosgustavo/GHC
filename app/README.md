# Aplicativo GHC

Consulte o [README principal](../README.md) para requisitos, instalação,
permissões, segurança e testes.

Execute `python -m harness --root C:\projeto` a partir desta pasta. Use
`--cli` para o terminal, `--model <nome>` para escolher um modelo inicial,
`--login` para autenticar pelo terminal ou `--minimized` para iniciar na bandeja.
No terminal, `--mode chat`, `--mode manual` e `--mode auto` selecionam a
política de comandos; o padrão é `chat`. Na interface gráfica, use o seletor
de permissões e o botão **Anexar**. A conversa mostra o modelo selecionado e
eventuais mudanças entre mensagens; a opção automática escolhe ao enviar.
O seletor **Automático (GHC)** usa uma heurística local, não o Copilot Fusion
oficial; os modelos concretos escolhidos podem depender da disponibilidade da conta.
Uma habilidade padrão orienta a escolha entre Python, CMD e PowerShell.
Código e scripts Python respeitam os mesmos modos de permissão e não são isolados.
Habilidades padrão de PDF, Word e Excel orientam a criação de arquivos usando
as bibliotecas de documentos do runtime; consulte os modos e limitações no README principal.

As conversas e o catálogo ficam em `~/.copilot-harness/ghc.sqlite3`, as
configurações em `~/.copilot-harness/settings.json` e o token GitHub em
`~/.copilot-harness/token.json`. `GITHUB_TOKEN` ou `GH_TOKEN`, quando
definidos, têm prioridade sobre o token salvo; removê-los do ambiente pode ser
necessário para sair dessa conta.

Anexos permanentes são copiados para a pasta configurável do GHC; os originais
não são alterados. Consulte o README principal sobre exclusão, histórico
legado, conversas temporárias, formatos e limitações de documentos.

O painel textual da conversa, o gerenciamento de skills locais e o download
manual de atualizações pela bandeja também estão descritos no README principal.

As ferramentas de leitura verificam se o caminho está na pasta de trabalho.
Essa verificação não é uma caixa de isolamento para comandos. A disponibilidade
de modelos, chamadas de ferramentas e imagens depende do serviço Copilot.

# GHC — GitHub Copilot Harness

Cliente desktop experimental para conversar com o GitHub Copilot no Windows,
incluindo o Windows 7 como plataforma-alvo. O projeto contém uma interface
Tkinter, um cliente de terminal e um instalador. A compatibilidade com Windows 7,
com a API atual do Copilot e com modelos específicos precisa ser validada no
ambiente de destino; os testes automatizados não comprovam essas integrações.

## Funcionalidades

- Login GitHub por código de dispositivo e histórico local em SQLite; conversas
  podem ser arquivadas, desarquivadas ou excluídas com confirmação. A tela
  inicial permite começar uma conversa permanente ou temporária; as temporárias
  existem apenas em memória durante a sessão. A opção temporária é escolhida
  antes da primeira mensagem e não aparece dentro de uma conversa iniciada.
- Chat com respostas em streaming, seleção de modelo e leitura de arquivos e
  pastas da pasta de trabalho.
- O padrão na interface é **Automático (GHC)**: uma heurística local escolhe
  modelos conforme a presença de imagens, extensão e termos associados a
  tarefas de código, usando o catálogo disponível. Não é o Copilot Fusion e
  não garante a escolha do melhor modelo; é possível escolher outro modelo
  manualmente. O modelo selecionado e mudanças posteriores aparecem na conversa;
  no modo automático a decisão ocorre ao enviar a mensagem. A disponibilidade
  depende da conta e da API.
- O catálogo é consultado após o login para a conta atual e salvo por provedor.
  Só são apresentados modelos de chat que anunciam suporte ao endpoint usado
  pelo GHC, sem bloqueio explícito de política ou ferramentas. Modelos exclusivos
  de outras APIs do Copilot não são suportados pelo GHC. A consulta usa uma API
  interna não documentada; disponibilidade e custos dependem da conta.
  Se a API recusar explicitamente um modelo como indisponível ou incompatível,
  o GHC tenta outros modelos do catálogo e informa a troca. Não repete comandos
  executados nem tenta novamente erros gerais de autenticação ou rede. Pode não
  haver alternativa disponível, e não há garantia de que o modelo alternativo
  seja mais recente ou tenha o mesmo custo.
- Anexos de texto UTF-8, imagens PNG/JPEG/GIF/WebP, PDF com texto, Word DOCX
  e Excel XLSX. Cada arquivo pode ter até 2 MiB e os anexos de uma mensagem,
  até 4 MiB; há limites adicionais de extração. PDFs digitalizados precisam de
  OCR, não disponível; `.doc` e `.xls` antigos não são suportados. Imagens
  exigem suporte multimodal pelo modelo e pela API. Os anexos podem ser
  removidos da conversa; o original selecionado não é alterado.
- Configurações de tema, modo padrão, modelo preferido, instruções pessoais
  para novas conversas, limite de contexto em caracteres serializados
  (0 = sem limite), fontes e navegador usado pelo GHC. A escolha de navegador
  não altera o padrão do Windows. As opções ficam em páginas de **Configurações**.
  Clique com o botão direito numa conversa para arquivar, desarquivar ou excluir.
  A página **Conta** também dá acesso ao botão Sobre e ao repositório.
- Pasta de arquivos configurável (padrão `~/.copilot-harness/files`): cópias
  dos anexos de conversas permanentes ficam em `attachments/<id-da-conversa>`.
  Alterar a pasta não move arquivos anteriores. Anexos temporários não são
  copiados para disco. Ao excluir anexo ou conversa, o GHC tenta excluir as
  cópias associadas e informa falhas; pode ser necessário removê-las manualmente.
  A pasta também é informada ao modelo como destino sugerido para downloads e
  documentos, mas comandos não são obrigados a usá-la e não há ferramenta
  específica de download ou geração de documentos.
- Temas claro, escuro e sistema; no Windows, a cor de destaque acompanha o Aero
  quando disponível e também colore suavemente a barra lateral e a seleção.
  A moldura da janela permanece nativa; o conteúdo não usa transparência
  Aero Glass. No Windows 7, o tema de sistema é claro.
- Bandeja do sistema no Windows: fechar a janela a oculta; use o menu do ícone
  para abrir ou sair. A bandeja usa o ícone próprio do GHC com fundo transparente.
  `--minimized` inicia oculto se a bandeja estiver disponível.
  **Verificar atualizações** consulta a última release estável do repositório;
  se houver versão maior com `GHC-Setup.exe`, oferece download para o caminho
  escolhido, sem executar o instalador. A comparação exige versões `x.y.z`
  ou `vx.y.z`. A consulta e o download exigem conexão e TLS compatível. Não
  há verificação de assinatura ou checksum: confira a procedência antes de executar.
- Três modos de permissão para comandos: **Somente bate-papo**, **Manual** e
  **Piloto automático**. O padrão inicial é Somente bate-papo; definir Piloto
  automático como padrão exige confirmação explícita.
- Execução de código Python e arquivos `.py`, além de CMD e PowerShell.
  A habilidade padrão de seleção de execução orienta o modelo a escolher a
  ferramenta apropriada para cada tarefa; é uma orientação ao modelo, não uma
  garantia de que ele sempre escolherá a melhor ferramenta.
- Habilidades padrão especializadas orientam a geração de PDF, documentos
  Word `.docx` e planilhas Excel `.xlsx` com ReportLab, python-docx e openpyxl.
  Elas orientam o modelo e não substituem a confirmação de execução. Para criar
  arquivos é necessário o modo Manual ou Piloto automático. A geração não
  exige Microsoft Office; `.doc` e `.xls` antigos não são produzidos. O openpyxl
  grava fórmulas, mas não calcula seus resultados.
- **Skills locais:** em **Skills**, adicione `SKILL.md` ou descubra arquivos
  na pasta escolhida e em suas subpastas imediatas. Revise o conteúdo e ative
  apenas fontes confiáveis; é possível definir parâmetros de texto por skill
  e ativar ou desativar cada uma. As instruções e parâmetros ativos são
  enviados ao modelo em cada conversa; não inclua segredos. Alterações no
  `SKILL.md` exigem nova aprovação. Outros arquivos da skill, incluindo scripts,
  não são verificados e podem mudar sem aviso. Scripts não são executados pelo
  gerenciador: o modelo pode solicitá-los pelas ferramentas de comando, sujeitas
  ao modo selecionado. No piloto automático eles podem executar sem confirmação
  e sem isolamento. O suporte atual não instala skills nem implementa todas as
  funcionalidades de outros harnesses.
- **Painel de conversa:** anexos textuais, PDF com texto, DOCX e XLSX podem
  ser abertos como texto extraído ao lado do chat. Cartões propostos na conversa
  também podem abrir URLs HTTP/HTTPS após confirmação; scripts, estilos e outros
  conteúdos ativos não são executados. O painel permite copiar o conteúdo para o rascunho do
  chat antes de enviá-lo. Não reproduz layout, imagens, gráficos ou edição de
  documentos; PDF digitalizado precisa de OCR. O conteúdo baixado da web é
  transitório, a menos que seja enviado na conversa.
- O modelo e as skills podem propor cartões na linha do tempo usando blocos
  `ghc-canvas` com JSON versão 1: `{"version":1,"title":"Título","content":"Texto"}`
  ou `{"version":1,"title":"Título","url":"https://exemplo.com"}`. Esses blocos
  permanecem na mensagem e abrem conteúdo textual no painel; links propostos
  precisam de confirmação antes do acesso. A apresentação não permite executar
  código nem alterar o histórico, e depende de o modelo seguir esse formato.

### Permissões e riscos

Somente bate-papo bloqueia as ferramentas de comandos, mas ainda permite que o
modelo leia arquivos dentro da pasta de trabalho. No modo Manual, cada comando
solicitado pelo modelo exige confirmação dentro da conversa. No Piloto automático, a ativação é
confirmada uma vez e os comandos seguintes são executados sem nova confirmação.
As mesmas regras valem para código e scripts Python. Na confirmação de um
arquivo `.py`, confira o caminho, os argumentos e o conteúdo do arquivo; o
conteúdo não é exibido automaticamente e pode mudar antes da execução.
Comandos `cmd` e PowerShell também podem iniciar instalações, mas não há
gerenciador de aplicativos nem automação de instaladores interativos.

**Comandos não são isolados na pasta de trabalho**: executam com as permissões
do usuário, podem acessar ou alterar outros arquivos, usar a rede e iniciar
outros processos. Revise cuidadosamente cada comando no modo Manual; conteúdo
de páginas, arquivos e anexos pode influenciar as respostas do modelo.
O botão Parar cancela entre etapas: não interrompe imediatamente uma chamada de
rede ou comando já iniciado. Comandos têm tempo limite de 120 segundos; processos
filhos iniciados por eles podem continuar em execução.
O Python executa em processo separado, mas **não é uma sandbox**. Não há entrada
interativa: código enviado ao Python usa a entrada para o próprio código e
scripts recebem entrada fechada. Bibliotecas adicionais além das incluídas não
são instaladas automaticamente.

O token GitHub é armazenado em texto simples no perfil do usuário, assim como
o histórico, que inclui o conteúdo e os dados de imagens anexadas. Proteja o
acesso a esses arquivos. Anexos e mensagens são enviados ao serviço Copilot.
O antigo `chats.json`, quando existe, é importado uma vez e preservado: excluir
conversas ou anexos no GHC não remove conteúdo dessa cópia legada. Apague-a
manualmente se não precisar dela. A exclusão no SQLite ou em disco não garante
apagamento seguro de backups, cópias anteriores ou dados recuperáveis.
O cliente usa uma API interna não documentada, sujeita a mudanças, e não há
garantia de acesso ou de disponibilidade dos modelos.

## Executar a partir do código

Requer Python com Tkinter. O alvo do projeto é Python 3.8 de 32 bits no Windows 7;
o Python 3.8 está fora de suporte. O uso de um sistema operacional sem suporte
apresenta riscos de segurança e pode impedir conexões TLS ou instalações.
É necessária uma conta com acesso ao Copilot e conexão com o GitHub.

No PowerShell, na raiz do repositório:

```powershell
cd app
python -m pip install -r requirements.txt
python -m harness --root C:\projeto
python -m harness --cli --root C:\projeto
```

No terminal, `--mode manual` exige aprovação por comando e `--mode auto`
ativa execução automática; o padrão é `--mode chat`. Comandos do chat de
terminal: `/help`, `/clear`, `/model <nome>` e `/exit`. Anexos pelo seletor
estão disponíveis na interface gráfica. Mais detalhes em [app/README.md](app/README.md).

## Instalação e compilação

Quando disponível, baixe `GHC-Setup.exe` na página de releases do repositório.
O instalador oferece diretório (padrão `C:\GHC`), atalhos, tentativa de fixação
na barra de tarefas e inicialização com o Windows. A pasta escolhida precisa
ser gravável pelo usuário; `C:\GHC` pode exigir permissões adicionais. A
fixação automática pode não funcionar em todas as versões do Windows.
Ao instalar ou desinstalar, o instalador pode forçar o encerramento de
processos chamados `GHC.exe`; salve o trabalho antes de continuar.

```powershell
GHC-Setup.exe --silent --dir C:\GHC --startmenu --desktop --taskbar --autostart --launch
```

Desinstale pelo aplicativo de configurações do Windows ou execute
`C:\GHC\uninstall.exe`. O instalador compilado inclui Python, Tk e as demais dependências Python do
aplicativo; não é necessário instalar Python nem executar pip na máquina de
destino. Antes de concluir, o instalador verifica o carregamento dos módulos,
Tcl e SSL do executável instalado e informa uma falha se a verificação não
passar. Essa verificação não comprova o funcionamento da interface, da rede
ou de todos os componentes do sistema.

O pacote também inclui um interpretador Python separado e sua biblioteca padrão
para executar código e scripts; ele não altera o Python padrão do Windows.
Esse interpretador inclui as bibliotecas de PDF, Word e Excel e dependências.
Na execução a partir do código-fonte, é usado o Python que iniciou o GHC,
com as bibliotecas instaladas pelo `requirements.txt`. O autoteste verifica se
o interpretador inicia e importa as bibliotecas de documentos.

O Windows precisa ter seus próprios pré-requisitos, incluindo Windows 7 SP1 e
Universal CRT (KB2999226); o instalador não instala atualizações do sistema
nem configura certificados ou conectividade. Na máquina de compilação,
use Windows, Python 3.8 x86 e PyInstaller 5.13.2:

```powershell
py -3.8-32 -m pip install pyinstaller==5.13.2
py -3.8-32 -m pip install -r app\requirements.txt
py -3.8-32 installer\build.py --app app
```

Cada build guarda um instalador com versão e data em `installer\dist`, sem
substituir os anteriores, e cria uma pasta própria em `installer\build`. Verifique o pacote em
um Windows 7 SP1 real, incluindo os requisitos de runtime/TLS, antes de distribuí-lo.
Para usar outra localização, informe `--output-dir C:\caminho\para\saida`;
as subpastas `build` e `dist` também preservam os arquivos existentes.
O fluxo do GitHub Actions gera instalador e ZIP portátil quando executado; não
implica que uma release ou teste em Windows 7 já exista.

## Testes

Na raiz do repositório:

```powershell
$env:PYTHONPATH = "app"
python -m unittest discover -s app\tests -v
python -m unittest discover -s installer\tests -v
```

Os testes do instalador usam uma pasta temporária e não exercitam a integração
real com o Registro, atalhos, bandeja ou inicialização do Windows. Também não
testam login, chat ou imagens contra o serviço real.

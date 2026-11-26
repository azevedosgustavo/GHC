---
name: python-desenvolvimento
description: Desenvolvimento, empacotamento e instalação de aplicações Python para Windows, com foco em Windows 7 de 32 bits.
---

# Desenvolvimento Python para Windows 7

Use estas orientações quando a tarefa envolver Python, dependências ou executáveis
para Windows 7. Identifique primeiro a versão e a arquitetura do Windows de
destino, os requisitos da aplicação e as permissões disponíveis. Observe as
permissões do GHC; antes de instalar software ou alterar o sistema, obtenha
autorização explícita do usuário.

## Compatibilidade e segurança

- Python 3.8 é a última série oficialmente compatível com Windows 7; Python 3.9
  requer Windows 8.1 ou posterior. O Python 3.8 está fora de suporte e não recebe
  correções de segurança. Python 3.8.10 foi a última versão dessa série com
  instaladores Windows oficiais; versões posteriores da série saíram como fonte.
- Em Windows 7 de 32 bits, use Python e dependências x86 compatíveis. Num sistema
  de 64 bits, escolha a arquitetura conforme o alvo. Confirme a versão, arquitetura,
  suporte das bibliotecas, Universal CRT e certificados/TLS da máquina.
- Não altere o runtime privado do GHC. Ele pode ser diferente de uma instalação
  completa e não deve ser presumido como tendo pip, Tkinter ou uma versão fixa.
  Use uma instalação ou ambiente separado para desenvolvimento e empacotamento.
- O Python embeddable é uma distribuição mínima: não presuma que inclua pip,
  Tcl/Tk ou outros componentes de desenvolvimento. Para GUI com Tkinter,
  prefira a instalação completa e teste o carregamento e a abertura da janela.
- O PyInstaller 5.13.2 é usado no build do GHC com Python 3.8, mas não é a
  última versão compatível com Python 3.8. Sua documentação informa Windows 8
  ou posterior; não prometa suporte ao Windows 7 sem testar o executável final
  no sistema de destino. Verifique a compatibilidade das versões e dependências.

## Ambiente Python separado

Se necessário e autorizado, o instalador oficial x86 do Python 3.8.10 está em
https://www.python.org/ftp/python/3.8.10/python-3.8.10.exe . Confira a origem,
integridade e assinatura antes de executar qualquer instalador. Por exemplo,
o comando abaixo foi relatado como funcional em uma máquina de teste Windows 7
32 bits; ajuste os caminhos e opções ao ambiente, sem sobrescrever instalações
existentes. `InstallAllUsers=1` pode exigir privilégios de administrador.

```cmd
python-3.8.10.exe /quiet /log C:\tmp\py_install.log InstallAllUsers=1 TargetDir=C:\Python3810 Include_tcltk=1 Include_pip=1 Include_test=0 Include_doc=0 Include_launcher=0 AssociateFiles=0 Shortcuts=0 PrependPath=0
```

Garanta que a pasta do log existe; confira o código de saída e o log. Valide o
interpretador instalado pelo caminho completo, sem depender de `PATH`:

```cmd
C:\Python3810\python.exe -c "import sys, struct, tkinter; print(sys.version, struct.calcsize('P') * 8, tkinter.TkVersion)"
C:\Python3810\python.exe -m pip --version
```

Se pip estiver ausente, verifique primeiro `python -m ensurepip --upgrade`
na instalação separada. Quando necessário, a PyPA disponibiliza o bootstrap
para Python 3.8 em https://bootstrap.pypa.io/pip/3.8/get-pip.py . Verifique
origem e integridade, obtenha autorização e execute-o com o Python escolhido.
Instale dependências no mesmo interpretador ou ambiente virtual que empacotará
a aplicação. Confirme com `python.exe -m pip show NOME`; versões atuais de
pacotes nem sempre são compatíveis com Python 3.8 ou Windows 7.

## Empacotamento e testes

- Para console: `python.exe -m PyInstaller --onefile --noconfirm arquivo.py`.
  Para interface: use também `--windowed`. Execute com o Python e a arquitetura
  escolhidos; use um diretório de trabalho conhecido para localizar `dist`.
- Um build bem-sucedido não comprova compatibilidade. Teste o `.exe` na
  arquitetura e versão reais de destino, incluindo abertura visual da GUI,
  funcionalidades, dependências, permissões e saída. Informe o que não foi
  testado. Tamanho do executável e suporte variam com dependências e versão.
- A limpeza de `build` e do arquivo `.spec` só deve ocorrer quando forem
  identificados como temporários do trabalho e houver autorização adequada.
  Não apague artefatos ou projetos do usuário presumindo que sejam descartáveis.

## Diagnóstico e boas práticas

- Separe lógica de interface e cubra a lógica com testes. Trate erros específicos
  como `ValueError` e `ZeroDivisionError` quando pertinentes; use UTF-8 para
  arquivos de texto e não use `eval` para interpretar expressões não confiáveis.
- `python` pode não estar no `PATH`. `sys.executable` aponta para o processo
  atual e não necessariamente para o Python de desenvolvimento escolhido;
  confira o caminho e a versão antes de instalar ou executar.
- Verifique a versão do PowerShell e a existência de `Invoke-WebRequest` antes
  de usá-lo. Se não estiver disponível, outra ferramenta aprovada, como
  `urllib`, pode servir para download, sujeito a TLS e certificados válidos.
- `0xC0000135` pode indicar uma DLL ausente, mas não identifica qual DLL;
  investigue a dependência, arquitetura, runtime e registros antes de concluir.
  `WinError 216` pode indicar incompatibilidade de arquitetura ou formato; confira
  o executável e o sistema. `No module named tkinter` pode indicar ausência de
  Tcl/Tk: verifique a instalação e suas dependências antes de reinstalar.
- Não conclua que um caminho é inacessível apenas porque uma ferramenta restrita
  ao workspace o recusou. Quando permitido, teste com a ferramenta apropriada;
  informe o código de saída e confirme a existência e conteúdo do resultado.
- Em uma máquina de teste foi relatado que a extração administrativa dos MSI do
  layout não produziu Tcl/Tk utilizável e que o pacote NuGet usado não o incluía.
  São observações daquele ambiente, não garantias para todas as distribuições.

Referências: https://docs.python.org/3.9/using/windows.html ,
https://www.python.org/downloads/release/python-3810/ ,
https://pyinstaller.org/en/v5.13.2/requirements.html e
https://pip.pypa.io/en/stable/installation/ .

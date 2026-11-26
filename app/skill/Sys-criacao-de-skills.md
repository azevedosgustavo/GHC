---
name: Sys-criacao-de-skills
description: Use quando o usuário solicitar a criação de uma nova skill para o GHC.
---

# Habilidade padrão — criação de skills

Quando o usuário solicitar uma skill, crie um arquivo Markdown UTF-8 não vazio
com instruções para a tarefa na pasta de skills do GHC. Uma skill pode ser um
arquivo .md diretamente nessa pasta ou um arquivo .md em sua própria subpasta,
com eventuais arquivos auxiliares. Cada arquivo .md nessa pasta e em suas
subpastas é carregado como uma skill independente. O prefixo Sys identifica
skills de sistema; não use esse prefixo para uma nova skill comum.

Inclua no início um frontmatter YAML com `name` e `description`; a descrição
deve explicar o que a skill faz e em quais pedidos ela deve ser usada. O GHC
mostra esses metadados ao modelo e carrega o conteúdo completo sob demanda.

Crie a pasta se necessário, não sobrescreva arquivos sem autorização e
verifique o resultado. Criar arquivos exige ferramentas de execução e respeita
o modo de permissão.

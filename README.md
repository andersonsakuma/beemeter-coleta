# Coleta de Campo — fichas do experimento de meliponicultura

Aplicativo de coleta de dados pelo celular do experimento de monitoramento das colônias de abelhas
nativas em Cametá do Ramos, Barreirinha/AM (**IPÊ/FIS**, Projeto Amazônia Bee).

Roda em <https://andersonsakuma.github.io/beemeter-coleta/> e como aplicativo Android: veja
[android/README.md](android/README.md).

## O que o aplicativo faz

- As fichas do plano de trabalho dos colaboradores locais (Anexo 05), com as mesmas abas e colunas
  da planilha do Anexo 05a: linha de base, instalação e verificação dos kits, ocupação da melgueira,
  pesagem e atividade, chuva, manejo, extração e amostras, assistência técnica, índice de boas
  práticas e produção dos meliponicultores assistidos.
- **Sorteio do controle** de cada grupo, com registro das colônias aptas e das testemunhas.
- Contador de entradas de 5 minutos, cronômetro da extração, foto da melgueira, GPS da colônia e
  código automático das amostras.
- Pendências do dia calculadas pelas frequências do plano (chuva, kits, ocupação, pesagem, envio).
- Envio da **planilha .xlsx** no formato do Anexo 05a, das fotos em **.zip** e de uma cópia de
  segurança em **.json**, que também junta os registros de dois aparelhos.

## Banco de dados e análise

A pasta [banco/](banco/README.md) tem o banco SQLite que junta as planilhas dos dois celulares, as
cópias de segurança, os CSV dos kits e as fotos (`banco_coleta.py`), e o programa de análise
estatística do estudo (`analise_meliponicultura.py`, Anexo 05b). O arquivo do banco, com os dados de
campo, fica fora do repositório.

## Por que este repositório existe separado

Mesma razão do `beemeter-painel`: o projeto completo fica num repositório **privado**. Aqui mora
**somente o aplicativo e as ferramentas de dados**: um arquivo HTML, a casca Android, o banco e a
análise — sem nenhum dado. O repositório é público, o Pages é gratuito e nenhum dado de campo fica aqui: o cadastro das colônias, os nomes e as coletas são
feitos no celular e só saem dele quando o monitor envia a planilha.

## Como publicar

Settings → Pages → **Source: Deploy from a branch** → `main` / `/ (root)` → Save.

Não há fluxo de Actions: a página é um arquivo único servido direto da raiz.

## Sobre os dados

Tudo fica no aparelho (`localStorage` para os registros; fotos em arquivos do aplicativo no Android
ou no `IndexedDB` do navegador). Não há servidor e o aplicativo não usa internet. O que for
registrado num celular não aparece em outro até que a cópia de segurança seja importada.

---

Anderson Cardoso Sakuma — **IPÊ/FIS**, Projeto Amazônia Bee

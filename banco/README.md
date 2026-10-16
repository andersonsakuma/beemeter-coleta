# Banco de dados da coleta

Um arquivo **SQLite** (`coleta.sqlite`) junta tudo o que é levantado em campo, dos dois celulares e
dos kits, num lugar só. O arquivo do banco **não** fica neste repositório: ele contém os dados de
campo e mora na pasta do projeto, fora do GitHub.

## O que entra

| Arquivo | Origem | Vai para |
|---|---|---|
| `coleta-<nome>-<data>.xlsx` | botão **Enviar planilha** do aplicativo | uma tabela por ficha |
| `copia-coleta-<nome>-<data>.json` | botão **Salvar cópia** do aplicativo | idem, inclusive registros excluídos (marcados) |
| `Anexo_05a_Planilha_Coleta_e_Ganhos_V1_FIS.xlsx` | planilha digitada à mão | fichas e parâmetros da aba F11_Ganhos |
| `K01.csv` … | descarga dos kits | `leituras_kit` |
| `fotos-<nome>-<data>.zip` | botão **Enviar fotos** do aplicativo | `fotos` (arquivos em `fotos/`, ao lado do banco) |

Reimportar o mesmo arquivo não duplica nada: cada registro do aplicativo tem um `id`, e vale a versão
mais recente. O cadastro das colônias é juntado campo a campo, para que o sorteio feito num celular
não se perca no outro. Cada importação fica registrada na tabela `importacoes`.

## Uso

```bash
python banco_coleta.py importar --banco coleta.sqlite  coleta-*.xlsx  fotos-*.zip  kits/*.csv
python banco_coleta.py resumo   --banco coleta.sqlite          # contagens e conferências
python banco_coleta.py exportar --banco coleta.sqlite --planilha consolidado.xlsx --kits kits
python analise_meliponicultura.py analisar --planilha consolidado.xlsx --kits kits
python banco_coleta.py consulta --banco coleta.sqlite "SELECT * FROM v_producao"
```

O **resumo** aponta: grupo sem sorteio ou com mais de um controle, valores fora da faixa esperada,
chuva lida duas vezes no mesmo dia, extração repetida, colônia sem extração de 2026 e kit sem
verificação há mais de 14 dias.

## Tabelas e visões

Tabelas (uma por ficha, com as colunas do Anexo 05a): `colonias`, `linha_base`, `instalacao_kit`,
`verificacao_kit`, `ocupacao`, `pesagem_atividade`, `chuva`, `manejo`, `extracao`, `assistencia`,
`praticas`, `producao_assistidos`, `sorteios`, `leituras_kit`, `fotos`, `parametros`, `importacoes`.
O esquema completo está em [esquema.sql](esquema.sql).

Visões prontas: `v_producao` (produção 2026 e 2027 por colônia, com o tratamento),
`v_ocupacao_atual` (última observação e dias desde ela), `v_chuva_mensal`, `v_kits_diario`
(médias e amplitudes diárias dos kits ligadas à colônia) e `v_praticas` (índice antes e depois).

Para navegar pelas tabelas sem programar: **DB Browser for SQLite** (<https://sqlitebrowser.org>).

Requer Python 3 com `pandas` e `openpyxl` — os mesmos do programa de análise.

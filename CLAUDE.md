# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

O repositório é escrito em português (código, docstrings, comentários, commits). Mantenha esse idioma.

## Comandos

```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt pytest

python -m pytest -q                        # todos os testes (offline, preços sintéticos, segundos)
python -m pytest tests/test_gerar_tela.py::TestClassificaEvidencia -q     # uma classe
python -m pytest -q -k "regua"                                            # um teste por nome

python gerar_tela.py                       # gera saida/ com dados reais (~70 downloads, minutos)
start saida\index.html
```

`python gerar_tela.py` é exatamente o que o GitHub Actions roda. Os testes nunca tocam a rede;
só o gerador baixa.

## Arquitetura

Pipeline de um comando só (`gerar_tela.py: main()`): lê `tickers.csv` → baixa cada papel
(`nucleo.data.load_prices`, único ponto de rede) → peneira de qualidade
(`nucleo.qualidade_dados.avalia_qualidade`) → `estado_de_hoje()` por aprovado →
`monta_pagina()` preenche `template.html` → grava `saida/index.html` e `saida/dados/{TICKER}.xlsx`.

Três invariantes que o código sustenta de propósito:

- **`estado_de_hoje` calibra e lê em conjuntos diferentes.** Os cortes de decil saem só do treino
  (`quantis_do_treino`), a estatística histórica sai só do teste, e o decil exibido vem da última
  linha da série completa — inclusive as linhas sem retorno futuro. Ler o decil na tabela filtrada
  por `dropna()` mostraria a posição de `DIST_HORIZONTE` pregões atrás, erro silencioso e grave.
- **`seleciona_destaques` é a única fonte de verdade sobre quais papéis existem na tela.** A tabela
  HTML e a gravação das planilhas chamam a mesma função; separá-las produziria link para arquivo
  inexistente ou arquivo sem link.
- **`classifica_evidencia` é o único lugar que emite juízo.** Armadilhas primeiro (excesso positivo
  com retorno negativo; excesso negativo dentro da zona), depois "fora da zona", depois a escala por
  episódios independentes. Mudar a ordem esconde justamente os casos que mais enganam.

`ZONA = (0, 1, 2)` (decis de viés observado) e `FORCA_EVIDENCIA` vivem no topo de `gerar_tela.py`;
os dez parâmetros do estudo vivem em `nucleo/config.py`.

O BOVA11 (`config.DIST_INDICE`) é a leitura mestra: se ele reprovar na peneira, `main()` encerra
com `SystemExit` e o job de publicação falha. Isso é intencional — falhas de papéis individuais o
gerador absorve e segue.

### Template

`template.html` tem nove marcadores `{{...}}`, listados na constante `MARCADORES`. Ao acrescentar
ou renomear um, atualize os três lugares: o template, `MARCADORES` e o dict `valores` em
`monta_pagina`. Os quatro rótulos que `classifica_evidencia` emite precisam aparecer na legenda do
template — há teste que verifica isso, e teste que garante que nenhum marcador sobra na página.

### `saida/` e a publicação

O artefato publicado é a pasta `saida/` **inteira**: os botões de download apontam para `dados/`
por caminho relativo. `saida/` não é versionada; é regerada a cada execução.
`.github/workflows/publicar.yml` roda em push na `main`, às 21:30 UTC em dias úteis e por clique
manual — `schedule`/`workflow_dispatch` só valem na branch padrão, por isso o gatilho de `push`
existe. `configure-pages` usa `enablement: true` para habilitar o Pages na primeira execução.

## `nucleo/` é código copiado — nunca edite aqui

`nucleo/` é cópia do repositório irmão
[`robusta_backtest`](https://github.com/GiovanniCharret/robusta_backtest) (`src/robusta_ml/`),
trazida para a tela rodar sem o laboratório no caminho de importação. `data.py`, `target.py`,
`features_mma.py` e `qualidade_dados.py` são cópia literal; `faixas.py` são cinco funções extraídas
de `extremos.py`; `config.py` foi reescrito com as dez constantes que a tela lê.

Uma correção feita direto em `nucleo/` se perde na próxima recópia e as duas versões divergem para
sempre. Corrija no laboratório, recopie, e **atualize o commit de origem registrado no README** —
a resincronização é manual e nada avisa quando ela atrasa.

## Escrita do código

O estilo aqui é denso em prosa e deliberado: cada função abre com um docstring que explica **por que
existe**, numera as fases da execução e descreve entrada e saída; os comentários de linha marcam as
fases e registram a razão de decisões que pareceriam arbitrárias (por que ASCII na barra da tqdm,
por que `file=sys.stdout`, por que a Fase 4 vem antes da Fase 3). Código novo deve seguir o mesmo
padrão — o repositório trata a justificativa como parte do artefato.

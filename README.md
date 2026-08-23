# CharretIA — previsor de movimentos da B3

Gera uma página estática com a posição de cada papel líquido da B3 na escala de afastamento da
média móvel, e o que historicamente aconteceu depois de dias naquela posição. Publicada
diariamente no GitHub Pages.

Este repositório é a **publicação**. A pesquisa que o originou vive no repositório irmão
[`robusta_backtest`](https://github.com/GiovanniCharret/robusta_backtest) — aqui não se mede nada
novo, apenas se aplica o que já foi medido e validado fora da amostra.

## Arquivos

| arquivo | papel |
|---|---|
| `gerar_tela.py` | o gerador: baixa, peneira, calcula o estado de hoje, grava a página e as planilhas |
| `template.html` | a página com marcadores `{{...}}`; sem dependência externa além das fontes |
| `tickers.csv` | os 70 papéis líquidos rastreados |
| `nucleo/` | cópia do que a tela usa do laboratório (ver *Proveniência*) |
| `saida/index.html` | resultado gerado |
| `saida/dados/{TICKER}.xlsx` | uma planilha de estudo por papel visível na tela |

**O artefato publicado é a pasta `saida/` inteira**, não só o `index.html`: os botões de download
apontam para `dados/` por caminho relativo e quebram se a pasta não subir junto. São 7 arquivos e
cerca de 2 megabytes — a página, mais uma planilha por papel exibido (`DIST_TOP_N`, hoje 5) e uma
do índice. `saida/` é gerada a cada execução e **não é versionada**.

## Proveniência do `nucleo/` — leia antes de mexer

A tela roda sozinha, então o que ela usa do laboratório está **copiado** aqui:

| arquivo | origem em `robusta_backtest` |
|---|---|
| `data.py`, `target.py`, `features_mma.py`, `qualidade_dados.py` | `src/robusta_ml/`, cópia literal |
| `faixas.py` | cinco funções extraídas de `src/robusta_ml/extremos.py` (708 linhas, arrasta matplotlib) |
| `config.py` | reescrito com as dez constantes que a tela lê, e só elas |

**Copiado do commit `e55455b48aca74c9742044815840472d0c310412`, em 23/08/2026.**

O preço da cópia é a **deriva silenciosa**: alguém corrige o laboratório, a tela continua
publicando o comportamento antigo, e nada avisa. Enquanto os dois repositórios estavam juntos, um
teste comparava os dois lados automaticamente; separados, **a resincronização passou a ser manual**.
Foi uma escolha consciente, e o custo dela é este parágrafo.

Ao mudar qualquer coisa em `robusta_ml/data.py`, `target.py`, `features_mma.py`,
`qualidade_dados.py` ou nas cinco funções de faixa em `extremos.py`, recopie para cá e **atualize
o commit de origem acima**. Nunca edite `nucleo/` diretamente: a correção se perderia na próxima
recópia, e as duas versões divergiriam para sempre.

## Quais papéis a tabela mostra

Os `DIST_TOP_N` primeiros (hoje 5), ordenados pela **posição no decil** — mais afastado para baixo
primeiro. Empate no decil é desfeito pela **força da evidência** (forte, moderada, fraca, e os dois
rótulos de alerta por último, porque são anti-sinais); empate nisso também, pelo maior excesso.

A lista completa dos aprovados não vai para a tela de propósito: 41 linhas poluem a leitura e,
pior, sugerem 41 oportunidades independentes — exatamente o erro que a página existe para evitar,
já que o efeito é de mercado inteiro.

**Só os papéis exibidos geram planilha.** A mesma função (`seleciona_destaques`) decide quem
aparece na tabela e quem vira arquivo, então a página nunca oferece download de arquivo inexistente
nem o pacote leva arquivo que ninguém alcança.

## O que vai nas planilhas de estudo

Cada uma cobre todos os pregões com escore válido, com as colunas `Close`, `mma_w90`,
`mma_dist_w90`, `mma_dist_z_w90`, `ret_45d`, `faixa` (o decil) e **`conjunto`**.

A última é a que importa: ela marca cada linha como `treino`, `embargo`, `teste` ou `sem_retorno`,
o que permite **conferir por fora** que a calibração dos cortes de decil não viu o futuro. No
BOVA11, por exemplo, o treino termina em 2020-10-23, seguem exatamente 45 linhas de `embargo` (o
tamanho do horizonte) e o teste começa em 2021-01-04. As 45 últimas linhas ficam `sem_retorno`
porque o retorno de 45 pregões à frente ainda não existe — e é entre elas que está o pregão de hoje,
o que a tela reporta.

## Rodar localmente

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pytest

# 1. Testes — offline, com preços sintéticos, não tocam a rede
python -m pytest -q

# 2. Gerar a página com dados reais (baixa ~70 papéis, leva alguns minutos).
#    É o mesmo comando que o GitHub Actions roda.
python gerar_tela.py

# 3. Abrir e conferir
start saida\index.html
```

## O que conferir antes de publicar

O passo 2 mostra uma barra de andamento com o placar ao lado (`ok N | fora M`) e uma linha por papel,
anunciada no momento em que ele é decidido:

```
  ok  RENT3    decil 0  +11,0 pp
  fora WEGE3    preço parado em 29% dos dias (máximo 15%)
```

Não há resumo no fim — a barra já carrega os totais. Confira, enquanto roda:

- **o BOVA11 tem de sair como `ok`.** Se ele for reprovado, o gerador para com erro. É proposital:
  sem a leitura mestra a tela perde o enquadramento e viraria uma lista de sinais soltos.
- **o placar final da barra** — hoje `ok 42 | fora 28`. Uma queda brusca nos aprovados costuma
  indicar problema na fonte de dados, não no mercado.
- **motivos de reprovação** — vêm por extenso em cada linha `fora`. Um papel novo reprovando por
  "treino insuficiente" é esperado; um papel antigo reprovando por "volatilidade impossível"
  significa que a série ganhou um desdobramento não ajustado e precisa ser investigada.

Na página aberta, confira:

- **nenhum `{{MARCADOR}}` visível** — se aparecer, o template e o gerador saíram de sincronia;
- **a régua da leitura mestra tem exatamente um segmento escuro**;
- **a tabela rola na horizontal dentro da moldura**, sem empurrar a página. Abaixo de 982 pixels
  de largura aparece o aviso de rolagem, e a coluna `dados` fica fora da vista até você rolar;
- **estreite a janela até a largura de um celular** — a caixa final passa de duas colunas para
  uma em 700 pixels, e é o ponto mais frágil do layout;
- **clique um botão `↓ XLSX`** — um na seção do índice, um por linha da tabela. Se o navegador
  abrir um erro em vez de salvar, a pasta `dados/` não foi gerada ou não subiu junto.

## Publicação

`.github/workflows/publicar.yml` roda a cada push na `main`, às 18h30 de Brasília em dias úteis, e
por clique manual (`Run workflow`). Em `Settings` → `Pages`, a origem precisa estar em
**GitHub Actions** — com "Deploy from a branch" o GitHub serve a raiz do repositório, que não tem
`index.html`, e o site responde 404.

Dois pontos que mordem:

1. **`schedule` e `workflow_dispatch` só valem na branch padrão.** Um workflow que existe apenas
   numa branch de trabalho não aparece para execução manual nem dispara no horário.
2. **A rede é a única dependência externa.** O `yfinance` falha em alguns papéis de forma
   intermitente e o gerador segue; se o **BOVA11** falhar, o processo para com erro, que é o
   comportamento certo.

## O que esta tela deliberadamente não faz

Não emite sinal de venda — o decil alto rende abaixo da média do próprio papel, mas só é negativo
em termos absolutos em cerca de metade dos casos. Não considera custo de operação nem risco.
E não trata os papéis como apostas independentes: o efeito é de mercado inteiro, e por isso o
índice vem antes de tudo na página.

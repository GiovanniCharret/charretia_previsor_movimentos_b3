# CharretIA — previsor de movimentos da B3

**No ar:** https://giovannicharret.github.io/charretia_previsor_movimentos_b3/

Gera **três páginas estáticas**, publicadas diariamente no GitHub Pages:

| página | pergunta que responde |
|---|---|
| `index.html` — **triagem** | onde cada papel líquido está hoje na escala de afastamento da média móvel, e o que historicamente aconteceu depois de dias naquela posição |
| `alertas.html` — **gatilhos** | quais papéis fecharam hoje numa faixa que o estudo mediu como protetiva, com o setup aprovado para cada papel |
| `metodo.html` — **método** | como cada versão da tela funciona, com que parâmetros, e como voltar a uma versão anterior |

As duas primeiras convivem porque respondem perguntas diferentes: a triagem sempre tem os setenta
papéis para mostrar; a de gatilhos fica **vazia na maioria dos pregões**, porque os episódios são
raros por definição. Por isso a triagem é a página de entrada, e um contador na barra de abas avisa
quando há gatilhos sem exigir que o visitante abra a outra página.

Este repositório é a **publicação**. A pesquisa que o originou vive no repositório irmão
[`rebuild_robusta_backtests`](https://github.com/GiovanniCharret/robusta_backtest) — aqui não se
mede nada novo, apenas se aplica o que já foi medido e validado fora da amostra.

## Arquivos

| arquivo | papel |
|---|---|
| `gerar_tela.py` | gerador da **triagem**: baixa, peneira, calcula o estado de hoje, grava a página e as planilhas |
| `gerar_alertas.py` | gerador dos **gatilhos**: cruza os setups aprovados com o fechamento de hoje |
| `gerar_metodo.py` | gerador do **método**: não toca a rede, monta a página a partir de `versoes.py` |
| `publicacao.py` | o que as três páginas dividem: a barra de abas, a cópia dos estilos e o estado do dia |
| `versoes.py` | o **registro histórico** das versões: pergunta, parâmetros, passo a passo e receita de retorno |
| `template*.html` | as três páginas com marcadores `{{...}}` |
| `estilo.css`, `estilo_componentes.css` | o sistema visual e os componentes, ambos linkados pelas três páginas |
| `tickers.csv` | os 70 papéis líquidos rastreados pela triagem |
| `estudo/setups.csv` | os setups aprovados, **exportados pelo laboratório** (ver *Proveniência do estudo*) |
| `nucleo/` | cópia do que as telas usam do laboratório (ver *Proveniência do núcleo*) |
| `saida/*.html` | as três páginas geradas |
| `saida/dados/{TICKER}.xlsx` | uma planilha de estudo por papel visível na triagem |
| `saida/estado.json` | ligação entre geradores: quantos papéis dispararam hoje |

**A ordem de execução importa.** `gerar_alertas.py` roda primeiro porque grava `saida/estado.json`,
de onde as outras duas tiram o contador da barra de abas. Invertida a ordem, o site publica com o
contador do dia anterior — ou sem contador nenhum na primeira execução.

**O artefato publicado é a pasta `saida/` inteira**, não só o `index.html`: os botões de download
apontam para `dados/` por caminho relativo e quebram se a pasta não subir junto. São 7 arquivos e
cerca de 2 megabytes — a página, mais uma planilha por papel exibido (`DIST_TOP_N`, hoje 5) e uma
do índice. `saida/` é gerada a cada execução e **não é versionada**.

## Proveniência do núcleo — leia antes de mexer

A tela roda sozinha, então o que ela usa do laboratório está **copiado** aqui:

| arquivo | origem em `robusta_backtest` |
|---|---|
| `data.py`, `target.py`, `features_mma.py` | `src/robusta_ml/`, cópia literal |
| `qualidade_dados.py` | `src/robusta_ml/`, cópia literal — inclui `apara_inicio` e `avalia_qualidade_por_divisao`, do achado U |
| `faixas.py` | cinco funções extraídas de `src/robusta_ml/extremos.py` (708 linhas, arrasta matplotlib) |
| `config.py` | reescrito com as constantes que as telas leem, em dois blocos — um por versão |

**Copiado do commit `e55455b48aca74c9742044815840472d0c310412`, em 23/08/2026, e resincronizado em
07/09/2026** (`qualidade_dados.py` recebeu as duas funções do achado U, sem as quais
`gerar_alertas.py` não roda).

O preço da cópia é a **deriva silenciosa**: alguém corrige o laboratório, a tela continua
publicando o comportamento antigo, e nada avisa. Enquanto os dois repositórios estavam juntos, um
teste comparava os dois lados automaticamente; separados, **a resincronização passou a ser manual**.
Foi uma escolha consciente, e o custo dela é este parágrafo.

Ao mudar qualquer coisa em `robusta_ml/data.py`, `target.py`, `features_mma.py`,
`qualidade_dados.py` ou nas cinco funções de faixa em `extremos.py`, recopie para cá e **atualize
o commit de origem acima**. Nunca edite `nucleo/` diretamente: a correção se perderia na próxima
recópia, e as duas versões divergiriam para sempre.

## Proveniência do estudo — `estudo/setups.csv`

A tela de gatilhos **não faz varredura nenhuma**. Ela lê `estudo/setups.csv`, gerado no laboratório
por `robusta_ml.exporta_setups` e versionado aqui. O arquivo traz, por linha, um setup
(papel, horizonte, janela) e — o que mais importa — o **corte do decil** daquele par (papel, janela),
medido lá sobre a história completa.

Por que o corte não é calculado aqui: a aplicação baixa só o necessário para o escore de hoje, uns
dois anos. Estimar o corte com essa amostra foi tentado em 06/09/2026 e produziu um defeito grave —
na GGBR4 com janela 200, o corte ia de **−2,010** (história completa) para **+0,465** (dois anos).
Um corte positivo faria o "decil mais afastado para baixo" incluir dias com o preço *acima* da
média. A divisão de trabalho é: **o laboratório baixa tudo e mede; a aplicação só lê e economiza.**

`estudo/PROVENIENCIA.md` registra a data da exportação, o commit do laboratório que a produziu e se
havia alterações não commitadas na ocasião. Para atualizar, a partir da raiz do laboratório:

```powershell
$env:PYTHONPATH="src"; uv run python -m robusta_ml.rank_protecao
$env:PYTHONPATH="src"; uv run python -m robusta_ml.rank_protecao --cortes
$env:PYTHONPATH="src"; uv run python -m robusta_ml.exporta_setups
```

O terceiro comando grava direto neste repositório. Como o `nucleo/`, é **sincronização manual**:
nada avisa quando o laboratório avança e o arquivo aqui fica para trás.

## Registro de versões — `versoes.py`

`metodo.html` é gerada a partir de `versoes.py`, que guarda, por versão: a pergunta que ela
responde, os parâmetros exatos, o passo a passo e — para as que não estão em produção — a receita
de retorno. É o que torna um retorno a uma versão anterior possível sem arqueologia de commit.

**Uma versão nova nasce quando um achado muda a pergunta, não quando um número muda de valor.**
Recalibrações entram como nota na versão vigente. Sem esse critério, cada nova varredura viraria
uma versão e o registro perde a serventia em poucos meses.

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

# 2. Gerar as três páginas com dados reais. A ORDEM importa: `gerar_alertas.py` grava
#    `saida/estado.json`, de onde as outras duas tiram o contador da barra de abas.
#    São os mesmos comandos que o GitHub Actions roda.
python gerar_alertas.py     # 61 papéis, ~1 minuto
python gerar_tela.py        # 70 papéis, ~1 minuto
python gerar_metodo.py      # sem rede, instantâneo

# 3. Abrir e conferir
start saida\index.html
```

Qualquer gerador roda sozinho, para conferência rápida — `python gerar_alertas.py PRIO3` verifica um
papel só. Fora da ordem acima, a barra de abas sai **sem contador**, que é o comportamento correto
quando ainda não se mediu: inventar um zero afirmaria que não houve gatilho, o que é diferente de
não saber.

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
por clique manual (`Run workflow`). O passo `configure-pages` usa `enablement: true`, então **o
próprio workflow habilita o Pages** na primeira execução — não é preciso acertar `Settings` → `Pages`
à mão.

Três pontos que mordem, todos aprendidos na marra:

1. **`schedule` e `workflow_dispatch` só valem na branch padrão.** Um workflow que existe apenas
   numa branch de trabalho não aparece para execução manual nem dispara no horário — fica invisível,
   sem nenhum erro em lugar nenhum. Foi por isso que o gatilho de `push` existe.
2. **Sem `enablement: true`, um repositório novo falha** com *"Get Pages site failed"*: a API
   responde 404 porque ainda não existe site algum. E com a origem em "Deploy from a branch" o
   GitHub serve a raiz do repositório, que não tem `index.html` — o site responde 404 mesmo com o
   job verde.
3. **A rede é a única dependência externa.** O `yfinance` falha em alguns papéis de forma
   intermitente e o gerador segue; se o **BOVA11** falhar, o processo para com erro, que é o
   comportamento certo.

## O que esta tela deliberadamente não faz

Não emite sinal de venda — o decil alto rende abaixo da média do próprio papel, mas só é negativo
em termos absolutos em cerca de metade dos casos. Não considera custo de operação nem risco.
E não trata os papéis como apostas independentes: o efeito é de mercado inteiro, e por isso o
índice vem antes de tudo na página.

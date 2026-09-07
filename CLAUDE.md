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

# As três páginas, NESTA ORDEM (gerar_alertas grava o estado que as outras duas leem):
python gerar_alertas.py                    # tela de gatilhos, 61 downloads
python gerar_tela.py                       # tela de triagem, ~70 downloads
python gerar_metodo.py                     # página de método, sem rede
start saida\index.html

python gerar_alertas.py PRIO3              # um papel só, para conferência rápida
```

São exatamente os comandos que o GitHub Actions roda, na mesma ordem. Os testes nunca tocam a rede;
só os dois primeiros geradores baixam.

## Arquitetura

**Três páginas, três geradores independentes, um módulo em comum.**

| gerador | página | fonte dos dados |
|---|---|---|
| `gerar_tela.py` | `index.html` — triagem | `tickers.csv` + downloads |
| `gerar_alertas.py` | `alertas.html` — gatilhos | `estudo/setups.csv` + downloads |
| `gerar_metodo.py` | `metodo.html` — método | `versoes.py`, **sem rede** |

`publicacao.py` carrega o que os três dividem: a barra de abas (`barra_de_abas`), a cópia dos
estilos para a pasta publicada (`copia_estatica`) e o estado do dia (`grava_estado`/`le_estado`).

Duas regras que não são óbvias e o código sustenta:

- **A ordem de execução importa.** `gerar_alertas.py` grava `saida/estado.json` com quantos papéis
  dispararam hoje, e as outras duas leem esse arquivo para o contador da barra de abas. Ausência
  dele **não é erro**: a barra sai sem contador, que é o correto quando ainda não se mediu —
  inventar um zero afirmaria que não houve gatilho, o que é diferente de não saber.
- **A tela de gatilhos não recalcula o corte do decil.** Ele vem medido no laboratório, em
  `estudo/setups.csv`. Com a história curta que a aplicação baixa, o corte da GGBR4 com janela 200
  ia de −2,010 para +0,465 — trocava de sinal, e um corte positivo faria o "decil mais afastado
  para baixo" incluir dias com o preço acima da média.

### A triagem (v1)

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
os parâmetros do estudo vivem em `nucleo/config.py`, em dois blocos — um por versão da tela.

### Os gatilhos (v2)

Dois laços (`gerar_alertas.py`). O primeiro, por papel: baixa **só o necessário para o escore de
hoje** (`janela + 252 - 1 + folga` pregões, calculado a partir da maior janela aprovada daquele
papel) e compara o escore de hoje com o corte que veio do laboratório. O segundo, por setup: cruza
com `estudo/setups.csv` e agrupa **janelas vizinhas numa faixa só** — médias vizinhas compartilham
cerca de 99% dos dados, então listá-las separadas sugeriria dezenas de gatilhos onde há um.

A linha "menos pior" dos papéis sem nenhum setup aprovado (`passa_barra` falso) é descartada: ela
pode disparar o decil, mas não é gatilho, e exibi-la ao lado dos aprovados apresentaria como sinal o
que a planilha marca como ausência de sinal.

### O método (v3 da documentação, não da tela)

`gerar_metodo.py` monta a página a partir de `versoes.py`, que é o **registro histórico**: por
versão, a pergunta que ela responde, os parâmetros exatos, o passo a passo e — só para as que não
estão em produção — a receita de retorno. Uma versão nova nasce quando um achado muda a *pergunta*,
não quando um número muda de valor.

O BOVA11 (`config.DIST_INDICE`) é a leitura mestra: se ele reprovar na peneira, `main()` encerra
com `SystemExit` e o job de publicação falha. Isso é intencional — falhas de papéis individuais o
gerador absorve e segue.

### Template

São três templates, um por página. `template.html` tem onze marcadores `{{...}}`, listados na
constante `MARCADORES`. Ao acrescentar ou renomear um, atualize os três lugares: o template,
`MARCADORES` e o dict `valores` em `monta_pagina`. Os quatro rótulos que `classifica_evidencia`
emite precisam aparecer na legenda do template — há teste que verifica isso, e teste que garante que
nenhum marcador sobra em nenhuma das três páginas.

**O estilo é externo.** Os 237 selos de `estilo.css` saíram do bloco `<style>` de `template.html` em
07/09/2026: com três páginas, mantê-lo embutido significaria três cópias que divergem na primeira
mudança de cor. `estilo_componentes.css` traz os componentes que as páginas acrescentaram — a
começar pela **barra de abas, que as três exibem** — e não redefine cor, fonte ou medida nenhuma:
todas vêm das variáveis de `estilo.css`.

⚠️ **As três páginas linkam OS DOIS.** O arquivo chamava-se `estilo_alertas.css` até 07/09/2026, e o
nome enganou: o `template.html` foi publicado sem o link e a barra da página inicial saiu como links
sublinhados grudados. O teste que existia verificava só uma direção — que todo estilo linkado é
copiado — e passava. Agora há também o inverso: **todo estilo declarado precisa estar linkado em
todo template**, e as classes que `barra_de_abas` emite precisam ter regra em algum deles.

### `saida/` e a publicação

O artefato publicado é a pasta `saida/` **inteira**: as três páginas, os dois estilos, o
`estado.json` e as planilhas em `dados/`, para onde os botões de download apontam por caminho
relativo. `saida/` não é versionada; é regerada a cada execução. **`estudo/` é o oposto**: vem do
laboratório, é versionada, e sem ela `gerar_alertas.py` não roda.
`.github/workflows/publicar.yml` roda em push na `main`, às 21:30 UTC em dias úteis e por clique
manual — `schedule`/`workflow_dispatch` só valem na branch padrão, por isso o gatilho de `push`
existe. `configure-pages` usa `enablement: true` para habilitar o Pages na primeira execução.

## `nucleo/` é código copiado — nunca edite aqui

`nucleo/` é cópia do repositório irmão
[`rebuild_robusta_backtests`](https://github.com/GiovanniCharret/robusta_backtest)
(`src/robusta_ml/`), trazida para as telas rodarem sem o laboratório no caminho de importação.
`data.py`, `target.py`, `features_mma.py` e `qualidade_dados.py` são cópia literal; `faixas.py` são
cinco funções extraídas de `extremos.py`; `config.py` foi reescrito com as constantes que as telas
leem, em dois blocos — um por versão.

Uma correção feita direto em `nucleo/` se perde na próxima recópia e as duas versões divergem para
sempre. Corrija no laboratório, recopie, e **atualize o commit de origem registrado no README** —
a resincronização é manual e nada avisa quando ela atrasa.

**`estudo/setups.csv` tem a mesma natureza**, e o mesmo risco: é gerado lá por
`robusta_ml.exporta_setups` e versionado aqui. `estudo/PROVENIENCIA.md` registra a data, o commit de
origem e se havia alterações não commitadas na ocasião. Nunca edite o arquivo à mão — reexporte.

## Escrita do código

O estilo aqui é denso em prosa e deliberado: cada função abre com um docstring que explica **por que
existe**, numera as fases da execução e descreve entrada e saída; os comentários de linha marcam as
fases e registram a razão de decisões que pareceriam arbitrárias (por que ASCII na barra da tqdm,
por que `file=sys.stdout`, por que a Fase 4 vem antes da Fase 3). Código novo deve seguir o mesmo
padrão — o repositório trata a justificativa como parte do artefato.

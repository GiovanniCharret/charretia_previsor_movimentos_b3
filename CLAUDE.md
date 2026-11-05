# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

O repositório é escrito em português (código, docstrings, comentários, commits). Mantenha esse idioma.

## Comandos

```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt pytest

python -m pytest -q                        # os 104 testes (offline, preços sintéticos, segundos)
python -m pytest tests/test_gerar_tela.py::TestClassificaEvidencia -q     # uma classe
python -m pytest -q -k "regua"                                            # um teste por nome

# As três páginas, NESTA ORDEM (gerar_extremos grava o estado que as outras duas leem):
python gerar_extremos.py                   # tela da faixa extrema (v3), 100 downloads
python gerar_setores.py                    # bancos e elétricas (v4), 18 downloads
python gerar_tela.py                       # tela de triagem, 100 downloads
python gerar_metodo.py                     # página de método, sem rede
start saida\index.html
```

São exatamente os comandos que o GitHub Actions roda, na mesma ordem. Os testes nunca tocam a rede;
só os dois primeiros geradores baixam.

## Arquitetura

**Quatro páginas, quatro geradores independentes, um módulo em comum.**

| gerador | página | fonte dos dados |
|---|---|---|
| `gerar_tela.py` | `index.html` — triagem | `lista_tickers_liquidos.xlsx` + downloads |
| `gerar_extremos.py` | `extremos.html` — faixa extrema (v3, a vigente) | `estudo/faixa_extrema_*.csv` + downloads |
| `gerar_setores.py` | `setores.html` — bancos e elétricas (v4, em observação) | `estudo/setores_*.csv` + downloads |
| `gerar_metodo.py` | `metodo.html` — método | `versoes.py`, **sem rede** |

`publicacao.py` carrega o que os três dividem: a barra de abas (`barra_de_abas`), a cópia dos
estilos para a pasta publicada (`copia_estatica`) e o estado do dia (`grava_estado`/`le_estado`).

Duas regras que não são óbvias e o código sustenta:

- **A ordem de execução importa.** `gerar_extremos.py` grava `saida/estado.json` com quantos papéis
  estão em destaque hoje, e as outras duas leem esse arquivo para o contador da aba "Faixa extrema".
  Ausência dele **não é erro**: a barra sai sem contador, que é o correto quando ainda não se mediu
  — inventar um zero afirmaria que não houve destaque, o que é diferente de não saber.
- **A faixa extrema não recalcula corte.** Ele vem medido no laboratório, em `estudo/`. Com a
  história curta que a aplicação baixa, o corte da GGBR4 com janela 200 ia de −2,010 para +0,465 —
  trocava de sinal (achado da antiga v2, que vale para qualquer corte de cauda).

### A triagem (v1)

Pipeline de um comando só (`gerar_tela.py: main()`): lê `lista_tickers_liquidos.xlsx` (coluna
`ticker`, 100 papéis; cópia da lista do laboratório) → baixa cada papel
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

### Os gatilhos (v2) — descontinuada em 04/11/2026

A tela de gatilhos (`alertas.html`, `gerar_alertas.py`, `estudo/setups.csv`) saiu do site depois de
duas semanas de uso da v3, que a substituiu com mais critério (decisão do usuário). Fica **só o
registro** em `versoes.py`, com a receita de retorno: o código está no commit `84bfcb5`. Não
recrie a página nem um link para `alertas.html` — há testes que falham se algum template ou a barra
de abas apontar para ela. As duas contas de download que só ela tinha (`pregoes_necessarios`,
`periodo_do_download`) foram para `gerar_extremos.py`.

Mudanças de apresentação entram no campo `notas` da versão vigente em `versoes.py`, não como versão
nova. A próxima versão nasce quando o **modelo** mudar.

### A faixa extrema (v3) — a versão vigente

Nasceu do achado W do laboratório (12/10/2026): a proteção por episódio da v2 era em grande parte
**efeito mecânico da contagem** (preços sem memória já devolvem 75% a 80%). O que restou é um
indício medido **por dia** nos percentis de 2,5% e 5%. Regras que não devem ser "melhoradas":

- **A medida é frequência por dia, nunca por episódio.** O episódio entra só como contagem de
  observações independentes, porque dias seguidos não são independentes.
- **As nove janelas são fixas** (5 a 200) e foram fixadas antes do teste conjunto. A tela mostra
  **em quais** delas o papel está no extremo hoje (`faixa_de_janelas`, formato "10–30 (3)", com
  vizinhança na lista de nove), e **só no corte da seção** em que ele aparece — misturar os cortes de
  2,5% e 5% numa linha confundiu a leitura (19/10/2026).
- **A frequência e a taxa-base da linha são as dessas janelas** (`_medida_das_janelas`, média
  simples entre elas, a partir de `estudo/faixa_extrema_por_janela.csv`), no horizonte de 45 pregões
  ou, na falta dele, de 20. Cada linha vem de poucos episódios; não há limite inferior na tela, porque
  ele ficava em 20% a 30% e foi lido como placebo.
- **Só é destaque quem tem frequência acima da própria taxa-base** (`acima_da_base`). Os demais
  ficam em `saida/faixa_extrema_do_dia.csv`, e a página diz quantos ficaram de fora.
- **O quadro "Um indício, não um achado" faz parte da página** e tem teste.
- Os cortes e as medidas vêm de `estudo/faixa_extrema_cortes.csv`, `faixa_extrema_medidas.csv` e
  `faixa_extrema_por_janela.csv`, exportados por `robusta_ml.faixa_extrema`. A tela não recalcula
  corte nem frequência, e **falha de propósito** se um dos três faltar.

### Bancos e elétricas (v4) — em observação

Nasceu do teste por setor do laboratório (04/11/2026): o decil 0, em 45 pregões, teve os menores
valores-p nas elétricas e nos bancos, sem sobreviver à correção pelos 66 testes. É **hipótese em
observação**, e a v3 continua sendo a versão em produção (`versoes.py` tem exatamente uma, e há
teste disso). Regras:

- **A lista de 18 papéis é travada no laboratório** (`SETORES_V4` em `robusta_ml/config.py`) e chega
  aqui dentro de `estudo/setores_cortes.csv`, com a coluna `setor`. Não acrescente papel aqui.
- **A linha é a da v3**, com a frequência e a taxa-base do próprio papel nas janelas em que ele está
  no decil 0 hoje (pedido do usuário). `gerar_setores.py` importa de `gerar_extremos.py` o
  download, o escore, `faixa_de_janelas`, `_medida_das_janelas` e `_secao_html`. Esta última e
  `_linha_html` ganharam o parâmetro `prefixo` da planilha (`setores_{TICKER}.xlsx`).
- **Uma seção por setor**, na ordem de `config.SETORES_ROTULOS`, sempre visíveis, mesmo vazias.
- **O contador da barra continua sendo o da faixa extrema**; a v4 só o lê.

### As planilhas de estudo da faixa extrema

`planilha_estudo.py` grava `saida/dados/extremos_{TICKER}.xlsx` para os papéis em destaque, com
link na última coluna da tabela (pedido do usuário, que é estudante e
quer ver o arranjo de treino e teste). `monta_estudo` é pura: devolve a série linha a linha de uma
janela — com `divisao`, `conjunto`, `treino_ate`, `corte_usado`, `na_faixa`, `episodio` — e o
resumo por divisão. Pontos que não são óbvios:

- **É uma reimplementação para estudo** da divisão por calendário do laboratório (treino acumulado,
  embargo igual ao horizonte, corte só do treino). Os números da tela não saem dela. Se o
  laboratório mudar a regra, atualize aqui à mão.
- **Só baixa a história completa dos papéis exibidos**, depois de montada a tabela do dia.
- **O link só aparece para a planilha que foi gravada** (`planilhas`, passado a `monta_pagina`).
  Falha no download deixa o papel com "—", e a página sai.
- O resumo traz **as duas contas lado a lado** — frequência por dia e episódios positivos —, que é o
  jeito mais direto de ver por que a v2 (descontinuada) e a v3 dão números diferentes.

### O método

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
laboratório, é versionada, e sem ela `gerar_extremos.py` não roda.
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

**Os arquivos de `estudo/` têm a mesma natureza**, e o mesmo risco: são gerados lá por
`robusta_ml.faixa_extrema` e versionados aqui. `estudo/PROVENIENCIA_FAIXA_EXTREMA.md` registra a
data, o commit de origem e se havia alterações não commitadas na ocasião. Nunca edite à mão —
reexporte.

## Os testes que não pertencem a nenhum gerador

`tests/test_site.py` cobre propriedades que **nenhum gerador sozinho garante**: as três páginas se
alcançam, nenhuma aponta para a tela descontinuada, exibem o mesmo contador, não deixam marcador de template escapar, e todo estilo declarado
está linkado em todo template.

Essa última nasceu de um defeito real (07/09/2026): o teste original verificava só que *todo estilo
linkado é copiado*, e passava enquanto a barra de abas da página inicial saía sem formatação nenhuma.
**Uma verificação que confirma um lado de uma relação bidirecional não é uma verificação da
relação.** Ao acrescentar um estático ou um componente compartilhado, escreva as duas direções.

## Escrita do código

O estilo aqui é denso em prosa e deliberado: cada função abre com um docstring que explica **por que
existe**, numera as fases da execução e descreve entrada e saída; os comentários de linha marcam as
fases e registram a razão de decisões que pareceriam arbitrárias (por que ASCII na barra da tqdm,
por que `file=sys.stdout`, por que a Fase 4 vem antes da Fase 3). Código novo deve seguir o mesmo
padrão — o repositório trata a justificativa como parte do artefato.

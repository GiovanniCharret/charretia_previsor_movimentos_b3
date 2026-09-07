"""
Os parâmetros que as telas leem — e só eles.

Por que este arquivo existe e não é cópia do `config.py` do laboratório: o de lá tem mais de
duzentas linhas, a maioria descrevendo experimentos que nenhuma tela roda (rede neural, varreduras
de janela, discretização supervisionada). Trazer tudo para cá faria alguém em manutenção procurar
aqui o botão errado. Estes são os valores efetivamente usados pelos geradores.

O arquivo tem DOIS blocos, um por versão da tela, porque os dois conjuntos de parâmetros são
independentes: a v1 responde "onde cada papel está na escala hoje", com janela e horizonte fixos; a
v2 responde "quem acionou um gatilho de proteção", com o setup que o estudo aprovou para cada papel.
Misturar os dois blocos faria uma recalibração de uma versão parecer que afeta a outra.

**Não edite aqui.** A fonte é `src/robusta_ml/config.py`, no repositório irmão
`rebuild_robusta_backtests`. Mude lá e recopie o valor para cá — e atualize o commit de origem
registrado no README.
"""

# ============================================================================
# Fonte dos dados
# ============================================================================

# Sufixo aplicado ao ticker no download (convenção da B3 no yfinance).
TICKER_SUFFIX = ".SA"

# Histórico baixado. "max" = tudo que a fonte tem — eventos extremos são raros, e mais história é
# a única saída real para o número pequeno de episódios independentes.
EXTREMOS_PERIOD = "max"

# ============================================================================
# v1 — TRIAGEM POR AFASTAMENTO (`gerar_tela.py`)
# ============================================================================

# Janela da média móvel. 90 fica na faixa em que o gradiente dos decis se mostrou mais forte nos
# horizontes curtos, e é uma das duas que a experiência do usuário apontou.
DIST_JANELA = 90

# Horizonte reportado, em pregões. 45 equilibra tamanho de efeito e número de episódios
# independentes: em 90 dias o efeito é maior, mas sobram poucos episódios para sustentá-lo.
DIST_HORIZONTE = 45

# Papel tratado como LEITURA MESTRA. O efeito medido é de mercado inteiro, então o índice vem antes
# dos papéis individuais — que são detalhamento dele, não apostas independentes.
DIST_INDICE = "BOVA11"

# Quantos papéis a tabela exibe. Uma tabela com os 41 aprovados polui a leitura e sugere 41
# oportunidades independentes, que é justamente o erro que a página tenta evitar. Ordenados por
# decil, desempate pela força da evidência.
DIST_TOP_N = 5

# Janela do desvio-padrão móvel que normaliza a distância (z = distância / desvio móvel).
# 252 ≈ um ano de pregão. Só usa passado, então não vaza futuro.
EXTREMOS_VOL_LAG = 252

# Número de faixas em que o escore é fatiado. 10 = decis. Cortes vêm só do treino.
EXTREMOS_N_FAIXAS = 10

# Início FIXO da janela de teste. Data de calendário, e não corte percentual: os históricos começam
# em anos diferentes, então a fração daria a cada papel uma janela distinta e as comparações entre
# papéis não valeriam.
EXTREMOS_INICIO_TESTE = "2021-01-01"

# Defasagem usada no cálculo da inclinação da média móvel. A tela não exibe inclinação, mas
# `build_features` exige o parâmetro.
SLOPE_LAG = 5


# ============================================================================
# v2 — GATILHOS DE PROTEÇÃO (`gerar_alertas.py`)
# ============================================================================
#
# Estes vêm dos achados N a U. Diferença de fundo em relação à v1: lá a janela e o horizonte são
# fixos e iguais para todos os papéis; aqui cada papel usa os setups que o estudo aprovou para ele,
# lidos de `estudo/setups.csv`. Nenhum destes valores é escolhido aqui — todos vêm da varredura.

# A faixa que dispara: o decil 0, o décimo mais afastado PARA BAIXO. Foi a faixa medida nos
# achados O a U; usar outra desfaria a correspondência entre o alerta e a proteção que ele exibe.
FAIXA_ALVO = 0

# Folga de pregões somada ao mínimo teórico do download. Cobre feriados, dias sem negócio e a
# diferença entre dias de calendário e pregões, que varia de papel para papel.
FOLGA_PREGOES = 40

# Quantos pregões por ano, para converter "preciso de N pregões" no período que o provedor aceita.
PREGOES_POR_ANO = 248

# Onde estão os setups aprovados, exportados pelo laboratório. O arquivo traz, por linha, um setup
# (papel, horizonte, janela) e o CORTE do decil daquele par (papel, janela), medido lá sobre a
# história completa. A aplicação não recalcula o corte: com a história curta que ela baixa, o corte
# da GGBR4 com janela 200 ia de −2,010 para +0,465 — trocava de sinal. Ver `estudo/PROVENIENCIA.md`.
ARQUIVO_SETUPS = "estudo/setups.csv"

# ============================================================================
# Comum às duas versões
# ============================================================================

# ⚠️ Os nomes com prefixo `EXTREMOS_` acima e os sem prefixo aqui carregam O MESMO VALOR: a duas
# grafias existem porque a v1 herdou os nomes do laboratório e a v2 nasceu com nomes curtos.
# Unificá-las exigiria tocar em `gerar_tela.py`, que está em produção e funciona. Registrado em
# 07/09/2026 como dívida deliberada, não como descuido.
VOL_LAG = EXTREMOS_VOL_LAG        # 252 — janela do desvio-padrão móvel
N_FAIXAS = EXTREMOS_N_FAIXAS      # 10  — decis

# Onde as páginas são gravadas.
DIR_SAIDA = "saida"

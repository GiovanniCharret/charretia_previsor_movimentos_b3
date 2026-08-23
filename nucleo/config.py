"""
Os dez parâmetros que a tela lê — e só eles.

Por que este arquivo existe e não é cópia do `config.py` do laboratório: o de lá tem 225 linhas, a
maioria descrevendo experimentos que a tela não roda (rede neural, varreduras de janela, binning
supervisionado). Trazer tudo para cá faria alguém em manutenção procurar aqui o botão errado.
Estes são os valores efetivamente usados por `gerar_tela.py`.

**Não edite aqui.** A fonte é `src/robusta_ml/config.py`, no repositório irmão `robusta_backtest`.
Mude lá e recopie o valor para cá — e atualize o commit de origem registrado no README.
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
# Parâmetros do estudo aplicado na tela
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

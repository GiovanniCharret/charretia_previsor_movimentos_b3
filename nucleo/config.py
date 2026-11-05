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
# Download do dia (`gerar_extremos.py`)
# ============================================================================
#
# A v2 (gatilhos de proteção) usava este bloco e foi descontinuada em 04/11/2026; as constantes que
# só ela lia (`FAIXA_ALVO`, `ARQUIVO_SETUPS`) saíram junto. As duas abaixo ficaram, porque a faixa
# extrema também baixa só o necessário para o escore de hoje.

# Folga de pregões somada ao mínimo teórico do download. Cobre feriados, dias sem negócio e a
# diferença entre dias de calendário e pregões, que varia de papel para papel.
FOLGA_PREGOES = 40

# Quantos pregões por ano, para converter "preciso de N pregões" no período que o provedor aceita.
PREGOES_POR_ANO = 248

# ============================================================================
# v3 — FAIXA EXTREMA (`gerar_extremos.py`)
# ============================================================================
#
# Vem do achado W (12/10/2026): a proteção por episódio da v2 é em grande parte efeito mecânico da
# contagem; o que sobrou é um indício medido POR DIA, nos percentis de 2,5% e 5%. As janelas, os
# percentis e os horizontes não são escolhidos aqui — vêm dentro dos dois arquivos abaixo, exportados
# pelo laboratório por `robusta_ml.faixa_extrema`. Ver `estudo/PROVENIENCIA_FAIXA_EXTREMA.md`.

# O limiar de cada (papel, janela, percentil), medido sobre a história completa.
ARQUIVO_FAIXA_CORTES = "estudo/faixa_extrema_cortes.csv"

# Por (papel, percentil, horizonte): frequência por dia, limite inferior, taxa-base e período medido.
ARQUIVO_FAIXA_MEDIDAS = "estudo/faixa_extrema_medidas.csv"

# A mesma medida janela a janela. É dela que sai a frequência da linha: a média das janelas em que o
# papel está no extremo hoje (pedido do usuário em 19/10/2026).
ARQUIVO_FAIXA_POR_JANELA = "estudo/faixa_extrema_por_janela.csv"

# ============================================================================
# v4 — BANCOS E ELÉTRICAS (`gerar_setores.py`) — hipótese em observação
# ============================================================================
#
# Vem do teste por setor do laboratório (04/11/2026): no decil 0, em 45 pregões, elétricas e bancos
# tiveram os menores valores-p entre 66 testes, sem sobreviver à correção. A lista de papéis, o
# corte e o horizonte vêm travados nos arquivos abaixo, exportados por `robusta_ml.setores_v4`.
# Ver `estudo/PROVENIENCIA_SETORES.md`.

# O limiar de cada (papel, janela) no decil 0, medido sobre a história completa, com o setor.
ARQUIVO_SETORES_CORTES = "estudo/setores_cortes.csv"

# A frequência por dia e a taxa-base de cada (papel, janela), em 45 pregões.
ARQUIVO_SETORES_POR_JANELA = "estudo/setores_por_janela.csv"

# O corte da hipótese: os 10% de dias mais afastados para baixo (o decil 0 da antiga v2).
SETORES_PERCENTIL = 0.10

# Como cada setor aparece na página, na ordem das seções. A chave é o nome da classificação.
SETORES_ROTULOS = {"Energia Elétrica": "Elétricas", "Intermediários Financeiros": "Bancos"}

# A nota ao lado do título de cada seção: o resultado que pôs o setor em observação.
SETORES_NOTAS = {
    "Energia Elétrica": "dez papéis · no teste, +8,5 pontos sobre a taxa-base (valor-p bruto 0,007)",
    "Intermediários Financeiros": "oito papéis · no teste, +9,7 pontos sobre a taxa-base (valor-p bruto 0,016)",
}

# ============================================================================
# Comum às duas versões
# ============================================================================

# ⚠️ Os nomes com prefixo `EXTREMOS_` acima e os sem prefixo aqui carregam O MESMO VALOR: a duas
# grafias existem porque a v1 herdou os nomes do laboratório e a v2 nasceu com nomes curtos.
# Unificá-las exigiria tocar em `gerar_tela.py`, que está em produção e funciona. Registrado em
# 07/09/2026 como dívida deliberada, não como descuido.
VOL_LAG = EXTREMOS_VOL_LAG        # 252 — janela do desvio-padrão móvel
N_FAIXAS = EXTREMOS_N_FAIXAS      # 10  — decis

# As divisões da validação encadeada do laboratório (`SETUP_DIVISOES` em `robusta_ml/config.py`).
# As telas não medem nada com elas — os números vêm prontos de `estudo/`. Elas estão aqui para as
# PLANILHAS DE ESTUDO (`planilha_estudo.py`) poderem mostrar, linha a linha, qual trecho foi treino
# e qual foi teste em cada divisão.
SETUP_DIVISOES = [("2006-01-01", "2010-01-01"), ("2010-01-01", "2014-01-01"),
                  ("2014-01-01", "2018-01-01"), ("2018-01-01", "2022-01-01"),
                  ("2022-01-01", "2027-01-01")]

# Onde as páginas são gravadas.
DIR_SAIDA = "saida"

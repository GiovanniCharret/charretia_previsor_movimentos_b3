import pandas as pd


def add_forward_returns(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """
    Adiciona colunas de retorno contínuo para cada horizonte de previsão.

    **Por que existe:** O modelo preditivo requer variáveis-alvo (y) que representem
    o desempenho futuro em múltiplos horizontes (ex: 20d, 45d, 90d). Esta função
    enriquece o DataFrame com essas variáveis contínuas (retorno em %, não discretizadas
    em labels 0/1), permitindo regressão OLS e análise de potencial preditivo.

    **Fases:**
    1. Entrada: DataFrame com coluna "Close" (preços de fechamento)
    2. Para cada horizonte h em horizons:
       - Calcula ret_xd = Close[t+h] / Close[t] - 1 (retorno contínuo)
       - Usa shift(-h) para alinhar o preço futuro com a data atual
    3. NaN é garantido nas últimas h linhas (sem futuro conhecido)
    4. Concatena todas as colunas de uma vez — acrescentá-las uma a uma fragmenta a estrutura
       interna do pandas e, num DataFrame que já traz centenas de colunas de feature, dispara
       `PerformanceWarning` (corrigido em 07/09/2026)
    5. Saída: DataFrame enriquecido com coluna ret_{h}d para cada h

    Args:
        df: DataFrame com coluna "Close" (preços de fechamento)
        horizons: Lista de horizontes em dias (ex: [20, 45, 90])

    Returns:
        DataFrame novo com as mesmas colunas + colunas ret_{h}d para cada horizonte
    """
    # Acumulador das colunas novas, na ordem dos horizontes pedidos
    novas = {}
    # Iterar cada horizonte solicitado
    for h in horizons:
        # Calcular retorno contínuo: Close[t+h] / Close[t] - 1
        # shift(-h) desloca o preço h dias para trás (futuro aparece como presente)
        novas[f"ret_{h}d"] = df["Close"].shift(-h) / df["Close"] - 1.0
    # Uma concatenação só, alinhada pelo índice (o mesmo, por construção)
    if novas:
        df = pd.concat([df, pd.DataFrame(novas, index=df.index)], axis=1)
    # Retornar DataFrame enriquecido (os últimos h valores de ret_{h}d são NaN automaticamente)
    return df

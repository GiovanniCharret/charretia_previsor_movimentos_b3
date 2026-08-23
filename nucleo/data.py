import pandas as pd
import yfinance as yf

# Colunas esperadas no DataFrame normalizado (OHLCV = Open, High, Low, Close, Volume)
_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza um DataFrame de preços para formato OHLCV canônico.

    **Por que existe:** O pipeline de backteste requer dados em formato padrão e ordenado.
    Esta função garante que qualquer entrada (com colunas extras, índice desordenado, etc)
    seja padronizada em 5 colunas (Open, High, Low, Close, Volume) e ordenada cronologicamente.

    **Fases:**
    1. Entrada: DataFrame com colunas OHLCV (possivelmente com extras) e índice potencialmente desordenado
    2. Ordena o DataFrame por índice (data) em ordem ascendente
    3. Seleciona apenas as 5 colunas OHLCV na ordem canônica
    4. Retorna uma cópia para evitar efeitos colaterais
    5. Saída: DataFrame ordenado e filtrado com apenas [Open, High, Low, Close, Volume]

    Args:
        df: DataFrame contendo pelo menos as colunas Open, High, Low, Close, Volume

    Returns:
        DataFrame com exatamente as colunas OHLCV, ordenado por índice ascendente
    """
    # Fase 1: Ordena por índice (data) em ordem ascendente
    out = df.sort_index()
    # Fase 2-3: Seleciona apenas as colunas OHLCV e cria uma cópia
    return out[_OHLCV].copy()


def load_prices(ticker: str, period: str) -> pd.DataFrame:
    """
    Baixa dados de preços via yfinance e normaliza ao formato OHLCV.

    **Por que existe:** Este é o único ponto de rede do pipeline. Centraliza todas as
    operações de download yfinance e garante que dados brutos sejam normalizados antes
    de entrar no pipeline de análise.

    **Fases:**
    1. Entrada: ticker (ex: "^BVSP") e period (ex: "10y")
    2. Baixa via yfinance com auto_adjust=True e progress=False
    3. Se o resultado tiver MultiIndex nas colunas, achata para o nível 0
    4. Passa o DataFrame normalizado para normalize_ohlcv
    5. Saída: DataFrame OHLCV normalizado pronto para o pipeline

    Args:
        ticker: Símbolo do ativo (ex: "^BVSP", "PETR4.SA")
        period: Período histórico (ex: "10y", "5y", "1y")

    Returns:
        DataFrame OHLCV normalizado com dados baixados de yfinance
    """
    # Fase 1-2: Baixa OHLCV via yfinance com ajuste automático de preços (splits/dividendos) habilitado e sem barra de progresso
    raw = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    # Fase 3: Se houver MultiIndex nas colunas (ex: ticker como nível 1), achata para nível 0
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    # Fase 4: Normaliza usando a função pura
    return normalize_ohlcv(raw)

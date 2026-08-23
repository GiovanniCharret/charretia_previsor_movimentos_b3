import pandas as pd


def _add_trigger_columns(df: pd.DataFrame, window: int, tol: float, persists: list[int]) -> pd.DataFrame:
    """
    Adiciona colunas de gatilho MMA (Média Móvel Simples) a um DataFrame.

    Por que existe: Transporta lógica de gatilho segura contra vazamento (state/signal/persist) do indicador
    legado para o pipeline de ML. Gatilhos devem respeitar um limiar de tolerância e não podem emitir
    inícios de sessão fantasmas no aquecimento (signal deve ver uma referência válida em t−1).

    Fases:
    1. Calcula o valor da SMA (mma_w{window}) como a média móvel de Close.
    2. Determina state: booleano above = Close > mma * (1 + tol), convertido para Int8.
    3. Detecta signal genuíno: cruzamento acima requer above AND NOT above[t-1] AND referência válida em t-1.
    4. Calcula streak: conta dias consecutivos em state a partir de cada mudança de regime.
    5. Para cada k em persists: dispara no k-ésimo dia após o início (one-shot), usando streak e signal deslocado.
    """
    # Fase 1: Calcula o valor da coluna SMA.
    vcol = f"mma_w{window}"
    df[vcol] = df["Close"].rolling(window).mean()

    # Fase 2: Determina state (acima do limiar de tolerância).
    above = df["Close"] > df[vcol] * (1 + tol)
    df[f"mma_state_w{window}_t{tol}"] = above.astype("Int8")

    # Fase 3: Detecta signal genuíno (cruzamento acima com referência válida em t-1, sem fantasma no aquecimento).
    cross = above & ~above.shift(1, fill_value=False) & df[vcol].notna().shift(1, fill_value=False)
    df[f"mma_signal_w{window}_t{tol}"] = cross.astype("Int8")

    # Fase 4: Calcula streak (conta dias consecutivos em state).
    streak = above.groupby((above != above.shift()).cumsum()).cumcount() + 1

    # Fase 5: Dispara persist no k-ésimo dia após o início (one-shot).
    for k in persists:
        # Ignora valores k não-positivos.
        if k <= 0:
            continue
        # Dispara quando: ainda em state, streak é k+1 (k dias após o início), e o início aconteceu k dias atrás.
        fires = above & (streak == k + 1) & cross.shift(k, fill_value=False)
        df[f"mma_persist_w{window}_t{tol}_k{k}"] = fires.astype("Int8")

    # Saída: df-fundação enriquecido com as colunas de gatilho.
    return df


def _add_continuous_columns(df: pd.DataFrame, window: int, slope_lag: int) -> pd.DataFrame:
    """
    Adiciona features contínuas de MMA (distância e inclinação) a um DataFrame.

    Por que existe: Features contínuas complementam os gatilhos ao capturar o momentum dos preços
    relativo à MMA (distância ao limiar) e a aceleração da MMA (inclinação). Elas formam o espaço
    de entrada da regressão.

    Fases:
    1. Calcula ou reutiliza a coluna de valor SMA (mma_w{window}).
    2. Calcula distância como Close/mma - 1 (quão longe do limiar, proporcional).
    3. Calcula inclinação como mma/mma.shift(slope_lag) - 1 (taxa de mudança da MMA).
    4. Retorna o DataFrame enriquecido.
    """
    # Fase 1: Calcula ou reutiliza a coluna de valor SMA.
    vcol = f"mma_w{window}"
    if vcol not in df:
        df[vcol] = df["Close"].rolling(window).mean()
    # Fase 2: Calcula distância (Close / mma - 1).
    df[f"mma_dist_w{window}"] = df["Close"] / df[vcol] - 1.0
    # Fase 3: Calcula inclinação (mma / mma.shift(slope_lag) - 1).
    df[f"mma_slope_w{window}"] = df[vcol] / df[vcol].shift(slope_lag) - 1.0
    # Fase 4: Retorna o DataFrame enriquecido.
    return df


def build_features(df: pd.DataFrame, windows: list[int], tols: list[float], persists: list[int], slope_lag: int = 5) -> tuple[pd.DataFrame, list[str]]:
    """
    Orchestrate feature construction: continuous columns + trigger columns over all window×tol×persist combos.

    Why: This function assembles the complete ML feature set from MMA by coordinating two helpers
    (_add_continuous_columns, _add_trigger_columns) and collecting the resulting feature names,
    excluding value columns (mma_w{w}) and OHLCV (Close).

    Phases:
    1. Inicializar lista vazia de feature names.
    2. Para cada janela (window): chamar _add_continuous_columns e anotar dist/slope.
    3. Para cada tolerância (tol): chamar _add_trigger_columns e anotar state/signal/persist(k>0).
    4. Retornar (df enriquecido, feature_cols com todos os nomes exceto value e Close).

    Saída: (df enriquecido, lista de colunas de feature).
    """
    # Fase 1: Inicializar lista de feature names.
    feats = []
    # Fase 2: Para cada janela, adicionar contínuas (dist, slope).
    for w in windows:
        # Chamar helper para adicionar colunas contínuas.
        _add_continuous_columns(df, window=w, slope_lag=slope_lag)
        # Anotar os nomes das features contínuas.
        feats += [f"mma_dist_w{w}", f"mma_slope_w{w}"]
        # Fase 3: Para cada tolerância, adicionar gatilhos (state, signal, persist).
        for tol in tols:
            # Chamar helper para adicionar colunas de gatilho.
            _add_trigger_columns(df, window=w, tol=tol, persists=persists)
            # Anotar state e signal.
            feats.append(f"mma_state_w{w}_t{tol}")
            feats.append(f"mma_signal_w{w}_t{tol}")
            # Anotar persist apenas para k > 0.
            for k in persists:
                # Só incluir k > 0 (conforme brief: "exclui valor e OHLCV").
                if k > 0:
                    feats.append(f"mma_persist_w{w}_t{tol}_k{k}")
    # Saída: (df enriquecido, lista de feature names).
    return df, feats

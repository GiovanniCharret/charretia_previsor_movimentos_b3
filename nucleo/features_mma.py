"""
Construção das features derivadas da média móvel aritmética (mma).

⚠️ **Todas as funções deste módulo DEVOLVEM colunas; nenhuma escreve no DataFrame recebido.**

Por que assim, e não com `df[coluna] = valor` como antes: cada atribuição dessas insere um bloco
novo na estrutura interna do pandas. Com 145 janelas por papel e quatro colunas por janela, eram
quase seiscentas inserções, e o pandas passava a emitir `PerformanceWarning: DataFrame is highly
fragmented` — o aviso não era cosmético: a varredura dos 61 papéis pagava por ele em tempo. Aqui as
colunas são acumuladas num dicionário e **uma única concatenação** monta o DataFrame final.

O efeito colateral bom da mudança: a média móvel de cada janela passou a ser calculada **uma vez**.
Antes, `_add_continuous_columns` e `_add_trigger_columns` calculavam a mesma `rolling(w).mean()`
cada um por sua conta — 145 janelas viravam 290 médias móveis por papel.
"""

import pandas as pd


def _add_trigger_columns(df: pd.DataFrame, window: int, tol: float, persists: list[int],
                         mma: pd.Series | None = None) -> dict[str, pd.Series]:
    """
    Monta as colunas de gatilho da mma (estado, sinal e persistência) para uma janela e tolerância.

    Por que existe: transporta a lógica de gatilho do indicador legado para o pipeline, com a trava
    anti-vazamento que o legado não tinha. Um gatilho precisa respeitar a banda de tolerância e
    **não pode emitir início de regime fantasma durante o aquecimento** — o `signal` exige uma
    referência válida em t−1, senão o primeiro dia com média disponível apareceria como cruzamento.

    Entrada: df (com a coluna `Close`), window, tol, persists, mma (a média móvel já calculada;
    quando ausente, é calculada aqui — o parâmetro existe para `build_features` não recalcular).
    Fase 1: a média móvel da janela, reaproveitada quando já vem pronta.
    Fase 2: estado — o fechamento acima da média corrigida pela tolerância.
    Fase 3: sinal — cruzamento genuíno: está acima, não estava em t−1, e havia referência em t−1.
    Fase 4: sequência de dias consecutivos no mesmo estado, para a persistência saber a idade dele.
    Fase 5: persistência — dispara **uma vez**, no k-ésimo dia após um início genuíno.
    Saída: dicionário {nome da coluna: série}, na ordem em que devem entrar no DataFrame.
    """
    # Fase 1: a média móvel. Vem pronta de `build_features`; calculada aqui só em uso avulso.
    if mma is None:
        mma = df["Close"].rolling(window).mean()

    # Fase 2: estado — acima da média, respeitada a banda de tolerância.
    above = df["Close"] > mma * (1 + tol)

    # Fase 3: sinal genuíno. As três condições juntas é que evitam o fantasma de aquecimento: a
    # terceira exige que a média já existisse em t−1, senão o primeiro dia válido viraria início.
    cross = above & ~above.shift(1, fill_value=False) & mma.notna().shift(1, fill_value=False)

    # Fase 4: quantos dias consecutivos no estado atual. O agrupamento por mudança de regime
    # reinicia a contagem a cada virada.
    streak = above.groupby((above != above.shift()).cumsum()).cumcount() + 1

    # As colunas desta combinação, na ordem de leitura.
    colunas = {
        f"mma_state_w{window}_t{tol}": above.astype("Int8"),
        f"mma_signal_w{window}_t{tol}": cross.astype("Int8"),
    }

    # Fase 5: uma coluna de persistência por k pedido.
    for k in persists:
        # k não-positivo não descreve persistência nenhuma.
        if k <= 0:
            continue
        # Dispara quando: ainda no estado, a sequência tem k+1 dias, e o início foi há exatamente k
        # dias. As três juntas tornam o disparo único por episódio, e não repetido enquanto durar.
        fires = above & (streak == k + 1) & cross.shift(k, fill_value=False)
        colunas[f"mma_persist_w{window}_t{tol}_k{k}"] = fires.astype("Int8")

    # Saída: as colunas, sem tocar no DataFrame recebido.
    return colunas


def _add_continuous_columns(df: pd.DataFrame, window: int, slope_lag: int,
                            mma: pd.Series | None = None) -> dict[str, pd.Series]:
    """
    Monta as colunas contínuas da mma (distância e inclinação) para uma janela.

    Por que existe: as contínuas complementam os gatilhos. O gatilho diz "está acima"; a distância
    diz **quanto** acima, e a inclinação diz se a própria média está subindo. Juntas formam o espaço
    de entrada da regressão — e a distância é a que sustenta toda a linha da proteção.

    As duas são razões, e não diferenças em reais, de propósito: assim são comparáveis entre papéis
    de preços muito diferentes, o que é o que permite empilhar papéis num painel único.

    Entrada: df (com `Close`), window, slope_lag, mma (média já calculada; ausente, calcula aqui).
    Fase 1: a média móvel da janela, reaproveitada quando já vem pronta.
    Fase 2: distância — fechamento sobre média, menos um.
    Fase 3: inclinação — média sobre ela mesma `slope_lag` pregões atrás, menos um.
    Saída: dicionário {nome da coluna: série}, incluindo a própria média (que é valor, não feature).
    """
    # Fase 1: a média móvel.
    if mma is None:
        mma = df["Close"].rolling(window).mean()
    # Fase 2 e 3: as duas razões. A média entra no dicionário porque o DataFrame a exibe para
    # conferência linha a linha, mas `build_features` a mantém FORA da lista de features.
    return {
        f"mma_w{window}": mma,
        f"mma_dist_w{window}": df["Close"] / mma - 1.0,
        f"mma_slope_w{window}": mma / mma.shift(slope_lag) - 1.0,
    }


def build_features(df: pd.DataFrame, windows: list[int], tols: list[float], persists: list[int],
                   slope_lag: int = 5) -> tuple[pd.DataFrame, list[str]]:
    """
    Monta o conjunto completo de features da mma e devolve o DataFrame enriquecido.

    Por que existe: coordena os dois auxiliares sobre todas as combinações de janela, tolerância e
    persistência, e devolve os nomes das features — excluindo as colunas de valor (`mma_w{w}`) e o
    OHLCV, que estão no DataFrame para inspeção mas não entram no modelo.

    Por que uma concatenação só, no fim: acrescentar coluna a coluna fragmenta a estrutura interna
    do pandas e faz o custo crescer com o quadrado do número de colunas. Com 145 janelas o aviso
    `DataFrame is highly fragmented` aparecia a cada papel da varredura.

    Entrada: df (OHLCV com `Close`), windows, tols, persists, slope_lag.
    Fase 1: para cada janela, calcular a média móvel **uma vez** e derivar dela as contínuas.
    Fase 2: para cada tolerância daquela janela, derivar os gatilhos da mesma média.
    Fase 3: concatenar tudo de uma vez ao DataFrame recebido.
    Saída: (DataFrame enriquecido, lista de nomes das features).
    """
    # Acumuladores: as colunas novas, na ordem de criação, e os nomes que são feature.
    novas: dict[str, pd.Series] = {}
    feats: list[str] = []

    # Fase 1: cada janela, com a média móvel calculada uma única vez.
    for w in windows:
        mma = df["Close"].rolling(w).mean()
        novas.update(_add_continuous_columns(df, window=w, slope_lag=slope_lag, mma=mma))
        # A média em si é valor, não feature — só a distância e a inclinação entram.
        feats += [f"mma_dist_w{w}", f"mma_slope_w{w}"]

        # Fase 2: cada tolerância, sobre a mesma média.
        for tol in tols:
            gatilhos = _add_trigger_columns(df, window=w, tol=tol, persists=persists, mma=mma)
            novas.update(gatilhos)
            # Os nomes saem do próprio dicionário: assim a lista de features não pode divergir das
            # colunas efetivamente criadas, que era um par de listas para manter em sincronia.
            feats += list(gatilhos)

    # Fase 3: uma concatenação só. `axis=1` alinha pelo índice, que é o mesmo por construção.
    if novas:
        df = pd.concat([df, pd.DataFrame(novas, index=df.index)], axis=1)

    # Saída: DataFrame enriquecido e os nomes das features.
    return df, feats

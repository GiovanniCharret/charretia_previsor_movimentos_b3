"""
Planilha de estudo das telas de gatilhos (v2) e da faixa extrema (v3).

Por que este módulo existe: o usuário é estudante e pediu, para a v2 e a v3, o mesmo que a triagem
já oferece — um arquivo do Excel por papel exibido, com a série linha a linha, para **ver** como o
treino e o teste foram arranjados e como cada coluna nasce da anterior. As duas telas leem números
prontos do laboratório; a planilha existe para esses números poderem ser conferidos por fora.

O que a planilha mostra é a **validação encadeada**, que é diferente da divisão única da triagem:

- a história é cortada em divisões de quatro anos; cada divisão é TESTADA com um corte calculado só
  com as linhas anteriores a ela (o treino dela), deixando um embargo do tamanho do horizonte entre
  os dois, porque o retorno futuro do fim do treino invadiria o começo do teste;
- por isso uma mesma linha é teste da sua divisão e treino das divisões seguintes. A coluna
  `conjunto` diz o papel da linha na divisão DELA, e `treino_ate` diz até que data ia o treino que
  produziu o `corte_usado` daquela linha.

⚠️ O cálculo daqui repete, para um papel e uma janela, o que o laboratório faz em
`robusta_ml.sweep_decis` e `robusta_ml.faixa_extrema`. É uma reimplementação para estudo: os números
da tela continuam vindo de `estudo/`. Se o laboratório mudar a regra de divisão, esta cópia não
acompanha sozinha.
"""

import numpy as np                                          # quantis e posições
import pandas as pd                                         # tabelas

from nucleo import config                                   # divisões e parâmetros
from nucleo.data import load_prices                         # download (único ponto de rede)
from nucleo.qualidade_dados import apara_inicio             # corta a cabeça anterior à listagem
from nucleo.features_mma import build_features              # média móvel e distância
from nucleo.faixas import add_dist_zscore                   # distância ÷ desvio-padrão móvel
from nucleo.qualidade_dados import avalia_qualidade_por_divisao      # peneira por época

# A legenda das colunas, gravada na aba `dicionário` de todo arquivo (convenção do projeto).
DICIONARIO = [
    ("Close", "Preço de fechamento ajustado."),
    ("mma_w{janela}", "Média móvel aritmética do fechamento, na janela indicada."),
    ("mma_dist_w{janela}", "Distância do fechamento até a média: Close ÷ média − 1."),
    ("mma_dist_z_w{janela}", "A distância dividida pelo desvio-padrão dela nos últimos 252 pregões. "
                             "É o escore que decide se o dia está 'longe demais' da média."),
    ("ret_{horizonte}d", "Retorno dos pregões seguintes: Close daqui a N pregões ÷ Close de hoje − 1. "
                         "Vazio nas últimas N linhas, porque o futuro ainda não existe."),
    ("divisao", "A divisão da validação encadeada em que a linha é TESTADA (início–fim). Vazio "
                "quando a linha não é teste de divisão nenhuma."),
    ("conjunto", "O papel da linha: 'teste' (medida com corte calculado só no passado dela); 'só "
                 "treino' (anterior à primeira divisão medida, ou de uma época reprovada na peneira "
                 "de qualidade — serve para calcular cortes, não é medida); 'aquecimento' (a média "
                 "ou o desvio ainda não existem); 'sem_retorno' (o retorno futuro ainda não existe "
                 "— é onde está o pregão de hoje)."),
    ("treino_ate", "A última data do treino que produziu o corte desta linha. Entre ela e o começo "
                   "do teste fica o embargo, do tamanho do horizonte."),
    ("corte_usado", "O limiar do escore naquela divisão: o percentil indicado, calculado SÓ com as "
                    "linhas do treino dela."),
    ("na_faixa", "Verdadeiro quando o escore do dia está no corte ou abaixo dele."),
    ("episodio", "Número do episódio: dias na faixa separados por no máximo N pregões contam como "
                 "um episódio só, porque seus retornos futuros se sobrepõem."),
    ("retorno_positivo", "Verdadeiro quando o retorno dos pregões seguintes foi maior que zero."),
    ("— aba `divisões` —", ""),
    ("treino_de / treino_ate / linhas_de_treino", "O trecho que calculou o corte daquela divisão."),
    ("dias_de_teste / dias_na_faixa / episodios", "Tamanho do teste, quantos dias ficaram na faixa "
                                                  "e em quantos episódios."),
    ("freq_positiva_na_faixa", "De cada 100 DIAS na faixa, em quantos o retorno seguinte foi "
                               "positivo. É a medida da faixa extrema (v3)."),
    ("episodios_positivos", "Quantos episódios tiveram média de retorno seguinte positiva. É a "
                            "base da 'proteção' da tela de gatilhos (v2) — medida que, sabe-se "
                            "desde 12/10/2026, é inflada pela própria contagem."),
    ("taxa_base", "De cada 100 dias QUAISQUER do teste, em quantos o retorno seguinte foi positivo."),
]


def divisoes_aprovadas(prices):
    """
    As divisões da validação encadeada que passam na peneira de qualidade, para este papel.

    Por que existe: o laboratório descarta, papel a papel, as épocas de liquidez baixa ou preço
    parado. A planilha precisa usar as mesmas divisões, senão mostraria testes que não entraram em
    número nenhum da tela.

    Entrada: prices (OHLCV já aparado).
    Saída: lista de pares (inicio, fim) das divisões aprovadas, em ordem.
    """
    qual = avalia_qualidade_por_divisao(prices, config.SETUP_DIVISOES)
    return [(r["inicio"], r["fim"]) for r in qual if r["aprovado"]]


def monta_estudo(prices, janela, horizonte, percentil, divisoes, min_treino=300):
    """
    Monta a série linha a linha de UMA janela, com o arranjo de treino e teste de cada divisão.

    Por que existe: é o coração da planilha, e é pura — recebe preços e devolve tabelas — para os
    testes conferirem o arranjo sem rede e sem disco.

    Entrada: prices (OHLCV já aparado), janela, horizonte, percentil (fração, como 0.10),
    divisoes (pares de datas), min_treino (linhas mínimas de treino para uma divisão valer).
    Fase 1: as colunas de sempre — média, distância, escore e retorno futuro.
    Fase 2: classificar as linhas que nunca são teste (aquecimento, sem retorno, só treino).
    Fase 3: por divisão, calcular o corte SÓ no treino e marcar as linhas de teste.
    Fase 4: numerar os episódios e resumir cada divisão.
    Saída: tupla (DataFrame linha a linha, DataFrame com uma linha por divisão).
    """
    col_z, col_ret = f"mma_dist_z_w{janela}", f"ret_{horizonte}d"
    # Fase 1: as mesmas funções que as telas usam, para a planilha não divergir delas.
    df, _feats = build_features(prices[["Close"]].copy(), [janela], [0.0], [1], config.SLOPE_LAG)
    df = add_dist_zscore(df, [janela], config.VOL_LAG)
    df = df[["Close", f"mma_w{janela}", f"mma_dist_w{janela}", col_z]].copy()
    df[col_ret] = df["Close"].shift(-horizonte) / df["Close"] - 1.0

    # Fase 2: o que cada linha é quando não é teste de ninguém.
    df["divisao"], df["conjunto"] = "", "só treino"
    df.loc[df[col_ret].isna(), "conjunto"] = "sem_retorno"
    df.loc[df[col_z].isna(), "conjunto"] = "aquecimento"
    df["treino_ate"], df["corte_usado"], df["na_faixa"] = "", np.nan, False

    # As linhas utilizáveis: têm escore e têm retorno futuro. É sobre elas que treino e teste são
    # contados, exatamente como no laboratório.
    validas = np.flatnonzero((df[col_z].notna() & df[col_ret].notna()).to_numpy())
    datas = df.index[validas]
    z, y = df[col_z].to_numpy(), df[col_ret].to_numpy()
    resumo, acionadas = [], []
    # Fase 3: cada divisão com o corte do PRÓPRIO treino.
    for inicio, fim in divisoes:
        # Quantas linhas utilizáveis ficam antes de cada borda do teste.
        p_ini = int((datas < pd.Timestamp(inicio)).sum())
        p_fim = int((datas < pd.Timestamp(fim)).sum())
        # O embargo: as últimas `horizonte` linhas antes do teste saem do treino.
        tr, te = validas[:max(0, p_ini - horizonte)], validas[p_ini:p_fim]
        # Divisão sem treino bastante ou sem teste não é medida.
        if len(tr) < min_treino or len(te) == 0:
            continue
        corte = float(np.quantile(z[tr], percentil))
        rotulo = f"{inicio[:4]}–{fim[:4]}"
        idx = df.index[te]
        df.loc[idx, "divisao"], df.loc[idx, "conjunto"] = rotulo, "teste"
        df.loc[idx, "treino_ate"] = str(df.index[tr[-1]].date())
        df.loc[idx, "corte_usado"] = corte
        df.loc[idx, "na_faixa"] = z[te] <= corte
        na = te[z[te] <= corte]
        acionadas.append(na)
        resumo.append({"divisao": rotulo, "treino_de": str(df.index[tr[0]].date()),
                       "treino_ate": str(df.index[tr[-1]].date()), "linhas_de_treino": len(tr),
                       "corte_usado": corte, "dias_de_teste": len(te), "dias_na_faixa": len(na),
                       "taxa_base": float((y[te] > 0).mean()), "_na": na})

    # Fase 4: os episódios são numerados sobre TODAS as divisões juntas — dois dias na faixa em
    # lados opostos de uma fronteira ainda têm retornos futuros sobrepostos.
    df["episodio"] = pd.array([pd.NA] * len(df), dtype="Int64")
    df["retorno_positivo"] = (df[col_ret] > 0).where(df[col_ret].notna())
    todas = np.sort(np.concatenate(acionadas)) if acionadas else np.array([], dtype=int)
    if len(todas):
        # A posição de cada linha entre as utilizáveis: é nessa régua que o salto é medido.
        ordem = np.searchsorted(validas, todas)
        numero = np.r_[0, np.cumsum(np.diff(ordem) > horizonte)] + 1
        df.loc[df.index[todas], "episodio"] = numero
    for r in resumo:
        na = r.pop("_na")
        ep = df.loc[df.index[na], "episodio"].to_numpy(dtype=float)
        r["episodios"] = int(len(np.unique(ep)))
        r["freq_positiva_na_faixa"] = float((y[na] > 0).mean()) if len(na) else np.nan
        # Episódio positivo = média do retorno seguinte dos dias dele maior que zero (a conta da v2).
        medias = pd.Series(y[na]).groupby(ep).mean() if len(na) else pd.Series(dtype=float)
        r["episodios_positivos"] = int((medias > 0).sum())
    # Saída: a série e o resumo por divisão.
    return df, pd.DataFrame(resumo)


def grava_planilha(caminho, estudos):
    """
    Grava o arquivo do Excel de um papel: uma aba de série por janela, o resumo e a legenda.

    Por que existe: as duas telas gravam o mesmo formato, e a legenda precisa ir junto em todo
    arquivo — uma planilha de estudo sem a explicação das colunas não ensina nada.

    Entrada: caminho (arquivo de saída), estudos (lista de tuplas: rótulo da janela, DataFrame da
    série, DataFrame do resumo por divisão).
    Fase 1: uma aba por janela, com o índice de datas.
    Fase 2: uma aba só com os resumos de todas as janelas, lado a lado na leitura.
    Fase 3: a legenda.
    Saída: o caminho gravado.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(caminho) as escritor:
        resumos = []
        # Fase 1: as séries.
        for rotulo, serie, resumo in estudos:
            serie.to_excel(escritor, sheet_name=f"janela {rotulo}", index_label="data")
            resumos.append(resumo.assign(janela=rotulo))
        # Fase 2: os resumos, com a janela na primeira coluna.
        juntos = pd.concat(resumos, ignore_index=True) if resumos else pd.DataFrame()
        if len(juntos):
            juntos = juntos[["janela"] + [c for c in juntos.columns if c != "janela"]]
        juntos.to_excel(escritor, sheet_name="divisões", index=False)
        # Fase 3: a legenda de todas as colunas.
        pd.DataFrame(DICIONARIO, columns=["coluna", "descrição"]).to_excel(
            escritor, sheet_name="dicionário", index=False)
    return caminho


def grava_estudo_do_papel(pasta, arquivo, ticker, janelas, horizonte, percentil):
    """
    Baixa a história completa de um papel e grava a planilha de estudo dele.

    Por que existe: as telas baixam só o necessário para o escore do dia; a planilha precisa da
    história inteira, porque é nela que estão o treino e o teste. Isso só é feito para os poucos
    papéis exibidos, e uma falha aqui não pode derrubar a página — o papel fica sem o link.

    Entrada: pasta (onde gravar), arquivo (nome do arquivo), ticker, janelas (uma aba por janela),
    horizonte, percentil.
    Fase 1: baixar tudo e aparar.
    Fase 2: as divisões que passam na peneira de qualidade.
    Fase 3: um estudo por janela, e o arquivo.
    Saída: True quando o arquivo foi gravado; False quando não foi possível.
    """
    try:
        # Fase 1: a história completa.
        prices = apara_inicio(load_prices(f"{ticker}{config.TICKER_SUFFIX}", config.EXTREMOS_PERIOD))
        # Fase 2: as mesmas divisões que o laboratório mediu.
        divisoes = divisoes_aprovadas(prices)
        # Fase 3: uma aba por janela.
        estudos = [(str(w),) + monta_estudo(prices, int(w), int(horizonte), percentil, divisoes)
                   for w in janelas]
        grava_planilha(pasta / arquivo, estudos)
        return True
    except Exception as erro:
        print(f"  planilha de {ticker} não gerada: {erro}", flush=True)
        return False


def link_planilha(arquivo, ticker):
    """
    O link de download de uma planilha de estudo, igual ao da tela de triagem.

    Por que existe: o nome do arquivo é usado em dois lugares — na gravação e na página — e
    centralizar o link aqui impede que um aponte para um arquivo que o outro não gravou.

    Entrada: arquivo (nome dentro de `dados/`), ticker.
    Saída: string com o HTML do link.
    """
    # `download` faz o navegador salvar o arquivo em vez de tentar abri-lo.
    return (f"<a class='baixar compacto' download href='dados/{arquivo}' "
            f"title='planilha de estudo de {ticker}'>↓ xlsx</a>")

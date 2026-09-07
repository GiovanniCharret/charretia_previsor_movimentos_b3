"""
Cinco funções de faixa/decil, copiadas LITERALMENTE de `robusta_ml/extremos.py`.

Por que este arquivo existe: a tela precisa rodar sozinha, sem o pacote de laboratório no caminho
de importação. O `extremos.py` original tem 708 linhas e arrasta matplotlib e o módulo de modelo
junto — nada disso serve à tela, que usa só estas cinco funções.

**Não edite aqui.** A fonte é `src/robusta_ml/extremos.py`, no repositório irmão
`robusta_backtest`. Recopie de lá em vez de corrigir à mão — e atualize o commit de origem
registrado no README.
"""

import numpy as np                                          # quantis, busca binária, episódios
import pandas as pd                                         # séries e datas


def add_dist_zscore(df, windows, vol_lag):
    """
    Acrescenta `mma_dist_z_w{w}` = dist normalizada pela sua própria dispersão recente (item 1.1).

    Por que existe: "afastar demais" é RELATIVO. Uma distância de −12% num período calmo é um
    evento; em 2020 é terça-feira. Dividir a dist pelo desvio-padrão móvel dela mesma torna o
    limiar auto-calibrado — é a operacionalização honesta da palavra "demais", e continua 100%
    derivado da mma (nenhum indicador novo entra).

    Entrada: df (com as colunas mma_dist_w{w}), windows (janelas), vol_lag (janela do desvio móvel).
    Fase 1: para cada janela, calcular o desvio-padrão móvel da dist sobre as últimas vol_lag
            barras — usa apenas passado e o próprio t, então não vaza futuro.
    Fase 2: dividir a dist pelo desvio; onde o desvio é 0 (série chapada), o resultado vira NaN
            para não gerar infinito.
    Fase 3: concatenar todas as colunas **de uma vez**. Acrescentá-las uma a uma fragmentava a
            estrutura interna do pandas e disparava `PerformanceWarning` na varredura de 145
            janelas — corrigido em 07/09/2026.
    Saída: um df novo, com uma coluna mma_dist_z_w{w} por janela.
    """
    # Acumulador das colunas novas, na ordem das janelas pedidas.
    novas = {}
    # Fase 1 e 2: uma coluna z por janela.
    for w in windows:
        # Coluna de distância contínua já produzida por build_features.
        dist = df[f"mma_dist_w{w}"]
        # Desvio-padrão móvel da própria distância (janela causal: passado + t).
        desvio = dist.rolling(vol_lag).std()
        # Desvio zero viraria divisão por zero → NaN explícito (linha descartada depois).
        desvio = desvio.replace(0.0, np.nan)
        # z = quantos desvios típicos a distância de hoje representa.
        novas[f"mma_dist_z_w{w}"] = dist / desvio
    # Fase 3: uma concatenação só, alinhada pelo índice (o mesmo, por construção).
    if novas:
        df = pd.concat([df, pd.DataFrame(novas, index=df.index)], axis=1)
    # Saída: df enriquecido.
    return df

def quantis_do_treino(x, train_idx, n_faixas):
    """
    Cortes de faixa (quantis) calculados SÓ nas linhas de treino (itens 1.2 e 2.1).

    Por que existe: fatiar por quantil fixa a TAXA DE EVENTOS antes de olhar o resultado (10% dos
    dias por decil), em vez de escolher um limiar a dedo olhando a resposta — que seria p-hacking.
    E calcular no treino evita que o limiar seja informado pelo futuro (mesma disciplina do
    standardize e do binning).

    Entrada: x (Series do z-score), train_idx (posições de treino), n_faixas (10 = decis).
    Fase 1: recortar só as linhas de treino e descartar NaN (warm-up).
    Fase 2: calcular os n_faixas-1 cortes internos (quantis 1/n, 2/n, …).
    Fase 3: remover cortes duplicados (série com pouca variação geraria bordas repetidas).
    Saída: lista ordenada de cortes internos (float).
    """
    # Fase 1: só treino, sem NaN.
    amostra = x.iloc[train_idx].dropna()
    # Sem amostra suficiente não há cortes a calcular.
    if len(amostra) == 0:
        return []
    # Fase 2: quantis internos (exclui 0 e 1, que são os extremos da própria amostra).
    qs = [i / n_faixas for i in range(1, n_faixas)]
    cortes = [float(amostra.quantile(q)) for q in qs]
    # Fase 3: descartar duplicados preservando a ordem (série pouco variada).
    unicos = []
    for c in cortes:
        if not unicos or c > unicos[-1]:
            unicos.append(c)
    # Saída: cortes internos únicos e crescentes.
    return unicos


def atribui_faixa(x, cortes):
    """
    Converte o z-score no índice da faixa (0 = mais negativa), aplicando cortes já calculados.

    Por que existe: separar o CÁLCULO dos cortes (só treino) da APLICAÇÃO deles (treino + teste) é
    o que mantém a disciplina anti-vazamento — a mesma separação de `fit` e `transform`.

    Entrada: x (Series do z-score), cortes (bordas internas vindas do treino).
    Fase 1: sem cortes, tudo cai na faixa 0 (degenerado, mas não quebra).
    Fase 2: np.searchsorted põe cada valor à direita do corte que o precede → índice da faixa.
    Fase 3: preservar NaN como NaN (linha sem z válido não pertence a faixa nenhuma).
    Saída: Series float com o índice da faixa (NaN onde x é NaN).
    """
    # Fase 1: caso degenerado sem cortes.
    if not cortes:
        return pd.Series(np.where(x.notna(), 0.0, np.nan), index=x.index)
    # Fase 2: índice da faixa por busca binária nas bordas.
    faixa = np.searchsorted(np.asarray(cortes, dtype=float), x.values, side="right").astype(float)
    # Fase 3: onde o z é NaN, a faixa também é NaN.
    faixa[np.isnan(x.values)] = np.nan
    # Saída: Series alinhada ao índice original.
    return pd.Series(faixa, index=x.index)


def conta_episodios(posicoes, gap):
    """
    Conta EPISÓDIOS independentes, não dias (a salvaguarda central contra o "n" inflado).

    Por que existe: eventos extremos vêm em blocos — uma crise gera 30 dias seguidos abaixo do
    limiar. Contá-los como 30 observações independentes infla a confiança de forma grosseira.
    Dias separados por menos que `gap` (o horizonte, cujos retornos futuros se sobrepõem) contam
    como UM episódio. É o número honesto para julgar se o resultado é conclusivo.

    Entrada: posicoes (array de índices posicionais dos dias de evento), gap (horizonte em dias).
    Fase 1: amostra vazia → zero episódios.
    Fase 2: ordenar e percorrer; cada salto maior que `gap` abre um novo episódio.
    Saída: int com o número de episódios independentes.
    """
    # Fase 1: sem eventos, sem episódios.
    p = np.sort(np.asarray(posicoes))
    if p.size == 0:
        return 0
    # Fase 2: começa com 1 episódio e conta os saltos grandes.
    return 1 + int((np.diff(p) > gap).sum())


def divide_por_calendario(indice, data_inicio_teste, embargo):
    """
    Split treino/teste por DATA fixa, em vez de por fração — para comparar papéis entre si.

    Por que existe: o corte percentual (`temporal_split`) dá a cada papel uma janela de teste
    diferente, porque os históricos começam em anos diferentes. Ao comparar a DERIVA entre empresas,
    isso invalidaria a comparação: a deriva de uma cobriria 2021-2026 e a de outra 2022-2026,
    períodos com condições de mercado distintas. Fixar a data iguala a régua para todos.

    Entrada: indice (DatetimeIndex das linhas já limpas), data_inicio_teste (string ou Timestamp),
    embargo (dias descartados entre treino e teste, = horizonte).
    Fase 1: achar a primeira posição cuja data alcança o corte.
    Fase 2: teste = daí até o fim; treino = do início até `embargo` linhas antes do corte.
    Saída: tupla (train_idx, test_idx) de índices posicionais, sem sobreposição.
    """
    # Fase 1: quantas linhas ficam ANTES do corte — essa contagem é a posição onde o teste começa.
    inicio = int((indice < pd.Timestamp(data_inicio_teste)).sum())
    # Fase 2: treino termina `embargo` linhas antes, para o retorno futuro do treino não invadir o teste.
    fim_treino = max(0, inicio - embargo)
    # Saída: os dois conjuntos de posições.
    return np.arange(0, fim_treino), np.arange(inicio, len(indice))

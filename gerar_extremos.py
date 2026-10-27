"""
Tela da faixa extrema (v3): quais papéis fecharam hoje entre os 2,5% ou 5% de dias mais afastados
para baixo da própria média.

Por que este script existe: o controle de 12/10/2026 (achado W do laboratório) mostrou que a medida
da tela de gatilhos — a proteção por episódio — é em grande parte efeito mecânico da contagem:
séries de preços sem memória já devolvem 75% a 80%. Depois do controle sobrou um **indício**, medido
de outro jeito: contando DIAS, o excesso sobre a taxa-base cresce quanto mais fundo é o corte
(+4,2 pontos em 20 pregões e +7,3 em 45 no percentil de 2,5%, juntando 59 papéis), com o percentil
de 30% em zero como controle. Esta tela publica esse indício, com esse nome.

O que ela NÃO faz, de propósito:

- **não recalcula corte.** Os limiares de cada (papel, janela, percentil) vêm medidos do
  laboratório, sobre a história completa, em `estudo/faixa_extrema_cortes.csv`;
- **não elege janela.** O teste que sustenta o indício usou nove janelas fixadas antes; a tela
  conta em quantas delas o papel está abaixo do corte, em vez de destacar uma;
- **não promete por papel.** Papel a papel o efeito não é detectável. A linha traz o limite
  inferior do papel porque o usuário decide olhando para ele, mas o texto da página diz o que o
  número vale.
"""

import sys                                                  # papel único pela linha de comando
from pathlib import Path                                    # caminhos

import numpy as np                                          # NaN
import pandas as pd                                         # tabelas
from tqdm import tqdm                                       # barra de andamento dos downloads

from nucleo import config                                   # parâmetros das telas
from nucleo.data import load_prices                         # download (único ponto de rede)
from nucleo.features_mma import build_features              # distância até a média
from nucleo.qualidade_dados import apara_inicio             # corta a cabeça anterior à listagem
from nucleo.faixas import add_dist_zscore                   # distância ÷ desvio-padrão móvel
from gerar_alertas import pregoes_necessarios, periodo_do_download   # quanto baixar
from publicacao import barra_de_abas, copia_estatica, le_estado      # o que as páginas dividem
from planilha_estudo import grava_estudo_do_papel, link_planilha     # a planilha de estudo

# Colunas da tabela do dia, fixadas para a página saber desenhar o caso vazio.
COLUNAS = ["ticker", "faixa", "janelas", "janelas_2_5", "janelas_5", "janelas_medidas",
           "horizonte", "freq", "taxa_base", "acima_da_base",
           "divisoes_usadas", "inicio_medido", "fim_medido"]

# A ordem de preferência do horizonte exibido: o de 45 pregões, e o de 20 só quando o papel não tem
# medida em 45. É o mesmo critério da tela de gatilhos — o número da linha é o do prazo mais longo
# disponível, que é o prazo em que o usuário monta posição.
HORIZONTES_PREFERIDOS = (45, 20)


def escores_de_hoje(prices, janelas, vol_lag, slope_lag):
    """
    O escore padronizado do último fechamento, para cada janela.

    Por que existe: é a única medida que a tela faz por conta própria. Tudo o mais — cortes e
    frequências — vem pronto do laboratório.

    Entrada: prices (OHLCV já aparado), janelas, vol_lag, slope_lag.
    Fase 1: construir a distância e o escore de todas as janelas de uma vez.
    Fase 2: ler a última linha de cada uma; sem história bastante, o escore fica ausente.
    Saída: dicionário {janela: escore de hoje, ou NaN}.
    """
    # Fase 1: uma construção só.
    df, _feats = build_features(prices.copy(), list(janelas), [0.0], [1], slope_lag)
    df = add_dist_zscore(df, list(janelas), vol_lag)
    # Fase 2: o valor da última linha — NaN quando a janela ainda não tem escore.
    return {int(w): float(df[f"mma_dist_z_w{w}"].iloc[-1]) for w in janelas}


def situacao_do_papel(escores, cortes):
    """
    Conta em quantas janelas o papel está hoje abaixo de cada corte.

    Por que existe: o indício não tem janela vencedora, então a leitura do dia é uma contagem —
    "abaixo do percentil de 2,5% em 6 das 9 janelas" diz mais do que o estado de uma janela só.

    Entrada: escores (dicionário {janela: escore de hoje}), cortes (DataFrame do papel com as
    colunas janela, percentil e corte).
    Fase 1: só entram as janelas que têm escore hoje E corte medido.
    Fase 2: contar as que estão no corte de 2,5% ou abaixo, e as que estão no de 5% ou abaixo, e
            guardar QUAIS são — a tabela mostra as janelas, e não só quantas.
    Saída: dicionário com as duas contagens, as duas listas de janelas, a lista das janelas
    acompanhadas e o total delas.
    """
    medidas, abaixo, quais = set(), {0.025: 0, 0.05: 0}, {0.025: [], 0.05: []}
    for _, c in cortes.iterrows():
        z = escores.get(int(c["janela"]), np.nan)
        # Fase 1: sem escore ou sem corte, a janela não conta nem a favor nem contra.
        if np.isnan(z) or np.isnan(c["corte"]):
            continue
        medidas.add(int(c["janela"]))
        # Fase 2: estar no corte ou abaixo dele.
        if z <= c["corte"]:
            abaixo[float(c["percentil"])] += 1
            quais[float(c["percentil"])].append(int(c["janela"]))
    # Quem está abaixo de 2,5% também está abaixo de 5%, por construção dos cortes.
    return {"janelas_2_5": abaixo[0.025], "janelas_5": abaixo[0.05],
            "janelas_medidas": len(medidas),
            "lista_2_5": sorted(quais[0.025]), "lista_5": sorted(quais[0.05]),
            "acompanhadas": sorted(medidas)}


def faixa_de_janelas(janelas, acompanhadas):
    """
    Escreve as janelas no extremo como faixas, no mesmo formato da tela de gatilhos: "10–30 (3)".

    Por que existe: o usuário precisa ver EM QUE médias o padrão apareceu, e não só quantas — a
    contagem "1 de 9" escondia a janela. Médias vizinhas na lista acompanhada viram uma faixa só,
    porque compartilham boa parte dos dados; o número entre parênteses é quantas médias a faixa
    reúne. As nove médias não são números seguidos (5, 10, 20, 30, 45, 60, 90, 130, 200), então
    "vizinhas" quer dizer vizinhas NESSA lista: 10, 20 e 30 formam "10–30 (3)".

    Entrada: janelas (as que estão no extremo), acompanhadas (todas as que têm medida hoje, em ordem).
    Fase 1: a posição de cada janela na lista acompanhada.
    Fase 2: quebrar em faixas sempre que a posição pular.
    Saída: texto, como "45" ou "10–30 (3) · 90"; vazio quando não há janela.
    """
    # Fase 1: as posições, na ordem da lista acompanhada.
    pos = sorted(acompanhadas.index(w) for w in janelas if w in acompanhadas)
    if not pos:
        return ""
    faixas, inicio, anterior = [], pos[0], pos[0]
    # Fase 2: uma faixa nova a cada salto de posição.
    for p in pos[1:] + [None]:
        if p is None or p != anterior + 1:
            de, ate, n = acompanhadas[inicio], acompanhadas[anterior], anterior - inicio + 1
            faixas.append(f"{de}" if n == 1 else f"{de}–{ate} ({n})")
            if p is not None:
                inicio = p
        if p is not None:
            anterior = p
    # Saída: as faixas, separadas por um ponto.
    return " · ".join(faixas)


def janelas_no_extremo(escores, cortes, percentil):
    """
    Quais janelas estão hoje no corte do percentil pedido, ou abaixo dele.

    Por que existe: a planilha de estudo de um papel abre uma aba por média em que ele está no
    extremo hoje — são as que explicam por que ele apareceu na tela.

    Entrada: escores (dicionário {janela: escore de hoje}), cortes (DataFrame do papel), percentil.
    Saída: lista ordenada das janelas.
    """
    c = cortes[np.isclose(cortes["percentil"], percentil)]
    return sorted(int(w) for w, corte in zip(c["janela"], c["corte"])
                  if not np.isnan(escores.get(int(w), np.nan)) and not np.isnan(corte)
                  and escores[int(w)] <= corte)


def _medida_das_janelas(por_janela, ticker, q, janelas):
    """
    A frequência e a taxa-base de um papel, só nas janelas em que ele está no extremo hoje.

    Por que existe: a coluna "janela" passou a mostrar EM QUAIS médias o papel disparou, e a
    frequência ao lado precisa ser a dessas médias — a média das nove, que é o número do teste
    conjunto, seria lida como se fosse delas (pedido do usuário em 19/10/2026).

    Entrada: por_janela (DataFrame do laboratório, uma linha por papel, percentil, horizonte e
    janela), ticker, q (percentil da faixa), janelas (as que estão no extremo hoje).
    Fase 1: as linhas daquele papel, percentil e janelas.
    Fase 2: o horizonte de 45 pregões; na falta dele em todas as janelas, o de 20.
    Fase 3: a média entre as janelas e o período que as sustenta.
    Saída: dicionário com horizonte, freq, taxa_base e o período; None quando não há medida.
    """
    # Fase 1: só as janelas que dispararam hoje.
    m = por_janela[(por_janela["ticker"] == ticker) & np.isclose(por_janela["percentil"], q)
                   & por_janela["janela"].isin(janelas)]
    # Fase 2: a preferência de horizonte da tela.
    h = next((x for x in HORIZONTES_PREFERIDOS if (m["horizonte"] == x).any()), None)
    if h is None:
        return None
    m = m[m["horizonte"] == h]
    # Fase 3: cada janela pesa igual, como no agregado do laboratório.
    return {"horizonte": h, "freq": float(m["freq_dias"].mean()),
            "taxa_base": float(m["taxa_base"].mean()),
            "divisoes_usadas": int(m["divisoes_usadas"].max()),
            "inicio_medido": str(m["inicio_medido"].min()), "fim_medido": str(m["fim_medido"].max())}


def monta_tabela(situacoes, medidas, por_janela=None):
    """
    Junta a situação de hoje com o que o laboratório mediu, e ordena os papéis.

    Por que existe: é o cruzamento que a página exibe, e é pura para os testes cobrirem a
    classificação e a ordem sem rede.

    Um papel entra na faixa de **2,5%** se está abaixo desse corte em pelo menos uma janela; entra
    na de **5%** se não chega ao de 2,5% em nenhuma, mas está abaixo do de 5% em alguma. Os números
    da linha são os do percentil da faixa em que ele caiu, no horizonte de 45 pregões — ou no de 20,
    quando o papel não tem medida em 45. A tabela segue o desenho da tela de gatilhos (pedido do
    usuário em 13/10/2026): uma coluna de limite inferior, uma de taxa-base, sem a frequência crua.

    Entrada: situacoes (dicionário {papel: saída de `situacao_do_papel`}), medidas (DataFrame com
    ticker, percentil, horizonte, freq_dias, taxa_base e o período medido), por_janela (a mesma
    medida janela a janela; quando presente, a frequência da linha é a das janelas no extremo hoje,
    e não a média das nove).
    Fase 1: descartar quem não está abaixo de corte nenhum.
    Fase 2: classificar na faixa e buscar as medidas daquele percentil, por horizonte.
    Fase 3: ordenar — faixa de 2,5% primeiro; depois mais médias no extremo; depois a frequência
            exibida; por fim o código, para a ordem não depender do arquivo.
    Saída: DataFrame com uma linha por papel na faixa extrema.
    """
    linhas = []
    for ticker, s in situacoes.items():
        # Fase 1: fora da faixa extrema.
        if s["janelas_5"] == 0:
            continue
        # Fase 2: a faixa mais funda em que o papel aparece.
        q = 0.025 if s["janelas_2_5"] > 0 else 0.05
        m = medidas[(medidas["ticker"] == ticker) & (np.isclose(medidas["percentil"], q))]
        m = m.set_index("horizonte")
        # Só as janelas DA faixa da tabela: na seção de 2,5%, as que passam do corte de 2,5%; na de
        # 5%, as que passam do de 5%. Misturar as duas confundia a leitura (usuário, 19/10/2026).
        lista = s.get("lista_2_5" if q == 0.025 else "lista_5", [])
        linha = {"ticker": ticker, "faixa": q,
                 "janelas": faixa_de_janelas(lista, s.get("acompanhadas", sorted(lista))),
                 **{k: v for k, v in s.items() if k not in ("lista_2_5", "lista_5", "acompanhadas")}}
        # O horizonte da linha: o de 45 pregões; na falta dele, o de 20. Sem nenhum dos dois, as
        # células ficam ausentes e a página mostra "—" — nunca um número inventado.
        h = next((x for x in HORIZONTES_PREFERIDOS
                  if x in m.index and not pd.isna(m.loc[x, "freq_dias"])), None)
        linha["horizonte"] = h if h is not None else np.nan
        linha["freq"] = float(m.loc[h, "freq_dias"]) if h is not None else np.nan
        linha["taxa_base"] = float(m.loc[h, "taxa_base"]) if h is not None else np.nan
        # Com o detalhe por janela, a frequência e a taxa-base passam a ser as das janelas que
        # dispararam hoje (usuário, 19/10/2026), no mesmo horizonte preferido.
        if por_janela is not None:
            proprio = _medida_das_janelas(por_janela, ticker, q, lista)
            linha["horizonte"] = proprio["horizonte"] if proprio else np.nan
            linha["freq"] = proprio["freq"] if proprio else np.nan
            linha["taxa_base"] = proprio["taxa_base"] if proprio else np.nan
            h = proprio["horizonte"] if proprio else None
        # O critério de exibição (usuário, 13/10/2026): o papel só vira destaque se, no passado
        # dele, estar nesta faixa veio com retorno positivo MAIS vezes que num dia qualquer. Papel
        # sem medida não tem como cumprir o critério, e por isso também não é destaque.
        linha["acima_da_base"] = bool(h is not None and linha["freq"] > linha["taxa_base"])
        # O período medido é o mesmo nos dois horizontes, a menos da cauda sem retorno futuro.
        linha["divisoes_usadas"] = int(m["divisoes_usadas"].max()) if len(m) else 0
        linha["inicio_medido"] = str(m["inicio_medido"].min()) if len(m) else ""
        linha["fim_medido"] = str(m["fim_medido"].max()) if len(m) else ""
        # E o período medido passa a ser o das janelas que dispararam.
        if por_janela is not None and proprio:
            for k in ("divisoes_usadas", "inicio_medido", "fim_medido"):
                linha[k] = proprio[k]
        linhas.append(linha)
    if not linhas:
        return pd.DataFrame(columns=COLUNAS)
    # Fase 3 e Saída: a ordem determinística.
    return (pd.DataFrame(linhas)[COLUNAS]
            .sort_values(["faixa", "janelas_2_5", "janelas_5", "freq", "ticker"],
                         ascending=[True, False, False, False, True], na_position="last")
            .reset_index(drop=True))


def _pct(x):
    """Percentual com uma casa, ou um traço quando não há medida (helper de renderização)."""
    return "—" if pd.isna(x) else f"{100 * x:.1f}%"


def _linha_html(r, planilhas=()):
    """Uma linha da tabela (helper de renderização)."""
    # O link da planilha de estudo só aparece quando o arquivo foi de fato gravado.
    dados = (link_planilha(f"extremos_{r['ticker']}.xlsx", r["ticker"])
             if r["ticker"] in planilhas else "<span class='posicao'>—</span>")
    # As janelas em que o papel está no extremo da faixa DESTA tabela, como na tela de gatilhos.
    janelas = r["janelas"] or "—"
    # O período medido e quantas épocas o sustentam — abaixo de três, é divisão única.
    periodo = (f"<span class='posicao'>{str(r['inicio_medido'])[:4]}–{str(r['fim_medido'])[:4]}"
               f"</span> <span class='posicao'>({r['divisoes_usadas']})</span>"
               if r["inicio_medido"] else "<span class='posicao'>sem medida</span>")
    # O horizonte a que o limite inferior e a taxa-base da linha se referem.
    horizonte = "—" if pd.isna(r["horizonte"]) else f"<b>{int(r['horizonte'])}</b>"
    return (f"<tr>"
            f"<td class='esq papel'>{r['ticker']}</td>"
            f"<td class='esq'>{janelas}</td>"
            f"<td class='esq'>{horizonte}</td>"
            f"<td class='destaque'>{_pct(r['freq'])}</td>"
            f"<td>{_pct(r['taxa_base'])}</td>"
            f"<td class='esq'>{periodo}</td>"
            f"<td class='esq'>{dados}</td>"
            f"</tr>")


def _secao_html(titulo, nota, d, planilhas=()):
    """Uma das duas seções da página, com a tabela ou o aviso de que está vazia (helper)."""
    cabeca = f"<div class='secao'><h2>{titulo}</h2><span class='nota'>{nota}</span></div>"
    # Seção vazia diz isso com todas as letras: é o caso comum, e não pode parecer falha.
    if d.empty:
        return cabeca + ("<div class='quadro'><table><tbody><tr><td class='esq'>"
                         "<span class='posicao'>nenhum destaque hoje</span></td></tr></tbody></table></div>")
    linhas = "".join(_linha_html(r, planilhas) for _, r in d.iterrows())
    return (cabeca + "<div class='quadro'><table><thead><tr>"
            "<th class='esq'>papel</th>"
            "<th class='esq'>janela <span class='sub2'>(faixa de janelas)</span></th>"
            "<th class='esq'>horizonte <span class='sub2'>(pregões)</span></th>"
            "<th>frequência</th>"
            "<th>taxa-base</th>"
            "<th class='esq'>período medido <span class='sub2'>(épocas)</span></th>"
            "<th class='esq'>dados</th>"
            f"</tr></thead><tbody>{linhas}</tbody></table></div>")


def monta_pagina(template, tabela, data_pregao, n_papeis, n_alerta=None, planilhas=()):
    """
    Preenche o template: a barra de abas, o resumo do dia e as duas seções.

    Por que existe: separa a renderização do cálculo, para os testes cobrirem a página sem rede.

    Entrada: template (string com os marcadores), tabela (saída de `monta_tabela`), data_pregao,
    n_papeis (quantos foram verificados), n_alerta (contador da aba de gatilhos; None se não medido).
    Fase 1: separar os destaques (frequência acima da taxa-base) e montar o resumo do dia.
    Fase 2: as duas seções, a de 2,5% primeiro.
    Fase 3: os marcadores.
    Saída: string com o HTML completo.
    """
    # Só vira destaque quem tem frequência acima da própria taxa-base. Os demais estão na faixa
    # hoje, mas o passado deles não mostrou vantagem ali — ficam no arquivo do dia e fora da tela.
    na_faixa = len(tabela)
    tabela = tabela[tabela["acima_da_base"].astype(bool)] if na_faixa else tabela
    omitidos = na_faixa - len(tabela)
    d25 = tabela[np.isclose(tabela["faixa"].astype(float), 0.025)] if len(tabela) else tabela
    d5 = tabela[np.isclose(tabela["faixa"].astype(float), 0.05)] if len(tabela) else tabela
    # Fase 1: o título diz o estado do dia sem adjetivo.
    if tabela.empty:
        titulo = "Nenhum destaque hoje"
        selo = "sem destaque"
    else:
        pp = "destaques" if len(tabela) > 1 else "destaque"
        titulo = f"{len(tabela)} {pp} na faixa extrema"
        selo = f"{len(d25)} em 2,5% · {len(d5)} em 5%"
    # Quem ficou de fora é dito com número, para o dia vazio não esconder que houve papel na faixa.
    if omitidos:
        pl = "papéis estão" if omitidos > 1 else "papel está"
        nota = (f"{omitidos} {pl} na faixa extrema hoje, mas sem destaque: no histórico, a "
                f"frequência não superou a taxa-base.")
    else:
        nota = "Nenhum papel está na faixa extrema hoje." if na_faixa == 0 else ""
    # Fase 2: as duas seções.
    corpo = (_secao_html("Abaixo do percentil de 2,5%",
                         "os 2,5% de dias mais afastados para baixo da média, na história do papel",
                         d25, planilhas)
             + _secao_html("Abaixo do percentil de 5%",
                           "não chegam ao corte de 2,5% em nenhuma janela, mas passam do de 5%", d5,
                           planilhas))
    # Fase 3: os marcadores. A barra vem de `publicacao` para ser igual em todas as páginas.
    for marca, valor in (("ABAS", barra_de_abas("extremos", n_alerta)), ("TITULO", titulo),
                         ("SELO", selo), ("NOTA", nota), ("CORPO", corpo),
                         ("DATA_PREGAO", data_pregao),
                         ("N_PAPEIS", str(n_papeis))):
        template = template.replace("{{" + marca + "}}", valor)
    return template


def main() -> None:
    """
    Invólucro de entrada e saída: lê o que o laboratório mediu, verifica o fechamento e grava a página.

    Fase 1: ler os cortes e as medidas exportados pelo laboratório.
    Fase 2: por papel, baixar só o necessário para o escore de hoje e contar as janelas abaixo.
    Fase 3: montar a tabela, renderizar e gravar.
    """
    raiz = Path(__file__).resolve().parent
    # Fase 1: os dois arquivos do laboratório. Sem eles não há o que comparar.
    arq_cortes, arq_medidas = raiz / config.ARQUIVO_FAIXA_CORTES, raiz / config.ARQUIVO_FAIXA_MEDIDAS
    arq_por_janela = raiz / config.ARQUIVO_FAIXA_POR_JANELA
    if not arq_cortes.exists() or not arq_medidas.exists() or not arq_por_janela.exists():
        raise SystemExit(
            f"{arq_cortes.name} ou {arq_medidas.name} não existe. Eles são gerados no laboratório "
            "por `robusta_ml.faixa_extrema` — ver `estudo/PROVENIENCIA_FAIXA_EXTREMA.md`.")
    cortes, medidas = pd.read_csv(arq_cortes), pd.read_csv(arq_medidas)
    por_janela = pd.read_csv(arq_por_janela)
    # Um papel pode vir pela linha de comando, para conferência rápida.
    if len(sys.argv) > 1:
        cortes = cortes[cortes["ticker"] == sys.argv[1]]
        if cortes.empty:
            raise SystemExit(f"{sys.argv[1]} não está entre os papéis medidos")
    papeis = sorted(cortes["ticker"].unique())
    print(f"TELA DA FAIXA EXTREMA — {len(papeis)} papéis")
    print("  cortes vindos do laboratório, medidos sobre a história completa de cada papel")

    # Fase 2: um papel por vez.
    situacoes, falhas, data_pregao, escores_do_dia = {}, [], "", {}
    barra = tqdm(papeis, desc="papéis", unit="papel", ncols=78, file=sys.stdout)
    for t in barra:
        c = cortes[cortes["ticker"] == t]
        janelas = sorted(c["janela"].astype(int).unique())
        # Quanto baixar sai da maior janela: só o necessário para existir o escore de hoje.
        precisa = pregoes_necessarios(max(janelas), config.VOL_LAG, config.FOLGA_PREGOES)
        try:
            prices = apara_inicio(load_prices(f"{t}{config.TICKER_SUFFIX}",
                                              periodo_do_download(precisa, config.PREGOES_POR_ANO)))
        except Exception as erro:
            falhas.append(t)
            barra.write(f"  ERRO {t:<8} {erro}")
            continue
        data_pregao = max(data_pregao, str(prices.index[-1].date()))
        escores_do_dia[t] = escores_de_hoje(prices, janelas, config.VOL_LAG, config.SLOPE_LAG)
        s = situacao_do_papel(escores_do_dia[t], c)
        situacoes[t] = s
        # Só quem está na faixa ganha linha no console.
        if s["janelas_5"]:
            barra.write(f"  NA FAIXA {t:<8} {s['janelas_2_5']} janelas abaixo de 2,5%, "
                        f"{s['janelas_5']} abaixo de 5% (de {s['janelas_medidas']})")
    barra.close()

    # Fase 3: a tabela, a página e os estáticos.
    tabela = monta_tabela(situacoes, medidas, por_janela)
    destaques = int(tabela["acima_da_base"].astype(bool).sum()) if len(tabela) else 0
    print(f"\n  {len(tabela)} papéis na faixa extrema, {destaques} com frequência acima da taxa-base")
    if falhas:
        print(f"  {len(falhas)} papéis falharam no download: {', '.join(falhas)}")
    saida = raiz / config.DIR_SAIDA
    saida.mkdir(parents=True, exist_ok=True)
    # Uma planilha de estudo por DESTAQUE: uma aba para cada média em que o papel está no extremo
    # hoje, no percentil da faixa dele e no horizonte da linha.
    planilhas = set()
    for _, r in tabela[tabela["acima_da_base"].astype(bool)].iterrows() if len(tabela) else []:
        t = r["ticker"]
        no_extremo = janelas_no_extremo(escores_do_dia[t], cortes[cortes["ticker"] == t], r["faixa"])
        if grava_estudo_do_papel(saida / "dados", f"extremos_{t}.xlsx", t, no_extremo,
                                 r["horizonte"], float(r["faixa"])):
            planilhas.add(t)
    html = monta_pagina((raiz / "template_extremos.html").read_text(encoding="utf-8"), tabela,
                        data_pregao, len(papeis), le_estado(saida).get("papeis_com_alerta"),
                        planilhas)
    (saida / "extremos.html").write_text(html, encoding="utf-8", newline="\n")
    copia_estatica(raiz, saida)
    tabela.to_csv(saida / "faixa_extrema_do_dia.csv", index=False, lineterminator="\n")
    print(f"Página gravada em {saida / 'extremos.html'}")


if __name__ == "__main__":
    main()

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

# Colunas da tabela do dia, fixadas para a página saber desenhar o caso vazio.
COLUNAS = ["ticker", "faixa", "janelas_2_5", "janelas_5", "janelas_medidas",
           "freq_20", "lim_inf_20", "freq_45", "lim_inf_45", "taxa_base_20", "taxa_base_45",
           "divisoes_usadas", "inicio_medido", "fim_medido"]


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
    Fase 2: contar as que estão no corte de 2,5% ou abaixo, e as que estão no de 5% ou abaixo.
    Saída: dicionário com as duas contagens e o total de janelas medidas.
    """
    medidas, abaixo = set(), {0.025: 0, 0.05: 0}
    for _, c in cortes.iterrows():
        z = escores.get(int(c["janela"]), np.nan)
        # Fase 1: sem escore ou sem corte, a janela não conta nem a favor nem contra.
        if np.isnan(z) or np.isnan(c["corte"]):
            continue
        medidas.add(int(c["janela"]))
        # Fase 2: estar no corte ou abaixo dele.
        if z <= c["corte"]:
            abaixo[float(c["percentil"])] += 1
    # Quem está abaixo de 2,5% também está abaixo de 5%, por construção dos cortes.
    return {"janelas_2_5": abaixo[0.025], "janelas_5": abaixo[0.05],
            "janelas_medidas": len(medidas)}


def monta_tabela(situacoes, medidas):
    """
    Junta a situação de hoje com o que o laboratório mediu, e ordena os papéis.

    Por que existe: é o cruzamento que a página exibe, e é pura para os testes cobrirem a
    classificação e a ordem sem rede.

    Um papel entra na faixa de **2,5%** se está abaixo desse corte em pelo menos uma janela; entra
    na de **5%** se não chega ao de 2,5% em nenhuma, mas está abaixo do de 5% em alguma. Os números
    da linha são os do percentil da faixa em que ele caiu.

    Entrada: situacoes (dicionário {papel: saída de `situacao_do_papel`}), medidas (DataFrame com
    ticker, percentil, horizonte, lim_inf, taxa_base e o período medido).
    Fase 1: descartar quem não está abaixo de corte nenhum.
    Fase 2: classificar na faixa e buscar as medidas daquele percentil, por horizonte.
    Fase 3: ordenar — faixa de 2,5% primeiro; depois mais janelas abaixo; depois o limite inferior
            do horizonte de 45 pregões; por fim o código, para a ordem não depender do arquivo.
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
        linha = {"ticker": ticker, "faixa": q, **s}
        for h in (20, 45):
            # Papel sem medida naquele horizonte fica com a célula ausente, e a página mostra "—".
            tem = h in m.index
            linha[f"freq_{h}"] = float(m.loc[h, "freq_dias"]) if tem else np.nan
            linha[f"lim_inf_{h}"] = float(m.loc[h, "lim_inf"]) if tem else np.nan
            linha[f"taxa_base_{h}"] = float(m.loc[h, "taxa_base"]) if tem else np.nan
        # O período medido é o mesmo nos dois horizontes, a menos da cauda sem retorno futuro.
        linha["divisoes_usadas"] = int(m["divisoes_usadas"].max()) if len(m) else 0
        linha["inicio_medido"] = str(m["inicio_medido"].min()) if len(m) else ""
        linha["fim_medido"] = str(m["fim_medido"].max()) if len(m) else ""
        linhas.append(linha)
    if not linhas:
        return pd.DataFrame(columns=COLUNAS)
    # Fase 3 e Saída: a ordem determinística.
    return (pd.DataFrame(linhas)[COLUNAS]
            .sort_values(["faixa", "janelas_2_5", "janelas_5", "lim_inf_45", "ticker"],
                         ascending=[True, False, False, False, True], na_position="last")
            .reset_index(drop=True))


def _pct(x):
    """Percentual com uma casa, ou um traço quando não há medida (helper de renderização)."""
    return "—" if pd.isna(x) else f"{100 * x:.1f}%"


def _linha_html(r):
    """Uma linha da tabela (helper de renderização)."""
    # A contagem na faixa do papel em destaque; a outra, apagada ao lado, quando acrescenta algo.
    if np.isclose(r["faixa"], 0.025):
        janelas = (f"<b>{r['janelas_2_5']}</b> de {r['janelas_medidas']}"
                   f" <span class='posicao'>· {r['janelas_5']} abaixo de 5%</span>")
    else:
        janelas = f"<b>{r['janelas_5']}</b> de {r['janelas_medidas']}"
    # O período medido e quantas épocas o sustentam — abaixo de três, é divisão única.
    periodo = (f"<span class='posicao'>{str(r['inicio_medido'])[:4]}–{str(r['fim_medido'])[:4]}"
               f"</span> <span class='posicao'>({r['divisoes_usadas']})</span>"
               if r["inicio_medido"] else "<span class='posicao'>sem medida</span>")
    return (f"<tr>"
            f"<td class='esq papel'>{r['ticker']}</td>"
            f"<td class='esq'>{janelas}</td>"
            f"<td><span class='destaque'>{_pct(r['freq_20'])}</span> "
            f"<span class='posicao'>piso {_pct(r['lim_inf_20'])}</span></td>"
            f"<td><span class='destaque'>{_pct(r['freq_45'])}</span> "
            f"<span class='posicao'>piso {_pct(r['lim_inf_45'])}</span></td>"
            f"<td>{_pct(r['taxa_base_20'])} <span class='posicao'>·</span> {_pct(r['taxa_base_45'])}</td>"
            f"<td class='esq'>{periodo}</td>"
            f"</tr>")


def _secao_html(titulo, nota, d):
    """Uma das duas seções da página, com a tabela ou o aviso de que está vazia (helper)."""
    cabeca = f"<div class='secao'><h2>{titulo}</h2><span class='nota'>{nota}</span></div>"
    # Seção vazia diz isso com todas as letras: é o caso comum, e não pode parecer falha.
    if d.empty:
        return cabeca + ("<div class='quadro'><table><tbody><tr><td class='esq'>"
                         "<span class='posicao'>nenhum papel hoje</span></td></tr></tbody></table></div>")
    linhas = "".join(_linha_html(r) for _, r in d.iterrows())
    return (cabeca + "<div class='quadro'><table><thead><tr>"
            "<th class='esq'>papel</th>"
            "<th class='esq'>janelas abaixo do corte</th>"
            "<th>20 pregões <span class='sub2'>(frequência · limite inferior)</span></th>"
            "<th>45 pregões <span class='sub2'>(frequência · limite inferior)</span></th>"
            "<th>taxa-base <span class='sub2'>(20 · 45 pregões)</span></th>"
            "<th class='esq'>período medido <span class='sub2'>(épocas)</span></th>"
            f"</tr></thead><tbody>{linhas}</tbody></table></div>")


def monta_pagina(template, tabela, data_pregao, n_papeis, n_alerta=None):
    """
    Preenche o template: a barra de abas, o resumo do dia e as duas seções.

    Por que existe: separa a renderização do cálculo, para os testes cobrirem a página sem rede.

    Entrada: template (string com os marcadores), tabela (saída de `monta_tabela`), data_pregao,
    n_papeis (quantos foram verificados), n_alerta (contador da aba de gatilhos; None se não medido).
    Fase 1: o resumo do dia — quantos papéis em cada faixa.
    Fase 2: as duas seções, a de 2,5% primeiro.
    Fase 3: os marcadores.
    Saída: string com o HTML completo.
    """
    d25 = tabela[np.isclose(tabela["faixa"].astype(float), 0.025)] if len(tabela) else tabela
    d5 = tabela[np.isclose(tabela["faixa"].astype(float), 0.05)] if len(tabela) else tabela
    # Fase 1: o título diz o estado do dia sem adjetivo.
    if tabela.empty:
        titulo = "Nenhum papel na faixa extrema hoje"
        selo = "sem papel"
    else:
        pp = "papéis" if len(tabela) > 1 else "papel"
        titulo = f"{len(tabela)} {pp} na faixa extrema"
        selo = f"{len(d25)} em 2,5% · {len(d5)} em 5%"
    # Fase 2: as duas seções.
    corpo = (_secao_html("Abaixo do percentil de 2,5%",
                         "os 2,5% de dias mais afastados para baixo da média, na história do papel",
                         d25)
             + _secao_html("Abaixo do percentil de 5%",
                           "não chegam ao corte de 2,5% em nenhuma janela, mas passam do de 5%", d5))
    # Fase 3: os marcadores. A barra vem de `publicacao` para ser igual em todas as páginas.
    for marca, valor in (("ABAS", barra_de_abas("extremos", n_alerta)), ("TITULO", titulo),
                         ("SELO", selo), ("CORPO", corpo), ("DATA_PREGAO", data_pregao),
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
    if not arq_cortes.exists() or not arq_medidas.exists():
        raise SystemExit(
            f"{arq_cortes.name} ou {arq_medidas.name} não existe. Eles são gerados no laboratório "
            "por `robusta_ml.faixa_extrema` — ver `estudo/PROVENIENCIA_FAIXA_EXTREMA.md`.")
    cortes, medidas = pd.read_csv(arq_cortes), pd.read_csv(arq_medidas)
    # Um papel pode vir pela linha de comando, para conferência rápida.
    if len(sys.argv) > 1:
        cortes = cortes[cortes["ticker"] == sys.argv[1]]
        if cortes.empty:
            raise SystemExit(f"{sys.argv[1]} não está entre os papéis medidos")
    papeis = sorted(cortes["ticker"].unique())
    print(f"TELA DA FAIXA EXTREMA — {len(papeis)} papéis")
    print("  cortes vindos do laboratório, medidos sobre a história completa de cada papel")

    # Fase 2: um papel por vez.
    situacoes, falhas, data_pregao = {}, [], ""
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
        s = situacao_do_papel(escores_de_hoje(prices, janelas, config.VOL_LAG, config.SLOPE_LAG), c)
        situacoes[t] = s
        # Só quem está na faixa ganha linha no console.
        if s["janelas_5"]:
            barra.write(f"  NA FAIXA {t:<8} {s['janelas_2_5']} janelas abaixo de 2,5%, "
                        f"{s['janelas_5']} abaixo de 5% (de {s['janelas_medidas']})")
    barra.close()

    # Fase 3: a tabela, a página e os estáticos.
    tabela = monta_tabela(situacoes, medidas)
    print(f"\n  {len(tabela)} papéis na faixa extrema")
    if falhas:
        print(f"  {len(falhas)} papéis falharam no download: {', '.join(falhas)}")
    saida = raiz / config.DIR_SAIDA
    saida.mkdir(parents=True, exist_ok=True)
    html = monta_pagina((raiz / "template_extremos.html").read_text(encoding="utf-8"), tabela,
                        data_pregao, len(papeis), le_estado(saida).get("papeis_com_alerta"))
    (saida / "extremos.html").write_text(html, encoding="utf-8", newline="\n")
    copia_estatica(raiz, saida)
    tabela.to_csv(saida / "faixa_extrema_do_dia.csv", index=False, lineterminator="\n")
    print(f"Página gravada em {saida / 'extremos.html'}")


if __name__ == "__main__":
    main()

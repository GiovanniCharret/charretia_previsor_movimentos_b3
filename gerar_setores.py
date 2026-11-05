"""
Tela de bancos e elétricas (v4): quais desses dezoito papéis fecharam hoje no decil 0.

Por que este script existe: no teste por setor do laboratório (04/11/2026), o decil 0 — os 10% de
dias mais afastados para baixo da própria média, o corte da antiga v2 — teve, em 45 pregões, +8,5
pontos sobre a taxa-base nas elétricas (valor-p 0,007) e +9,7 nos bancos (0,016). Foram os menores
valores-p entre 66 testes, mas nenhum sobreviveu à correção pelo número de testes. Como os dois
setores foram escolhidos por terem saído no topo, a confirmação limpa só vem dos pregões que ainda
vão acontecer. Esta tela existe para acompanhar a hipótese: ela publica, dia a dia, quem está no
decil 0, com o mesmo desenho de tabela da v3.

O que ela NÃO faz, de propósito:

- **não recalcula corte nem frequência.** Os limiares e as medidas vêm do laboratório, em
  `estudo/setores_cortes.csv` e `estudo/setores_por_janela.csv`;
- **não muda a lista de papéis.** Os dezoito são os do teste, travados no laboratório; acrescentar
  um papel agora seria mudar a hipótese depois de vê-la;
- **não chama a linha de sinal.** A página diz que é uma hipótese em observação.

As funções que não dependem do corte — o download, o escore de hoje, as faixas de janelas, a
frequência das janelas no extremo e o desenho da linha — são as da v3, importadas de
`gerar_extremos.py`.
"""

import sys                                                  # papel único pela linha de comando
from pathlib import Path                                    # caminhos

import numpy as np                                          # NaN
import pandas as pd                                         # tabelas
from tqdm import tqdm                                       # barra de andamento dos downloads

from nucleo import config                                   # parâmetros das telas
from nucleo.data import load_prices                         # download (único ponto de rede)
from nucleo.qualidade_dados import apara_inicio             # corta a cabeça anterior à listagem
from gerar_extremos import (escores_de_hoje, faixa_de_janelas, janelas_no_extremo,
                            _medida_das_janelas, _secao_html,  # o que a v3 já resolve
                            pregoes_necessarios, periodo_do_download)
from publicacao import barra_de_abas, copia_estatica, le_estado      # o que as páginas dividem
from planilha_estudo import grava_estudo_do_papel                    # a planilha de estudo

# Colunas da tabela do dia, fixadas para a página saber desenhar o caso vazio.
COLUNAS = ["ticker", "setor", "faixa", "janelas", "n_janelas", "janelas_medidas", "horizonte",
           "freq", "taxa_base", "acima_da_base", "divisoes_usadas", "inicio_medido", "fim_medido"]


def situacao_no_decil(escores, cortes, percentil):
    """
    Em quais janelas o papel está hoje no decil 0, ou abaixo do corte dele.

    Por que existe: a v3 conta dois cortes ao mesmo tempo (2,5% e 5%); a v4 tem um só, e a linha
    precisa saber quais janelas passaram dele e quais foram acompanhadas.

    Entrada: escores (dicionário {janela: escore de hoje}), cortes (DataFrame do papel com janela,
    percentil e corte), percentil (o corte da hipótese, 0.10).
    Fase 1: as janelas acompanhadas são as que têm escore hoje E corte medido.
    Fase 2: as que estão no corte ou abaixo, pela mesma função da v3.
    Saída: dicionário com a lista das janelas no decil e a lista das acompanhadas.
    """
    # Fase 1: só conta a janela que pode ser comparada hoje.
    c = cortes[np.isclose(cortes["percentil"], percentil)]
    acompanhadas = sorted(int(w) for w, corte in zip(c["janela"], c["corte"])
                          if not np.isnan(escores.get(int(w), np.nan)) and not np.isnan(corte))
    # Fase 2 e Saída: as que estão no decil 0 hoje.
    return {"lista": janelas_no_extremo(escores, cortes, percentil), "acompanhadas": acompanhadas}


def monta_tabela(situacoes, por_janela, setor_de, percentil):
    """
    Junta a situação de hoje com o que o laboratório mediu, e ordena os papéis.

    Por que existe: é o cruzamento que a página exibe, e é pura para os testes cobrirem a
    classificação e a ordem sem rede.

    A linha segue a v3 (pedido do usuário em 04/11/2026): a frequência e a taxa-base são **do próprio
    papel**, nas janelas em que ele está no decil 0 hoje, no horizonte de 45 pregões. Só vira
    destaque quem tem frequência acima da própria taxa-base, como na v3.

    Entrada: situacoes ({papel: saída de `situacao_no_decil`}), por_janela (a medida do laboratório
    janela a janela), setor_de ({papel: setor}), percentil.
    Fase 1: descartar quem não está no decil 0 em janela nenhuma.
    Fase 2: as janelas como faixas, e a frequência e a taxa-base dessas janelas.
    Fase 3: ordenar — mais janelas no decil primeiro; depois a frequência; por fim o código.
    Saída: DataFrame com uma linha por papel no decil 0.
    """
    linhas = []
    for ticker, s in situacoes.items():
        # Fase 1: fora do decil 0 hoje.
        if not s["lista"]:
            continue
        # Fase 2: a medida das janelas que dispararam, como na v3.
        m = _medida_das_janelas(por_janela, ticker, percentil, s["lista"])
        linha = {"ticker": ticker, "setor": setor_de.get(ticker, ""), "faixa": percentil,
                 "janelas": faixa_de_janelas(s["lista"], s["acompanhadas"]),
                 "n_janelas": len(s["lista"]), "janelas_medidas": len(s["acompanhadas"])}
        # Sem medida, as células ficam ausentes e a página mostra "—" — nunca um número inventado.
        for k in ("horizonte", "freq", "taxa_base"):
            linha[k] = m[k] if m else np.nan
        linha["divisoes_usadas"] = m["divisoes_usadas"] if m else 0
        linha["inicio_medido"] = m["inicio_medido"] if m else ""
        linha["fim_medido"] = m["fim_medido"] if m else ""
        # O critério de exibição da v3: o passado do papel nessas janelas superou o dia qualquer.
        linha["acima_da_base"] = bool(m and linha["freq"] > linha["taxa_base"])
        linhas.append(linha)
    if not linhas:
        return pd.DataFrame(columns=COLUNAS)
    # Fase 3 e Saída: a ordem determinística.
    return (pd.DataFrame(linhas)[COLUNAS]
            .sort_values(["n_janelas", "freq", "ticker"], ascending=[False, False, True],
                         na_position="last")
            .reset_index(drop=True))


def monta_pagina(template, tabela, data_pregao, n_papeis, n_alerta=None, planilhas=()):
    """
    Preenche o template: a barra de abas, o resumo do dia e uma seção por setor.

    Por que existe: separa a renderização do cálculo, para os testes cobrirem a página sem rede.

    Entrada: template, tabela (saída de `monta_tabela`), data_pregao, n_papeis (quantos foram
    verificados), n_alerta (contador da aba da faixa extrema; None se não medido), planilhas (os
    papéis cuja planilha de estudo foi gravada).
    Fase 1: separar os destaques e montar o resumo do dia.
    Fase 2: uma seção por setor, na ordem da configuração; a linha é desenhada pela função da v3.
    Fase 3: os marcadores.
    Saída: string com o HTML completo.
    """
    # Fase 1: só vira destaque quem tem frequência acima da própria taxa-base.
    no_decil = len(tabela)
    tabela = tabela[tabela["acima_da_base"].astype(bool)] if no_decil else tabela
    omitidos = no_decil - len(tabela)
    if tabela.empty:
        titulo, selo = "Nenhum destaque hoje", "sem destaque"
    else:
        pp = "destaques" if len(tabela) > 1 else "destaque"
        titulo = f"{len(tabela)} {pp} no decil 0"
        selo = " · ".join(f"{(tabela['setor'] == s).sum()} {rotulo.lower()}"
                          for s, rotulo in config.SETORES_ROTULOS.items())
    # Quem ficou de fora é dito com número, para o dia vazio não esconder que houve papel no decil.
    if omitidos:
        pl = "papéis estão" if omitidos > 1 else "papel está"
        nota = (f"{omitidos} {pl} no decil 0 hoje, mas sem destaque: no histórico, a frequência "
                f"não superou a taxa-base.")
    else:
        nota = "Nenhum dos dezoito papéis está no decil 0 hoje." if no_decil == 0 else ""
    # Fase 2: uma seção por setor; a linha e a seção são as da v3, com o prefixo das planilhas.
    corpo = "".join(
        _secao_html(rotulo, config.SETORES_NOTAS[s],
                    tabela[tabela["setor"] == s] if len(tabela) else tabela,
                    planilhas, prefixo="setores")
        for s, rotulo in config.SETORES_ROTULOS.items())
    # Fase 3: os marcadores. A barra vem de `publicacao` para ser igual em todas as páginas.
    for marca, valor in (("ABAS", barra_de_abas("setores", n_alerta)), ("TITULO", titulo),
                         ("SELO", selo), ("NOTA", nota), ("CORPO", corpo),
                         ("DATA_PREGAO", data_pregao), ("N_PAPEIS", str(n_papeis))):
        template = template.replace("{{" + marca + "}}", valor)
    return template


def main() -> None:
    """
    Invólucro de entrada e saída: lê o que o laboratório mediu, verifica o fechamento e grava a página.

    Fase 1: ler os cortes e a medida por janela exportados pelo laboratório.
    Fase 2: por papel, baixar só o necessário para o escore de hoje e ver em quais janelas está no
            decil 0.
    Fase 3: montar a tabela, gravar as planilhas dos destaques, renderizar e gravar.
    """
    raiz = Path(__file__).resolve().parent
    # Fase 1: os dois arquivos do laboratório. Sem eles não há o que comparar.
    arq_cortes, arq_janelas = raiz / config.ARQUIVO_SETORES_CORTES, raiz / config.ARQUIVO_SETORES_POR_JANELA
    if not arq_cortes.exists() or not arq_janelas.exists():
        raise SystemExit(
            f"{arq_cortes.name} ou {arq_janelas.name} não existe. Eles são gerados no laboratório "
            "por `robusta_ml.setores_v4` — ver `estudo/PROVENIENCIA_SETORES.md`.")
    cortes, por_janela = pd.read_csv(arq_cortes), pd.read_csv(arq_janelas)
    setor_de = cortes.drop_duplicates("ticker").set_index("ticker")["setor"].to_dict()
    q = config.SETORES_PERCENTIL
    # Um papel pode vir pela linha de comando, para conferência rápida.
    if len(sys.argv) > 1:
        cortes = cortes[cortes["ticker"] == sys.argv[1]]
        if cortes.empty:
            raise SystemExit(f"{sys.argv[1]} não está entre os papéis da v4")
    papeis = sorted(cortes["ticker"].unique())
    print(f"TELA DE BANCOS E ELÉTRICAS — {len(papeis)} papéis, decil 0")

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
        situacoes[t] = situacao_no_decil(escores_do_dia[t], c, q)
        # Só quem está no decil ganha linha no console.
        if situacoes[t]["lista"]:
            barra.write(f"  NO DECIL 0 {t:<8} janelas {situacoes[t]['lista']}")
    barra.close()

    # Fase 3: a tabela, as planilhas, a página e os estáticos.
    tabela = monta_tabela(situacoes, por_janela, setor_de, q)
    destaques = int(tabela["acima_da_base"].astype(bool).sum()) if len(tabela) else 0
    print(f"\n  {len(tabela)} papéis no decil 0, {destaques} com frequência acima da taxa-base")
    if falhas:
        print(f"  {len(falhas)} papéis falharam no download: {', '.join(falhas)}")
    saida = raiz / config.DIR_SAIDA
    saida.mkdir(parents=True, exist_ok=True)
    # Uma planilha de estudo por destaque: uma aba para cada janela em que o papel está no decil 0.
    planilhas = set()
    for _, r in tabela[tabela["acima_da_base"].astype(bool)].iterrows() if len(tabela) else []:
        t = r["ticker"]
        if grava_estudo_do_papel(saida / "dados", f"setores_{t}.xlsx", t, situacoes[t]["lista"],
                                 r["horizonte"], q):
            planilhas.add(t)
    # O contador da barra continua sendo o da faixa extrema, gravado por `gerar_extremos.py`.
    html = monta_pagina((raiz / "template_setores.html").read_text(encoding="utf-8"), tabela,
                        data_pregao, len(papeis), le_estado(saida).get("papeis_com_alerta"),
                        planilhas)
    (saida / "setores.html").write_text(html, encoding="utf-8", newline="\n")
    copia_estatica(raiz, saida)
    tabela.to_csv(saida / "setores_do_dia.csv", index=False, lineterminator="\n")
    print(f"Página gravada em {saida / 'setores.html'}")


if __name__ == "__main__":
    main()

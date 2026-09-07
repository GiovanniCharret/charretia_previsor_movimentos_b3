"""
Tela de alertas: quais papéis fecharam hoje no decil que os achados O a W mediram como protetivo.

Por que este script existe: o estudo produziu milhares de setups (papel × horizonte × janela) que
superam a taxa-base do próprio papel. Isso é uma tabela histórica. A pergunta operacional é outra e
tem uma resposta por dia: **quais desses setups estão acionados AGORA?** Um setup só vale hoje se o
fechamento de hoje caiu no decil mais afastado para baixo daquela janela.

Os setups vêm de `estudo/setups.csv`, exportado pelo laboratório — este repositório não faz a
varredura, só lê o resultado dela. Ver `estudo/PROVENIENCIA.md`.

Os dois laços:

1. **Por papel.** Baixa a história, calcula a distância até cada média móvel, normaliza em escore
   padronizado e descobre o corte do decil 0 daquele papel. Devolve, por janela, se o fechamento de
   hoje está abaixo do corte.
2. **Por setup aprovado.** Cruza a planilha do estudo com o estado de hoje e mantém só os setups
   cuja janela disparou. Agrupa janelas vizinhas e apresenta por horizonte.

Três decisões que valem estar escritas, porque não são óbvias:

- **O download não é de 200 pregões.** O escore de hoje exige `janela + 252 - 1` pregões, porque o
  desvio-padrão móvel que normaliza a distância tem um ano. Com janela 200 são 451, e com 200 dias
  não existiria escore nenhum. O script calcula quanto cada papel precisa a partir da maior janela
  aprovada dele e baixa só isso.
- **O corte do decil vem de toda a história até ontem, não dos últimos 200 dias.** "Decil 0 dos
  últimos 200 dias" dispararia uns vinte dias por construção, esteja o papel longe da média ou não.
  E usar o passado inteiro para definir o limiar de hoje **não é vazamento**: a disciplina de treino
  do laboratório existe para a medição ser honesta; em produção, olhar todo o passado é o correto.
- **A faixa é o decil 0**, o décimo mais afastado para baixo. Foi a faixa medida; qualquer outra
  desfaria a correspondência entre o alerta e os números de proteção que ele exibe.
"""

import sys                                                  # papel único pela linha de comando
from math import ceil                                       # arredondamento do período
from pathlib import Path                                    # caminhos

import numpy as np                                          # NaN e arrays
import pandas as pd                                         # tabelas
from tqdm import tqdm                                       # barra de andamento dos 61 downloads

from nucleo import config                                   # parâmetros da tela
from nucleo.data import load_prices                         # download (único ponto de rede)
from nucleo.features_mma import build_features              # distância até a média
from nucleo.qualidade_dados import apara_inicio             # corta a cabeça anterior à listagem
from nucleo.faixas import add_dist_zscore                    # escore padronizado
from publicacao import barra_de_abas, copia_estatica, grava_estado   # o que as 3 páginas dividem


def pregoes_necessarios(janela_maxima, vol_lag, folga):
    """
    Quantos pregões precisam ser baixados para o escore de HOJE existir.

    Por que existe: é a conta que o pedido original errava. O escore padronizado é a distância até a
    média dividida pelo desvio-padrão móvel dessa distância. A distância só existe depois de
    `janela` pregões; o desvio só existe depois de mais `vol_lag`. Com a maior janela aprovada (200)
    e o desvio de um ano (252), são 451 pregões antes de haver um único escore — e o pedido falava
    em 200 dias, que não produziria nenhum.

    Entrada: janela_maxima (a maior média móvel usada pelo papel), vol_lag (janela do desvio móvel),
    folga (pregões extras para cobrir feriados e a diferença entre dias de calendário e pregões).
    Fase 1: somar as duas janelas, descontando a sobreposição de um pregão, e acrescentar a folga.
    Saída: int com o número de pregões.
    """
    # Fase 1: o -1 é a sobreposição — o primeiro dia do desvio é o último dia da média.
    return int(janela_maxima) + int(vol_lag) - 1 + int(folga)


def periodo_do_download(pregoes, pregoes_por_ano):
    """
    Converte "preciso de N pregões" no período que o provedor de dados aceita.

    Por que existe: o provedor recebe períodos relativos ("2y"), não contagens. Arredondar para
    baixo produziria escore ausente em silêncio, que é o pior modo de falha possível — a página
    diria "nenhum alerta" sem distinguir "não disparou" de "não foi possível medir".

    Entrada: pregoes (quantos são necessários), pregoes_por_ano.
    Fase 1: dividir e arredondar para CIMA, nunca para baixo.
    Fase 2: nunca menos de um ano, por mais curta que seja a janela.
    Saída: string no formato aceito pelo provedor, como "2y".
    """
    # Fase 1 e 2: arredonda para cima, com piso de um ano.
    return f"{max(1, ceil(pregoes / pregoes_por_ano))}y"


def estado_das_janelas(prices, cortes, vol_lag, slope_lag):
    """
    LAÇO 1 — o escore de hoje de cada janela, comparado com o corte que o laboratório mediu.

    Por que existe: é a medida do dia. E ela **não calcula o corte** — recebe. A primeira versão
    calculava, sobre a história curta que a aplicação baixa, e o resultado foi um defeito grave: na
    GGBR4 com janela 200, o corte saía **+0,465** com dois anos e **−2,010** com a história completa.
    Um corte positivo faria o "decil mais afastado para baixo" incluir dias com o preço ACIMA da
    média. A divisão de trabalho decidida pelo usuário resolve isso: o laboratório baixa tudo e
    grava o corte na planilha; aqui só se baixa o necessário para o escore de hoje.

    Dois modos de ausência, ambos explícitos, porque confundir "não sei" com "não" faria a página
    omitir alertas reais sem avisar: janela sem história suficiente para ter escore, e janela cujo
    corte o laboratório não conseguiu medir.

    Entrada: prices (OHLCV já aparado), cortes (dicionário {janela: corte}), vol_lag, slope_lag.
    Fase 1: construir a distância e o escore padronizado para todas as janelas de uma vez.
    Fase 2: por janela, sem escore → ausência de medida com motivo.
    Fase 3: sem corte vindo do estudo → ausência de gatilho com motivo.
    Fase 4: disparar é o escore de hoje estar no corte ou abaixo dele.
    Saída: DataFrame com uma linha por janela.
    """
    janelas = sorted(cortes)
    # Fase 1: uma construção só para todas as janelas.
    df, _feats = build_features(prices.copy(), list(janelas), [0.0], [1], slope_lag)
    df = add_dist_zscore(df, list(janelas), vol_lag)

    linhas = []
    for w in janelas:
        z = df[f"mma_dist_z_w{w}"].dropna()
        corte = float(cortes[w])
        # Fase 2: sem escore não há medida.
        if len(z) == 0:
            linhas.append({"janela": int(w), "z_hoje": float("nan"), "corte": corte,
                           "dispara": False, "n_pregoes_com_escore": 0,
                           "motivo": f"história insuficiente para o escore da janela {w}: "
                                     f"precisa de {w + vol_lag - 1} pregões"})
            continue
        # Fase 3: sem corte medido no laboratório não há gatilho.
        if np.isnan(corte):
            linhas.append({"janela": int(w), "z_hoje": float(z.iloc[-1]), "corte": corte,
                           "dispara": False, "n_pregoes_com_escore": len(z),
                           "motivo": "sem corte no estudo: o quantil não tinha escores bastantes"})
            continue
        # Fase 4: a comparação.
        linhas.append({"janela": int(w), "z_hoje": float(z.iloc[-1]), "corte": corte,
                       "dispara": bool(z.iloc[-1] <= corte),
                       "n_pregoes_com_escore": len(z), "motivo": ""})
    return pd.DataFrame(linhas)


def agrupa_faixas_contiguas(janelas):
    """
    Agrupa janelas vizinhas numa faixa só.

    Por que existe: quando um papel dispara, ele dispara em dezenas de janelas vizinhas ao mesmo
    tempo — a EGIE3 tem 651 setups aprovados, em janelas contíguas. Listar todas sugeriria dezenas
    de gatilhos onde há um: janelas vizinhas compartilham cerca de 99% dos dados. A mesma lição da
    contagem de episódios, aplicada ao eixo da janela em vez do eixo do tempo.

    Entrada: janelas (iterável de inteiros, em qualquer ordem).
    Fase 1: sem janelas, sem faixas.
    Fase 2: ordenar e quebrar sempre que houver salto maior que um.
    Saída: lista de tuplas (primeira, última) de cada faixa contígua.
    """
    # Fase 1: nada a agrupar.
    j = sorted(set(int(x) for x in janelas))
    if not j:
        return []
    # Fase 2: percorrer abrindo faixa nova a cada salto.
    faixas, inicio, anterior = [], j[0], j[0]
    for x in j[1:]:
        if x != anterior + 1:
            faixas.append((inicio, anterior)); inicio = x
        anterior = x
    faixas.append((inicio, anterior))
    return faixas


# Colunas da tabela de alertas, fixadas para a página saber desenhar o caso vazio.
COLUNAS_ALERTA = ["posicao_papel", "total_papeis", "ticker", "horizonte", "janela_de", "janela_ate",
                  "n_setups", "episodios", "protecao", "prot_lo", "taxa_base",
                  # A janela de tempo que sustenta a taxa-base. Sem ela, 60,4% medidos em oito anos
                  # e 53,0% medidos em vinte aparecem lado a lado como se fossem comparáveis.
                  "divisoes_usadas", "inicio_medido", "fim_medido"]


def monta_alertas(aprovados, estados, total_papeis=None):
    """
    LAÇO 2 — cruza os setups aprovados com o estado de hoje e agrupa o que disparou.

    Por que existe: a planilha do estudo diz quais setups protegem; o laço 1 diz quais janelas estão
    acionadas hoje. O alerta é a interseção. Pura, para os testes cobrirem o cruzamento sem rede.

    A linha "menos pior" dos papéis sem nenhum setup aprovado (a IRBR3) é descartada aqui: ela pode
    disparar o decil, mas não é gatilho, e exibi-la ao lado dos aprovados apresentaria como sinal o
    que a própria planilha marca como ausência de sinal.

    Entrada: aprovados (DataFrame da aba `aprovados`), estados (dicionário {(papel, janela): bool}),
    total_papeis (quantos papéis o ranking classificou; ausente, sai da própria tabela).
    Fase 0: o denominador do ranking, que acompanha cada linha até a página.
    Fase 1: descartar as linhas que não são gatilho e as janelas que não dispararam.
    Fase 2: por papel e horizonte, agrupar as janelas em faixas contíguas.
    Fase 3: cada faixa vira uma linha, com os números do MELHOR setup dela — nunca uma média entre
            setups, que seria um número que ninguém mediu.
    Saída: DataFrame com uma linha por (papel, horizonte, faixa contígua).
    """
    # Fase 0: a colocação sozinha não diz nada — "#31" é meio de tabela em 61 papéis e é o fim dela
    # em 32. O denominador vem da tabela inteira, antes de qualquer filtro, e viaja como coluna para
    # a renderização não precisar de um argumento a mais.
    if total_papeis is None:
        total_papeis = int(aprovados["posicao_papel"].max()) if len(aprovados) else 0
    total_papeis = int(total_papeis)

    # Fase 1: só gatilhos de verdade, e só as janelas acionadas hoje.
    a = aprovados[aprovados["passa_barra"].astype(bool)].copy()
    a = a[[bool(estados.get((t, int(w)), False))
           for t, w in zip(a["ticker"], a["janela"])]]
    if a.empty:
        return pd.DataFrame(columns=COLUNAS_ALERTA)

    linhas = []
    # Fase 2: cada papel, cada horizonte.
    for (ticker, h), d in a.groupby(["ticker", "horizonte"]):
        for inicio, fim in agrupa_faixas_contiguas(d["janela"]):
            # As linhas desta faixa contígua.
            faixa = d[(d["janela"] >= inicio) & (d["janela"] <= fim)]
            # Fase 3: o melhor setup da faixa representa a faixa.
            melhor = faixa.nlargest(1, "prot_lo").iloc[0]
            linhas.append({
                "posicao_papel": int(melhor["posicao_papel"]), "total_papeis": total_papeis,
                "ticker": ticker,
                "horizonte": int(h), "janela_de": int(inicio), "janela_ate": int(fim),
                "n_setups": int(len(faixa)), "episodios": int(melhor["episodios"]),
                "protecao": float(melhor["protecao"]), "prot_lo": float(melhor["prot_lo"]),
                "taxa_base": float(melhor["taxa_base"]),
                "divisoes_usadas": int(melhor["divisoes_usadas"]),
                "inicio_medido": str(melhor["inicio_medido"]),
                "fim_medido": str(melhor["fim_medido"]),
            })
    # Saída: do setup mais sustentado para o menos, dentro de cada horizonte.
    return (pd.DataFrame(linhas)[COLUNAS_ALERTA]
            .sort_values(["horizonte", "prot_lo"], ascending=[True, False])
            .reset_index(drop=True))


def _linha_html(r):
    """Uma linha da tabela de alertas (helper de renderização)."""
    # Faixa de uma janela só aparece como número simples; faixa larga mostra o intervalo.
    faixa = (f"{r['janela_de']}" if r["janela_de"] == r["janela_ate"]
             else f"{r['janela_de']}–{r['janela_ate']}")
    # O número de setups da faixa fica ao lado, para o leitor saber que são janelas vizinhas.
    setups = "" if r["n_setups"] == 1 else f" <span class='posicao'>({r['n_setups']})</span>"
    # A colocação vai com o denominador: "#31/61" se lê sozinho, "#31" precisa de contexto externo.
    lugar = f"#{r['posicao_papel']}/{r['total_papeis']}"
    # O período em que a taxa-base daquele papel foi medida, em anos. Abaixo de três épocas o
    # resultado é divisão única, não validação encadeada — e a marca avisa isso sem texto extra.
    periodo = f"{str(r['inicio_medido'])[:4]}–{str(r['fim_medido'])[:4]}"
    epocas = f" <span class='posicao'>({r['divisoes_usadas']})</span>"
    return (f"<tr>"
            f"<td class='esq papel'>{r['ticker']} <span class='posicao'>{lugar}</span></td>"
            f"<td class='esq'>{faixa}{setups}</td>"
            f"<td class='destaque'>{100 * r['protecao']:.1f}%</td>"
            f"<td>{100 * r['prot_lo']:.1f}%</td>"
            f"<td>{100 * r['taxa_base']:.1f}%</td>"
            f"<td class='esq'><span class='posicao'>{periodo}</span>{epocas}</td>"
            f"</tr>")


def monta_pagina(template, alertas, data_pregao, n_papeis):
    """
    Preenche o template: a barra de abas, o cabeçalho da leitura e as seções por horizonte.

    Por que existe: separa a renderização do cálculo, para o teste da página não precisar de rede e
    para o texto poder ser revisto sem tocar na medição.

    Cada horizonte vira uma seção própria, e não uma coluna de uma tabela única, porque é o
    horizonte que define **quanto tempo a afirmação cobre** — misturar tudo numa lista apagaria a
    diferença entre "positivo em 3 pregões" e "positivo em 45", que não são a mesma promessa.

    Entrada: template (string com os marcadores), alertas (DataFrame de `monta_alertas`),
    data_pregao, n_papeis.
    Fase 1: sem nenhum alerta, desenhar o vazio — é o caso COMUM e precisa ser explícito, nunca
            parecer que a página quebrou.
    Fase 2: com alertas, o cabeçalho de leitura mais uma seção por horizonte presente.
    Fase 3: a barra de abas, com o contador do dia, e os demais marcadores.
    Saída: string com o HTML completo.
    """
    papeis_alerta = int(alertas["ticker"].nunique()) if len(alertas) else 0
    # Fase 1: dia sem alerta. Sem cor de alarme e sem cor de acento: um dia sem gatilho não é um
    # evento, e pintá-lo sugeriria que algo aconteceu ou falhou.
    if alertas.empty:
        corpo = (
            "<section class='vazio'>"
            "<div class='rotulo'>gatilhos acionados no fechamento</div>"
            "<h1>Nenhum gatilho hoje</h1>"
            f"<p>Nenhum dos {n_papeis} papéis fechou no decil mais afastado para baixo de uma "
            "janela que o estudo aprovou. <b>É o resultado esperado na maioria dos pregões</b> — os "
            "episódios são raros por definição, e um dia sem sinal não é uma falha da tela.</p>"
            "<div class='atalho'><a class='baixar' href='index.html'>"
            "← ver onde cada papel está na escala</a></div>"
            "</section>")
    else:
        # Fase 2: o cabeçalho da leitura, com o número que resume o dia.
        pl = "s" if len(alertas) > 1 else ""
        pp = "papéis" if papeis_alerta > 1 else "papel"
        partes = [
            "<section class='mestra'><div class='mestra-topo'><div>"
            "<div class='rotulo'>gatilhos acionados no fechamento</div>"
            f"<h1>{len(alertas)} gatilho{pl} em {papeis_alerta} {pp}</h1>"
            "<p class='sub'>Cada linha é um papel que fechou no decil mais afastado para baixo de "
            "uma janela que o estudo aprovou <em>para ele</em>. A afirmação é sobre <b>não "
            "perder</b>, e não sobre quanto se ganha.</p>"
            f"</div><div class='veredito v-zona'>{papeis_alerta} {pp}</div>"
            "</div></section>"]
        # Uma seção por horizonte, do mais curto para o mais longo.
        for h in sorted(alertas["horizonte"].unique()):
            d = alertas[alertas["horizonte"] == h]
            linhas = "".join(_linha_html(r) for _, r in d.iterrows())
            partes.append(
                f"<div class='secao'><h2>Horizonte de {h} pregões</h2></div>"
                f"<div class='quadro'><table><thead><tr>"
                f"<th class='esq'>papel</th>"
                f"<th class='esq'>janela <span class='sub2'>(faixa de janelas)</span></th>"
                f"<th>proteção</th><th>limite inferior</th><th>taxa-base</th>"
                f"<th class='esq'>período medido <span class='sub2'>(épocas)</span></th>"
                f"</tr></thead><tbody>{linhas}</tbody></table></div>")
        corpo = "".join(partes)

    # Fase 3: os marcadores. A barra vem de `publicacao` para ser idêntica nas três páginas.
    for marca, valor in (("ABAS", barra_de_abas("gatilhos", papeis_alerta)),
                         ("CORPO", corpo),
                         ("DATA_PREGAO", data_pregao),
                         ("N_PAPEIS", str(n_papeis))):
        template = template.replace("{{" + marca + "}}", valor)
    return template


def main() -> None:
    """
    Invólucro de entrada e saída: lê os setups exportados, roda os dois laços e grava a página.

    Fase 1: ler `estudo/setups.csv` e descobrir, por papel, quais janelas verificar e com que corte.
    Fase 2: LAÇO 1 — por papel, baixar só a história necessária e medir o estado de cada janela.
    Fase 3: LAÇO 2 — cruzar com os setups aprovados e agrupar em faixas contíguas.
    Fase 4: renderizar, gravar e registrar o estado do dia para as outras duas páginas.
    """
    raiz = Path(__file__).resolve().parent
    # Fase 1: os setups vindos do laboratório. Este repositório não faz a varredura.
    caminho = raiz / config.ARQUIVO_SETUPS
    if not caminho.exists():
        raise SystemExit(
            f"{caminho} não existe. Ele é gerado no laboratório "
            "(`rebuild_robusta_backtests`) por `robusta_ml.exporta_setups` — ver "
            "`estudo/PROVENIENCIA.md`.")
    aprovados = pd.read_csv(caminho)
    # O denominador do ranking sai daqui, ANTES de qualquer filtro: rodar para um papel só não pode
    # transformar "#31/61" em "#31/31".
    total_papeis = int(aprovados["posicao_papel"].max())
    # Um papel pode vir pela linha de comando, para conferência rápida.
    if len(sys.argv) > 1:
        aprovados = aprovados[aprovados["ticker"] == sys.argv[1]]
        if aprovados.empty:
            raise SystemExit(f"{sys.argv[1]} não está entre os papéis do estudo")
    # O corte de cada (papel, janela) vem medido sobre a história completa. Recalculá-lo com a
    # história curta daqui foi o defeito de 06/09: na GGBR4 o corte trocava de sinal.
    cortes_por_papel = {t: dict(zip(d["janela"].astype(int), d["corte"]))
                        for t, d in aprovados.groupby("ticker")}
    papeis = sorted(aprovados["ticker"].unique())
    print(f"TELA DE GATILHOS — {len(papeis)} papéis, {len(aprovados)} setups do estudo")
    print(f"  faixa que dispara: decil {config.FAIXA_ALVO} (o mais afastado para baixo)")
    print("  cortes vindos do laboratório, medidos sobre a história completa de cada papel")

    # Fase 2: LAÇO 1. A barra da tqdm dá o andamento — são 61 downloads, cerca de um minuto — e o
    # contador ao lado mostra o placar de gatilhos em tempo real, para uma execução em que nada
    # dispara não parecer travada. `file=sys.stdout` porque o resumo final usa print: com a barra no
    # stderr (o padrão da tqdm), os dois fluxos se intercalam fora de ordem no log do GitHub Actions.
    estados, falhas, data_pregao = {}, [], ""
    disparando = 0
    barra = tqdm(papeis, desc="papéis", unit="papel", ncols=78, file=sys.stdout)
    for t in barra:
        janelas = sorted(cortes_por_papel[t])
        # Quanto baixar: sai da maior janela do papel, não de um número fixo. E é pouco, porque o
        # corte já vem medido — aqui só se precisa do escore de HOJE.
        precisa = pregoes_necessarios(max(janelas), config.VOL_LAG, config.FOLGA_PREGOES)
        periodo = periodo_do_download(precisa, config.PREGOES_POR_ANO)
        try:
            prices = apara_inicio(load_prices(f"{t}{config.TICKER_SUFFIX}", periodo))
        except Exception as erro:
            falhas.append((t, str(erro)))
            # `barra.write` em vez de `print`, senão a linha embaralha a barra em andamento.
            barra.write(f"  ERRO {t:<8} {erro}")
            barra.set_postfix_str(f"gatilhos {disparando} | falhas {len(falhas)}")
            continue
        # A data do pregão é a do último fechamento disponível, igual para todos.
        data_pregao = max(data_pregao, str(prices.index[-1].date()))
        e = estado_das_janelas(prices, cortes_por_papel[t], config.VOL_LAG, config.SLOPE_LAG)
        for _, r in e.iterrows():
            estados[(t, int(r["janela"]))] = bool(r["dispara"])
        # Só quem dispara merece uma linha: sessenta linhas de "sem disparo" enterrariam as três que
        # interessam. Quem ficou sem medida aparece junto, porque ausência de medida não é ausência
        # de gatilho e a diferença precisa ser visível.
        n_disparo = int(e["dispara"].sum())
        n_sem = int(e["motivo"].astype(bool).sum())
        if n_disparo:
            disparando += 1
            extra = f" | {n_sem} sem história" if n_sem else ""
            barra.write(f"  DISPAROU {t:<8} {n_disparo}/{len(janelas)} janelas{extra}")
        elif n_sem == len(janelas):
            # Nenhuma janela pôde ser medida: silêncio aqui seria confundido com "não disparou".
            barra.write(f"  sem medida {t:<8} {periodo} não cobre os {precisa} pregões necessários")
        barra.set_postfix_str(f"gatilhos {disparando} | falhas {len(falhas)}")
    barra.close()

    # Fase 3: LAÇO 2.
    alertas = monta_alertas(aprovados, estados, total_papeis)
    n_papeis_alerta = int(alertas["ticker"].nunique()) if len(alertas) else 0
    print(f"\n  {len(alertas)} gatilhos acionados em {n_papeis_alerta} papéis")
    if falhas:
        print(f"  {len(falhas)} papéis falharam no download: {', '.join(t for t, _ in falhas)}")

    # Fase 4: a página, os estáticos e o estado do dia.
    saida = raiz / config.DIR_SAIDA
    html = monta_pagina((raiz / "template_alertas.html").read_text(encoding="utf-8"),
                        alertas, data_pregao, len(papeis))
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "alertas.html").write_text(html, encoding="utf-8", newline="\n")
    copia_estatica(raiz, saida)
    alertas.to_csv(saida / "alertas.csv", index=False, lineterminator="\n")
    # O estado é o que permite à triagem exibir o contador sem refazer 61 downloads.
    grava_estado(saida, n_papeis_alerta, len(alertas), data_pregao)
    print(f"Página gravada em {saida / 'alertas.html'}")


if __name__ == "__main__":
    main()

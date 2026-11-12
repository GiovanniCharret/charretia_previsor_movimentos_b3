"""
Os gráficos por papel da faixa extrema (v3): o retorno em 45 pregões em cada faixa da distância.

Por que este módulo existe: o usuário quer **ver**, para cada papel em destaque, o que veio depois
de dias em cada faixa de afastamento da média — e em que faixa o papel está hoje — sem abrir a
planilha (pedido de 11/11/2026). Uma página por papel, aberta pela coluna "gráficos" da tabela da
v3, com um seletor das nove janelas.

O eixo horizontal são as faixas da distância normalizada (a mesma fórmula da v3: distância até a
média dividida pelo desvio-padrão móvel dela). São os dez decis, com o decil 0 aberto em 0–2,5%,
2,5–5% e 5–10%, para os extremos da v3 aparecerem em detalhe. O eixo vertical é o retorno em 45
pregões. Cada faixa mostra a distribuição como caixa: do percentil 25 ao 75, com a mediana, e
hastes do 10 ao 90.

**É uma leitura descritiva**: as faixas vêm da história inteira do papel, e não da validação
encadeada que sustenta a frequência da tabela. A página diz isso. Os números que decidem quem é
destaque continuam vindo do laboratório.
"""

import json                                                 # dados embutidos na página
from html import escape                                     # texto seguro no HTML

import numpy as np                                          # quantis
import pandas as pd                                         # séries

from nucleo import config                                   # parâmetros das telas
from nucleo.data import load_prices                         # download (único ponto de rede)
from nucleo.qualidade_dados import apara_inicio             # corta a cabeça anterior à listagem
from nucleo.features_mma import build_features              # distância até a média
from nucleo.faixas import add_dist_zscore                   # distância ÷ desvio-padrão móvel

# As bordas das faixas, em fração da história: 2,5%, 5% e depois os decis.
BORDAS = [0.025, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]

# O nome de cada faixa, na ordem do eixo — da mais afastada para baixo à mais afastada para cima.
ROTULOS = ["0–2,5%", "2,5–5%", "5–10%"] + [f"decil {d}" for d in range(1, 10)]


def resumo_por_faixa(prices, janelas, horizonte, vol_lag, slope_lag):
    """
    Para cada janela, a distribuição do retorno seguinte em cada faixa, e a faixa de hoje.

    Por que existe: é a conta inteira dos gráficos, separada da página para ser testada sem rede.

    Entrada: prices (OHLCV já aparado, história completa), janelas, horizonte, vol_lag, slope_lag.
    Fase 1: construir o escore de todas as janelas e o retorno seguinte uma vez.
    Fase 2: por janela, as bordas das faixas sobre a história inteira do escore.
    Fase 3: por faixa, os quantis do retorno, a fração de dias sem perda e a contagem.
    Fase 4: a faixa e o escore de hoje (a última linha, que ainda não tem retorno seguinte).
    Saída: dicionário {janela: {"faixas": [...], "hoje": índice da faixa, "escore_hoje": valor}}.
    """
    # Fase 1: uma construção só para todas as janelas.
    df, _feats = build_features(prices.copy(), list(janelas), [0.0], [1], slope_lag)
    df = add_dist_zscore(df, list(janelas), vol_lag)
    retorno = df["Close"].shift(-horizonte) / df["Close"] - 1
    saida = {}
    for w in janelas:
        z = df[f"mma_dist_z_w{w}"]
        validos = z.dropna()
        # Sem história bastante, a janela fica fora da página.
        if len(validos) < 500:
            continue
        # Fase 2: as bordas vêm da história inteira do escore (leitura descritiva).
        bordas = np.quantile(validos.to_numpy(), BORDAS)
        # O índice da faixa de cada dia: 0 para "0–2,5%", 11 para o decil 9.
        faixa = pd.Series(np.searchsorted(bordas, validos.to_numpy(), side="left"), index=validos.index)
        faixas = []
        for k, rotulo in enumerate(ROTULOS):
            # Fase 3: só os dias daquela faixa que já têm retorno seguinte.
            r = retorno.reindex(faixa.index[faixa == k]).dropna().to_numpy()
            if len(r) == 0:
                faixas.append({"rotulo": rotulo, "n": 0})
                continue
            p10, p25, p50, p75, p90 = np.quantile(r, [0.10, 0.25, 0.50, 0.75, 0.90])
            faixas.append({"rotulo": rotulo, "n": int(len(r)), "p10": float(p10), "p25": float(p25),
                           "p50": float(p50), "p75": float(p75), "p90": float(p90),
                           "nao_perdeu": float((r >= 0).mean())})
        # Fase 4: onde o papel está hoje.
        saida[int(w)] = {"faixas": faixas, "hoje": int(faixa.iloc[-1]),
                         "escore_hoje": float(validos.iloc[-1]),
                         "inicio": str(validos.index[0].date())}
    # Saída: uma entrada por janela com história bastante.
    return saida


def pagina_graficos(ticker, resumo, data_pregao, horizonte, janelas_no_extremo=()):
    """
    A página interativa de um papel: seletor das janelas e o gráfico de caixas.

    Por que existe: separa o HTML da conta, para os testes cobrirem a página sem rede.

    Entrada: ticker, resumo (saída de `resumo_por_faixa`), data_pregao, horizonte,
    janelas_no_extremo (as que o puseram na tabela hoje; a página abre na primeira delas).
    Fase 1: escolher a janela inicial e montar os botões.
    Fase 2: embutir os dados e o desenho, que é feito no navegador a partir deles.
    Saída: string com o HTML completo.
    """
    janelas = sorted(resumo)
    # Fase 1: abre numa janela que explica por que o papel está na tabela.
    inicial = next((w for w in janelas_no_extremo if w in resumo), janelas[0] if janelas else None)
    botoes = ""
    for w in janelas:
        # A borda colorida marca as janelas que puseram o papel na tabela hoje.
        classe = "jan no-extremo" if w in janelas_no_extremo else "jan"
        # A janela inicial já abre marcada como selecionada.
        marcado = ' aria-pressed="true"' if w == inicial else ""
        botoes += f"<button type='button' data-w='{w}' class='{classe}'{marcado}>{w}</button>"
    # Fase 2: os dados vão como texto JSON; o desenho é refeito a cada troca de janela.
    dados = json.dumps({str(w): resumo[w] for w in janelas}, ensure_ascii=False)
    t = escape(ticker)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CharretIA — {t} por faixa</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;1,8..60,400&display=swap">
<link rel="stylesheet" href="../estilo.css">
<link rel="stylesheet" href="../estilo_componentes.css">
<style>
  .seletor {{ display:flex; flex-wrap:wrap; gap:6px; margin:14px 0 6px; }}
  .jan {{ font-family:var(--mono); font-size:13px; padding:6px 12px; border:1px solid var(--rule-forte);
          background:var(--surface); color:var(--ink-2); border-radius:4px; cursor:pointer; }}
  .jan.no-extremo {{ border-color:var(--acento); color:var(--acento); }}
  .jan[aria-pressed="true"] {{ background:var(--acento); color:var(--surface); border-color:var(--acento); }}
  .jan:focus-visible {{ outline:2px solid var(--acento); outline-offset:2px; }}
  .grafico {{ background:var(--surface); border:1px solid var(--rule); padding:12px; overflow-x:auto; }}
  .grafico svg {{ width:100%; min-width:640px; height:auto; display:block; font-family:var(--mono); }}
  .caixa {{ fill:var(--fraca-fundo); stroke:var(--fraca); }}
  .caixa.hoje {{ fill:var(--acento-fundo); stroke:var(--acento); stroke-width:2; }}
  .haste {{ stroke:var(--fraca); }} .haste.hoje {{ stroke:var(--acento); }}
  .mediana {{ stroke:var(--ink); stroke-width:2; }}
  .zero {{ stroke:var(--alerta); stroke-dasharray:4 3; }}
  .grade {{ stroke:var(--rule); }}
  .eixo {{ fill:var(--ink-3); font-size:11px; }}
  .eixo.hoje {{ fill:var(--acento); font-weight:700; }}
  .resumo-janela {{ font-family:var(--mono); font-size:13px; color:var(--ink-2); margin:8px 0 0; }}
</style>
</head>
<body>
<div class="env">
  <header>
    <div>
      <div class="marca">Charret<span>IA</span></div>
      <div class="rotulo" style="margin-top:6px">faixa extrema — {t} por faixa de afastamento</div>
    </div>
    <div class="carimbo">pregão de <b>{escape(data_pregao)}</b><br>retorno em {int(horizonte)} pregões</div>
  </header>

  <section class="mestra">
    <div class="rotulo">o que veio depois de cada faixa</div>
    <h1>{t}</h1>
    <p class="sub">Cada caixa mostra o retorno em {int(horizonte)} pregões dos dias em que o papel
    esteve naquela faixa de afastamento da média: a caixa vai do percentil 25 ao 75, o traço escuro
    é a mediana e as hastes vão do percentil 10 ao 90. A linha tracejada é o zero — acima dela, o
    papel não perdeu. <b>A faixa de hoje está destacada.</b> As janelas com borda colorida são as
    que puseram o papel na tabela hoje.</p>
    <div class="seletor" role="group" aria-label="janela da média móvel, em pregões">{botoes}</div>
    <p class="resumo-janela" id="resumo"></p>
  </section>

  <div class="grafico"><svg id="g" viewBox="0 0 880 380" role="img" aria-label="retorno por faixa"></svg></div>

  <section class="glossario"><div class="leitura"><dl>
    <div class="verbete"><dt>faixa</dt><dd>A distância do fechamento até a média móvel, dividida pelo
    desvio-padrão dela no último ano, comparada com a história inteira do papel. "0–2,5%" são os
    2,5% de dias mais afastados para baixo; "decil 9", os 10% mais afastados para cima.</dd></div>
    <div class="verbete"><dt>leitura descritiva</dt><dd>As faixas daqui vêm da história inteira, e
    não da validação com treino e teste que sustenta a frequência da tabela. Servem para ver a forma
    da relação, não para medir vantagem.</dd></div>
    <div class="verbete"><dt>não perdeu</dt><dd>Fração dos dias da faixa em que o fechamento
    {int(horizonte)} pregões depois foi maior ou igual ao do dia.</dd></div>
  </dl></div></section>

  <div class="rodape leitura"><p><a href="../extremos.html">← Faixa extrema</a></p></div>
</div>
<script>
const DADOS = {dados};
const svg = document.getElementById("g"), resumo = document.getElementById("resumo");
const NS = "http://www.w3.org/2000/svg";
function el(nome, attrs, texto) {{
  const e = document.createElementNS(NS, nome);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (texto !== undefined) e.textContent = texto;
  svg.appendChild(e); return e;
}}
const pct = v => (100 * v).toFixed(1).replace(".", ",") + "%";
function desenha(w) {{
  const d = DADOS[w]; svg.innerHTML = "";
  const fx = d.faixas.filter(f => f.n > 0);
  const lo = Math.min(0, ...fx.map(f => f.p10)), hi = Math.max(0, ...fx.map(f => f.p90));
  const E = 64, D = 16, T = 16, B = 300, larg = (880 - E - D) / d.faixas.length;
  const y = v => T + (hi - v) / (hi - lo || 1) * (B - T);
  for (let i = 0; i <= 4; i++) {{
    const v = lo + (hi - lo) * i / 4, yy = y(v);
    el("line", {{x1: E, x2: 880 - D, y1: yy, y2: yy, class: "grade"}});
    el("text", {{x: E - 6, y: yy + 4, "text-anchor": "end", class: "eixo"}}, pct(v));
  }}
  el("line", {{x1: E, x2: 880 - D, y1: y(0), y2: y(0), class: "zero"}});
  d.faixas.forEach((f, i) => {{
    const cx = E + larg * (i + 0.5), w2 = larg * 0.32, h = i === d.hoje ? " hoje" : "";
    el("text", {{x: cx, y: B + 18, "text-anchor": "middle", class: "eixo" + h}}, f.rotulo);
    el("text", {{x: cx, y: B + 34, "text-anchor": "middle", class: "eixo" + h}},
       f.n ? pct(f.nao_perdeu) : "—");
    el("text", {{x: cx, y: B + 50, "text-anchor": "middle", class: "eixo" + h}}, f.n ? f.n + " dias" : "");
    if (!f.n) return;
    el("line", {{x1: cx, x2: cx, y1: y(f.p90), y2: y(f.p10), class: "haste" + h}});
    el("rect", {{x: cx - w2, y: y(f.p75), width: 2 * w2, height: Math.max(1, y(f.p25) - y(f.p75)),
                 class: "caixa" + h}});
    el("line", {{x1: cx - w2, x2: cx + w2, y1: y(f.p50), y2: y(f.p50), class: "mediana"}});
  }});
  el("text", {{x: 8, y: B + 34, class: "eixo"}}, "não perdeu");
  const f = d.faixas[d.hoje];
  resumo.textContent = `média de ${{w}} pregões · hoje na faixa ${{f.rotulo}} (escore ` +
    `${{d.escore_hoje.toFixed(2).replace(".", ",")}}) · história desde ${{d.inicio}}` +
    (f.n ? ` · nessa faixa, não perdeu em ${{pct(f.nao_perdeu)}} de ${{f.n}} dias` : "");
}}
document.querySelectorAll(".jan").forEach(b => b.addEventListener("click", () => {{
  document.querySelectorAll(".jan").forEach(x => x.removeAttribute("aria-pressed"));
  b.setAttribute("aria-pressed", "true"); desenha(b.dataset.w);
}}));
{f'desenha("{inicial}");' if inicial is not None else ''}
</script>
</body>
</html>
"""


def grava_graficos(pasta, ticker, data_pregao, janelas_no_extremo=()):
    """
    Baixa a história completa de um papel e grava a página dos gráficos dele.

    Por que existe: as telas baixam só o necessário para o escore do dia; os gráficos precisam da
    história inteira. Feito só para os destaques, e uma falha não derruba a tabela — o papel fica
    sem o link.

    Entrada: pasta (onde gravar), ticker, data_pregao, janelas_no_extremo.
    Fase 1: baixar tudo e aparar.
    Fase 2: o resumo das nove janelas e a página.
    Saída: True quando a página foi gravada; False quando não foi possível.
    """
    try:
        # Fase 1: a história completa.
        prices = apara_inicio(load_prices(f"{ticker}{config.TICKER_SUFFIX}", config.EXTREMOS_PERIOD))
        # Fase 2: as nove janelas da v3, no horizonte de 45 pregões.
        resumo = resumo_por_faixa(prices, config.GRAFICOS_JANELAS, config.GRAFICOS_HORIZONTE,
                                  config.VOL_LAG, config.SLOPE_LAG)
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{ticker}.html").write_text(
            pagina_graficos(ticker, resumo, data_pregao, config.GRAFICOS_HORIZONTE,
                            list(janelas_no_extremo)), encoding="utf-8", newline="\n")
        return True
    except Exception as erro:
        print(f"  gráficos de {ticker} não gerados: {erro}", flush=True)
        return False


def link_graficos(ticker):
    """O link da página de gráficos de um papel, na coluna antes de "dados" (helper)."""
    return (f"<a class='baixar compacto' href='graficos/{escape(ticker)}.html' "
            f"title='gráficos de {escape(ticker)} por faixa'>gráficos</a>")

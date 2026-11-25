"""
Gerador da tela diária de triagem — preenche `template.html` com os dados do pregão mais recente.

Por que este módulo existe: o estudo, no repositório irmão `robusta_backtest`, responde "existe
efeito?"; este projeto responde "como está hoje?". São coisas diferentes, com ciclos de vida
diferentes, e por isso vivem em repositórios separados — aqui não se mede nada novo, apenas se
aplica o que já foi medido e validado fora da amostra.

O que a tela mostra, e por quê:
  - **Só o índice.** O efeito medido é de mercado inteiro (aparece no próprio BOVA11). Até
    23/11/2026 havia também uma tabela de detalhamento por papel; o usuário a retirou por ser
    ruído, e a leitura por papel vive na faixa extrema (v3). Por isso só o índice é baixado.
  - **Evidência ao lado do sinal.** Episódios independentes, frequência de acerto e a taxa-base
    aparecem junto do decil de hoje. Sinal sem a força da evidência engana.

Disciplina mantida do estudo: cortes de decil calculados só no treino, desvio-padrão móvel causal,
embargo igual ao horizonte, e peneira de qualidade de dados antes de qualquer cálculo.
"""

from datetime import datetime, timedelta, timezone          # carimbo de execução
from pathlib import Path                                    # caminhos
import sys                                                  # fluxo de saída único para a barra
import numpy as np                                          # medidas
import pandas as pd                                         # séries e datas

from nucleo import config                                   # parâmetros do estudo
from publicacao import (barra_de_abas, copia_estatica,      # o que as 3 páginas dividem
                        le_estado)
from nucleo.data import load_prices                         # download (único ponto de rede)
from nucleo.target import add_forward_returns               # alvos ret_{h}d
from nucleo.features_mma import build_features              # distância até a média
from nucleo.qualidade_dados import avalia_qualidade         # peneira obrigatória
from nucleo.faixas import (add_dist_zscore, quantis_do_treino, atribui_faixa,
                           divide_por_calendario, conta_episodios)

# Marcadores que o template espera. Existe como constante para o teste poder garantir que nenhum
# sobrou na página final — marcador não substituído é bug visível para quem lê.
MARCADORES = ["TITULO_INDICE", "SUB_INDICE", "VEREDITO", "CLASSE_VEREDITO",
              "REGUA", "MEDIDAS", "BAIXAR_INDICE", "CARIMBO",
              # Os dois últimos vieram com a segunda tela (07/09/2026): a barra de navegação, que
              # `publicacao.barra_de_abas` monta igual para as três páginas, e a frase de rodapé que
              # leva à tela de gatilhos — sem ela, a segunda página depende de o visitante reparar
              # na barra de abas.
              "ABAS", "TRAVESSIA"]

# Fuso de Brasília como deslocamento FIXO, e não `ZoneInfo("America/Sao_Paulo")`: o Windows não traz
# a base IANA, então `zoneinfo` puxaria o pacote `tzdata` para dentro do requirements só por causa
# desta linha. O Brasil extinguiu o horário de verão em 2019, então UTC-3 vale o ano inteiro e a
# simplificação não erra. Se o horário de verão voltar, é aqui que se conserta.
FUSO_BRASILIA = timezone(timedelta(hours=-3))

# Decis considerados "zona de viés observado" (os três mais afastados para baixo).
ZONA = (0, 1, 2)

# Decil de alerta de "ganhar menos" (pedido do usuário, 25/11/2026). No teste da v1 na forma da v3,
# o decil 9 do Ibovespa (cinco divisões, dias, frequência de não perder) foi a única leitura que
# passou a correção: −20,8 pontos, valor-p corrigido 0,020. No BOVA11, mesma direção sem passar.
ALERTA = (9,)

def estado_de_hoje(prices, window, horizon, slope_lag, vol_lag, n_faixas, data_inicio_teste):
    """
    Em que decil o papel está HOJE, e o que historicamente veio depois de dias nesse decil.

    Por que existe: é a ponte entre o estudo e a tela. O estudo mede decis sobre linhas que já têm
    retorno futuro conhecido; a tela precisa da posição do **último pregão**, que por definição
    ainda não tem retorno futuro. Misturar as duas coisas faria a tela exibir a posição de
    `horizon` pregões atrás — um erro silencioso e grave.

    Entrada: prices (OHLCV) e os parâmetros do estudo.
    Fase 1: construir distância até a média e o escore padronizado.
    Fase 2: sobre as linhas COM retorno futuro, dividir treino/teste e achar os cortes de decil
            usando somente o treino.
    Fase 3: medir, no teste, o que veio depois dos dias de cada decil.
    Fase 4: aplicar os mesmos cortes à série completa e ler o decil da ÚLTIMA linha — o de hoje.
    Fase 5: montar a tabela auditável que a tela oferece para download.
    Saída: dict com decil de hoje, distância, as estatísticas históricas daquele decil, e sob a
    chave "df" a tabela linha a linha que gerou tudo isso.
    """
    # Fase 1: distância e escore padronizado da janela pedida.
    df, _feats = build_features(prices.copy(), [window], [0.0], [1], slope_lag)
    df = add_dist_zscore(df, [window], vol_lag)
    df = add_forward_returns(df, [horizon])
    col_z, col_d = f"mma_dist_z_w{window}", f"mma_dist_w{window}"

    # Fase 2: só as linhas com retorno futuro conhecido servem para calibrar e medir.
    d = df[[col_z, f"ret_{horizon}d"]].dropna().astype(float)
    tr, te = divide_por_calendario(d.index, data_inicio_teste, embargo=horizon)
    cortes = quantis_do_treino(d[col_z], tr, n_faixas)
    faixa = atribui_faixa(d[col_z], cortes)
    y = d[f"ret_{horizon}d"]

    # Fase 4 (antes da 3 porque define QUAL decil medir): decil do último pregão disponível.
    z_completo = df[col_z].dropna()
    faixa_completa = atribui_faixa(z_completo, cortes)
    hoje = int(faixa_completa.iloc[-1])

    # Fase 3: histórico do teste restrito ao decil de hoje.
    pos = te[(faixa.iloc[te] == hoje).values]
    base = float(y.iloc[te].mean()) if len(te) else float("nan")
    media = float(y.iloc[pos].mean()) if len(pos) else float("nan")

    # Fase 5: a tabela auditável. Cobre todas as linhas com escore válido — inclusive as recentes
    # que ainda não têm retorno futuro, sem as quais o pregão de hoje não apareceria no arquivo.
    estudo = df.loc[z_completo.index, ["Close", f"mma_w{window}", col_d, col_z,
                                       f"ret_{horizon}d"]].copy()
    estudo["faixa"] = faixa_completa
    # `conjunto` é a coluna que torna a disciplina anti-vazamento verificável por fora: começa
    # como "sem_retorno" (linhas sem alvo conhecido), e só as linhas que ENTRARAM no cálculo
    # recebem rótulo. As que sobram como "embargo" são exatamente as descartadas entre treino e
    # teste — vê-las no arquivo é a prova de que o descarte aconteceu.
    estudo["conjunto"] = "sem_retorno"
    estudo.loc[d.index, "conjunto"] = "embargo"
    estudo.loc[d.index[tr], "conjunto"] = "treino"
    estudo.loc[d.index[te], "conjunto"] = "teste"
    estudo.index.name = "data"

    # Saída: tudo que uma linha da tela precisa, mais a tabela que a originou.
    return {"decil": hoje, "dist": float(df[col_d].dropna().iloc[-1]),
            "media": media, "base": base, "excesso": media - base,
            "freq_pos": float((y.iloc[pos] > 0).mean()) if len(pos) else float("nan"),
            "episodios": conta_episodios(pos, horizon), "n_dias": int(len(pos)),
            "df": estudo}


def _pct(v, casas=1, sinal=False):
    """Formata fração como porcentagem no padrão brasileiro (vírgula decimal), tolerando NaN."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    txt = f"{100*v:+.{casas}f}" if sinal else f"{100*v:.{casas}f}"
    return txt.replace(".", ",") + "%"


def _carimbo(agora=None):
    """
    Formata o instante da execução no horário de Brasília, como a página o exibe.

    Por que existe: a tela é gerada por um robô e publicada sozinha, então quem abre a página não
    tem como saber se está lendo o pregão de hoje ou uma publicação que travou há três dias. O
    carimbo é a única parte da tela que o leitor pode conferir contra o próprio relógio.

    Entrada: agora (datetime; `None` = o instante atual).
    Fase 1: sem argumento, ler o relógio já no fuso de Brasília.
    Fase 2: com argumento consciente de fuso, converter — o GitHub Actions roda em UTC, e sem esta
            conversão a página anunciaria 21h34 para um fechamento das 18h34.
    Saída: string no padrão brasileiro, "23/08/2026 às 18h34".
    """
    # Fase 1: o instante atual já nasce no fuso certo.
    if agora is None:
        agora = datetime.now(FUSO_BRASILIA)
    # Fase 2: converter o que vier de outro fuso (datetime ingênuo é usado como está).
    elif agora.tzinfo is not None:
        agora = agora.astimezone(FUSO_BRASILIA)
    # Saída: dia/mês/ano e hora no formato que se lê em voz alta em português.
    return agora.strftime("%d/%m/%Y às %Hh%M")


def _link_download(ticker, compacto=False):
    """
    Link para a planilha de estudo do papel, no formato que o navegador salva em vez de abrir.

    Por que existe: o caminho do arquivo é derivado do ticker na página e na gravação em `main()`;
    centralizar aqui garante que os dois tenham a mesma regra de nome.
    """
    # `download` é o atributo que faz o navegador baixar; sem ele o Excel abriria como binário.
    classe = "baixar compacto" if compacto else "baixar"
    return (f'<a class="{classe}" download href="dados/{ticker}.xlsx" '
            f'title="planilha de estudo de {ticker}">↓ xlsx</a>')


def _travessia(n_alerta):
    """
    A frase de rodapé que aponta para a outra tela (helper de renderização).

    Por que existe: sem um caminho explícito, a segunda página é inalcançável para quem não repara
    na barra de abas. E a frase precisa dizer **por que** são duas páginas: aqui a escala é a mesma
    para todos os papéis; lá cada papel tem o setup que o estudo aprovou para ele. São perguntas
    diferentes, não duas versões da mesma.

    Entrada: n_alerta (papéis com gatilho acionado hoje; None quando ainda não se mediu).
    Fase 1: sem medida, apenas o convite — afirmar "nenhum gatilho" seria dizer o que não se sabe.
    Fase 2: com medida, o número do dia, no singular ou no plural correto.
    Saída: string com o HTML do parágrafo.
    """
    explica = ("É outra pergunta e outra medida: aqui a escala é a mesma para todos os papéis; lá "
               "cada papel é comparado com os dias mais extremos da própria história.")
    # Fase 1: ainda não medido.
    if n_alerta is None:
        return f"{explica} <a href='extremos.html'>Ver a faixa extrema →</a>"
    # Fase 2: medido e vazio, ou medido com destaques.
    if n_alerta == 0:
        return (f"<b>Nenhum destaque na faixa extrema hoje</b> — o resultado esperado na maioria "
                f"dos pregões. {explica} <a href='extremos.html'>Ver a faixa extrema →</a>")
    pp = "papéis estão" if n_alerta > 1 else "papel está"
    return (f"<b>Hoje {n_alerta} {pp} em destaque na faixa extrema.</b> {explica} "
            f"<a href='extremos.html'>Ver os destaques →</a>")


def monta_pagina(indice, template, agora=None, estado=None):
    """
    Preenche o template com os dados do índice, devolvendo o HTML final.

    Por que existe: separar o cálculo (acima) da renderização (aqui) mantém as duas coisas
    testáveis — e é possível gerar a página inteira sem tocar na rede, o que os testes fazem.

    Entrada: indice (dict de `estado_de_hoje` do BOVA11 + chave "ticker"), template (string com
    os marcadores de MARCADORES), agora (instante do carimbo; `None` = agora, e é o que a
    publicação usa — o parâmetro existe para o teste poder fixar o relógio), estado (o que
    `gerar_extremos.py` gravou, para a barra de abas).
    Fase 1: montar a leitura mestra — título, veredito, régua de dez segmentos e as cinco medidas.
    Fase 2: substituir os marcadores. Nenhum pode sobrar.
    Saída: string com o HTML completo.
    """
    # Fase 1: a leitura mestra. O veredito tem três estados: zona de viés de alta, decil de alerta
    # ("ganhar menos") ou terreno neutro.
    t = indice["ticker"]
    if indice["decil"] in ZONA:
        # O índice está na zona onde o viés de alta foi observado.
        titulo, sub = f"{t} está afastado para baixo", \
            "O mercado inteiro está na zona onde o viés de alta foi observado."
        veredito, classe_veredito = "mercado na zona", "v-zona"
    elif indice["decil"] in ALERTA:
        # O índice está no decil de cima: historicamente, ganhou menos nos 45 pregões seguintes.
        titulo, sub = f"{t} está afastado para cima", \
            ("Em dias assim, o índice subiu com menos frequência nos 45 pregões seguintes. "
             "É ganhar menos, não cair: não é sinal de venda.")
        veredito, classe_veredito = "tende a ganhar menos", "v-alerta"
    else:
        # Nem uma ponta nem a outra.
        titulo, sub = f"{t} está em terreno neutro", "Não há viés a explorar hoje."
        veredito, classe_veredito = "sem sinal", ""

    # Régua: dez segmentos; os três primeiros pintados como zona, o decil 9 como alerta, e o atual
    # destacado (no decil 9, o destaque mantém a cor de alerta).
    def _classe_seg(i):
        # Monta a classe do segmento i combinando "aqui" com a pintura da faixa.
        partes = ["seg"]
        # O decil de hoje leva o destaque.
        if i == indice["decil"]:
            partes.append("aqui")
        # O decil de alerta é pintado sempre; a zona, só quando não é o de hoje (como antes).
        if i in ALERTA:
            partes.append("alerta")
        elif i in ZONA and i != indice["decil"]:
            partes.append("zona")
        return " ".join(partes)
    regua = "".join(f'<div class="{_classe_seg(i)}"><i>{i}</i></div>' for i in range(10))

    # Cinco medidas do índice (a mesma ordem da tela aprovada).
    medidas = "".join(
        f'<div class="medida"><div class="v">{v}</div><div class="k">{k}</div></div>'
        for v, k in [
            (_pct(indice["dist"], sinal=True), "distância à média"),
            (_pct(indice["media"], sinal=True), "retorno histórico do decil"),
            (_pct(indice["base"], sinal=True), "taxa-base do período"),
            (_pct(indice["freq_pos"], casas=0), "frequência positiva"),
            (str(indice["episodios"]), "episódios independentes"),
        ])

    # Fase 2: substituir todos os marcadores.
    # A barra e a travessia vêm do estado que `gerar_extremos.py` deixou. Ausência dele não é erro:
    # a barra sai sem contador e a travessia sem número, que é o correto quando ainda não se mediu.
    estado = estado or {}
    n_alerta = estado.get("papeis_com_alerta")
    valores = {"TITULO_INDICE": titulo, "SUB_INDICE": sub, "VEREDITO": veredito,
               "CLASSE_VEREDITO": classe_veredito, "REGUA": regua,
               "MEDIDAS": medidas,
               "BAIXAR_INDICE": _link_download(indice["ticker"]),
               "CARIMBO": _carimbo(agora),
               "ABAS": barra_de_abas("triagem", n_alerta),
               "TRAVESSIA": _travessia(n_alerta)}
    html = template
    for chave, valor in valores.items():
        html = html.replace("{{" + chave + "}}", valor)
    # Saída: HTML pronto para gravar.
    return html


def main() -> None:
    """
    I/O da geração: baixa o índice, aplica a peneira, calcula o estado de hoje e grava a página.

    Por que só o índice: desde 23/11/2026 a página não tem mais a tabela de papéis (pedido do
    usuário), e os ~100 downloads que a alimentavam deixaram de servir para alguma coisa.

    Fase 1: ler o template.
    Fase 2: baixar o índice e passar pela peneira de qualidade. Sem ele não há página: o processo
            encerra com erro, e o fluxo de publicação mantém a última versão no ar.
    Fase 3: calcular o estado de hoje.
    Fase 4: montar a página e gravar em `saida/index.html`, com a planilha de estudo do índice.
    """
    aqui = Path(__file__).parent
    # Fase 1: o template.
    template = (aqui / "template.html").read_text(encoding="utf-8")
    t = config.DIST_INDICE
    print(f"TRIAGEM — {t} | janela {config.DIST_JANELA}, horizonte {config.DIST_HORIZONTE} dias")

    # Fase 2: download e peneira. Qualquer falha aqui encerra: sem a leitura mestra não há página.
    try:
        prices = load_prices(f"{t}{config.TICKER_SUFFIX}", config.EXTREMOS_PERIOD)
    except Exception as erro:
        raise SystemExit(f"O índice {t} não pôde ser baixado: {erro}")
    q = avalia_qualidade(prices, janela_max=config.DIST_JANELA,
                         vol_lag=config.EXTREMOS_VOL_LAG,
                         data_inicio_teste=config.EXTREMOS_INICIO_TESTE,
                         min_treino_util=750)
    if not q["aprovado"]:
        # Motivo por extenso: distingue dado ruim de série curta, e essa diferença precisa ser lida.
        raise SystemExit(f"O índice {t} não passou na peneira ({'; '.join(q['motivos'])}) — "
                         f"sem ele a tela não pode ser gerada.")

    # Fase 3: o estado de hoje.
    indice = estado_de_hoje(prices, config.DIST_JANELA, config.DIST_HORIZONTE,
                            config.SLOPE_LAG, config.EXTREMOS_VOL_LAG,
                            config.EXTREMOS_N_FAIXAS, config.EXTREMOS_INICIO_TESTE)
    indice["ticker"] = t
    print(f"  ok  {t:<8} decil {indice['decil']}  "
          f"{_pct(indice['excesso'], sinal=True).replace('%', ' pp')}")

    # Fase 4: montar e gravar.
    saida = aqui / "saida"; saida.mkdir(exist_ok=True)
    destino = saida / "index.html"
    # O estado vem de `gerar_extremos.py`, que roda antes no fluxo de publicação. Ausência não é
    # erro: a barra sai sem contador, que é o correto quando ainda não se mediu.
    estado = le_estado(saida)
    destino.write_text(monta_pagina(indice, template, estado=estado), encoding="utf-8")
    # Os estilos acompanham a página: ela os linka por caminho relativo, e sem a cópia o site sobe
    # sem formatação nenhuma.
    copia_estatica(aqui, saida)
    # A planilha de estudo do índice, alcançada pelo botão da leitura mestra.
    pasta_dados = saida / "dados"; pasta_dados.mkdir(exist_ok=True)
    indice["df"].to_excel(pasta_dados / f"{t}.xlsx", sheet_name="estudo")
    print(f"página gravada em {destino}")


if __name__ == "__main__":
    main()

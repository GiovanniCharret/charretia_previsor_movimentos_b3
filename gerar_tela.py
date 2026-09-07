"""
Gerador da tela diária de triagem — preenche `template.html` com os dados do pregão mais recente.

Por que este módulo existe: o estudo, no repositório irmão `robusta_backtest`, responde "existe
efeito?"; este projeto responde "como está hoje?". São coisas diferentes, com ciclos de vida
diferentes, e por isso vivem em repositórios separados — aqui não se mede nada novo, apenas se
aplica o que já foi medido e validado fora da amostra.

O que a tela mostra, e por quê:
  - **O índice primeiro.** O efeito medido é de mercado inteiro (aparece no próprio BOVA11), então
    os papéis individuais são detalhamento dele, não apostas independentes.
  - **Só o lado comprado.** O decil alto rende abaixo da média do próprio papel, mas só é negativo
    em termos absolutos em cerca de metade dos casos. Render menos que a própria média não é cair.
  - **Evidência ao lado do sinal.** Número de episódios independentes, frequência de acerto e a
    taxa-base do papel aparecem em toda linha. Sinal sem a força da evidência engana.

Disciplina mantida do estudo: cortes de decil calculados só no treino, desvio-padrão móvel causal,
embargo igual ao horizonte, e peneira de qualidade de dados antes de qualquer cálculo.
"""

from datetime import datetime, timedelta, timezone          # carimbo de execução
from pathlib import Path                                    # caminhos
import sys                                                  # fluxo de saída único para a barra
import numpy as np                                          # medidas
import pandas as pd                                         # séries e datas
from tqdm import tqdm                                       # barra de andamento dos ~70 downloads

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
              "REGUA", "MEDIDAS", "LINHAS", "BAIXAR_INDICE", "CARIMBO",
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

# Ordem de força da evidência, usada só para desempatar papéis no mesmo decil. Os dois rótulos de
# alerta ficam por último de propósito: são anti-sinais, e não podem passar à frente de uma linha
# fraca porém coerente só porque têm muitos episódios.
FORCA_EVIDENCIA = {"c-forte": 0, "c-moderada": 1, "c-fraca": 2, "c-alerta": 3}


def classifica_evidencia(episodios, excesso, media, na_zona):
    """
    Traduz os números de uma linha no rótulo de evidência exibido na tela.

    Por que existe: o rótulo é a única parte da tela que emite juízo, então a regra precisa estar
    num só lugar, testada, e não espalhada pelo código de renderização. Ela mede **força da
    evidência**, não tamanho do retorno — um papel pode ter retorno alto e evidência fraca.

    Entrada: episodios (eventos independentes), excesso (retorno do decil menos a taxa-base),
    media (retorno absoluto do decil), na_zona (o papel está nos decis 0 a 2?).

    Fase 1: armadilhas primeiro, porque elas VENCEM qualquer força — bate a base mas perde dinheiro
            (excesso positivo com retorno negativo), ou o histórico contradiz o padrão (excesso
            negativo dentro da zona). Deixar a força falar antes esconderia justamente os casos
            que mais enganam.
    Fase 2: fora da zona não é sinal, por melhor que seja o histórico.
    Fase 3: dentro da zona, a escala vem do número de episódios independentes.
    Saída: tupla (classe css, rótulo legível).
    """
    # Fase 1: as duas armadilhas, antes de qualquer avaliação de força.
    if na_zona and excesso > 0 and media < 0:
        return "c-alerta", "bate a base, mas perde"
    if na_zona and excesso < 0:
        return "c-alerta", "contradiz o padrão"
    # Fase 2: fora dos decis baixos não há viés observado a reportar.
    if not na_zona:
        return "c-fraca", "fora da zona"
    # Fase 3: escala por episódios independentes (o "n" honesto), não por tamanho de retorno.
    if episodios > 15:
        return "c-forte", "forte"
    if episodios >= 5:
        return "c-moderada", "moderada"
    return "c-fraca", "fraca"


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


def _mini_regua(decil):
    """Dez quadradinhos com o decil atual aceso — a posição do papel lida de relance, não como número."""
    return "".join('<span class="on"></span>' if i == decil else "<span></span>"
                   for i in range(10))


def seleciona_destaques(papeis, top_n):
    """
    Escolhe e ordena os papéis que aparecem na tabela, já com a evidência classificada.

    Por que existe: a tabela e a gravação das planilhas precisam concordar sobre QUAIS papéis estão
    na tela — se divergirem, a página oferece download de arquivo que não existe, ou o pacote leva
    dezenas de arquivos que ninguém alcança. Uma função só, usada pelos dois, elimina a divergência.

    Entrada: papeis (lista de dicts de `estado_de_hoje`, sem o índice), top_n (quantos exibir).
    Fase 1: classificar a evidência de cada papel — precisa vir antes da ordenação, porque é o
            critério de desempate.
    Fase 2: ordenar por decil (mais afastado para baixo primeiro), depois por força da evidência,
            depois por excesso decrescente como último desempate.
    Fase 3: cortar em top_n.
    Saída: lista de tuplas (papel, na_zona, classe css, rótulo), na ordem de exibição.
    """
    # Fase 1: classificar antes de ordenar.
    avaliados = []
    for p in papeis:
        # Estar na zona de viés muda o rótulo, então entra na classificação.
        na_zona = p["decil"] in ZONA
        classe, rotulo = classifica_evidencia(p["episodios"], p["excesso"], p["media"], na_zona)
        avaliados.append((p, na_zona, classe, rotulo))
    # Fase 2: decil, força da evidência, excesso decrescente.
    avaliados.sort(key=lambda a: (a[0]["decil"], FORCA_EVIDENCIA[a[2]], -a[0]["excesso"]))
    # Fase 3 e saída: só os primeiros.
    return avaliados[:top_n]


def _link_download(ticker, compacto=False):
    """
    Link para a planilha de estudo do papel, no formato que o navegador salva em vez de abrir.

    Por que existe: o caminho do arquivo é derivado do ticker em dois lugares da página (leitura
    mestra e tabela). Centralizar aqui garante que os dois nunca divirjam — e que a gravação em
    `main()` e o link tenham a mesma regra de nome.
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
               "cada papel tem o setup que o estudo aprovou para ele.")
    # Fase 1: ainda não medido.
    if n_alerta is None:
        return f"{explica} <a href='alertas.html'>Ver os gatilhos de proteção →</a>"
    # Fase 2: medido e vazio, ou medido com gatilhos.
    if n_alerta == 0:
        return (f"<b>Nenhum gatilho de proteção acionado hoje</b> — o resultado esperado na maioria "
                f"dos pregões. {explica} <a href='alertas.html'>Ver a tela de gatilhos →</a>")
    pp = "papéis" if n_alerta > 1 else "papel"
    return (f"<b>Hoje {n_alerta} {pp} acionaram gatilhos de proteção.</b> {explica} "
            f"<a href='alertas.html'>Ver os gatilhos →</a>")


def monta_pagina(indice, papeis, template, top_n=config.DIST_TOP_N, agora=None,
                 estado=None):
    """
    Preenche o template com os dados do índice e dos papéis, devolvendo o HTML final.

    Por que existe: separar o cálculo (acima) da renderização (aqui) mantém as duas coisas
    testáveis — e é possível gerar a página inteira sem tocar na rede, o que os testes fazem.

    Entrada: indice (dict de `estado_de_hoje` do BOVA11 + chave "ticker"), papeis (lista de dicts
    iguais), template (string com os marcadores de MARCADORES), top_n (quantos papéis exibir),
    agora (instante do carimbo; `None` = agora, e é o que a publicação usa — o parâmetro existe
    para o teste poder fixar o relógio).
    Fase 1: montar a leitura mestra — título, veredito, régua de dez segmentos e as cinco medidas.
    Fase 2: montar uma linha de tabela por papel em destaque.
    Fase 3: substituir os marcadores. Nenhum pode sobrar.
    Saída: string com o HTML completo.
    """
    # Fase 1: a leitura mestra. O veredito depende de o índice estar ou não na zona de viés.
    na_zona_idx = indice["decil"] in ZONA
    titulo = (f"{indice['ticker']} está em terreno neutro" if not na_zona_idx
              else f"{indice['ticker']} está afastado para baixo")
    sub = ("Não há viés a explorar hoje." if not na_zona_idx
           else "O mercado inteiro está na zona onde o viés de alta foi observado.")
    veredito = "sem sinal" if not na_zona_idx else "mercado na zona"
    classe_veredito = "" if not na_zona_idx else "v-zona"

    # Régua: dez segmentos, os três primeiros pintados como zona, o atual destacado.
    regua = "".join(
        f'<div class="seg aqui"><i>{i}</i></div>' if i == indice["decil"]
        else f'<div class="seg zona"><i>{i}</i></div>' if i in ZONA
        else f'<div class="seg"><i>{i}</i></div>'
        for i in range(10))

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

    # Fase 2: uma linha por papel em destaque (a seleção e a ordem vêm de `seleciona_destaques`).
    linhas = []
    for p, na_zona, classe, rotulo in seleciona_destaques(papeis, top_n):
        # Linhas de destaque: dentro da zona e sem armadilha.
        marcada = ' class="marcada"' if na_zona and classe not in ("c-alerta", "c-fraca") else ""
        # Retorno e excesso ganham ênfase quando são positivos e o papel está na zona.
        forte = ' class="destaque"' if na_zona and p["media"] > 0 else ""
        linhas.append(
            f'<tr{marcada}>'
            f'<td class="esq"><span class="papel">{p["ticker"]}</span></td>'
            f'<td class="esq"><span class="mini">{_mini_regua(p["decil"])}</span></td>'
            f'<td>{_pct(p["dist"], sinal=True)}</td>'
            f'<td{forte}>{_pct(p["media"], sinal=True)}</td>'
            f'<td>{_pct(p["base"], sinal=True)}</td>'
            f'<td{forte}>{_pct(p["excesso"], sinal=True).replace("%", " pp")}</td>'
            f'<td>{_pct(p["freq_pos"], casas=0)}</td>'
            f'<td>{p["episodios"]}</td>'
            f'<td class="esq"><span class="chip {classe}">{rotulo}</span></td>'
            f'<td class="esq">{_link_download(p["ticker"], compacto=True)}</td>'
            f'</tr>')

    # Fase 3: substituir todos os marcadores.
    # A barra e a travessia vêm do estado que `gerar_alertas.py` deixou. Ausência dele não é erro:
    # a barra sai sem contador e a travessia sem número, que é o correto quando ainda não se mediu.
    estado = estado or {}
    n_alerta = estado.get("papeis_com_alerta")
    valores = {"TITULO_INDICE": titulo, "SUB_INDICE": sub, "VEREDITO": veredito,
               "CLASSE_VEREDITO": classe_veredito, "REGUA": regua,
               "MEDIDAS": medidas, "LINHAS": "".join(linhas),
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
    I/O da geração: baixa os papéis, aplica a peneira, calcula o estado de hoje e grava a página.

    Fase 1: ler a lista de tickers e o template.
    Fase 2: para cada papel, baixar e passar pela peneira de qualidade (com exigência de treino
            útil). Aprovados e reprovados anunciam uma linha cada, na hora — não há resumo no fim,
            porque a barra já carrega o placar e repetir os números só afastaria o motivo de cada
            reprovação do momento em que ela aconteceu.
    Fase 3: calcular o estado de hoje de cada aprovado e separar o índice dos demais.
    Fase 4: montar a página e gravar em `saida/index.html`.
    Fase 5: gravar uma planilha de estudo por papel aprovado.
    """
    aqui = Path(__file__).parent
    # Fase 1: lista de papéis e template.
    # Lista de papéis: mora DENTRO da pasta, senão a publicação dependeria de um arquivo do
    # laboratório que não sobe junto.
    tickers = pd.read_csv(aqui / "tickers.csv")["tickers"].dropna().tolist()
    template = (aqui / "template.html").read_text(encoding="utf-8")
    print(f"{len(tickers)} papéis na lista | janela {config.DIST_JANELA}, "
          f"horizonte {config.DIST_HORIZONTE} dias")

    # `reprovados` é só um contador: o motivo de cada reprovação é anunciado na hora, e não guardado
    # para um resumo no fim.
    aprovados, reprovados = [], 0
    # Fase 2 e 3: peneira e estado de hoje, papel a papel. A barra da tqdm dá o andamento (são
    # ~70 downloads, alguns minutos), e o contador ao lado dela mostra o placar em tempo real —
    # sem ele, uma execução com muitas reprovações só apareceria no fim.
    # `file=sys.stdout` porque o resumo final usa print: com a barra no stderr (o padrão da tqdm),
    # os dois fluxos se intercalam fora de ordem no log do GitHub Actions.
    barra = tqdm(tickers, desc="papéis", unit="papel", ncols=78, file=sys.stdout)
    for t in barra:
        try:
            prices = load_prices(f"{t}{config.TICKER_SUFFIX}", config.EXTREMOS_PERIOD)
        except Exception:
            reprovados += 1
            barra.write(f"  fora {t:<8} falha no download")
            barra.set_postfix_str(f"ok {len(aprovados)} | fora {reprovados}")
            continue
        q = avalia_qualidade(prices, janela_max=config.DIST_JANELA,
                             vol_lag=config.EXTREMOS_VOL_LAG,
                             data_inicio_teste=config.EXTREMOS_INICIO_TESTE,
                             min_treino_util=750)
        if not q["aprovado"]:
            reprovados += 1
            # Motivo por extenso: é o que distingue um papel novo demais de uma série com
            # desdobramento não ajustado, e essa diferença precisa ser lida, não contada.
            barra.write(f"  fora {t:<8} {'; '.join(q['motivos'])}")
            barra.set_postfix_str(f"ok {len(aprovados)} | fora {reprovados}")
            continue
        try:
            e = estado_de_hoje(prices, config.DIST_JANELA, config.DIST_HORIZONTE,
                               config.SLOPE_LAG, config.EXTREMOS_VOL_LAG,
                               config.EXTREMOS_N_FAIXAS, config.EXTREMOS_INICIO_TESTE)
            e["ticker"] = t
            aprovados.append(e)
            # Linha curta de sucesso. `tqdm.write` em vez de `print` para não embaralhar a barra.
            # Apenas texto ASCII: o console do Windows usa cp1252 por padrão, e um símbolo como
            # "✓" derrubaria a execução com erro de codificação.
            barra.write(f"  ok  {t:<8} decil {e['decil']}  "
                        f"{_pct(e['excesso'], sinal=True).replace('%', ' pp')}")
        except Exception as erro:
            reprovados += 1
            barra.write(f"  fora {t:<8} erro no cálculo: {erro}")
        barra.set_postfix_str(f"ok {len(aprovados)} | fora {reprovados}")
    barra.close()

    # Separar o índice (a leitura mestra) dos papéis individuais.
    indice = next((e for e in aprovados if e["ticker"] == config.DIST_INDICE), None)
    if indice is None:
        raise SystemExit(f"O índice {config.DIST_INDICE} não passou na peneira — "
                         f"sem ele a tela não pode ser gerada.")
    papeis = [e for e in aprovados if e["ticker"] != config.DIST_INDICE]

    # Fase 4: montar e gravar.
    saida = aqui / "saida"; saida.mkdir(exist_ok=True)
    destino = saida / "index.html"
    # O estado vem de `gerar_alertas.py`, que roda antes no fluxo de publicação. Ausência não é
    # erro: a barra sai sem contador, que é o correto quando ainda não se mediu.
    estado = le_estado(saida)
    destino.write_text(monta_pagina(indice, papeis, template, config.DIST_TOP_N, estado=estado),
                       encoding="utf-8")
    # Os estilos acompanham a página: ela os linka por caminho relativo, e sem a cópia o site sobe
    # sem formatação nenhuma.
    copia_estatica(aqui, saida)

    # Fase 5: uma planilha por papel VISÍVEL na tela — o índice mais os destaques da tabela. Os
    # aprovados que ficaram de fora da tabela não geram arquivo: a página não tem link para eles, e
    # publicar dados que ninguém alcança só engorda o pacote. A mesma `seleciona_destaques` decide
    # aqui e na tabela, então os dois nunca divergem.
    visiveis = [indice] + [p for p, _, _, _ in seleciona_destaques(papeis, config.DIST_TOP_N)]
    pasta_dados = saida / "dados"; pasta_dados.mkdir(exist_ok=True)
    for e in tqdm(visiveis, desc="planilhas", unit="arq", ncols=78, file=sys.stdout):
        e["df"].to_excel(pasta_dados / f"{e['ticker']}.xlsx", sheet_name="estudo")

    mb = sum(p.stat().st_size for p in pasta_dados.glob("*.xlsx")) / 1e6
    print(f"\npágina gravada em {destino}")
    print(f"{len(visiveis)} planilhas de estudo em {pasta_dados} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()

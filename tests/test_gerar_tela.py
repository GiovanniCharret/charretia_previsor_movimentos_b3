import re
from datetime import datetime, timezone

import numpy as np, pandas as pd, pytest
from gerar_tela import estado_de_hoje, monta_pagina, FUSO_BRASILIA, MARCADORES


def _papel(ticker, decil, episodios=8, excesso=0.02, media=0.05):
    """Papel mínimo para testar ordenação — só os campos que entram nos critérios."""
    return {"ticker": ticker, "decil": decil, "dist": -0.1, "media": media, "base": media - excesso,
            "excesso": excesso, "freq_pos": 0.6, "episodios": episodios, "n_dias": 100}


def _precos(n=2500, semente=3):
    # Passeio com reversão à média, longo o bastante para aquecimento + treino + teste.
    rng = np.random.default_rng(semente)
    close = np.empty(n); close[0] = 100.0
    for i in range(1, n):
        close[i] = close[i-1] + 0.25 * (100.0 - close[i-1]) / 10.0 + rng.normal(0, 1.0)
    idx = pd.bdate_range(end=pd.Timestamp("2026-08-21"), periods=n)
    return pd.DataFrame({"Open": close, "High": close, "Low": close,
                         "Close": close, "Volume": 1e6}, index=idx)


def test_estado_de_hoje_devolve_decil_e_historico():
    # O estado de HOJE precisa usar a última linha disponível, inclusive as que ainda não têm
    # retorno futuro conhecido — senão a tela mostraria a posição de 45 pregões atrás.
    d = estado_de_hoje(_precos(), window=90, horizon=45, slope_lag=5, vol_lag=252,
                       n_faixas=10, data_inicio_teste="2021-01-01")
    for c in ("decil", "dist", "media", "base", "excesso", "freq_pos", "episodios", "n_dias"):
        assert c in d, c
    assert 0 <= d["decil"] <= 9
    assert d["episodios"] <= d["n_dias"]


def test_estado_de_hoje_devolve_dataframe_auditavel():
    # O arquivo baixável tem de permitir conferir POR FORA que a calibração não viu o futuro.
    # Para isso ele precisa carregar, linha a linha, a que conjunto cada pregão pertenceu.
    d = estado_de_hoje(_precos(), window=90, horizon=45, slope_lag=5, vol_lag=252,
                       n_faixas=10, data_inicio_teste="2021-01-01")
    df = d["df"]
    for c in ("Close", "mma_w90", "mma_dist_w90", "mma_dist_z_w90", "faixa", "ret_45d", "conjunto"):
        assert c in df.columns, c
    # Os quatro rótulos precisam existir, senão o arquivo não conta a história completa.
    assert set(df["conjunto"]) == {"treino", "embargo", "teste", "sem_retorno"}
    # Nenhuma linha de treino pode cair dentro da janela de teste — é a disciplina central.
    assert df.index[df["conjunto"] == "treino"].max() < pd.Timestamp("2021-01-01")
    # A última linha é o pregão de hoje, que por definição ainda não tem retorno futuro.
    assert df["conjunto"].iloc[-1] == "sem_retorno"
    # E ela tem faixa atribuída, senão a tela não teria de onde ler o decil de hoje.
    assert df["faixa"].iloc[-1] == d["decil"]


def test_a_pagina_nao_tem_mais_o_detalhamento_por_papel():
    # Retirado a pedido do usuário em 23/11/2026: era ruído. Só o índice tem planilha e link.
    template = open("template.html", encoding="utf-8").read()
    assert "Detalhamento por papel" not in template and "{{LINHAS}}" not in template
    html = monta_pagina(_papel("BOVA11", 3), template)
    assert html.count('href="dados/') == 1 and 'href="dados/BOVA11.xlsx"' in html
    assert 'class="papel"' not in html


def test_monta_pagina_substitui_todos_os_marcadores():
    # Nenhum marcador pode sobrar na página final — sobra de marcador é bug visível ao usuário.
    template = open("template.html", encoding="utf-8").read()
    indice = {"ticker": "BOVA11", "decil": 3, "dist": -0.027, "media": 0.016, "base": 0.016,
              "excesso": 0.0, "freq_pos": 0.51, "episodios": 10, "n_dias": 120}
    html = monta_pagina(indice, template)
    for m in MARCADORES:
        assert "{{" + m + "}}" not in html, f"marcador {m} não substituído"
    assert "BOVA11" in html


def test_monta_pagina_marca_o_decil_atual_na_regua():
    template = open("template.html", encoding="utf-8").read()
    indice = {"ticker": "BOVA11", "decil": 7, "dist": 0.05, "media": 0.01, "base": 0.01,
              "excesso": 0.0, "freq_pos": 0.5, "episodios": 8, "n_dias": 100}
    html = monta_pagina(indice, template)
    # a régua tem 10 segmentos e exatamente um marcado como "aqui".
    assert html.count('class="seg aqui"') == 1
    # o segmento marcado carrega o número do decil atual.
    assert '<div class="seg aqui"><i>7</i></div>' in html


class TestCarimboDeExecucao:
    def test_usa_o_horario_recebido(self):
        # O carimbo é injetável para o teste poder fixar o instante — sem isso a única verificação
        # possível seria por expressão regular, que não pega erro de formato.
        template = open("template.html", encoding="utf-8").read()
        html = monta_pagina(_papel("BOVA11", 3), template,
                            agora=datetime(2026, 8, 23, 18, 34, tzinfo=FUSO_BRASILIA))
        assert "23/08/2026 às 18h34" in html

    def test_converte_horario_de_outro_fuso(self):
        # O GitHub Actions roda em UTC: sem a conversão, a página anunciaria 21h34 para um pregão
        # que fechou às 18h34 — três horas de erro no único número que o leitor pode conferir
        # contra o próprio relógio.
        template = open("template.html", encoding="utf-8").read()
        html = monta_pagina(_papel("BOVA11", 3), template,
                            agora=datetime(2026, 8, 23, 21, 34, tzinfo=timezone.utc))
        assert "23/08/2026 às 18h34" in html

    def test_sem_argumento_carimba_o_instante_atual(self):
        # O caminho que a publicação de fato usa: nenhum chamador passa `agora`.
        template = open("template.html", encoding="utf-8").read()
        html = monta_pagina(_papel("BOVA11", 3), template)
        assert re.search(r"\d{2}/\d{2}/\d{4} às \d{2}h\d{2}", html)

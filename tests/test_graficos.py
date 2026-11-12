"""
Os gráficos por papel da faixa extrema (v3): retorno em 45 pregões por faixa, uma janela por vez.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from graficos import ROTULOS, link_graficos, pagina_graficos, resumo_por_faixa
from gerar_extremos import monta_pagina

RAIZ = Path(__file__).resolve().parents[1]


def _precos(n=2500, semente=3):
    rng = np.random.default_rng(semente)
    close = 30 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, size=n)))
    idx = pd.bdate_range("2012-01-02", periods=n)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close,
                         "Volume": 9_000_000.0}, index=idx)


class TestResumo:
    def test_doze_faixas_por_janela_na_ordem_do_eixo(self):
        r = resumo_por_faixa(_precos(), [10, 60], 45, 252, 5)
        assert set(r) == {10, 60}
        assert [f["rotulo"] for f in r[10]["faixas"]] == ROTULOS and len(ROTULOS) == 12

    def test_as_faixas_dividem_a_historia_nas_proporcoes_certas(self):
        # 0–2,5% tem um quarto do tamanho de um decil; os decis têm tamanhos parecidos.
        f = resumo_por_faixa(_precos(), [20], 45, 252, 5)[20]["faixas"]
        n = np.array([x["n"] for x in f], dtype=float)
        assert abs(n[0] / n[5] - 0.25) < 0.1
        assert abs(n[5] / n[10] - 1) < 0.15

    def test_a_caixa_esta_em_ordem_e_a_faixa_de_hoje_existe(self):
        r = resumo_por_faixa(_precos(), [30], 45, 252, 5)[30]
        for x in r["faixas"]:
            assert x["p10"] <= x["p25"] <= x["p50"] <= x["p75"] <= x["p90"]
            assert 0 <= x["nao_perdeu"] <= 1
        assert 0 <= r["hoje"] < 12

    def test_janela_sem_historia_bastante_fica_de_fora(self):
        assert resumo_por_faixa(_precos(600), [200], 45, 252, 5) == {}


class TestPagina:
    def test_abre_na_janela_que_pos_o_papel_na_tabela(self):
        r = resumo_por_faixa(_precos(), [10, 30, 60], 45, 252, 5)
        html = pagina_graficos("VALE3", r, "2026-11-11", 45, [30])
        assert 'desenha("30");' in html
        assert "data-w='30' class='jan no-extremo' aria-pressed=\"true\"" in html
        dados = json.loads(html.split("const DADOS = ")[1].split(";\n")[0])
        assert set(dados) == {"10", "30", "60"}

    def test_a_pagina_diz_que_e_leitura_descritiva_e_volta_para_a_tabela(self):
        html = pagina_graficos("VALE3", resumo_por_faixa(_precos(), [10], 45, 252, 5), "2026-11-11", 45)
        assert "leitura descritiva" in html and 'href="../extremos.html"' in html
        assert 'href="../estilo.css"' in html


class TestColunaNaTabela:
    def _tabela(self):
        return pd.DataFrame([{"ticker": "BOM3", "faixa": 0.025, "janelas": "10", "janelas_2_5": 1,
                              "janelas_5": 1, "janelas_medidas": 9, "horizonte": 45, "freq": 0.63,
                              "taxa_base": 0.54, "acima_da_base": True, "divisoes_usadas": 5,
                              "inicio_medido": "2006-01-02", "fim_medido": "2026-09-11"}])

    def test_a_coluna_vem_antes_de_dados_e_so_linka_o_que_foi_gravado(self):
        t = (RAIZ / "template_extremos.html").read_text(encoding="utf-8")
        com = monta_pagina(t, self._tabela(), "2026-11-11", 98, None, {"BOM3"}, {"BOM3"})
        assert com.index("<th class='esq'>gráficos</th>") < com.index("<th class='esq'>dados</th>")
        assert "graficos/BOM3.html" in com
        sem = monta_pagina(t, self._tabela(), "2026-11-11", 98)
        assert "graficos/BOM3.html" not in sem and "<th class='esq'>gráficos</th>" in sem

    def test_a_v4_nao_ganha_a_coluna(self):
        from gerar_setores import monta_pagina as pagina_v4
        t = (RAIZ / "template_setores.html").read_text(encoding="utf-8")
        tab = self._tabela().assign(setor="Energia Elétrica", faixa=0.10, n_janelas=1)
        assert "gráficos</th>" not in pagina_v4(t, tab, "2026-11-11", 18)

    def test_o_link_aponta_para_a_pasta_de_graficos(self):
        assert "href='graficos/VALE3.html'" in link_graficos("VALE3")

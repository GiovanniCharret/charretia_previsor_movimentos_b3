"""
A tela de bancos e elétricas (v4): o decil 0 nos dois setores em observação.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from nucleo import config
from gerar_setores import COLUNAS, monta_pagina, monta_tabela, situacao_no_decil

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATE = (RAIZ / "template_setores.html").read_text(encoding="utf-8")


def _cortes(ticker="ITUB4"):
    # Três janelas com corte do decil 0 em -1,3.
    return pd.DataFrame({"ticker": ticker, "janela": [10, 20, 30], "percentil": 0.10,
                         "corte": -1.3, "setor": "Intermediários Financeiros"})


def _por_janela(ticker, freqs, base=0.55):
    return pd.DataFrame([{"ticker": ticker, "percentil": 0.10, "horizonte": 45, "janela": w,
                          "freq_dias": f, "taxa_base": base, "dias": 120, "episodios": 9,
                          "divisoes_usadas": 5, "inicio_medido": "2006-03-01",
                          "fim_medido": "2026-08-31"} for w, f in freqs.items()])


class TestSituacao:
    def test_lista_so_as_janelas_no_corte_ou_abaixo(self):
        s = situacao_no_decil({10: -2.0, 20: -1.3, 30: 0.4}, _cortes(), 0.10)
        assert s["lista"] == [10, 20] and s["acompanhadas"] == [10, 20, 30]

    def test_janela_sem_escore_hoje_nao_e_acompanhada(self):
        s = situacao_no_decil({10: -2.0, 20: np.nan, 30: 0.4}, _cortes(), 0.10)
        assert s["acompanhadas"] == [10, 30]


class TestTabela:
    def _tabela(self):
        sit = {"ITUB4": {"lista": [10, 20], "acompanhadas": [10, 20, 30]},
               "EGIE3": {"lista": [30], "acompanhadas": [10, 20, 30]},
               "BBAS3": {"lista": [], "acompanhadas": [10, 20, 30]}}
        pj = pd.concat([_por_janela("ITUB4", {10: 0.70, 20: 0.60, 30: 0.40}),
                        _por_janela("EGIE3", {10: 0.80, 20: 0.80, 30: 0.50})])
        setor = {"ITUB4": "Intermediários Financeiros", "EGIE3": "Energia Elétrica",
                 "BBAS3": "Intermediários Financeiros"}
        return monta_tabela(sit, pj, setor, 0.10)

    def test_fora_do_decil_nao_entra(self):
        assert "BBAS3" not in set(self._tabela()["ticker"])

    def test_a_frequencia_e_a_do_proprio_papel_nas_janelas_de_hoje(self):
        # Pedido do usuário (04/11/2026): o número da linha é o do papel, como na v3.
        t = self._tabela().set_index("ticker")
        assert t.loc["ITUB4", "freq"] == np.mean([0.70, 0.60])
        assert t.loc["ITUB4", "janelas"] == "10–20 (2)" and t.loc["ITUB4", "horizonte"] == 45
        # Nas janelas de hoje (só a 30), a EGIE3 fica abaixo da própria taxa-base: não é destaque.
        assert t.loc["EGIE3", "freq"] == 0.50 and not t.loc["EGIE3", "acima_da_base"]
        assert t.loc["ITUB4", "acima_da_base"]

    def test_mais_janelas_no_decil_vem_primeiro(self):
        assert list(self._tabela()["ticker"]) == ["ITUB4", "EGIE3"]

    def test_dia_vazio_tem_as_colunas(self):
        assert list(monta_tabela({}, _por_janela("X", {10: 0.5}), {}, 0.10).columns) == COLUNAS


class TestPagina:
    def _pagina(self, tabela, **kw):
        return monta_pagina(TEMPLATE, tabela, "2026-11-04", 18, **kw)

    def test_uma_secao_por_setor_mesmo_vazia(self):
        html = self._pagina(pd.DataFrame(columns=COLUNAS))
        for rotulo in config.SETORES_ROTULOS.values():
            assert f"<h2>{rotulo}</h2>" in html
        assert html.count("nenhum destaque hoje") == 2
        assert "Nenhum dos dezoito papéis está no decil 0 hoje." in html

    def test_so_o_destaque_aparece_e_os_demais_sao_contados(self):
        t = TestTabela()._tabela()
        html = self._pagina(t)
        assert "ITUB4" in html and "EGIE3" not in html
        assert "1 papel está no decil 0 hoje, mas sem destaque" in html

    def test_a_planilha_da_v4_tem_prefixo_proprio(self):
        html = self._pagina(TestTabela()._tabela(), planilhas={"ITUB4"})
        assert "dados/setores_ITUB4.xlsx" in html and "extremos_ITUB4" not in html

    def test_nenhum_marcador_sobra_e_a_pagina_se_marca_na_barra(self):
        html = self._pagina(pd.DataFrame(columns=COLUNAS))
        assert "{{" not in html
        assert 'href="setores.html" aria-current="page"' in html

    def test_diz_que_e_hipotese_em_observacao(self):
        # O aviso faz parte da página: a v4 acompanha uma hipótese, não publica um achado.
        assert "Uma hipótese em observação" in TEMPLATE
        assert "nenhum" in TEMPLATE and "sobreviveu à correção" in TEMPLATE

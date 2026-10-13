"""
A tela da faixa extrema (v3): contagem de janelas abaixo do corte, classificação e renderização.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gerar_extremos import (COLUNAS, escores_de_hoje, monta_pagina, monta_tabela,
                            situacao_do_papel)

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATE = (RAIZ / "template_extremos.html").read_text(encoding="utf-8")


def _cortes(janelas=(5, 20, 90), c25=-2.0, c5=-1.5):
    # Os limiares de um papel: o de 2,5% fica mais abaixo que o de 5%, em toda janela.
    return pd.DataFrame([{"janela": w, "percentil": q, "corte": c}
                         for w in janelas for q, c in ((0.025, c25), (0.05, c5))])


def _medidas(ticker, q, lim20=0.21, lim45=0.25, f20=0.60, f45=0.63):
    comum = {"ticker": ticker, "percentil": q, "taxa_base": 0.54, "divisoes_usadas": 5,
             "inicio_medido": "2006-01-02", "fim_medido": "2026-09-11"}
    return [{**comum, "horizonte": 20, "freq_dias": f20, "lim_inf": lim20},
            {**comum, "horizonte": 45, "freq_dias": f45, "lim_inf": lim45}]


def _precos(n=600, queda=False, semente=4):
    rng = np.random.default_rng(semente)
    close = 30 * np.exp(np.cumsum(rng.normal(0.0, 0.011, size=n)))
    if queda:
        close[-15:] = close[-16] * np.linspace(0.98, 0.65, 15)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close,
                         "Volume": 9_000_000.0}, index=idx)


class TestEscoresDeHoje:
    def test_queda_forte_deixa_o_escore_bem_negativo(self):
        e = escores_de_hoje(_precos(queda=True), [5, 20], vol_lag=252, slope_lag=5)
        assert e[5] < -1 and e[20] < -2

    def test_janela_sem_historia_fica_ausente(self):
        # Trezentos pregões não comportam janela 200 mais o desvio de um ano: NaN, nunca zero.
        e = escores_de_hoje(_precos(300), [200], vol_lag=252, slope_lag=5)
        assert np.isnan(e[200])


class TestSituacao:
    def test_conta_as_janelas_abaixo_de_cada_corte(self):
        s = situacao_do_papel({5: -2.5, 20: -1.7, 90: -0.3}, _cortes())
        # Só a janela 5 passa do corte de 2,5%; a 5 e a 20 passam do de 5%.
        assert s == {"janelas_2_5": 1, "janelas_5": 2, "janelas_medidas": 3}

    def test_janela_sem_escore_nao_conta_nem_a_favor_nem_contra(self):
        # Ausência de medida não é ausência de afastamento: a janela sai do denominador.
        s = situacao_do_papel({5: -2.5, 20: float("nan"), 90: -0.3}, _cortes())
        assert s["janelas_medidas"] == 2 and s["janelas_2_5"] == 1


class TestTabela:
    def test_classifica_na_faixa_mais_funda_e_deixa_de_fora_quem_nao_esta(self):
        sit = {"FUNDO3": {"janelas_2_5": 2, "janelas_5": 4, "janelas_medidas": 9},
               "RASO3": {"janelas_2_5": 0, "janelas_5": 1, "janelas_medidas": 9},
               "FORA3": {"janelas_2_5": 0, "janelas_5": 0, "janelas_medidas": 9}}
        med = pd.DataFrame(_medidas("FUNDO3", 0.025) + _medidas("FUNDO3", 0.05)
                           + _medidas("RASO3", 0.025) + _medidas("RASO3", 0.05, lim45=0.30))
        t = monta_tabela(sit, med)
        assert list(t["ticker"]) == ["FUNDO3", "RASO3"]
        assert list(t["faixa"]) == [0.025, 0.05]
        # Os números da linha são os do percentil da faixa em que o papel caiu.
        assert t.iloc[1]["lim_inf_45"] == pytest.approx(0.30)

    def test_dentro_da_faixa_vem_primeiro_quem_esta_abaixo_em_mais_janelas(self):
        sit = {"POUCAS3": {"janelas_2_5": 1, "janelas_5": 1, "janelas_medidas": 9},
               "MUITAS3": {"janelas_2_5": 6, "janelas_5": 8, "janelas_medidas": 9}}
        med = pd.DataFrame(_medidas("POUCAS3", 0.025, lim45=0.40) + _medidas("MUITAS3", 0.025))
        assert list(monta_tabela(sit, med)["ticker"]) == ["MUITAS3", "POUCAS3"]

    def test_papel_sem_medida_aparece_com_as_celulas_ausentes(self):
        # Um papel pode ter corte e não ter medida (nenhuma época aprovada na peneira). Ele está na
        # faixa hoje e a página precisa mostrar isso, sem inventar número.
        sit = {"NOVO3": {"janelas_2_5": 1, "janelas_5": 1, "janelas_medidas": 4}}
        t = monta_tabela(sit, pd.DataFrame(_medidas("OUTRO3", 0.025)))
        assert len(t) == 1 and np.isnan(t.iloc[0]["lim_inf_20"])

    def test_dia_sem_ninguem_devolve_a_tabela_vazia_com_as_colunas(self):
        t = monta_tabela({"FORA3": {"janelas_2_5": 0, "janelas_5": 0, "janelas_medidas": 9}},
                         pd.DataFrame(_medidas("FORA3", 0.05)))
        assert t.empty and list(t.columns) == COLUNAS


class TestPagina:
    def _tabela(self):
        sit = {"FUNDO3": {"janelas_2_5": 2, "janelas_5": 4, "janelas_medidas": 9},
               "RASO3": {"janelas_2_5": 0, "janelas_5": 1, "janelas_medidas": 9}}
        med = pd.DataFrame(_medidas("FUNDO3", 0.025) + _medidas("RASO3", 0.05))
        return monta_tabela(sit, med)

    def test_nenhum_marcador_escapa_com_papeis_e_no_dia_vazio(self):
        assert "{{" not in monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 61, 3)
        assert "{{" not in monta_pagina(TEMPLATE, pd.DataFrame(columns=COLUNAS), "2026-10-09", 61)

    def test_as_duas_secoes_aparecem_sempre_e_cada_papel_na_sua(self):
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 61)
        a, b = html.index("Abaixo do percentil de 2,5%"), html.index("Abaixo do percentil de 5%")
        assert a < html.index("FUNDO3") < b < html.index("RASO3")

    def test_secao_vazia_diz_que_esta_vazia(self):
        # O caso comum: a seção não pode sumir nem parecer quebrada.
        html = monta_pagina(TEMPLATE, pd.DataFrame(columns=COLUNAS), "2026-10-09", 61)
        assert html.count("nenhum papel hoje") == 2
        assert "Nenhum papel na faixa extrema hoje" in html

    def test_a_pagina_diz_que_e_indicio_e_nao_achado(self):
        # O aviso faz parte da página, e não de uma nota de rodapé: a tabela exibe frequências por
        # papel, e papel a papel o efeito não é detectável.
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 61)
        assert "Um indício, não um achado" in html
        assert "não é detectável" in html

    def test_a_linha_mostra_frequencia_e_limite_inferior_dos_dois_horizontes(self):
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 61)
        assert "60.0%" in html and "piso 21.0%" in html
        assert "63.0%" in html and "piso 25.0%" in html

    def test_a_barra_marca_a_propria_pagina(self):
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 61)
        assert 'href="extremos.html" aria-current="page"' in html


def test_a_tela_de_gatilhos_avisa_que_a_medida_dela_nao_passou_no_controle():
    # A v2 continua no ar porque conta a evolução da pesquisa — mas quem abre a página precisa
    # saber, na própria página, que o limite inferior dela não é vantagem sobre a taxa-base.
    html = (RAIZ / "template_alertas.html").read_text(encoding="utf-8")
    assert "versão anterior da pesquisa" in html
    assert 'href="extremos.html"' in html

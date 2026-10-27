"""
A tela da faixa extrema (v3): contagem de médias no extremo, critério de destaque e renderização.
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


def _medidas(ticker, q, f20=0.60, f45=0.63, base=0.54):
    comum = {"ticker": ticker, "percentil": q, "taxa_base": base, "lim_inf": 0.2,
             "divisoes_usadas": 5, "inicio_medido": "2006-01-02", "fim_medido": "2026-09-11"}
    return [{**comum, "horizonte": 20, "freq_dias": f20},
            {**comum, "horizonte": 45, "freq_dias": f45}]


def _sit(k25, k5, n=9):
    return {"janelas_2_5": k25, "janelas_5": k5, "janelas_medidas": n}


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
    def test_conta_as_medias_abaixo_de_cada_corte(self):
        s = situacao_do_papel({5: -2.5, 20: -1.7, 90: -0.3}, _cortes())
        # Só a média de 5 passa do corte de 2,5%; a de 5 e a de 20 passam do de 5%.
        assert (s["janelas_2_5"], s["janelas_5"], s["janelas_medidas"]) == (1, 2, 3)
        # E a tabela precisa saber QUAIS, não só quantas.
        assert s["lista_2_5"] == [5] and s["lista_5"] == [5, 20]
        assert s["acompanhadas"] == [5, 20, 90]

    def test_media_sem_escore_nao_conta_nem_a_favor_nem_contra(self):
        # Ausência de medida não é ausência de afastamento: a média sai do denominador.
        s = situacao_do_papel({5: -2.5, 20: float("nan"), 90: -0.3}, _cortes())
        assert s["janelas_medidas"] == 2 and s["janelas_2_5"] == 1


class TestFaixaDeJanelas:
    NOVE = [5, 10, 20, 30, 45, 60, 90, 130, 200]

    def test_uma_janela_so_aparece_como_numero(self):
        from gerar_extremos import faixa_de_janelas
        assert faixa_de_janelas([45], self.NOVE) == "45"

    def test_vizinhas_na_lista_acompanhada_viram_uma_faixa_com_a_contagem(self):
        # O formato da tela de gatilhos: "3–9 (7)". Aqui as vizinhas são as da lista de nove.
        from gerar_extremos import faixa_de_janelas
        assert faixa_de_janelas([10, 20, 30], self.NOVE) == "10–30 (3)"
        assert faixa_de_janelas([10, 20, 30, 90], self.NOVE) == "10–30 (3) · 90"
        assert faixa_de_janelas([], self.NOVE) == ""

    def test_janela_sem_historia_nao_quebra_a_vizinhanca(self):
        # Papel novo sem as médias de 130 e 200: 60 e 90 continuam vizinhas, e 90 é a última.
        from gerar_extremos import faixa_de_janelas
        assert faixa_de_janelas([60, 90], [5, 10, 20, 30, 45, 60, 90]) == "60–90 (2)"


class TestTabela:
    def test_a_secao_de_2_5_mostra_so_as_janelas_de_2_5(self):
        # A confusão relatada em 19/10/2026: na tabela de 2,5% aparecia "1 de 9 · 2 abaixo de 5%".
        # A linha passa a mostrar só as janelas que passaram do corte DAQUELA tabela.
        s = situacao_do_papel({5: -2.5, 20: -1.7, 90: -0.3}, _cortes())
        t = monta_tabela({"WEGE3": s}, pd.DataFrame(_medidas("WEGE3", 0.025))).iloc[0]
        assert t["faixa"] == 0.025 and t["janelas"] == "5"
        html = monta_pagina(TEMPLATE, monta_tabela({"WEGE3": s}, pd.DataFrame(_medidas("WEGE3", 0.025))),
                            "2026-10-16", 98)
        assert "abaixo de 5%</span>" not in html and " de 9" not in html

    def test_classifica_na_faixa_mais_funda_e_deixa_de_fora_quem_nao_esta(self):
        sit = {"FUNDO3": _sit(2, 4), "RASO3": _sit(0, 1), "FORA3": _sit(0, 0)}
        med = pd.DataFrame(_medidas("FUNDO3", 0.025) + _medidas("FUNDO3", 0.05)
                           + _medidas("RASO3", 0.025) + _medidas("RASO3", 0.05, f45=0.70))
        t = monta_tabela(sit, med)
        assert list(t["ticker"]) == ["FUNDO3", "RASO3"]
        assert list(t["faixa"]) == [0.025, 0.05]
        # Os números da linha são os do percentil da faixa em que o papel caiu, em 45 pregões.
        assert t.iloc[1]["freq"] == pytest.approx(0.70)
        assert list(t["horizonte"]) == [45, 45]

    def test_na_falta_do_horizonte_de_45_a_linha_usa_o_de_20(self):
        # Pedido do usuário em 13/10/2026: vale o de 45 pregões, "seguido pelo de 20 dias, na
        # ausência do de 45".
        med = pd.DataFrame([m for m in _medidas("CURTO3", 0.025, f20=0.58) if m["horizonte"] == 20])
        t = monta_tabela({"CURTO3": _sit(1, 1)}, med).iloc[0]
        assert t["horizonte"] == 20 and t["freq"] == pytest.approx(0.58)

    def test_marca_quem_tem_frequencia_acima_da_taxa_base(self):
        # O critério de exibição do usuário: só é destaque o papel em que estar na faixa veio com
        # retorno positivo mais vezes que num dia qualquer. O caso real foi a NATU3 em 13/10/2026:
        # 51,4% de frequência contra 52,8% de taxa-base — está na faixa, e não é destaque.
        sit = {"NATU3": _sit(0, 1, 6), "BOM3": _sit(1, 1)}
        med = pd.DataFrame(_medidas("NATU3", 0.05, f45=0.514, base=0.528) + _medidas("BOM3", 0.025))
        t = monta_tabela(sit, med).set_index("ticker")
        assert bool(t.loc["BOM3", "acima_da_base"]) is True
        assert bool(t.loc["NATU3", "acima_da_base"]) is False

    def test_dentro_da_faixa_vem_primeiro_quem_esta_no_extremo_em_mais_medias(self):
        sit = {"POUCAS3": _sit(1, 1), "MUITAS3": _sit(6, 8)}
        med = pd.DataFrame(_medidas("POUCAS3", 0.025, f45=0.90) + _medidas("MUITAS3", 0.025))
        assert list(monta_tabela(sit, med)["ticker"]) == ["MUITAS3", "POUCAS3"]

    def test_papel_sem_medida_fica_na_tabela_do_dia_mas_nao_e_destaque(self):
        # Sem medida não há como saber se a frequência supera a taxa-base. O papel fica no arquivo
        # do dia, com as células ausentes, e fora da tela.
        t = monta_tabela({"NOVO3": _sit(1, 1, 4)}, pd.DataFrame(_medidas("OUTRO3", 0.025)))
        assert len(t) == 1 and np.isnan(t.iloc[0]["freq"])
        assert bool(t.iloc[0]["acima_da_base"]) is False

    def test_dia_sem_ninguem_devolve_a_tabela_vazia_com_as_colunas(self):
        t = monta_tabela({"FORA3": _sit(0, 0)}, pd.DataFrame(_medidas("FORA3", 0.05)))
        assert t.empty and list(t.columns) == COLUNAS


class TestFrequenciaDasJanelasNoExtremo:
    def _detalhe(self):
        # Duas janelas com frequências bem diferentes, para a média das nove não esconder nada.
        comum = {"ticker": "BOM3", "percentil": 0.025, "dias": 30, "episodios": 4,
                 "divisoes_usadas": 4, "inicio_medido": "2010-01-04", "fim_medido": "2026-09-11"}
        return pd.DataFrame([{**comum, "horizonte": 45, "janela": 10, "freq_dias": 0.80, "taxa_base": 0.55},
                             {**comum, "horizonte": 45, "janela": 90, "freq_dias": 0.40, "taxa_base": 0.57},
                             {**comum, "horizonte": 20, "janela": 30, "freq_dias": 0.70, "taxa_base": 0.52}])

    def test_a_frequencia_e_a_das_janelas_que_dispararam(self):
        # Pedido do usuário em 19/10/2026: a frequência da linha é a das janelas no extremo hoje.
        sit = {"BOM3": {**_sit(1, 1), "lista_2_5": [10], "lista_5": [10], "acompanhadas": [10, 30, 90]}}
        t = monta_tabela(sit, pd.DataFrame(_medidas("BOM3", 0.025)), self._detalhe()).iloc[0]
        assert t["freq"] == pytest.approx(0.80) and t["taxa_base"] == pytest.approx(0.55)
        assert t["janelas"] == "10"

    def test_varias_janelas_pesam_igual(self):
        sit = {"BOM3": {**_sit(2, 2), "lista_2_5": [10, 90], "lista_5": [10, 90],
                        "acompanhadas": [10, 30, 90]}}
        t = monta_tabela(sit, pd.DataFrame(_medidas("BOM3", 0.025)), self._detalhe()).iloc[0]
        assert t["freq"] == pytest.approx(0.60) and t["taxa_base"] == pytest.approx(0.56)
        # 0,60 contra 0,56: é destaque.
        assert bool(t["acima_da_base"]) is True

    def test_janela_que_so_tem_medida_em_20_usa_o_horizonte_de_20(self):
        sit = {"BOM3": {**_sit(1, 1), "lista_2_5": [30], "lista_5": [30], "acompanhadas": [10, 30, 90]}}
        t = monta_tabela(sit, pd.DataFrame(_medidas("BOM3", 0.025)), self._detalhe()).iloc[0]
        assert t["horizonte"] == 20 and t["freq"] == pytest.approx(0.70)


class TestPagina:
    def _tabela(self):
        sit = {"FUNDO3": _sit(2, 4), "RASO3": _sit(0, 1), "NATU3": _sit(0, 1, 6)}
        med = pd.DataFrame(_medidas("FUNDO3", 0.025) + _medidas("RASO3", 0.05)
                           + _medidas("NATU3", 0.05, f45=0.514, base=0.528))
        return monta_tabela(sit, med)

    def _so_abaixo(self):
        med = pd.DataFrame(_medidas("NATU3", 0.05, f45=0.514, base=0.528))
        return monta_tabela({"NATU3": _sit(0, 1, 6)}, med)

    def test_nenhum_marcador_escapa_em_nenhum_dos_tres_estados(self):
        vazio = pd.DataFrame(columns=COLUNAS)
        for t in (self._tabela(), self._so_abaixo(), vazio):
            assert "{{" not in monta_pagina(TEMPLATE, t, "2026-10-09", 98, 3)

    def test_so_aparece_quem_tem_frequencia_acima_da_taxa_base(self):
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 98)
        assert "FUNDO3" in html and "RASO3" in html
        assert "<td class='esq papel'>NATU3" not in html
        assert "2 destaques na faixa extrema" in html
        # E a página diz que houve papel na faixa sem destaque, com o número.
        assert "1 papel está na faixa extrema hoje, mas sem destaque" in html

    def test_dia_em_que_ha_papel_na_faixa_mas_nenhum_destaque(self):
        # O caso de 13/10/2026: a NATU3 na faixa, com frequência abaixo da taxa-base.
        html = monta_pagina(TEMPLATE, self._so_abaixo(), "2026-10-09", 98)
        assert "Nenhum destaque hoje" in html
        assert html.count("nenhum destaque hoje") == 2
        assert "1 papel está na faixa extrema hoje, mas sem destaque" in html

    def test_dia_sem_papel_nenhum_na_faixa(self):
        html = monta_pagina(TEMPLATE, pd.DataFrame(columns=COLUNAS), "2026-10-09", 98)
        assert "Nenhum destaque hoje" in html
        assert "Nenhum papel está na faixa extrema hoje." in html

    def test_as_duas_secoes_aparecem_sempre_e_cada_papel_na_sua(self):
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 98)
        a, b = html.index("Abaixo do percentil de 2,5%"), html.index("Abaixo do percentil de 5%")
        assert a < html.index("FUNDO3") < b < html.index("RASO3")

    def test_a_pagina_diz_que_e_indicio_e_nao_achado(self):
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 98)
        assert "Um indício, não um achado" in html
        assert "não é detectável" in html

    def test_a_tabela_mostra_frequencia_e_taxa_base_sem_limite_inferior(self):
        # A coluna de limite inferior foi trocada pela de frequência (usuário, 13/10/2026): o piso
        # de 21% contra taxa-base de 53% foi lido como se fosse o placebo.
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 98)
        assert "<th>frequência</th>" in html and "<th>taxa-base</th>" in html
        assert "limite inferior" not in html
        assert "63.0%" in html and "54.0%" in html

    def test_a_coluna_das_medias_explica_o_que_conta(self):
        # "Janelas abaixo do corte" não se lia sozinho; o cabeçalho e o glossário dizem agora que
        # são médias móveis e quantas são.
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 98)
        assert "janela <span class='sub2'>(faixa de janelas)</span>" in html
        assert "5, 10, 20, 30, 45" in html

    def test_a_barra_marca_a_propria_pagina(self):
        html = monta_pagina(TEMPLATE, self._tabela(), "2026-10-09", 98)
        assert 'href="extremos.html" aria-current="page"' in html


def test_a_tela_de_gatilhos_avisa_que_a_medida_dela_nao_passou_no_controle():
    # A v2 continua no ar porque conta a evolução da pesquisa — mas quem abre a página precisa
    # saber, na própria página, que o limite inferior dela não é vantagem sobre a taxa-base.
    html = (RAIZ / "template_alertas.html").read_text(encoding="utf-8")
    assert "versão anterior da pesquisa" in html
    assert 'href="extremos.html"' in html

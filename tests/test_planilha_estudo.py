"""
A planilha de estudo das telas v2 e v3: o arranjo de treino e teste, linha a linha.
"""
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import gerar_alertas
import gerar_extremos
from planilha_estudo import DICIONARIO, grava_planilha, link_planilha, monta_estudo

DIVISOES = [("2014-01-01", "2018-01-01"), ("2018-01-01", "2022-01-01")]
RAIZ = Path(__file__).resolve().parents[1]


def _precos(n=3200, semente=5):
    rng = np.random.default_rng(semente)
    close = 30 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, size=n)))
    idx = pd.bdate_range("2010-01-04", periods=n)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close,
                         "Volume": 9_000_000.0}, index=idx)


@pytest.fixture(scope="module")
def estudo():
    return monta_estudo(_precos(), 20, 20, 0.10, DIVISOES)


class TestArranjoDeTreinoETeste:
    def test_as_colunas_seguem_a_ordem_em_que_uma_nasce_da_outra(self, estudo):
        serie, _ = estudo
        assert list(serie.columns) == ["Close", "mma_w20", "mma_dist_w20", "mma_dist_z_w20",
                                       "ret_20d", "divisao", "conjunto", "treino_ate",
                                       "corte_usado", "na_faixa", "episodio", "retorno_positivo"]

    def test_cada_linha_tem_um_papel_e_os_quatro_aparecem(self, estudo):
        serie, _ = estudo
        assert set(serie["conjunto"]) == {"aquecimento", "só treino", "teste", "sem_retorno"}
        # As últimas linhas não têm retorno futuro: é onde está o pregão de hoje.
        assert (serie["conjunto"].iloc[-20:] == "sem_retorno").all()

    def test_o_corte_de_cada_divisao_vem_so_do_passado_dela(self, estudo):
        # A regra que a planilha existe para deixar visível: o treino termina ANTES do teste, com
        # o embargo do tamanho do horizonte entre os dois.
        serie, resumo = estudo
        for _, r in resumo.iterrows():
            teste = serie[serie["divisao"] == r["divisao"]]
            assert r["treino_ate"] < str(teste.index[0].date())
            utilizaveis = serie[serie["mma_dist_z_w20"].notna() & serie["ret_20d"].notna()]
            entre = utilizaveis[(utilizaveis.index > r["treino_ate"])
                                & (utilizaveis.index < teste.index[0])]
            assert len(entre) == 20
            # E o corte é o percentil pedido, calculado nessas linhas de treino e só nelas.
            treino = utilizaveis[utilizaveis.index <= r["treino_ate"]]["mma_dist_z_w20"]
            assert r["corte_usado"] == pytest.approx(np.quantile(treino, 0.10))

    def test_a_segunda_divisao_treina_com_mais_historia_que_a_primeira(self, estudo):
        # Treino acumulado: cada divisão usa tudo o que veio antes dela.
        _, resumo = estudo
        assert list(resumo["divisao"]) == ["2014–2018", "2018–2022"]
        assert resumo.iloc[1]["linhas_de_treino"] > resumo.iloc[0]["linhas_de_treino"]

    def test_na_faixa_e_o_escore_no_corte_ou_abaixo_dele(self, estudo):
        serie, _ = estudo
        t = serie[serie["conjunto"] == "teste"]
        assert ((t["mma_dist_z_w20"] <= t["corte_usado"]) == t["na_faixa"]).all()
        # Fora do teste ninguém está "na faixa": não há corte para comparar.
        assert not serie[serie["conjunto"] != "teste"]["na_faixa"].any()

    def test_dias_seguidos_na_faixa_formam_um_episodio_so(self, estudo):
        serie, resumo = estudo
        na = serie[serie["na_faixa"]]
        assert na["episodio"].notna().all()
        # Há menos episódios que dias, e o resumo conta os dois.
        assert na["episodio"].nunique() < len(na)
        assert resumo["dias_na_faixa"].sum() == len(na)

    def test_o_resumo_traz_as_duas_contas_a_por_dia_e_a_por_episodio(self, estudo):
        # A v3 conta dias; a v2 contava episódios. A planilha mostra as duas lado a lado, que é o
        # jeito mais direto de ver por que elas dão números diferentes.
        _, resumo = estudo
        for c in ("freq_positiva_na_faixa", "taxa_base", "episodios", "episodios_positivos"):
            assert c in resumo.columns
        assert (resumo["episodios_positivos"] <= resumo["episodios"]).all()

    def test_divisao_sem_treino_bastante_nao_vira_teste(self):
        # A divisão de 2010 não tem história anterior para calcular o corte.
        serie, resumo = monta_estudo(_precos(), 20, 20, 0.10,
                                     [("2010-01-01", "2014-01-01")] + DIVISOES)
        assert "2010–2014" not in set(resumo["divisao"])
        assert (serie[serie.index < "2014-01-01"]["conjunto"] != "teste").all()


class TestArquivo:
    def test_grava_uma_aba_por_janela_mais_o_resumo_e_a_legenda(self, estudo):
        with tempfile.TemporaryDirectory() as d:
            caminho = grava_planilha(Path(d) / "dados" / "extremos_AAAA3.xlsx",
                                     [("20",) + estudo, ("45",) + estudo])
            # `with` fecha o arquivo antes de a pasta temporária ser apagada (o Windows exige).
            with pd.ExcelFile(caminho) as arquivo:
                abas = arquivo.sheet_names
            assert abas == ["janela 20", "janela 45", "divisões", "dicionário"]
            # A aba de resumo diz de qual janela é cada linha.
            assert set(pd.read_excel(caminho, sheet_name="divisões")["janela"]) == {20, 45}

    def test_a_legenda_explica_a_coluna_conjunto(self):
        # Planilha de estudo sem a explicação das colunas não ensina nada.
        texto = dict(DICIONARIO)
        assert "teste" in texto["conjunto"] and "aquecimento" in texto["conjunto"]


class TestLinkNasPaginas:
    def test_o_link_aponta_para_a_pasta_de_dados_e_baixa(self):
        html = link_planilha("gatilhos_VALE3.xlsx", "VALE3")
        assert "href='dados/gatilhos_VALE3.xlsx'" in html and "download" in html

    def _ranking_v3(self):
        sit = {"BOM3": {"janelas_2_5": 1, "janelas_5": 2, "janelas_medidas": 9}}
        comum = {"ticker": "BOM3", "percentil": 0.025, "taxa_base": 0.54, "divisoes_usadas": 5,
                 "inicio_medido": "2006-01-02", "fim_medido": "2026-09-11"}
        med = pd.DataFrame([{**comum, "horizonte": 45, "freq_dias": 0.63}])
        return gerar_extremos.monta_tabela(sit, med)

    def test_a_faixa_extrema_so_linka_a_planilha_que_foi_gravada(self):
        # Link para arquivo que não existe vira erro no navegador: o papel sem planilha mostra "—".
        t = (RAIZ / "template_extremos.html").read_text(encoding="utf-8")
        com = gerar_extremos.monta_pagina(t, self._ranking_v3(), "2026-10-09", 98, None, {"BOM3"})
        sem = gerar_extremos.monta_pagina(t, self._ranking_v3(), "2026-10-09", 98)
        assert "dados/extremos_BOM3.xlsx" in com and "<th class='esq'>dados</th>" in com
        assert "dados/extremos_BOM3.xlsx" not in sem

    def test_a_tela_de_gatilhos_tambem_tem_a_coluna_de_dados(self):
        a = pd.DataFrame([{"posicao_papel": 2, "total_papeis": 61, "ticker": "VALE3",
                           "horizonte": 45, "janela_de": 24, "janela_ate": 28, "janela_ref": 26,
                           "n_setups": 5, "episodios": 40, "protecao": 0.8, "prot_lo": 0.59,
                           "taxa_base": 0.55, "divisoes_usadas": 5,
                           "inicio_medido": "2006-01-02", "fim_medido": "2026-09-11"}])
        t = (RAIZ / "template_alertas.html").read_text(encoding="utf-8")
        html = gerar_alertas.monta_pagina(t, a, "2026-10-09", 61, {"VALE3"})
        assert "dados/gatilhos_VALE3.xlsx" in html and "<th class='esq'>dados</th>" in html
        # A janela que a planilha abre é a do melhor setup da faixa.
        assert gerar_alertas.ranqueia_papeis(a).iloc[0]["janela_ref"] == 26

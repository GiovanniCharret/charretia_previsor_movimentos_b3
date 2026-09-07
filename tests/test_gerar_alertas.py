import numpy as np
import pandas as pd
import pytest

from gerar_alertas import (pregoes_necessarios, periodo_do_download, estado_das_janelas,
                           agrupa_faixas_contiguas, monta_alertas, monta_pagina)


def _precos(n, final_em_queda=False, semente=3):
    # Passeio multiplicativo (o aditivo chega a preço negativo em séries longas), com opção de
    # terminar despencando — que é o estado que precisa disparar o alerta.
    rng = np.random.default_rng(semente)
    close = 30 * np.exp(np.cumsum(rng.normal(0.0, 0.011, size=n)))
    if final_em_queda:
        # Últimos 15 pregões caindo forte: o fechamento fica bem abaixo de qualquer média móvel.
        close[-15:] = close[-16] * np.linspace(0.98, 0.70, 15)
    idx = pd.bdate_range("2019-01-01", periods=n)
    return pd.DataFrame({"Open": close, "High": close, "Low": close,
                         "Close": close, "Volume": 9_000_000.0}, index=idx)


class TestQuantoBaixar:
    def test_pregoes_necessarios_soma_janela_desvio_e_folga(self):
        # O escore de hoje só existe depois de `janela + desvio - 1` pregões. Foi o furo que os
        # 200 dias pedidos originalmente teriam aberto: com janela 200 não haveria escore nenhum.
        assert pregoes_necessarios(200, vol_lag=252, folga=40) == 200 + 252 - 1 + 40
        assert pregoes_necessarios(10, vol_lag=252, folga=40) == 10 + 252 - 1 + 40

    def test_periodo_do_download_arredonda_para_cima_e_nunca_encolhe(self):
        # Pedir menos que o necessário produziria escore ausente em silêncio.
        assert periodo_do_download(491, pregoes_por_ano=248) == "2y"
        assert periodo_do_download(301, pregoes_por_ano=248) == "2y"
        assert periodo_do_download(700, pregoes_por_ano=248) == "3y"
        # Nunca menos de um ano, por mais curta que seja a janela.
        assert periodo_do_download(50, pregoes_por_ano=248) == "1y"


class TestEstadoDasJanelas:
    def test_marca_disparo_comparando_o_escore_de_hoje_com_o_corte_recebido(self):
        # O laço 1 do script. O corte NÃO é calculado aqui: vem do laboratório, medido sobre a
        # história completa. Recalculá-lo com a história curta que a aplicação baixa foi o defeito
        # de 06/09 — na GGBR4 o corte ia de -2,010 para +0,465, trocando de sinal.
        p = _precos(600, final_em_queda=True)
        e = estado_das_janelas(p, {10: -1.0, 20: -1.0}, vol_lag=252, slope_lag=5)
        assert set(e["janela"]) == {10, 20}
        assert e["dispara"].all(), e.to_string()
        # Disparar é o escore de hoje estar no corte ou abaixo dele.
        assert (e["z_hoje"] <= e["corte"]).all()

    def test_nao_dispara_quando_o_escore_esta_acima_do_corte(self):
        e = estado_das_janelas(_precos(600), {10: -3.0, 20: -3.0}, vol_lag=252, slope_lag=5)
        assert not e["dispara"].any()

    def test_janela_sem_historico_suficiente_sai_como_indefinida(self):
        # Série de 300 pregões não comporta janela 200 (precisaria de 451). A resposta honesta é
        # ausência de medida, nunca um falso negativo silencioso.
        e = estado_das_janelas(_precos(300), {10: -1.0, 200: -1.0}, vol_lag=252, slope_lag=5)
        j200 = e[e["janela"] == 200].iloc[0]
        assert np.isnan(j200["z_hoje"])
        assert bool(j200["dispara"]) is False
        assert j200["motivo"] != ""

    def test_janela_sem_corte_no_estudo_nao_dispara_e_diz_por_que(self):
        # O laboratório deixa o corte ausente quando o quantil não tinha escores bastantes. A
        # aplicação não pode inventar um: sem corte, não há gatilho.
        e = estado_das_janelas(_precos(600, final_em_queda=True), {10: float("nan")},
                               vol_lag=252, slope_lag=5)
        assert bool(e.iloc[0]["dispara"]) is False
        assert "corte" in e.iloc[0]["motivo"]


class TestAgrupaFaixas:
    def test_agrupa_janelas_contiguas_em_uma_faixa(self):
        # A EGIE3 dispara em dezenas de janelas vizinhas ao mesmo tempo. Listar todas sugeriria
        # dezenas de gatilhos onde há um: janelas vizinhas compartilham ~99% dos dados.
        assert agrupa_faixas_contiguas([93, 94, 95, 100, 101, 150]) == [(93, 95), (100, 101), (150, 150)]
        assert agrupa_faixas_contiguas([]) == []
        assert agrupa_faixas_contiguas([7]) == [(7, 7)]


class TestMontaAlertas:
    def _aprovados(self):
        return pd.DataFrame([
            {"ticker": "AAAA3", "horizonte": 3, "janela": 10, "episodios": 40, "protecao": 0.90,
             "prot_lo": 0.75, "taxa_base": 0.50, "passa_barra": True, "posicao_papel": 1,
             "divisoes_usadas": 5, "inicio_medido": "2006-03-01", "fim_medido": "2026-08-31"},
            {"ticker": "AAAA3", "horizonte": 3, "janela": 11, "episodios": 39, "protecao": 0.89,
             "prot_lo": 0.74, "taxa_base": 0.50, "passa_barra": True, "posicao_papel": 1,
             "divisoes_usadas": 5, "inicio_medido": "2006-03-01", "fim_medido": "2026-08-31"},
            {"ticker": "AAAA3", "horizonte": 20, "janela": 10, "episodios": 35, "protecao": 0.80,
             "prot_lo": 0.66, "taxa_base": 0.50, "passa_barra": True, "posicao_papel": 1,
             "divisoes_usadas": 5, "inicio_medido": "2006-03-01", "fim_medido": "2026-08-31"},
            {"ticker": "BBBB3", "horizonte": 3, "janela": 50, "episodios": 30, "protecao": 0.85,
             "prot_lo": 0.70, "taxa_base": 0.50, "passa_barra": True, "posicao_papel": 2,
             "divisoes_usadas": 2, "inicio_medido": "2018-01-02", "fim_medido": "2026-09-04"},
        ])

    def test_so_entram_os_setups_cuja_janela_disparou(self):
        # O laço 2: cruzar os aprovados com o estado de hoje. A BBBB3 não disparou, então some.
        estados = {("AAAA3", 10): True, ("AAAA3", 11): True, ("BBBB3", 50): False}
        a = monta_alertas(self._aprovados(), estados)
        assert set(a["ticker"]) == {"AAAA3"}
        # Uma linha por (papel, horizonte, faixa contígua): as janelas 10 e 11 viram uma faixa.
        assert len(a) == 2
        assert sorted(a["horizonte"]) == [3, 20]

    def test_agrupa_as_janelas_vizinhas_e_guarda_o_intervalo(self):
        estados = {("AAAA3", 10): True, ("AAAA3", 11): True, ("BBBB3", 50): False}
        a = monta_alertas(self._aprovados(), estados)
        h3 = a[a["horizonte"] == 3].iloc[0]
        assert h3["janela_de"] == 10 and h3["janela_ate"] == 11
        assert h3["n_setups"] == 2
        # A proteção exibida é a do melhor setup da faixa, não uma média que ninguém mediu.
        assert h3["protecao"] == pytest.approx(0.90)
        assert h3["prot_lo"] == pytest.approx(0.75)

    def test_a_colocacao_vem_com_o_denominador_do_ranking(self):
        # "#31" não se lê sozinho: 31 de 61 é meio de tabela, 31 de 32 é o fim dela. O denominador
        # sai da tabela inteira quando não é informado.
        estados = {("AAAA3", 10): True, ("AAAA3", 11): True, ("BBBB3", 50): False}
        a = monta_alertas(self._aprovados(), estados)
        assert (a["total_papeis"] == 2).all()

    def test_o_denominador_informado_prevalece_sobre_a_tabela_filtrada(self):
        # Rodar para um papel só filtra a tabela; se o denominador viesse dela, "#31/61" viraria
        # "#31/31" e a leitura inverteria de sentido.
        ap = self._aprovados()
        so_um = ap[ap["ticker"] == "AAAA3"]
        a = monta_alertas(so_um, {("AAAA3", 10): True, ("AAAA3", 11): True}, total_papeis=61)
        assert (a["total_papeis"] == 61).all()

    def test_o_ganho_nao_aparece_na_tabela(self):
        # O usuário pediu a coluna fora em 06/09: exibir o ganho enviesa a decisão, porque sugere
        # que o objetivo é ganhar. O objetivo declarado é proteger.
        a = monta_alertas(self._aprovados(), {("AAAA3", 10): True})
        assert "ganho_pp" not in a.columns

    def test_sem_nenhum_disparo_devolve_tabela_vazia_com_as_colunas(self):
        # Dia sem alerta é o caso comum — a página precisa saber desenhar o vazio.
        a = monta_alertas(self._aprovados(), {("AAAA3", 10): False, ("AAAA3", 11): False,
                                              ("BBBB3", 50): False})
        assert a.empty
        assert "ticker" in a.columns and "horizonte" in a.columns

    def test_a_linha_menos_pior_nao_vira_alerta(self):
        # A IRBR3 entra na planilha com `passa_barra` falso. Ela pode disparar o decil, mas não é
        # gatilho — exibi-la ao lado dos aprovados seria apresentar como sinal o que não é.
        ap = pd.DataFrame([{"ticker": "IRBR3", "horizonte": 3, "janela": 3, "episodios": 65,
                            "protecao": 0.57, "prot_lo": 0.44, "taxa_base": 0.49,
                            "passa_barra": False, "posicao_papel": 61,
                            "divisoes_usadas": 4, "inicio_medido": "2010-01-04",
                            "fim_medido": "2026-09-04"}])
        assert monta_alertas(ap, {("IRBR3", 3): True}).empty

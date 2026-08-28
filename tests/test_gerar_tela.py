import re
from datetime import datetime, timezone

import numpy as np, pandas as pd, pytest
from gerar_tela import (classifica_evidencia, estado_de_hoje, monta_pagina,
                        seleciona_destaques, FUSO_BRASILIA, MARCADORES)


def _papel(ticker, decil, episodios=8, excesso=0.02, media=0.05):
    """Papel mínimo para testar ordenação — só os campos que entram nos critérios."""
    return {"ticker": ticker, "decil": decil, "dist": -0.1, "media": media, "base": media - excesso,
            "excesso": excesso, "freq_pos": 0.6, "episodios": episodios, "n_dias": 100}


class TestSelecionaDestaques:
    def test_corta_no_limite_pedido(self):
        papeis = [_papel(f"AAA{i}", decil=i % 3) for i in range(20)]
        assert len(seleciona_destaques(papeis, 5)) == 5

    def test_decil_mais_baixo_vem_primeiro(self):
        escolhidos = seleciona_destaques([_papel("ALTO", 7), _papel("BAIXO", 0),
                                          _papel("MEIO", 2)], 3)
        assert [p["ticker"] for p, _, _, _ in escolhidos] == ["BAIXO", "MEIO", "ALTO"]

    def test_empate_no_decil_e_desempatado_pela_evidencia(self):
        # Mesmo decil, mesmo excesso: quem tem mais episódios (evidência mais forte) vem antes.
        papeis = [_papel("FRACO", 0, episodios=3), _papel("FORTE", 0, episodios=20),
                  _papel("MODER", 0, episodios=8)]
        assert [p["ticker"] for p, _, _, _ in seleciona_destaques(papeis, 3)] == \
            ["FORTE", "MODER", "FRACO"]

    def test_alerta_perde_para_evidencia_fraca(self):
        # "contradiz o padrão" (excesso negativo na zona) é anti-sinal: não pode passar à frente
        # de uma linha fraca porém coerente, por mais episódios que tenha.
        papeis = [_papel("ALERTA", 0, episodios=30, excesso=-0.02),
                  _papel("FRACO", 0, episodios=3, excesso=0.01)]
        assert [p["ticker"] for p, _, _, _ in seleciona_destaques(papeis, 2)] == ["FRACO", "ALERTA"]

    def test_devolve_a_classificacao_junto(self):
        # A classificação sai daqui para que a tabela e a escolha das planilhas nunca divirjam.
        (papel, na_zona, classe, rotulo), = seleciona_destaques([_papel("XPTO", 0)], 5)
        assert papel["ticker"] == "XPTO" and na_zona is True
        assert classe == "c-moderada" and rotulo == "moderada"


def _precos(n=2500, semente=3):
    # Passeio com reversão à média, longo o bastante para aquecimento + treino + teste.
    rng = np.random.default_rng(semente)
    close = np.empty(n); close[0] = 100.0
    for i in range(1, n):
        close[i] = close[i-1] + 0.25 * (100.0 - close[i-1]) / 10.0 + rng.normal(0, 1.0)
    idx = pd.bdate_range(end=pd.Timestamp("2026-08-21"), periods=n)
    return pd.DataFrame({"Open": close, "High": close, "Low": close,
                         "Close": close, "Volume": 1e6}, index=idx)


class TestClassificaEvidencia:
    def test_alerta_vence_tudo_quando_bate_a_base_mas_perde(self):
        # O caso MGLU3: excesso positivo e retorno absoluto negativo. É o rótulo mais importante,
        # porque é o único que separa "melhor que a própria média" de "ganha dinheiro".
        c, r = classifica_evidencia(episodios=20, excesso=0.035, media=-0.044, na_zona=True)
        assert c == "c-alerta" and "perde" in r

    def test_alerta_quando_o_historico_contradiz(self):
        # Excesso negativo dentro da zona: o decil baixo rendeu PIOR que a base (caso CSNA3).
        c, r = classifica_evidencia(episodios=20, excesso=-0.027, media=-0.055, na_zona=True)
        assert c == "c-alerta" and "contradiz" in r

    def test_fora_da_zona_nao_recebe_forca(self):
        # Papel que não está nos decis baixos não é sinal, por melhor que seja o histórico.
        c, r = classifica_evidencia(episodios=30, excesso=0.08, media=0.09, na_zona=False)
        assert c == "c-fraca" and "fora da zona" in r

    def test_escala_por_episodios(self):
        # A força mede EVIDÊNCIA (nº de episódios), não tamanho do retorno.
        assert classifica_evidencia(20, 0.05, 0.06, True)[0] == "c-forte"
        assert classifica_evidencia(8, 0.05, 0.06, True)[0] == "c-moderada"
        assert classifica_evidencia(3, 0.05, 0.06, True)[0] == "c-fraca"

    def test_retorno_alto_com_poucos_episodios_continua_fraco(self):
        # Retorno enorme sustentado por 2 episódios não vira evidência forte.
        c, _ = classifica_evidencia(episodios=2, excesso=0.30, media=0.35, na_zona=True)
        assert c == "c-fraca"


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


def test_monta_pagina_mostra_no_maximo_o_limite():
    # Tabela longa demais polui a leitura: a tela mostra só os primeiros por posição no decil.
    template = open("template.html", encoding="utf-8").read()
    indice = _papel("BOVA11", 3)
    html = monta_pagina(indice, [_papel(f"AAA{i}", i % 4) for i in range(20)], template, top_n=5)
    # `class="papel"` só existe nas linhas do corpo — contar "<tr" incluiria o cabeçalho.
    assert html.count('class="papel"') == 5
    # E só os exibidos ganham link de download, senão a página apontaria para arquivo inexistente.
    assert html.count('href="dados/') == 6                      # 5 papéis + o índice


def test_legenda_explica_todos_os_rotulos_possiveis():
    # Todo rótulo que a tela consegue emitir precisa estar explicado na legenda — senão o leitor
    # encontra um chip sem tradução, que foi exatamente o defeito relatado.
    template = open("template.html", encoding="utf-8").read()
    emitidos = {classifica_evidencia(ep, ex, me, zona)[1]
                for ep in (2, 8, 20) for ex in (-0.01, 0.01) for me in (-0.01, 0.01)
                for zona in (True, False)}
    for rotulo in emitidos:
        assert f">{rotulo}</span>" in template, f"rótulo sem explicação na legenda: {rotulo}"


def test_monta_pagina_inclui_links_de_download():
    # Um arquivo por papel visível na tela — índice inclusive.
    template = open("template.html", encoding="utf-8").read()
    indice = {"ticker": "BOVA11", "decil": 3, "dist": -0.027, "media": 0.016, "base": 0.016,
              "excesso": 0.0, "freq_pos": 0.51, "episodios": 10, "n_dias": 120}
    papeis = [{"ticker": "RENT3", "decil": 0, "dist": -0.173, "media": 0.108, "base": -0.002,
               "excesso": 0.110, "freq_pos": 0.73, "episodios": 7, "n_dias": 90}]
    html = monta_pagina(indice, papeis, template)
    assert 'href="dados/BOVA11.xlsx"' in html
    assert 'href="dados/RENT3.xlsx"' in html
    # O atributo `download` é o que faz o navegador salvar em vez de tentar abrir.
    assert html.count("download") >= 2
    # O botão da tabela NÃO pode usar a classe `mini`, que pertence à régua de decis: a colisão
    # faria ele herdar um grid de dez colunas e esticar. Só o navegador revela isso, então o
    # nome fica travado aqui.
    assert 'class="baixar mini"' not in html
    assert 'class="baixar compacto"' in html


def test_monta_pagina_substitui_todos_os_marcadores():
    # Nenhum marcador pode sobrar na página final — sobra de marcador é bug visível ao usuário.
    template = open("template.html", encoding="utf-8").read()
    indice = {"ticker": "BOVA11", "decil": 3, "dist": -0.027, "media": 0.016, "base": 0.016,
              "excesso": 0.0, "freq_pos": 0.51, "episodios": 10, "n_dias": 120}
    papeis = [{"ticker": "RENT3", "decil": 0, "dist": -0.173, "media": 0.108, "base": -0.002,
               "excesso": 0.110, "freq_pos": 0.73, "episodios": 7, "n_dias": 90}]
    html = monta_pagina(indice, papeis, template)
    for m in MARCADORES:
        assert "{{" + m + "}}" not in html, f"marcador {m} não substituído"
    assert "RENT3" in html and "BOVA11" in html


def test_monta_pagina_marca_o_decil_atual_na_regua():
    template = open("template.html", encoding="utf-8").read()
    indice = {"ticker": "BOVA11", "decil": 7, "dist": 0.05, "media": 0.01, "base": 0.01,
              "excesso": 0.0, "freq_pos": 0.5, "episodios": 8, "n_dias": 100}
    html = monta_pagina(indice, [], template)
    # a régua tem 10 segmentos e exatamente um marcado como "aqui".
    assert html.count('class="seg aqui"') == 1
    # o segmento marcado carrega o número do decil atual.
    assert '<div class="seg aqui"><i>7</i></div>' in html


class TestCarimboDeExecucao:
    def test_usa_o_horario_recebido(self):
        # O carimbo é injetável para o teste poder fixar o instante — sem isso a única verificação
        # possível seria por expressão regular, que não pega erro de formato.
        template = open("template.html", encoding="utf-8").read()
        html = monta_pagina(_papel("BOVA11", 3), [], template,
                            agora=datetime(2026, 8, 23, 18, 34, tzinfo=FUSO_BRASILIA))
        assert "23/08/2026 às 18h34" in html

    def test_converte_horario_de_outro_fuso(self):
        # O GitHub Actions roda em UTC: sem a conversão, a página anunciaria 21h34 para um pregão
        # que fechou às 18h34 — três horas de erro no único número que o leitor pode conferir
        # contra o próprio relógio.
        template = open("template.html", encoding="utf-8").read()
        html = monta_pagina(_papel("BOVA11", 3), [], template,
                            agora=datetime(2026, 8, 23, 21, 34, tzinfo=timezone.utc))
        assert "23/08/2026 às 18h34" in html

    def test_sem_argumento_carimba_o_instante_atual(self):
        # O caminho que a publicação de fato usa: nenhum chamador passa `agora`.
        template = open("template.html", encoding="utf-8").read()
        html = monta_pagina(_papel("BOVA11", 3), [], template)
        assert re.search(r"\d{2}/\d{2}/\d{4} às \d{2}h\d{2}", html)

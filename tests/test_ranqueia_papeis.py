"""
O ranqueamento dos papéis do dia — a leitura que o uso real de um mês pediu (12/10/2026).

A tela deixou de listar setups por horizonte e passou a listar **papéis**, ordenados pelo alcance
dos horizontes em que cada um dispara. Os testes aqui fixam as três regras que o usuário definiu e
a propriedade matemática que as torna consistentes.
"""
import itertools

import pandas as pd
import pytest

from gerar_alertas import COLUNAS_RANQUEADAS, ranqueia_papeis

# Os horizontes que têm setup aprovado no estudo. O 90 existe na grade e não sobrevive à barra.
HORIZONTES = [3, 5, 10, 20, 45]


def _alerta(ticker, horizonte, prot_lo=0.70, posicao=10, janela_de=10, janela_ate=10,
            n_setups=1, taxa_base=0.50, divisoes=5, de="2006-03-01", ate="2026-08-31"):
    # Uma linha no formato que `monta_alertas` devolve.
    return {"posicao_papel": posicao, "total_papeis": 61, "ticker": ticker,
            "horizonte": horizonte, "janela_de": janela_de, "janela_ate": janela_ate,
            "n_setups": n_setups, "episodios": 40, "protecao": prot_lo + 0.1,
            "prot_lo": prot_lo, "taxa_base": taxa_base, "divisoes_usadas": divisoes,
            "inicio_medido": de, "fim_medido": ate}


class TestUmaLinhaPorPapel:
    def test_colapsa_os_horizontes_de_um_papel_numa_linha_so(self):
        # Antes eram quatro linhas da PRIO3, uma por horizonte. A decisão é sobre o papel.
        a = pd.DataFrame([_alerta("PRIO3", h) for h in (3, 5, 10, 20)])
        r = ranqueia_papeis(a)
        assert len(r) == 1
        assert r.iloc[0]["ticker"] == "PRIO3"

    def test_tabela_vazia_mantem_as_colunas(self):
        # Dia sem gatilho é o caso comum; a página precisa saber desenhar o vazio.
        r = ranqueia_papeis(pd.DataFrame(columns=["ticker", "horizonte", "prot_lo"]))
        assert r.empty
        assert list(r.columns) == COLUNAS_RANQUEADAS


class TestOrdenacaoPeloAlcance:
    def test_o_caso_que_o_usuario_definiu_20_vence_3_mais_5_mais_10(self):
        # A regra, nas palavras dele: "o que apareceu no de 20 é mostrado primeiro pois 20 > 18".
        a = pd.DataFrame([_alerta("UMVINTE", 20, prot_lo=0.55),
                          _alerta("TRESCINCODEZ", 3, prot_lo=0.95),
                          _alerta("TRESCINCODEZ", 5, prot_lo=0.95),
                          _alerta("TRESCINCODEZ", 10, prot_lo=0.95)])
        r = ranqueia_papeis(a)
        # Vence mesmo com limite inferior MUITO menor: o alcance manda, e só depois a taxa.
        assert list(r["ticker"]) == ["UMVINTE", "TRESCINCODEZ"]
        assert list(r["peso"]) == [20, 18]

    def test_quem_aparece_em_todos_os_horizontes_lidera(self):
        a = pd.DataFrame([_alerta("TODOS", h) for h in HORIZONTES]
                         + [_alerta("SOQUARENTACINCO", 45)])
        r = ranqueia_papeis(a)
        assert list(r["ticker"]) == ["TODOS", "SOQUARENTACINCO"]

    def test_somar_os_dias_equivale_a_ordenar_pelo_maior_horizonte(self):
        # A propriedade que torna a regra consistente: cada horizonte é MAIOR que a soma de todos os
        # menores (45 > 38, 20 > 18, 10 > 8, 5 > 3). Por isso somar os dias nunca discorda de
        # comparar os conjuntos do maior prazo para o menor. Verificado em todos os 961 pares de
        # subconjuntos não vazios — se alguém acrescentar um horizonte que quebre a propriedade,
        # este teste falha antes de a ordenação ficar incoerente.
        conjuntos = [c for n in range(1, len(HORIZONTES) + 1)
                     for c in itertools.combinations(HORIZONTES, n)]
        for a, b in itertools.product(conjuntos, repeat=2):
            por_soma = sum(a) > sum(b)
            # A comparação lexicográfica: do maior prazo para o menor, quem tem o prazo que o outro
            # não tem vence.
            por_maior = sorted(a, reverse=True) > sorted(b, reverse=True)
            assert por_soma == por_maior, f"{a} contra {b}"


class TestOsNumerosVemDoMaiorHorizonte:
    def test_a_linha_exibe_o_limite_inferior_do_maior_prazo_e_nao_o_melhor(self):
        # O caso real da LREN3 em 04/09/2026: 72% em 3 pregões e 52% em 10. O prazo da decisão é o
        # maior, então é 52% que a linha mostra. Exibir o melhor número de qualquer prazo enganaria
        # quem lê a tabela como "quanto este papel protege no prazo em que eu opero".
        a = pd.DataFrame([_alerta("LREN3", 3, prot_lo=0.72, janela_de=40, janela_ate=87),
                          _alerta("LREN3", 10, prot_lo=0.52, janela_de=46, janela_ate=47)])
        r = ranqueia_papeis(a).iloc[0]
        assert r["horizonte_principal"] == 10
        assert r["prot_lo"] == pytest.approx(0.52)
        assert (r["janela_de"], r["janela_ate"]) == (46, 47)

    def test_dentro_do_maior_horizonte_vence_a_melhor_faixa(self):
        # Um papel pode disparar em duas faixas separadas no mesmo prazo; a que representa é a de
        # maior limite inferior, nunca uma média entre elas.
        a = pd.DataFrame([_alerta("AAAA3", 20, prot_lo=0.60, janela_de=5, janela_ate=9),
                          _alerta("AAAA3", 20, prot_lo=0.80, janela_de=30, janela_ate=40)])
        r = ranqueia_papeis(a).iloc[0]
        assert r["prot_lo"] == pytest.approx(0.80)
        assert r["janela_de"] == 30

    def test_os_demais_horizontes_saem_em_ordem_decrescente_sem_o_principal(self):
        a = pd.DataFrame([_alerta("AAAA3", h) for h in (3, 5, 10, 20)])
        r = ranqueia_papeis(a).iloc[0]
        assert r["horizonte_principal"] == 20
        assert r["horizontes"] == "10-5-3"

    def test_papel_de_um_horizonte_so_nao_tem_outros(self):
        # A célula fica vazia, e não com um traço ou um "—": a renderização decide como mostrar.
        r = ranqueia_papeis(pd.DataFrame([_alerta("AAAA3", 45)])).iloc[0]
        assert r["horizontes"] == ""


class TestDesempates:
    def test_empate_no_peso_desfaz_pelo_limite_inferior_do_maior_horizonte(self):
        # O caso real de NATU3 e LREN3 em 04/09: ambos com {3,5,10}, peso 18.
        a = pd.DataFrame([_alerta("NATU3", 3), _alerta("NATU3", 5),
                          _alerta("NATU3", 10, prot_lo=0.596),
                          _alerta("LREN3", 3), _alerta("LREN3", 5),
                          _alerta("LREN3", 10, prot_lo=0.520)])
        r = ranqueia_papeis(a)
        assert list(r["peso"]) == [18, 18]
        assert list(r["ticker"]) == ["NATU3", "LREN3"]

    def test_empate_tambem_no_limite_inferior_desfaz_pela_colocacao_do_papel(self):
        # Terceiro critério, para a ordem ser determinística em vez de herdada da ordem do arquivo.
        a = pd.DataFrame([_alerta("SEGUNDO", 20, prot_lo=0.70, posicao=45),
                          _alerta("PRIMEIRO", 20, prot_lo=0.70, posicao=12)])
        r = ranqueia_papeis(a)
        assert list(r["ticker"]) == ["PRIMEIRO", "SEGUNDO"]

    def test_a_ordem_nao_depende_da_ordem_de_entrada(self):
        linhas = [_alerta("AAAA3", 20, prot_lo=0.70, posicao=12),
                  _alerta("BBBB3", 20, prot_lo=0.70, posicao=45),
                  _alerta("CCCC3", 45, prot_lo=0.55, posicao=60)]
        primeira = list(ranqueia_papeis(pd.DataFrame(linhas))["ticker"])
        segunda = list(ranqueia_papeis(pd.DataFrame(linhas[::-1]))["ticker"])
        assert primeira == segunda == ["CCCC3", "AAAA3", "BBBB3"]

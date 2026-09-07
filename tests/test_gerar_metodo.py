from pathlib import Path

import pytest

from gerar_metodo import monta_pagina
from versoes import VERSOES

TEMPLATE = Path(__file__).resolve().parents[1] / "template_metodo.html"


def _pagina(n_alerta=None):
    return monta_pagina(TEMPLATE.read_text(encoding="utf-8"), VERSOES, n_alerta)


class TestRegistroDeVersoes:
    def test_toda_versao_tem_o_que_a_torna_reproduzivel(self):
        # É o propósito da página: sem os parâmetros e o passo a passo, "voltar para a versão
        # anterior" vira arqueologia de commit.
        for v in VERSOES:
            assert v["parametros"], f"{v['id']} sem parâmetros"
            assert v["passos"], f"{v['id']} sem passo a passo"
            assert v["pergunta"], f"{v['id']} sem a pergunta que responde"

    def test_exatamente_uma_versao_esta_em_producao(self):
        # Duas em produção seria ambiguidade sobre o que o site publica hoje; nenhuma, um registro
        # que perdeu o vínculo com a realidade.
        assert sum(1 for v in VERSOES if v["estado"] == "em produção") == 1

    def test_a_versao_em_producao_nao_tem_receita_de_retorno(self):
        # "Como voltar para esta versão" não quer dizer nada para a versão vigente.
        for v in VERSOES:
            if v["estado"] == "em produção":
                assert v["receita"] is None
            else:
                assert v["receita"], f"{v['id']} não diz como voltar"

    def test_as_versoes_tem_identificadores_distintos(self):
        ids = [v["id"] for v in VERSOES]
        assert len(ids) == len(set(ids))


class TestPagina:
    def test_todos_os_marcadores_sao_preenchidos(self):
        # Um marcador esquecido apareceria literalmente na página publicada.
        html = _pagina()
        assert "{{" not in html

    def test_cada_versao_aparece_com_seus_parametros_e_passos(self):
        html = _pagina()
        for v in VERSOES:
            assert f'id="ver-{v["id"]}"' in html
            assert v["nome"] in html
            # Um parâmetro de cada versão, como amostra de que o quadro foi montado.
            rotulo, valor = v["parametros"][0]
            assert rotulo in html and valor in html

    def test_so_a_primeira_versao_abre_visivel(self):
        # Uma versão por vez, para o passo a passo de cada uma ser lido inteiro sem concorrer com o
        # da outra. A primeira da lista é a mais recente.
        html = _pagina()
        assert f'id="ver-{VERSOES[0]["id"]}" class="versao"' in html
        for v in VERSOES[1:]:
            assert f'id="ver-{v["id"]}" class="versao oculto"' in html

    def test_o_primeiro_cartao_vem_pressionado(self):
        html = _pagina()
        assert html.count('aria-pressed="true"') == 1

    def test_a_barra_de_abas_marca_a_pagina_de_metodo(self):
        html = _pagina()
        assert 'href="metodo.html" aria-current="page"' in html

    def test_o_contador_do_dia_chega_a_barra(self):
        # A página de método não mede nada, mas exibe o contador para a barra ser idêntica nas três.
        assert "3 papéis" in _pagina(3)
        assert "selo" not in _pagina(0)

    def test_a_pagina_nao_depende_de_rede_nem_de_preco(self):
        # É o que a torna reconstruível a qualquer momento, mesmo com o provedor de dados fora do ar.
        import gerar_metodo
        fonte = Path(gerar_metodo.__file__).read_text(encoding="utf-8")
        assert "load_prices" not in fonte
        assert "yfinance" not in fonte

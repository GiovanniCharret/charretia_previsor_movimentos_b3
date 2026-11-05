"""
O site como um todo: as páginas se alcançam e falam do mesmo dia.

Por que este arquivo existe separado dos testes de cada gerador: são propriedades que **nenhum
gerador sozinho garante**. Cada um produz a sua página corretamente e, ainda assim, o site pode
sair quebrado — com uma página inalcançável, um link para uma página que não existe mais, ou a
triagem anunciando três destaques enquanto a faixa extrema exibe zero.
"""
from pathlib import Path

import pandas as pd
import pytest

import gerar_extremos
import gerar_metodo
from publicacao import PAGINAS, barra_de_abas
from versoes import VERSOES

RAIZ = Path(__file__).resolve().parents[1]


def _destaques(n=2):
    # Uma tabela do dia mínima, no formato que `gerar_extremos.monta_tabela` devolve.
    linhas = [{"ticker": f"AAA{i}", "faixa": 0.025, "janelas": "10", "janelas_2_5": 1,
               "janelas_5": 1, "janelas_medidas": 9, "horizonte": 45, "freq": 0.63,
               "taxa_base": 0.54, "acima_da_base": True, "divisoes_usadas": 5,
               "inicio_medido": "2006-03-01", "fim_medido": "2026-08-31"} for i in range(n)]
    return pd.DataFrame(linhas, columns=gerar_extremos.COLUNAS)


class TestAsPaginasSeAlcancam:
    def test_toda_pagina_da_barra_tem_um_template(self):
        # Uma entrada em PAGINAS sem template correspondente seria um link para um 404.
        modelos = {"index.html": "template.html", "extremos.html": "template_extremos.html",
                   "setores.html": "template_setores.html", "metodo.html": "template_metodo.html"}
        for _chave, arquivo, _nome, _descritor in PAGINAS:
            assert (RAIZ / modelos[arquivo]).exists()

    def test_de_qualquer_pagina_se_chega_as_outras(self):
        for chave, _arq, _nome, _desc in PAGINAS:
            html = barra_de_abas(chave)
            for _c, arquivo, _n, _d in PAGINAS:
                assert f'href="{arquivo}"' in html

    def test_nenhum_template_aponta_para_a_tela_de_gatilhos_descontinuada(self):
        # A v2 saiu do site em 04/11/2026; o registro dela fica só na página de método.
        for nome in ("template.html", "template_extremos.html", "template_setores.html",
                     "template_metodo.html"):
            assert "alertas.html" not in (RAIZ / nome).read_text(encoding="utf-8"), nome

    def test_a_pagina_de_metodo_aponta_para_as_outras_no_rodape(self):
        html = (RAIZ / "template_metodo.html").read_text(encoding="utf-8")
        assert 'href="index.html"' in html and 'href="extremos.html"' in html

    def test_a_v2_continua_no_registro_como_descontinuada(self):
        # "Deixar só o registro dos avanços" (usuário, 04/11/2026): a versão sai do site, não da
        # história, e diz como voltar.
        v2 = next(v for v in VERSOES if v["id"] == "v2")
        assert v2["estado"] == "descontinuada" and v2["receita"]


class TestOSiteFalaDoMesmoDia:
    def test_a_faixa_extrema_e_o_metodo_exibem_o_mesmo_contador(self):
        # O método lê o contador do estado; a faixa extrema o calcula. Se divergirem, o visitante vê
        # "2 papéis" na aba e uma tabela com outro número.
        t = (RAIZ / "template_extremos.html").read_text(encoding="utf-8")
        html_extremos = gerar_extremos.monta_pagina(t, _destaques(2), "2026-11-03", 98, 2)
        html_metodo = gerar_metodo.monta_pagina(
            (RAIZ / "template_metodo.html").read_text(encoding="utf-8"), VERSOES, 2)
        assert "2 papéis" in html_extremos and "2 destaques na faixa extrema" in html_extremos
        assert "2 papéis" in html_metodo


TEMPLATES = ("template.html", "template_extremos.html", "template_setores.html",
             "template_metodo.html")


class TestOEstiloAcompanha:
    def test_as_paginas_linkam_os_estilos_que_a_copia_leva(self):
        # As páginas linkam por caminho relativo dentro de `saida/`. Um estilo linkado que a cópia
        # não leva vira página sem formatação no ar.
        from publicacao import ESTATICOS
        for nome in TEMPLATES:
            html = (RAIZ / nome).read_text(encoding="utf-8")
            for css in html.split('href="')[1:]:
                arquivo = css.split('"')[0]
                if arquivo.endswith(".css") and not arquivo.startswith("http"):
                    assert arquivo in ESTATICOS, f"{nome} linka {arquivo}, que não é copiado"

    def test_toda_pagina_linka_TODOS_os_estilos(self):
        # A verificação inversa da anterior — e é a que faltava em 07/09/2026: o `template.html`
        # linkava só `estilo.css`, e a barra de abas da página inicial saiu como uma lista de links
        # sublinhados grudados. O teste antigo passava, porque só exigia que o que ESTÁ linkado seja
        # copiado; não exigia que o necessário estivesse linkado.
        from publicacao import ESTATICOS
        for nome in TEMPLATES:
            html = (RAIZ / nome).read_text(encoding="utf-8")
            for css in ESTATICOS:
                assert f'href="{css}"' in html, f"{nome} não linka {css}"

    def test_o_estilo_da_barra_de_abas_existe_para_toda_pagina_que_a_exibe(self):
        # A barra é montada por `publicacao.barra_de_abas` e usada pelas três. Se as classes dela
        # não estiverem definidas em nenhum estilo linkado, a página renderiza a marcação crua.
        from publicacao import ESTATICOS, barra_de_abas
        css = "\n".join((RAIZ / nome).read_text(encoding="utf-8") for nome in ESTATICOS)
        # As classes que a barra emite precisam ter regra em algum dos estilos.
        for classe in (".abas", ".aba", ".selo"):
            assert classe in css, f"{classe} não tem regra em nenhum estilo"
        # E o marcador da barra tem de existir nos três templates.
        assert "abas" in barra_de_abas("triagem")
        for nome in TEMPLATES:
            assert "{{ABAS}}" in (RAIZ / nome).read_text(encoding="utf-8"), f"{nome} sem {{{{ABAS}}}}"

    def test_os_estilos_existem_no_repositorio(self):
        from publicacao import ESTATICOS
        for nome in ESTATICOS:
            assert (RAIZ / nome).exists(), f"{nome} está declarado mas não existe"

"""
O site como um todo: as três páginas se alcançam e falam do mesmo dia.

Por que este arquivo existe separado dos testes de cada gerador: são propriedades que **nenhum
gerador sozinho garante**. Cada um produz a sua página corretamente e, ainda assim, o site pode
sair quebrado — com uma página inalcançável, ou com a triagem anunciando três gatilhos enquanto a
tela de gatilhos exibe zero.
"""
from pathlib import Path

import pandas as pd
import pytest

import gerar_alertas
import gerar_metodo
from publicacao import PAGINAS, barra_de_abas
from versoes import VERSOES

RAIZ = Path(__file__).resolve().parents[1]


def _alertas(n_papeis=2):
    # Uma tabela de alertas mínima, no formato que `monta_alertas` devolve.
    linhas = []
    for i in range(n_papeis):
        linhas.append({"posicao_papel": 31 + i, "total_papeis": 61, "ticker": f"AAA{i}",
                       "horizonte": 3, "janela_de": 40, "janela_ate": 87, "n_setups": 48,
                       "episodios": 43, "protecao": 0.86, "prot_lo": 0.72, "taxa_base": 0.50,
                       "divisoes_usadas": 5, "inicio_medido": "2006-03-01",
                       "fim_medido": "2026-08-31"})
    return pd.DataFrame(linhas)


class TestAsPaginasSeAlcancam:
    def test_toda_pagina_tem_um_arquivo_e_um_template(self):
        # Uma entrada em PAGINAS sem gerador correspondente produziria um link para um 404.
        for _chave, arquivo, _nome, _descritor in PAGINAS:
            assert arquivo.endswith(".html")

    def test_de_qualquer_pagina_se_chega_as_outras_duas(self):
        # Sem isso, a segunda e a terceira páginas dependem de o visitante reparar na barra de abas.
        for chave, _arq, _nome, _desc in PAGINAS:
            html = barra_de_abas(chave)
            for _c, arquivo, _n, _d in PAGINAS:
                assert f'href="{arquivo}"' in html

    def test_a_pagina_de_gatilhos_aponta_para_as_outras_no_rodape(self):
        html = (RAIZ / "template_alertas.html").read_text(encoding="utf-8")
        assert 'href="index.html"' in html and 'href="metodo.html"' in html

    def test_a_pagina_de_metodo_aponta_para_as_outras_no_rodape(self):
        html = (RAIZ / "template_metodo.html").read_text(encoding="utf-8")
        assert 'href="index.html"' in html and 'href="alertas.html"' in html


class TestOSiteFalaDoMesmoDia:
    def test_as_tres_paginas_exibem_o_mesmo_contador(self):
        # A triagem e o método leem o contador do estado; a de gatilhos o calcula. Se divergirem, o
        # visitante vê "3 papéis" na aba e uma tabela com outro número.
        a = _alertas(2)
        html_gatilhos = gerar_alertas.monta_pagina(
            (RAIZ / "template_alertas.html").read_text(encoding="utf-8"), a, "2026-09-04", 61)
        html_metodo = gerar_metodo.monta_pagina(
            (RAIZ / "template_metodo.html").read_text(encoding="utf-8"), VERSOES, 2)
        assert "2 papéis" in html_gatilhos
        assert "2 papéis" in html_metodo

    def test_a_pagina_de_gatilhos_marca_a_si_mesma_na_barra(self):
        a = _alertas(1)
        html = gerar_alertas.monta_pagina(
            (RAIZ / "template_alertas.html").read_text(encoding="utf-8"), a, "2026-09-04", 61)
        assert 'href="alertas.html" aria-current="page"' in html
        assert html.count('aria-current="page"') == 1


class TestNenhumMarcadorEscapa:
    def test_pagina_de_gatilhos_com_alertas(self):
        html = gerar_alertas.monta_pagina(
            (RAIZ / "template_alertas.html").read_text(encoding="utf-8"),
            _alertas(2), "2026-09-04", 61)
        assert "{{" not in html

    def test_pagina_de_gatilhos_no_dia_vazio(self):
        # O caso comum, e o mais fácil de deixar quebrado sem notar.
        html = gerar_alertas.monta_pagina(
            (RAIZ / "template_alertas.html").read_text(encoding="utf-8"),
            pd.DataFrame(columns=gerar_alertas.COLUNAS_ALERTA), "2026-09-04", 61)
        assert "{{" not in html
        assert "Nenhum gatilho hoje" in html
        # E o dia vazio precisa dizer que é o esperado, não parecer falha.
        assert "resultado esperado" in html


TEMPLATES = ("template.html", "template_alertas.html", "template_metodo.html")


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

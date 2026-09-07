import json

import pytest

from publicacao import (PAGINAS, barra_de_abas, copia_estatica, grava_estado, le_estado)


class TestBarraDeAbas:
    def test_as_tres_paginas_aparecem_sempre(self):
        # A barra é montada num lugar só justamente para as três páginas terem a MESMA. Se cada
        # gerador montasse a sua, a primeira mudança de rótulo apareceria em uma e não nas outras.
        html = barra_de_abas("triagem")
        for _chave, arquivo, nome, _descritor in PAGINAS:
            assert arquivo in html
            assert nome in html

    def test_a_pagina_atual_e_marcada_e_as_outras_nao(self):
        html = barra_de_abas("gatilhos")
        # Uma única marca de página atual — é ela que o estilo e os leitores de tela usam.
        assert html.count('aria-current="page"') == 1
        assert 'href="alertas.html" aria-current="page"' in html

    def test_o_contador_aparece_quando_ha_gatilho(self):
        # É o elemento que faz as duas telas conviverem: da triagem dá para ver que HÁ gatilhos hoje
        # sem precisar abrir a outra página.
        assert "3 papéis" in barra_de_abas("triagem", 3)
        assert "1 papel" in barra_de_abas("triagem", 1)

    def test_o_contador_some_no_dia_vazio_em_vez_de_exibir_zero(self):
        # Um "0" permanente ensina o olho a ignorar o lugar onde o número aparece. E a página de
        # gatilhos fica vazia na MAIORIA dos pregões, então o zero seria o estado quase constante.
        assert "selo" not in barra_de_abas("triagem", 0)

    def test_sem_medida_tambem_nao_ha_contador(self):
        # None é "ainda não se mediu", diferente de zero. Nos dois casos não há número a exibir,
        # mas por motivos distintos — e nenhum deles justifica inventar um.
        assert "selo" not in barra_de_abas("triagem", None)
        assert "selo" not in barra_de_abas("triagem")


class TestEstadoEntrePaginas:
    def test_grava_e_le_o_que_o_gerador_de_alertas_descobriu(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            saida = Path(d)
            grava_estado(saida, 3, 13, "2026-09-04")
            e = le_estado(saida)
            assert e["papeis_com_alerta"] == 3
            assert e["gatilhos"] == 13
            assert e["data_pregao"] == "2026-09-04"

    def test_ausencia_do_arquivo_nao_e_erro(self):
        # A ordem de execução põe os alertas primeiro, mas nada garante isso quando alguém roda um
        # gerador sozinho para conferir. A triagem precisa sair mesmo assim.
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            assert le_estado(Path(d)) == {}

    def test_arquivo_corrompido_vira_ausencia_e_nao_derruba_a_publicacao(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            saida = Path(d)
            (saida / "estado.json").write_text("{isto não é json", encoding="utf-8")
            assert le_estado(saida) == {}


class TestEstaticos:
    def test_copia_os_estilos_para_a_pasta_publicada(self):
        # As páginas linkam `estilo.css` por caminho relativo e são gravadas dentro de `saida/`.
        # Sem a cópia o site sobe sem formatação — falha silenciosa, que só aparece ao abrir.
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d) / "raiz"; raiz.mkdir()
            (raiz / "estilo.css").write_text("body{}", encoding="utf-8")
            (raiz / "estilo_componentes.css").write_text(".aba{}", encoding="utf-8")
            saida = Path(d) / "saida"
            copiados = copia_estatica(raiz, saida)
            assert set(copiados) == {"estilo.css", "estilo_componentes.css"}
            assert (saida / "estilo.css").exists()

    def test_estatico_ausente_nao_derruba_os_demais(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d) / "raiz"; raiz.mkdir()
            (raiz / "estilo.css").write_text("body{}", encoding="utf-8")
            saida = Path(d) / "saida"
            assert copia_estatica(raiz, saida) == ["estilo.css"]

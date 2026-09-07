"""
Gera a página de método: como cada versão da tela funciona, passo a passo.

Por que esta página existe: as duas telas do site respondem perguntas diferentes, com parâmetros
diferentes, e ambas nasceram de uma sequência de achados. Sem um registro publicado, três coisas se
perdem: **o que** cada versão mede, **por que** ela mede assim, e **como voltar** para uma versão
anterior se a atual se mostrar errada. As duas primeiras vivem nos documentos de planejamento do
laboratório, que não são publicados; a terceira não vivia em lugar nenhum.

Diferença deste gerador para os outros dois: ele **não toca a rede e não lê preço nenhum**. O
conteúdo vem inteiro de `versoes.py`, que é o registro histórico. Por isso a página é reconstruível
a qualquer momento, mesmo sem o provedor de dados no ar.

O seletor de versão é o único trecho com comportamento na página: uma versão visível por vez, para
o passo a passo de cada uma ser lido inteiro sem concorrer com o da outra.
"""

from pathlib import Path                                    # caminhos

from nucleo import config                                   # onde a página é gravada
from publicacao import barra_de_abas, copia_estatica, le_estado   # o que as 3 páginas dividem
from versoes import VERSOES                                 # o registro histórico


def _cartao(v, primeiro):
    """
    O cartão de uma versão no seletor (helper de renderização).

    Por que existe: o cartão é o que responde "esta versão foi superada, ou é outra coisa?". Por
    isso ele traz, no lugar mais visível depois do nome, **a pergunta que aquela versão responde** —
    duas versões podem coexistir se respondem perguntas diferentes, e é o que acontece aqui.

    Entrada: v (dicionário de uma versão), primeiro (bool; a versão aberta por padrão).
    Saída: string com o HTML do cartão.
    """
    # O primeiro cartão vem pressionado, e é a versão que a página abre.
    pressionado = "true" if primeiro else "false"
    return (f'<button type="button" class="cartao" data-versao="{v["id"]}" '
            f'aria-pressed="{pressionado}">'
            f'<div class="cartao-topo">'
            f'<span class="v">{v["id"]}</span><span class="t">{v["nome"]}</span>'
            f'<span class="estado {v["classe_estado"]}">{v["estado"]}</span></div>'
            f'<p class="q">{v["pergunta"]}</p>'
            f'</button>')


def _parametros(v):
    """
    O quadro de parâmetros de uma versão (helper de renderização).

    Por que existe: é o bloco que torna a versão **reproduzível**. Sem os valores exatos, "voltar
    para a versão anterior" vira arqueologia de commit — alguém teria de descobrir, lendo
    diferenças entre versões do código, que a v1 usava janela 90 e peneira de qualidade global.

    Entrada: v (dicionário de uma versão).
    Saída: string com o HTML do quadro.
    """
    # Um par por linha, em duas colunas quando a tela comporta.
    pares = "".join(f'<div class="par"><dt>{rotulo}</dt><dd>{valor}</dd></div>'
                    for rotulo, valor in v["parametros"])
    return (f'<div class="params"><h3>parâmetros que definem esta versão</h3>'
            f'<dl>{pares}</dl></div>')


def _passos(v):
    """
    A lista numerada do passo a passo (helper de renderização).

    Por que existe: a numeração aqui **carrega informação** — é a ordem em que as etapas agem, e
    cada uma depende da anterior. Não é decoração: trocar a ordem mudaria o resultado.

    Entrada: v (dicionário de uma versão).
    Saída: string com o HTML da lista.
    """
    itens = "".join(f'<li><div><h3>{titulo}</h3><p>{texto}</p></div></li>'
                    for titulo, texto in v["passos"])
    return (f'<div class="secao"><h2>O passo a passo</h2></div>'
            f'<div class="leitura" style="margin-top:16px"><ol class="passos">{itens}</ol></div>')


def _mudou(v):
    """
    O bloco do que mudou, e a receita de retorno quando existe (helper de renderização).

    Por que existe: separa o que a versão *sabe* do que ela *faz*. O passo a passo descreve a
    mecânica; este bloco registra o achado que justificou a mecânica ser essa. É a parte que
    preserva a pesquisa, e não só o produto.

    A receita só aparece nas versões que **não** estão em produção: para a vigente, "como voltar"
    não quer dizer nada.

    Entrada: v (dicionário de uma versão).
    Saída: string com o HTML do bloco, mais a receita quando houver.
    """
    itens = "".join(f"<li>{x}</li>" for x in v["mudou"])
    html = (f'<div class="mudou leitura"><h3>{v["titulo_mudou"]}</h3>'
            f'<ul>{itens}</ul></div>')
    # A receita de retorno, quando a versão não é a vigente.
    if v["receita"]:
        html += (f'<div class="receita leitura"><h3>como voltar para esta versão</h3>'
                 f'<pre>{v["receita"]}</pre></div>')
    return html


def monta_pagina(template, versoes, n_papeis_alerta=None):
    """
    Preenche o template com o seletor de versões e o detalhamento de cada uma.

    Por que existe: separa a renderização do registro, para o teste conferir a página sem tocar em
    disco e para o texto das versões ser revisto em `versoes.py` sem mexer em HTML.

    Entrada: template (string com os marcadores), versoes (lista de dicionários de `versoes.py`),
    n_papeis_alerta (para o contador da barra de abas; None quando ainda não se mediu).
    Fase 1: o seletor, com a primeira versão aberta.
    Fase 2: um bloco por versão — parâmetros, passo a passo e o que mudou.
    Fase 3: a barra de abas e os marcadores.
    Saída: string com o HTML completo.
    """
    # Fase 1: os cartões, na ordem do registro (mais recente primeiro).
    cartoes = "".join(_cartao(v, i == 0) for i, v in enumerate(versoes))
    # Fase 2: um bloco por versão; só o primeiro visível.
    blocos = []
    for i, v in enumerate(versoes):
        oculto = "" if i == 0 else " oculto"
        blocos.append(
            f'<div id="ver-{v["id"]}" class="versao{oculto}">'
            f'<div class="secao"><h2>{v["id"]} · {v["nome"]}</h2>'
            f'<span class="nota">{v["data"]} · {v["origem"]}</span></div>'
            f'{_parametros(v)}{_passos(v)}{_mudou(v)}'
            f'</div>')
    # Fase 3: os marcadores.
    for marca, valor in (("ABAS", barra_de_abas("metodo", n_papeis_alerta)),
                         ("VERSOES", f'<div class="versoes">{cartoes}</div>'),
                         ("BLOCOS", "".join(blocos))):
        template = template.replace("{{" + marca + "}}", valor)
    return template


def main() -> None:
    """
    Invólucro de entrada e saída: monta a página e grava.

    Não toca a rede: o conteúdo inteiro vem de `versoes.py`.

    Fase 1: ler o estado do dia, só para o contador da barra de abas.
    Fase 2: montar a página.
    Fase 3: gravar, junto com os arquivos de estilo.
    """
    raiz = Path(__file__).resolve().parent
    saida = raiz / config.DIR_SAIDA
    # Fase 1: o contador vem do gerador de alertas; ausência não é erro.
    estado = le_estado(saida)
    n_alerta = estado.get("papeis_com_alerta")
    print(f"PÁGINA DE MÉTODO — {len(VERSOES)} versões registradas")
    for v in VERSOES:
        print(f"  {v['id']:<4} {v['nome']:<26} {v['estado']:<14} "
              f"{len(v['passos'])} passos, {len(v['parametros'])} parâmetros")

    # Fase 2 e 3: montar e gravar.
    html = monta_pagina((raiz / "template_metodo.html").read_text(encoding="utf-8"),
                        VERSOES, n_alerta)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "metodo.html").write_text(html, encoding="utf-8", newline="\n")
    copia_estatica(raiz, saida)
    print(f"Página gravada em {saida / 'metodo.html'}")


if __name__ == "__main__":
    main()

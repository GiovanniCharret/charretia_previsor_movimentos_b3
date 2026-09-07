"""
O que as três páginas do site compartilham: a barra de navegação e os arquivos estáticos.

Por que este módulo existe: o site passou a ter três páginas (`index.html`, `alertas.html`,
`metodo.html`), geradas por três scripts independentes. Duas coisas precisam ser **idênticas** nas
três, e nenhuma delas pertence a um gerador específico:

1. **A barra de abas.** Se cada gerador montasse a sua, a primeira mudança de rótulo apareceria em
   uma página e não nas outras — o visitante veria dois sites diferentes conforme a página em que
   entrasse. É exatamente o modo de deriva que a extração do estilo para `estilo.css` acabou de
   resolver no CSS, aplicado agora ao HTML.
2. **A cópia dos arquivos estáticos** para a pasta publicada. As páginas linkam `estilo.css` por
   caminho relativo, e o `index.html` é gravado dentro de `saida/` — sem a cópia, a página sobe sem
   formatação nenhuma.

O contador de gatilhos na aba cria uma dependência entre páginas: a triagem precisa saber quantos
papéis dispararam hoje, e só o gerador de alertas sabe disso. A ligação é um arquivo de estado
minúsculo, escrito por `gerar_alertas.py` e lido pelos outros dois. **Ausência dele não é erro** —
a barra simplesmente sai sem contador, que é o comportamento correto quando ainda não se mediu.
"""

import json                                                 # o arquivo de estado entre páginas
import shutil                                               # cópia dos estáticos
from pathlib import Path                                    # caminhos

# As três páginas do site, na ordem em que aparecem na barra. Cada entrada traz o arquivo, o nome
# curto da aba e o que ela responde — o descritor existe porque "Triagem" e "Gatilhos" sozinhos não
# distinguem uma página da outra para quem chega de fora.
PAGINAS = [
    ("triagem", "index.html", "Triagem", "onde cada papel está na escala, hoje"),
    ("gatilhos", "alertas.html", "Gatilhos", "quem entrou numa faixa que o estudo aprovou"),
    ("metodo", "metodo.html", "Método", "como cada versão funciona, passo a passo"),
]

# Arquivos que acompanham as páginas para a pasta publicada. As TRÊS páginas linkam os dois:
# `estilo.css` traz o sistema visual e `estilo_componentes.css` traz a barra de abas.
ESTATICOS = ["estilo.css", "estilo_componentes.css"]

# Onde o gerador de alertas deixa o que os outros dois precisam saber.
ARQUIVO_ESTADO = "estado.json"


def barra_de_abas(atual, n_papeis_alerta=None):
    """
    O HTML da navegação entre as três páginas, com o contador de gatilhos do dia.

    Por que existe: ver o cabeçalho do módulo — três geradores montando a própria barra divergiriam
    na primeira mudança. Aqui ela é montada uma vez e as três páginas recebem a mesma.

    O contador é o que faz as duas telas conviverem: a página de gatilhos fica vazia na maioria dos
    pregões, e sem o contador o visitante precisaria abri-la para descobrir isso. Com ele, a triagem
    — que sempre tem o que mostrar — avisa que hoje há gatilhos. E ele **some** quando não há nenhum,
    em vez de exibir um zero: um "0" permanente ensina o olho a ignorar o lugar onde o número
    aparece.

    Entrada: atual (a chave da página sendo gerada), n_papeis_alerta (quantos papéis dispararam
    hoje; None quando ainda não se mediu, 0 quando se mediu e não houve nenhum).
    Fase 1: cada página vira um link, e a atual é marcada para o leitor saber onde está.
    Fase 2: a aba de gatilhos recebe o contador, quando há o que contar.
    Saída: string com o `<nav>` completo.
    """
    partes = []
    # Fase 1: um link por página.
    for chave, arquivo, nome, descritor in PAGINAS:
        # A página atual não é link para si mesma: `aria-current` é o que anuncia isso a leitores
        # de tela, e o estilo se pendura nele em vez de numa classe separada.
        marca = ' aria-current="page"' if chave == atual else ""
        # Fase 2: o contador, só na aba de gatilhos e só quando há gatilho.
        selo = ""
        if chave == "gatilhos" and n_papeis_alerta:
            plural = "papéis" if n_papeis_alerta > 1 else "papel"
            selo = f' <span class="selo">{n_papeis_alerta} {plural}</span>'
        partes.append(
            f'<a class="aba" href="{arquivo}"{marca}>'
            f'<span class="n">{nome}{selo}</span>'
            f'<span class="d">{descritor}</span></a>')
    # Saída: a barra inteira.
    return ('<nav class="abas" aria-label="telas do site">' + "".join(partes) + "</nav>")


def copia_estatica(raiz, saida):
    """
    Leva os arquivos de estilo para a pasta publicada.

    Por que existe: as páginas linkam `estilo.css` por caminho relativo e são gravadas dentro de
    `saida/`. Sem a cópia, o navegador procura o arquivo ao lado da página, não o encontra, e a
    página sobe sem formatação — falha silenciosa, que só aparece quando alguém abre o site.

    Entrada: raiz (pasta do repositório), saida (pasta publicada).
    Fase 1: garantir a pasta de destino.
    Fase 2: copiar cada estático que existir, ignorando os ausentes sem quebrar.
    Saída: lista dos nomes efetivamente copiados.
    """
    # Fase 1: a pasta pode não existir ainda.
    saida.mkdir(parents=True, exist_ok=True)
    copiados = []
    # Fase 2: um arquivo por vez; um ausente não derruba os demais.
    for nome in ESTATICOS:
        origem = raiz / nome
        if origem.exists():
            shutil.copyfile(origem, saida / nome)
            copiados.append(nome)
    return copiados


def grava_estado(saida, n_papeis_alerta, n_gatilhos, data_pregao):
    """
    Registra o que o gerador de alertas descobriu, para as outras páginas lerem.

    Por que existe: é a única informação que atravessa geradores. Um arquivo de estado explícito é
    preferível a fazer a triagem recalcular os alertas — isso duplicaria 61 downloads e abriria a
    possibilidade de as duas páginas discordarem sobre o mesmo dia.

    Entrada: saida (pasta publicada), n_papeis_alerta, n_gatilhos, data_pregao.
    Fase 1: garantir a pasta e gravar as três informações.
    Saída: o caminho gravado.
    """
    # Fase 1: um objeto pequeno, legível a olho nu se alguém precisar conferir.
    saida.mkdir(parents=True, exist_ok=True)
    caminho = saida / ARQUIVO_ESTADO
    caminho.write_text(json.dumps({"papeis_com_alerta": int(n_papeis_alerta),
                                   "gatilhos": int(n_gatilhos),
                                   "data_pregao": str(data_pregao)},
                                  ensure_ascii=False, indent=2),
                       encoding="utf-8", newline="\n")
    return caminho


def le_estado(saida):
    """
    Lê o que o gerador de alertas deixou, tolerando ausência.

    Por que existe: a ordem de execução no fluxo de publicação põe os alertas primeiro, mas nada
    garante essa ordem quando alguém roda um gerador sozinho para conferir. **Ausência não é erro**:
    a barra sai sem contador, que é o correto quando ainda não se mediu — inventar um zero afirmaria
    que não houve gatilho, o que é diferente de não saber.

    Entrada: saida (pasta publicada).
    Fase 1: sem arquivo, sem informação.
    Fase 2: arquivo ilegível também vira ausência, em vez de derrubar a geração da página.
    Saída: dict com o estado, ou {} quando não há.
    """
    caminho = Path(saida) / ARQUIVO_ESTADO
    # Fase 1: ainda não foi medido.
    if not caminho.exists():
        return {}
    # Fase 2: um arquivo corrompido não pode impedir a publicação da triagem.
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return {}

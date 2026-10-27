"""
O histórico das versões da tela: o que cada uma responde, com que parâmetros e por que mudou.

Por que este arquivo existe separado do gerador: **é o registro da pesquisa**, não código de
apresentação. Ele preserva a história e é o que torna um retorno a uma versão anterior possível sem
arqueologia de commit — a receita de cada versão está aqui, em texto, ao lado dos números que a
definem.

Por que dados em Python e não um arquivo de configuração: o conteúdo é texto longo em português com
marcação, e a única coisa que o lê é o gerador ao lado. Um formato intermediário acrescentaria uma
etapa de leitura sem ganhar nada — e perderia a possibilidade de comentar cada entrada, que é
metade do valor de um registro histórico.

**Regra de quando nasce uma versão nova:** quando um achado muda a *pergunta*, não quando um número
muda de valor. Recalibrações e mudanças de apresentação entram como **nota** na versão vigente — é
o campo `notas`, uma lista de pares (data, texto). Sem esse critério, cada nova varredura viraria
uma versão e a página perde a serventia em poucos meses.

Confirmado pelo usuário em 12/10/2026, ao reorganizar a tabela de gatilhos depois de um mês de uso
real: aquilo mudou como a resposta é **lida**, não o que é **perguntado** — logo, nota na v2. A
próxima versão nasce quando o **modelo** mudar.

Foi o que aconteceu no mesmo dia: o controle com preços sem memória mostrou que a medida da v2 era
em grande parte efeito da contagem, e a medida passou a ser outra (dias, e não episódios; percentis
de 2,5% e 5%). Isso é a **v3**. A v2 fica como "mantida", com a nota do que foi descoberto e a
página dela no ar — o registro existe para contar o caminho, inclusive o que não se sustentou.

Ordem da lista: da mais recente para a mais antiga. A primeira é a que a página abre.
"""

VERSOES = [
    {
        "id": "v3",
        "nome": "Faixa extrema",
        "estado": "em produção",
        "classe_estado": "e-ativa",
        "data": "12/10/2026",
        "origem": "achado W",
        "pergunta": "Que papéis fecharam hoje entre os <b>2,5% ou 5% de dias mais afastados para "
                    "baixo</b> da própria média — a única faixa em que restou indício depois do "
                    "controle com preços sem memória?",
        "parametros": [
            ("papéis", "61"),
            ("janelas", "5, 10, 20, 30, 45, 60, 90, 130, 200"),
            ("cortes", "percentis de 2,5% e 5%"),
            ("horizontes", "20 e 45 pregões"),
            ("medida", "frequência por dia"),
            ("desvio da distância", "252 pregões"),
            ("divisões da validação", "5 · 2006 → 2027"),
            ("tamanho de amostra do intervalo", "episódios"),
            ("teste conjunto", "59 papéis, peso igual"),
            ("placebo", "uma moeda por data · 200 séries"),
            ("excesso em 2,5% (20 · 45)", "+4,2 · +7,3 pontos"),
            ("valor-p em 2,5% (20 · 45)", "0,15 · 0,035"),
        ],
        "passos": [
            ("O controle com preços sem memória",
             "Os retornos diários reais de cada papel são reordenados para destruir qualquer "
             "memória, mantendo a distribuição e a tendência. Nessas séries nada pode ser previsto; "
             "o que uma medida mostrar ali é <b>efeito da própria forma de contar</b>."),
            ("A proteção por episódio não passa no controle",
             "Em preços sem memória ela já devolve de 75% a 80%. O tamanho do episódio depende do "
             "que vem depois: a queda que reverte vira um episódio curto e positivo, a que continua "
             "estica o mesmo episódio. Dar peso igual a cada episódio multiplica as reversões."),
            ("Contar dias em vez de episódios",
             "Cada dia acionado é uma observação, e nada do que acontece depois decide o peso "
             "dela. Nessa medida as séries sem memória ficam <b>na taxa-base</b>, como devem."),
            ("Cortes do próprio papel, só do treino",
             "A distância é dividida pelo desvio-padrão do próprio papel e comparada com os "
             "percentis de 2,5% e 5% dele, calculados no treino de cada divisão."),
            ("Nove janelas fixadas antes",
             "De 5 a 200 pregões. Não se elege janela vencedora: o número de um papel é a média "
             "entre as nove, e a tela conta em quantas delas ele está abaixo do corte hoje."),
            ("Juntar os papéis com peso igual",
             "Cada papel é medido contra a própria taxa-base e entra com o mesmo peso. BOVA11 e "
             "SMAL11 ficam fora da média, porque são cestas dos outros."),
            ("Placebo conjunto, uma moeda por data",
             "Os papéis caem juntos, então a direção de cada dia é sorteada <b>uma vez para "
             "todos</b>. Isso mantém o movimento conjunto do mercado e os períodos de agitação, e "
             "desfaz só a memória de direção."),
            ("O controle de 30% e a escada",
             "O percentil de 30% entra como controle e fica em zero. O excesso cresce conforme o "
             "corte aprofunda: +2,2 pontos em 10%, +3,1 em 5%, +4,2 em 2,5% (20 pregões)."),
        ],
        "titulo_mudou": "O que esta versão sabe e a anterior não sabia",
        "mudou": [
            "<b>A proteção por episódio da v2 mede principalmente a contagem.</b> Papel a papel, "
            "ela não se distingue do placebo: de 61 papéis, passam de 1 a 5 por horizonte, e 3 "
            "passariam só por acaso.",
            "<b>O teste de rotação da v2 não pegava isso</b>, porque rotacionar os retornos desfaz "
            "justamente o vínculo mecânico entre o episódio e o desfecho.",
            "<b>O que sobra é pequeno e mora nos extremos.</b> Contando dias, o excesso sobre a "
            "taxa-base vai de zero (percentil de 30%) a 4 a 7 pontos (percentil de 2,5%), e cresce "
            "com o horizonte.",
            "<b>É indício, não achado.</b> Contra o placebo conjunto, só um de seis testes passa de "
            "5%. As quedas extremas caem nas mesmas datas para quase todos os papéis, então 59 "
            "papéis valem muito menos que 59 amostras.",
            "<b>Papel a papel o efeito não é detectável</b>: um papel tem menos de dez episódios "
            "extremos em vinte anos, e o limite inferior dele fica abaixo da taxa-base.",
            "<b>Os mesmos decis não indicam saída.</b> No decil mais alto, nenhuma medida se separa "
            "do placebo; nos prazos curtos o papel tende a continuar, não a devolver.",
        ],
        "notas": [
            ("13/10/2026", "A lista de papéis passou a ter <b>100</b> (planilha do laboratório). A "
                           "tabela ganhou o desenho da v2: uma coluna de frequência e uma de "
                           "taxa-base, no horizonte de 45 pregões (20 na falta dele). O limite "
                           "inferior saiu da tela — com cerca de dez episódios por papel ele ficava "
                           "em 20% a 30% e foi lido como placebo. <b>Só aparece o papel cuja "
                           "frequência supera a própria taxa-base</b>. Ganhou também a planilha de "
                           "estudo de cada papel, com o treino e o teste de cada divisão."),
            ("19/10/2026", "A coluna das médias passou a mostrar <b>em quais janelas</b> o papel "
                           "está no extremo, como na v2 (\"10–30 (3)\"), e só no corte da seção em "
                           "que ele aparece. A frequência e a taxa-base da linha passaram a ser "
                           "<b>as dessas janelas</b>, e não a média das nove — mais coerente com o "
                           "que a linha mostra, ao custo de cada número vir de menos episódios."),
        ],
        "receita": None,
    },
    {
        "id": "v2",
        "nome": "Gatilhos de proteção",
        "estado": "mantida",
        "classe_estado": "e-mantida",
        "data": "07/09/2026",
        "origem": "achados N a U",
        "pergunta": "Em que papel, hoje, um gatilho técnico indica <b>não perder</b> nos próximos "
                    "pregões — com o setup que o estudo aprovou para aquele papel?",
        # Os parâmetros que tornam a versão reproduzível. Pares (rótulo, valor), na ordem de leitura.
        "parametros": [
            ("papéis", "61"),
            ("grade de busca", "198 janelas × 7 horizontes"),
            ("horizontes", "3, 5, 10, 20, 45, 90"),
            ("faixa que dispara", "decil 0 de 10"),
            ("desvio da distância", "252 pregões"),
            ("divisões da validação", "5 · 2006 → 2027"),
            ("embargo", "= horizonte"),
            ("piso de episódios", "30"),
            ("barra de aprovação", "máx(50%, taxa-base)"),
            ("intervalo", "Clopper-Pearson 95%"),
            ("setups aprovados", "14.470"),
            ("valor-p da permutação", "0,0220"),
        ],
        "passos": [
            ("Grade sem poda",
             "198 janelas × 7 horizontes = <b>1.386 combinações por papel</b>. Nada é removido por "
             "ter ido mal, para o denominador continuar significando alguma coisa."),
            ("Peneira de qualidade, divisão por divisão",
             "Cada época de quatro anos é avaliada isolada: liquidez, preço parado, cabeça anterior "
             "à listagem. Uma época reprovada é <b>descartada sozinha</b> — o papel inteiro não cai "
             "por causa dela."),
            ("Validação encadeada",
             "Cinco divisões sucessivas. Os cortes de decil de cada uma saem <b>só do treino "
             "dela</b>, e o embargo entre treino e teste é igual ao horizonte, porque o retorno "
             "futuro do fim do treino invadiria o começo do teste."),
            ("Episódios, não dias",
             "Dias contíguos no decil extremo contam como <b>uma observação só</b>: os retornos "
             "futuros deles se sobrepõem, então tratá-los como independentes inflaria a amostra."),
            ("Proteção como alvo",
             "A medida é a fração de episódios cujo retorno seguinte saiu positivo. Não é retorno "
             "esperado, não é excesso: é <b>frequência de não perder</b>."),
            ("A barra é a taxa-base do próprio papel",
             "Nunca 50%. Um papel que subiu em 60% dos dias precisa proteger em mais de 60% para "
             "estar fazendo alguma coisa — com a barra em 50%, “protege” seria só a deriva."),
            ("Limite inferior, não a proporção crua",
             "A ordenação usa o limite inferior exato de 95% da proporção. Pela crua, <b>dois "
             "acertos em dois episódios valeriam 100%</b> e venceriam noventa episódios com 75%."),
            ("Teste de permutação em dois níveis",
             "O nulo é <b>rotação circular</b> da série de retornos, nunca embaralhamento: a "
             "rotação preserva a distribuição, a dependência local e os aglomerados de "
             "volatilidade, destruindo só o alinhamento com o dia do evento. O segundo nível refaz "
             "a busca inteira dentro de cada rotação — e só ele autoriza conclusão."),
        ],
        "titulo_mudou": "O que esta versão sabe e a anterior não sabia",
        "mudou": [
            "A média móvel prevê a <b>direção, não a magnitude</b>: a proteção atravessa vinte anos "
            "e cinco épocas, enquanto o excesso desaparece.",
            "<b>Não existe setup por papel identificável pelo gradiente</b> (achado N). Escolher "
            "empata com não escolher, e o ótimo foge com a borda da grade.",
            "<b>Não há horizonte privilegiado.</b> A v1 fixava 45 pregões; aqui todo horizonte "
            "vale, com uma exclusão só — o de 1 pregão, porque o sinal nasce no fechamento e a "
            "execução é na abertura seguinte.",
            "A peneira de qualidade <b>precisa ser por época</b>, não global: papéis sólidos eram "
            "reprovados inteiros por causa de uma década antiga de baixa liquidez.",
            "A taxa-base de cada papel é medida sobre uma <b>janela de tempo diferente</b>, porque "
            "nem toda época sobrevive à peneira. Só 13 dos 61 papéis usam as cinco divisões — por "
            "isso a tabela de gatilhos exibe o período medido ao lado de cada linha.",
        ],
        # Notas: o que mudou DEPOIS de a versão entrar no ar, sem mudar a pergunta que ela responde.
        "notas": [
            ("12/10/2026", "Primeiro retorno de <b>uso real</b>, após um mês acompanhando os "
                           "alertas. A tela deixou de ser uma seção por horizonte e passou a ser "
                           "<b>uma tabela só, com um papel por linha</b>, ordenada pela soma dos "
                           "dias dos horizontes em que o papel dispara. O usuário monta posição "
                           "olhando 45 e 20 pregões; a presença nos prazos curtos entra como "
                           "<em>reforço do mesmo gatilho</em>, não como alternativa a ele. A coluna "
                           "de proteção crua saiu — a decisão sempre se apoiou no limite inferior, "
                           "e exibir as duas convidava a ler a mais otimista. Os números da linha "
                           "passaram a vir do <b>maior horizonte</b> do papel, que é o prazo da "
                           "decisão: um papel com 72% em 3 pregões e 52% em 10 exibe 52%."),
            ("12/10/2026", "<b>A medida desta versão não passou no controle.</b> Em séries de preços "
                           "sem memória, a proteção por episódio já devolve de 75% a 80%, contra a "
                           "taxa-base de 52% a 55% usada como barra. O ranking de proteção ordena "
                           "os papéis principalmente pelo que afeta essa contagem, e não por "
                           "previsibilidade. A página continua no ar, com um aviso, porque registra "
                           "o caminho da pesquisa; a medida corrigida é a da v3."),
        ],
        "receita": "<b>1.</b> A página de gatilhos continua sendo gerada por <code>gerar_alertas.py</code>;\n"
                   "   para voltar a tratá-la como a versão vigente, remova o aviso do topo de\n"
                   "   <code>template_alertas.html</code> e troque os estados neste registro.\n"
                   "<b>2.</b> Ela depende de <code>estudo/setups.csv</code>, exportado pelo laboratório.\n"
                   "<b>3.</b> Antes de voltar, leia o achado W: os números desta versão comparam\n"
                   "   uma medida por episódio com uma taxa-base por dia.",
    },
    {
        "id": "v1",
        "nome": "Triagem por afastamento",
        "estado": "mantida",
        "classe_estado": "e-mantida",
        "data": "23/08/2026",
        "origem": "achado L",
        "pergunta": "Onde cada papel líquido está hoje na escala de afastamento da média móvel de "
                    "90 pregões, e o que aconteceu depois de dias parecidos?",
        "parametros": [
            ("papéis", "70"),
            ("janela da média móvel", "90 pregões"),
            ("horizonte", "45 pregões"),
            ("leitura mestra", "BOVA11"),
            ("faixas", "10 decis"),
            ("zona de viés", "decis 0, 1 e 2"),
            ("desvio da distância", "252 pregões"),
            ("início do teste", "2021-01-01"),
            ("papéis exibidos", "5"),
            ("peneira de qualidade", "global"),
        ],
        "passos": [
            ("Baixar a história completa dos papéis líquidos",
             "Setenta papéis, período <code>max</code>, uma requisição por papel."),
            ("Peneira de qualidade, no papel inteiro",
             "Liquidez média, fração de dias com preço parado e histórico mínimo, avaliados sobre "
             "<b>toda a série de uma vez</b>. Reprovado, o papel some da tela."),
            ("Distância até a média, em desvios-padrão",
             "A distância percentual dividida pelo desvio dos últimos 252 pregões — é o que torna "
             "papel volátil e papel calmo comparáveis na mesma escala."),
            ("Decis com cortes do treino",
             "Os dez cortes vêm dos dados anteriores a 2021; o período de 2021 em diante é o teste. "
             "O papel de hoje é posicionado por esses cortes."),
            ("Leitura mestra do índice",
             "O BOVA11 é medido primeiro. Se ele não está na zona de viés, os papéis abaixo são "
             "<b>sinais soltos</b> — e a página diz isso. Falha do índice derruba a publicação de "
             "propósito."),
            ("Tabela dos papéis na zona",
             "Cada papel na zona (decis 0 a 2) entra com o histórico do decil dele, a taxa-base, a "
             "vantagem entre as duas e o número de episódios que sustentam a leitura."),
        ],
        "titulo_mudou": "Por que ela continua no ar",
        "mudou": [
            "Ela responde uma <b>pergunta panorâmica</b>: onde estão os setenta papéis hoje. A v2 "
            "responde uma pergunta pontual, e fica vazia na maioria dos pregões.",
            "A leitura mestra do índice não tem equivalente na v2 — lá cada papel é medido sozinho, "
            "sem condicionar no mercado.",
            "<b>Suas limitações são conhecidas</b> e estão registradas: janela e horizonte fixos "
            "escolhidos antes do achado N, peneira de qualidade global, e uma única divisão entre "
            "treino e teste em vez de cinco.",
        ],
        "notas": [],
        # A receita de retorno só existe para versões que não estão em produção — para a vigente,
        # "como voltar" não faz sentido.
        "receita": "<b>1.</b> Restaure os parâmetros do quadro acima em <code>nucleo/config.py</code>.\n"
                   "<b>2.</b> Publique <code>gerar_tela.py</code> como a página de entrada.\n"
                   "<b>3.</b> A v1 não depende de artefato do laboratório: ela mede tudo\n"
                   "   na hora. Não é preciso sincronizar planilha nenhuma.",
    },
]

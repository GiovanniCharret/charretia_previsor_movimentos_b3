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
muda de valor. Recalibrações entram como nota na versão vigente. Sem esse critério, cada nova
varredura viraria uma versão e a página perde a serventia em poucos meses.

Ordem da lista: da mais recente para a mais antiga. A primeira é a que a página abre.
"""

VERSOES = [
    {
        "id": "v2",
        "nome": "Gatilhos de proteção",
        "estado": "em produção",
        "classe_estado": "e-ativa",
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
        "receita": None,
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
        # A receita de retorno só existe para versões que não estão em produção — para a vigente,
        # "como voltar" não faz sentido.
        "receita": "<b>1.</b> Restaure os parâmetros do quadro acima em <code>nucleo/config.py</code>.\n"
                   "<b>2.</b> Publique <code>gerar_tela.py</code> como a página de entrada.\n"
                   "<b>3.</b> A v1 não depende de artefato do laboratório: ela mede tudo\n"
                   "   na hora. Não é preciso sincronizar planilha nenhuma.",
    },
]

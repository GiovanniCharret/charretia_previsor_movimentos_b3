"""
Filtro de QUALIDADE DE DADOS de uma série de preços — a peneira que roda antes de qualquer estudo.

Por que este módulo existe: durante os estudos de agosto de 2026, três defeitos de dados quase
entraram nos resultados como se fossem descobertas, e cada um foi pego por uma medida diferente:

  - **SUZB3**: volume financeiro mediano ZERO e 60% de dias com preço repetido, porque o código só
    passou a negociar de fato depois da fusão de 2019. O histórico anterior é preenchimento.
  - **CMIG4 e CPFE3**: volatilidade anual de 177% e 355%, impossível para distribuidoras de energia
    — quase certamente desdobramento de ações não ajustado, que cria um retorno diário absurdo.
  - **LREN3, CYRE3, WEGE3, RADL3, TEND3**: 20% a 40% de dias com preço parado.

O último é o mais perigoso PARA ESTE PROJETO em particular. Preço parado, e a diferença entre as
pontas de compra e venda em papéis pouco líquidos, produzem uma queda aparente seguida de uma alta
aparente **sem que nenhum negócio real tenha ocorrido nesses preços**. Isso é exatamente o padrão
que o estudo de caudas mede — ou seja, um papel ruim de dados fabrica o nosso "achado" do nada.

Lição registrada: **liquidez alta não garante dado limpo.** CMIG4 negociava 45 milhões de reais por
dia e mesmo assim estava quebrada; foi a volatilidade que a denunciou. Por isso o filtro olha quatro
coisas, e não uma.
"""

import numpy as np                                          # medidas numéricas
import pandas as pd                                         # séries de preço


def treino_util(indice, janela_max, vol_lag, data_inicio_teste):
    """
    Quantos pregões SOBRAM para treinar, depois do aquecimento e do período reservado ao teste.

    Por que existe: "quantos pregões o papel tem" é o número errado, e confiar nele deixou passar
    quatro papéis na primeira triagem dos 70. O HAPV3, por exemplo, tem 2.069 pregões — parece
    bastar — mas com teste a partir de 2021 sobram ~679 antes do corte, e o aquecimento consome
    451 deles (média móvel de 200 dias + desvio-padrão móvel de 252). Restam ~228 pregões para
    cortar dez decis, ou seja, 23 observações por decil. Cortes assim não significam nada.

    Entrada: indice (DatetimeIndex da série), janela_max (a maior média móvel do estudo), vol_lag
    (janela do desvio móvel), data_inicio_teste (onde o teste começa, em calendário).
    Fase 1: contar as linhas anteriores ao início do teste — é todo o material candidato a treino.
    Fase 2: descontar o aquecimento; a primeira linha com escore padronizado válido só aparece
            depois de janela_max + vol_lag − 1 pregões.
    Saída: int, nunca negativo.
    """
    # Fase 1: material candidato a treino (tudo que antecede o corte de calendário).
    antes = int((indice < pd.Timestamp(data_inicio_teste)).sum())
    # Fase 2: descontar o aquecimento das duas médias encadeadas; piso em zero.
    return max(0, antes - (int(janela_max) + int(vol_lag) - 1))


def avalia_qualidade(prices, min_pregoes=1000, min_volume_mm=5.0,
                     max_fracao_parado=0.15, max_volatilidade_anual=1.0,
                     janela_max=None, vol_lag=None, data_inicio_teste=None,
                     min_treino_util=750):
    """
    Avalia se uma série de preços é confiável o bastante para entrar num estudo.

    Por que existe: centralizar a peneira num só lugar, testado, em vez de repetir verificações
    ad-hoc a cada análise — e garantir que todo estudo use exatamente o mesmo critério, senão a
    comparação entre papéis fica contaminada por quem passou por qual filtro.

    Entrada: prices (DataFrame com Close e Volume), mais os quatro limiares.
    Fase 1: contar pregões — histórico curto não sustenta split com treino, embargo e teste.
    Fase 2: volume financeiro diário mediano (fechamento × quantidade), que é a medida certa de
            liquidez; quantidade de ações sozinha engana entre papéis de preços muito diferentes.
    Fase 3: fração de dias com variação EXATAMENTE zero — o detector de preço parado.
    Fase 4: volatilidade anual dos retornos diários; valor absurdo denuncia desdobramento não
            ajustado ou outro erro na série, mesmo em papel líquido.
    Fase 5: treino ÚTIL — calculado só quando o contexto do estudo é informado (janela_max, vol_lag
            e data_inicio_teste). É o que sobra para treinar depois do aquecimento e do corte de
            calendário, e é o número que de fato limita a confiabilidade dos cortes de decil.
            Ignorar isso deixou passar quatro papéis na primeira triagem dos 70 tickers líquidos.
    Fase 6: juntar os motivos de reprovação (todos, não só o primeiro) e decidir.
    Saída: dict com as medidas, `treino_util` (None quando não calculável), `motivos` e `aprovado`.
    """
    # Fase 1: tamanho do histórico.
    n = len(prices)
    # Retornos diários, base das medidas seguintes.
    retornos = prices["Close"].pct_change().dropna()

    # Fase 2: liquidez em reais por dia (mediana é robusta a dias atípicos).
    volume_financeiro = float((prices["Close"] * prices["Volume"]).median()) if n else 0.0

    # Fase 3: fração de dias em que o preço não mudou nada (preço parado / negócio inexistente).
    fracao_parado = float((retornos == 0).mean()) if len(retornos) else 1.0

    # Fase 4: volatilidade anualizada (desvio-padrão diário × raiz de 252 pregões).
    volatilidade = float(retornos.std() * np.sqrt(252)) if len(retornos) > 1 else float("nan")

    # Fase 5: treino útil, só quando o contexto do estudo foi informado.
    treino = None
    if janela_max is not None and vol_lag is not None and data_inicio_teste is not None:
        treino = treino_util(prices.index, janela_max, vol_lag, data_inicio_teste)

    # Fase 6: acumular TODOS os motivos de reprovação, para o diagnóstico ser completo.
    motivos = []
    if n < min_pregoes:
        motivos.append(f"histórico curto ({n} pregões, mínimo {min_pregoes})")
    if volume_financeiro < min_volume_mm * 1e6:
        motivos.append(f"liquidez baixa ({volume_financeiro/1e6:.1f} milhões por dia, "
                       f"mínimo {min_volume_mm})")
    if fracao_parado > max_fracao_parado:
        motivos.append(f"preço parado em {100*fracao_parado:.0f}% dos dias "
                       f"(máximo {100*max_fracao_parado:.0f}%)")
    if not np.isnan(volatilidade) and volatilidade > max_volatilidade_anual:
        motivos.append(f"volatilidade anual impossível ({100*volatilidade:.0f}%) — provável "
                       f"desdobramento não ajustado na série")

    # Reprovar por treino insuficiente: o histórico total pode enganar, o treino útil não.
    if treino is not None and treino < min_treino_util:
        motivos.append(f"treino insuficiente ({treino} pregões úteis após aquecimento de "
                       f"{int(janela_max) + int(vol_lag) - 1} e corte em {data_inicio_teste}; "
                       f"mínimo {min_treino_util})")

    # Saída: as medidas + o veredito, para que a decisão seja auditável.
    return {"pregoes": n, "volume_financeiro_mediano": volume_financeiro,
            "fracao_preco_parado": fracao_parado, "volatilidade_anual": volatilidade,
            "treino_util": treino, "motivos": motivos, "aprovado": len(motivos) == 0}

# Proveniência da amplitude (v3.1)

**Arquivos gerados. Não edite à mão.**

`amplitude_limiares.csv` e `amplitude_excessos.csv` vêm dos dois testes de amplitude do
laboratório (`rebuild_robusta_backtests`), de 26/11/2026: o do limiar travado no treino (veredito:
indício) e a contagem de episódios. Ver `planning/PLAN.md` de lá, seção "RESULTADO — a amplitude
com o limiar travado no treino".

| exportado em | 26/11/2026 às 06:53 |
|---|---|
| commit do laboratório | `1ede148` |
| árvore de trabalho | **com alterações não commitadas** |
| origem | `amplitude_episodios_resultado.xlsx` (aba "limiares") e `amplitude_limiar_resultado.xlsx` (aba "principais") |
| roteiro | roteiro de rascunho do laboratório (`exporta_amplitude.py`), ainda fora do pacote `robusta_ml` |

## O que os números significam

- **amplitude** de um papel numa média móvel: a fração dos OUTROS papéis acompanhados que fecharam
  no próprio corte da faixa extrema, ou abaixo dele, na mesma média e no mesmo percentil. BOVA11,
  SMAL11 e IBOV11 não entram na conta, porque são cestas dos outros;
- `limiar_fracao`: o limiar de "muitos papéis", por percentil e janela. É a mediana da amplitude nos
  dias de faixa extrema do **treino da divisão mais recente** (treino até 2022, 70 papéis). Em 68
  outros papéis, isso dá de 7 a 10 papéis no corte de 2,5% e de 10 a 13 no de 5%;
- `excesso`: o quanto a frequência de retorno positivo em 45 pregões ficou acima da taxa-base, na
  média dos papéis e das nove janelas, só nos dias de queda larga ou só nos de queda isolada;
- `excesso_misturado`: a mesma conta com os dois tipos juntos, ponderada pela fração de dias de
  cada um. É o que a frequência da v3 carrega;
- `deslocamento`: `excesso − excesso_misturado`. É o que a tela soma à frequência do papel para
  chegar à "frequência ajustada".

## O que isto vale

**Indício**: valor-p corrigido de 0,014 (2,5%) e 0,008 (5%) contra o placebo conjunto. A hipótese
nasceu dos mesmos dados em que foi testada. O deslocamento é uma média entre papéis; papel a papel
não há dias bastantes para medir separado.

Duas diferenças conhecidas em relação ao teste: lá, o corte de cada papel vinha do treino de cada
divisão; aqui ele é o da história completa (`faixa_extrema_cortes.csv`). E o teste usou 70 papéis,
enquanto a tela acompanha os da lista de 100. Por isso o limiar é uma **fração**, e não um número de
papéis.

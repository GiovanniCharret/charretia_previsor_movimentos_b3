# Proveniência de `setups.csv`

**Este arquivo é gerado. Não edite à mão.**

Produzido por `robusta_ml.exporta_setups`, no repositório do laboratório
(`rebuild_robusta_backtests`), a partir da aba `aprovados` de `rank_protecao.xlsx`.

## Origem

| exportado em | 07/09/2026 às 11:09 |
|---|---|
| commit do laboratório | `a5be6d8` |
| árvore de trabalho | **com alterações não commitadas** |

## Conteúdo

- **14470 setups** aprovados, em **61 papéis**
- horizontes presentes: 3, 5, 10, 20, 45 pregões
- linhas descartadas por não terem corte medido: 0

## O que os números significam

- a faixa que dispara é o **decil 0** de 10, o mais afastado para baixo;
- a distância até a média é normalizada pelo desvio-padrão de **252 pregões**;
- a coluna `corte` é o limiar desse decil medido sobre **toda a história do papel até a
  data da exportação**. No estudo, cada divisão usa o corte do treino dela, porque medir
  com dados do futuro seria vazamento; aqui o corte usa o passado inteiro, que é o correto
  para operar — usar o passado para definir o limiar de hoje não olha para frente. São
  cortes diferentes, e cada um está certo no seu lugar;
- `passa_barra` é falso apenas na linha **menos pior** dos papéis que não têm nenhum setup
  acima da própria taxa-base. Essas linhas não são gatilho, e a aplicação as descarta;
- `divisoes_usadas` diz sobre quantas épocas a taxa-base daquele papel foi medida. Abaixo
  de 3, leia o resultado como divisão única, não como validação encadeada.

## Como atualizar

A partir da raiz do laboratório, nesta ordem:

```powershell
$env:PYTHONPATH="src"; uv run python -m robusta_ml.rank_protecao
$env:PYTHONPATH="src"; uv run python -m robusta_ml.rank_protecao --cortes
$env:PYTHONPATH="src"; uv run python -m robusta_ml.exporta_setups
```

O terceiro comando grava `setups.csv` e este arquivo direto neste repositório.

# Proveniência de bancos e elétricas (v4)

**Arquivos gerados. Não edite à mão.**

`setores_cortes.csv` e `setores_por_janela.csv` são produzidos por `robusta_ml.setores_v4`,
no repositório do laboratório (`rebuild_robusta_backtests`).

| exportado em | 04/11/2026 às 22:38 |
|---|---|
| commit do laboratório | `db50c2d` |
| árvore de trabalho | **com alterações não commitadas** |
| papéis | 18 |
| cortes medidos | 162 |

## O que os números significam

- papéis: os 18 de Energia Elétrica e Intermediários Financeiros, travados em 04/11/2026;
- janelas: 5, 10, 20, 30, 45, 60, 90, 130, 200 pregões;
- corte: o percentil de 10% (o decil 0) da distância até
  a média dividida pelo desvio-padrão móvel de 252 pregões do papel;
- horizonte: 45 pregões;
- `corte`: o limiar de cada janela sobre a história completa — é o que a aplicação
  compara com o fechamento do dia;
- `freq_dias`: fração dos DIAS no decil 0 com retorno seguinte positivo, na validação
  encadeada, com o corte só do treino de cada divisão; `taxa_base`: o mesmo num dia qualquer.

## O que isto vale

**É uma hipótese em observação.** No teste por setor de 04/11/2026, o decil 0 em 45 pregões
deu +8,5 pontos sobre a taxa-base nas elétricas (valor-p 0,007) e +9,7 nos bancos (0,016),
mas não sobreviveu à correção pelos 66 testes feitos. A confirmação vem dos pregões futuros.

## Como atualizar

```powershell
$env:PYTHONPATH="src"; uv run python -m robusta_ml.setores_v4
```

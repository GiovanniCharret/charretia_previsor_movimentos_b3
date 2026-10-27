# Proveniência da faixa extrema

**Arquivos gerados. Não edite à mão.**

`faixa_extrema_cortes.csv` e `faixa_extrema_medidas.csv` são produzidos por
`robusta_ml.faixa_extrema`, no repositório do laboratório (`rebuild_robusta_backtests`).

| exportado em | 19/10/2026 às 21:36 |
|---|---|
| commit do laboratório | `db50c2d` |
| árvore de trabalho | **com alterações não commitadas** |
| papéis | 98 |
| cortes medidos | 1764 |

## O que os números significam

- janelas: 5, 10, 20, 30, 45, 60, 90, 130, 200 pregões;
- percentis: 2,5% e 5% da distância até a média dividida pelo desvio-padrão móvel de
  252 pregões do próprio papel;
- `corte`: o limiar de cada (janela, percentil) sobre a história completa — é o que a
  aplicação compara com o fechamento do dia;
- `freq_dias`: fração dos DIAS acionados com retorno seguinte positivo, na validação
  encadeada, média entre as janelas. Conta dias, não episódios;
- `lim_inf`: limite inferior exato de 95% dessa fração, usando o número de episódios como
  tamanho de amostra, porque dias seguidos não são independentes;
- `faixa_extrema_por_janela.csv`: a mesma medida janela a janela. A tela exibe a média das
  janelas em que o papel está no extremo HOJE — cada uma vem de poucos episódios.

## O que isto vale

**É um indício, não um achado.** Juntando 59 papéis, o excesso sobre a taxa-base no
percentil de 2,5% é de +4,2 pontos em 20 pregões e +7,3 em 45, com o percentil de 30% em
zero como controle. Contra o placebo conjunto por data, só um de seis testes passa de 5%.
Papel a papel, o efeito não é detectável.

## Como atualizar

```powershell
$env:PYTHONPATH="src"; uv run python -m robusta_ml.faixa_extrema
```

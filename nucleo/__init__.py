"""
Cópia do que a tela precisa do laboratório — o repositório irmão `robusta_backtest`,
pacote `src/robusta_ml/`.

Por que existe: esta tela roda sozinha, sem o laboratório no caminho de importação, e o
laboratório segue livre para mudar sem quebrar a publicação diária.

O preço da cópia é a deriva silenciosa: uma correção feita lá não chega aqui, e nada avisa.
Enquanto os dois viviam no mesmo repositório, um teste comparava os dois lados a cada execução;
separados, **a resincronização é manual**. O README registra de qual commit esta cópia veio —
mantenha aquele registro atualizado a cada recópia.

Os módulos servem às DUAS telas. `data`, `features_mma` e `faixas` são usados pelas duas;
`qualidade_dados` traz, além da peneira global que a v1 usa, a apara da cabeça anterior à listagem
e a avaliação por época que o achado U introduziu e a v2 exige.

**Nenhum arquivo aqui deve ser editado à mão.** Uma correção feita aqui se perde na próxima
recópia, e as duas versões divergem para sempre. Mude no laboratório e recopie.
"""

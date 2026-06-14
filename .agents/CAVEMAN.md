# CAVEMAN

Protocolo local para economizar tokens em tarefas de manutenção.

## Regras

- Ler pouco, mas ler o arquivo certo.
- Começar por `git status --short` e `git diff --stat`.
- Usar `rg` ou `Select-String` antes de abrir arquivos grandes.
- Não repetir contexto já registrado em `.agents/PROJECT_MEMORY.md`.
- Não despejar logs; resumir achados e citar `run_id`.
- Responder com ação, evidência e próximo passo.
- Preferir patches pequenos e verificáveis.

## Saída Esperada

- Máximo de detalhes necessários para executar ou revisar.
- Arquivos citados com caminho.
- Testes executados ou motivo objetivo para não executar.

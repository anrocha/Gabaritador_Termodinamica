# CLAUDE.md

Este projeto usa `AGENTS.md` como fonte principal de instruções para agentes.

Leitura recomendada, nessa ordem:

1. `AGENTS.md`
2. `.agents/PROJECT_MEMORY.md`
3. `.agents/WORKFLOWS.md`
4. `.agents/DECISIONS.md`
5. `.agents/CAVEMAN.md` quando o objetivo for reduzir tokens

Regras rápidas:

- Não tocar em `.git/COMMIT_EDITMSG`.
- Não commitar sem pedido explícito.
- Não ler `logs/` inteiro; usar apenas o `run_id` citado.
- OpenAI interpreta; CoolProp e ferramentas internas calculam.
- Manter o app incremental e não destrutivo.

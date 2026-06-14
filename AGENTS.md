# AGENTS.md

## Acordos do Repositório

- Trabalhe de forma incremental e não destrutiva; preserve as abas e fluxos existentes.
- Não toque em `.git/COMMIT_EDITMSG`, não faça commit e não reescreva histórico sem pedido explícito.
- Antes de mudanças relevantes, faça leitura curta: `git status --short`, `git diff --stat`, `git log --oneline -n 5`.
- Não leia `logs/` inteiro; abra somente o `run_id` citado ou o log necessário para depuração.
- Trate `logs/` como auditoria local do Gabaritador; não use logs antigos como fonte da verdade para outro exercício.

## Arquitetura do App

- `app.py`: UI Streamlit e composição das abas.
- `openai_assistant.py`: interpretação/plano pela OpenAI; não deve calcular propriedades.
- `thermo_executor.py`: roteamento e execução determinística das ferramentas internas.
- `thermo_facts.py`: normalização canônica de fatos, unidades e aliases.
- `exercise_rendering.py`: renderização didática do Gabaritador.
- `*_core.py`: cálculos determinísticos com CoolProp ou modelos termodinâmicos clássicos.

## Regras Termodinâmicas

- OpenAI interpreta enunciados; CoolProp e módulos determinísticos calculam.
- Propriedades obtíveis por CoolProp não são dados faltantes.
- Unidades globais afetam apenas exibição; solvers recebem unidades explícitas e consistentes.
- Toda resposta deve mostrar origem das propriedades, fórmulas, substituição numérica e validação física quando aplicável.

## Validação

- Para alterações em Python, rode `python -m py_compile` nos módulos alterados.
- Para alterações só de documentação/memória, valide existência dos arquivos e frontmatter de skills.
- Não corrija bugs não relacionados no mesmo patch; registre como observação se aparecerem.

## Modo Econômico

- Use a skill/protocolo `caveman` para economia de tokens.
- Prefira buscas direcionadas com `rg`, `Select-String`, `git diff --stat` e leitura por arquivo específico.
- Evite despejar arquivos grandes; resuma evidências e cite caminhos/linhas quando útil.

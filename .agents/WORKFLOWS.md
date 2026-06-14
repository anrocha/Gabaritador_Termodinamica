# Workflows

## Antes de Trabalhar

1. Rodar `git status --short`.
2. Rodar `git diff --stat`.
3. Rodar `git log --oneline -n 5` quando histórico ajudar.
4. Ler apenas os arquivos relacionados ao pedido.

## Gabaritador

1. Receber texto, imagem ou ambos.
2. A OpenAI interpreta e produz plano estruturado.
3. O sistema normaliza fatos em nomes canônicos.
4. O executor escolhe ferramenta principal e auxiliares.
5. CoolProp ou módulos locais calculam estados e balanços.
6. Renderizador mostra cada questão: interpretação, dados, fórmula, substituição, resultado e origem.
7. Logger salva input, plano e output com o mesmo `run_id`.

## Correção de Bug

1. Reproduzir pelo log ou cenário mínimo.
2. Identificar se o erro está em interpretação, normalização, execução ou renderização.
3. Corrigir a menor camada responsável.
4. Validar com `py_compile` e, se necessário, caso sintético.

## Trabalho com Logs

- Abrir somente os arquivos do `run_id` citado.
- Não usar resultados antigos para renderizar plano novo.
- Se input e output divergem, verificar `plan_id`, ferramenta planejada e ferramenta executada.

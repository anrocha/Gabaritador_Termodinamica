---
name: caveman
description: Use quando o usuário pedir economia de tokens, execução enxuta, contexto mínimo, análise rápida de repo, redução de verbosidade ou evitar releitura de logs/código grande. Mantém rigor usando git, buscas direcionadas e evidência mínima suficiente.
---

# CAVEMAN

Siga um modo enxuto e verificável.

## Procedimento

1. Comece por evidência curta: `git status --short`, `git diff --stat` e busca direcionada.
2. Leia só arquivos diretamente relacionados ao pedido.
3. Evite abrir `logs/` inteiro; use apenas o `run_id` citado.
4. Resuma achados em poucas linhas.
5. Faça patches pequenos e focados.
6. Valide com o menor comando suficiente.

## Comunicação

- Seja direto.
- Não repita histórico já conhecido.
- Cite apenas arquivos relevantes.
- Não cole conteúdo grande de arquivos.
- Termine com resultado, validação e próximo passo opcional.

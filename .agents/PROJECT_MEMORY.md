# Memória do Projeto

## Objetivo

Gabaritador de Termodinâmica em Streamlit para resolver exercícios com interpretação por OpenAI, cálculo determinístico por CoolProp e explicação didática item a item.

## Estado Atual

- O projeto já usa git.
- Existe uma alteração local em `exercise_rendering.py` que não deve ser sobrescrita sem revisão.
- Logs de exercícios ficam em `logs/YYYY-MM-DD/` e servem para auditoria.
- A pasta antiga `skills/` existe; a localização canônica para skills do repo passa a ser `.agents/skills/`.

## Módulos Principais

- `app.py`: UI, abas e estado de sessão.
- `thermo_core.py`: propriedades por pares, título e utilidades gerais.
- `cycle_core.py`: ciclo simples de compressão de vapor.
- `standard_cycle_core.py`: ciclo padrão por pressões.
- `turbine_core.py`: turbina de vapor/água.
- `evaporator_core.py`: evaporador com ar e R134a.
- `reservoir_cycle_core.py`: ciclos entre reservatórios.
- `openai_assistant.py`: interpretação multimodal e plano estruturado.
- `tool_catalog.py`: catálogo de ferramentas disponíveis.
- `thermo_facts.py`: fatos canônicos, aliases e unidades.
- `thermo_orchestrator.py`: base de orquestração por fatos/ferramentas.
- `thermo_executor.py`: executor determinístico e roteamento defensivo.
- `exercise_rendering.py`: respostas por questão, fórmulas, tabelas e gráficos.
- `exercise_logger.py`: logs compactos de input, plano, output e erro.

## Invariantes

- Nunca calcular propriedades termodinâmicas com a IA.
- Nunca converter unidades globais antes do cálculo; converter apenas na exibição.
- Nunca ocultar item do enunciado; se não resolver, mostrar bloqueio claro.
- Nunca tratar título/qualidade `x` como temperatura, pressão ou energia.

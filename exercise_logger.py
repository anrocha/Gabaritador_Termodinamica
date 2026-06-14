from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openai_assistant import ThermoPlan
from thermo_executor import ExecutionResult
from thermo_facts import canonical_fact_lines, ranked_tool_readiness


LOG_ROOT = Path("logs")


def new_run_id(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return current.strftime("%Y%m%d-%H%M%S-%f")


def log_input(
    run_id: str,
    statement: str,
    files_payload: list[dict[str, Any]],
    model: str,
    plan: ThermoPlan,
) -> str:
    now = datetime.now()
    path = _log_path(now, run_id, "input")
    files = "\n".join(
        f"- `{item.get('name', 'arquivo')}` | tipo: `{item.get('content_type', '')}` | tamanho: {len(item.get('data', b''))} bytes"
        for item in files_payload
    ) or "- Nenhum arquivo enviado."
    content = f"""# Input do exercício

- Run ID: `{run_id}`
- Data/hora: `{now.isoformat(timespec="seconds")}`
- Modelo OpenAI: `{model}`
- Regra: imagem e texto do usuário foram consolidados na mesma interpretação.

## Interpretação consolidada

{plan.entrada_oficial.strip() or "[sem entrada oficial consolidada]"}

## Interpretação da imagem

{plan.interpretacao_imagem.strip() or "[sem interpretação de imagem]"}

## Texto adicional digitado

{plan.texto_usuario.strip() or statement.strip() or "[sem texto digitado]"}

## Diagnóstico da entrada

{plan.diagnostico_entrada.strip() or "[sem diagnóstico]"}

## Arquivos enviados

{files}

## Privacidade

O conteúdo binário dos arquivos não foi salvo neste log. Apenas metadados foram registrados.
"""
    return _write(path, content)


def log_plan(run_id: str, plan: ThermoPlan, plan_id: str) -> str:
    now = datetime.now()
    path = _log_path(now, run_id, "plan")
    content = f"""# Plano interpretado

- Run ID: `{run_id}`
- Plan ID: `{plan_id}`
- Data/hora: `{now.isoformat(timespec="seconds")}`

## Resumo

- Categoria: `{plan.categoria}`
- Tipo: `{plan.tipo_problema}`
- Fluido: `{plan.fluido}`
- Ferramentas: `{", ".join(plan.ferramentas_necessarias) or "-"}`
- Confiança: `{plan.confianca:.0%}`

## Dados faltantes

{_bullet_list(plan.dados_faltantes)}

## Dados conhecidos

{_planner_items(plan.dados_conhecidos)}

## Fatos canônicos

{_bullet_list(canonical_fact_lines(plan))}

## Ferramentas candidatas

{_tool_readiness(plan)}

## Estados

{_planned_states(plan)}

## Objetivos

{_bullet_list(plan.objetivos)}

## Questões

{_bullet_list(tuple(f"{question.item}: {question.objetivo}" for question in plan.questoes))}
"""
    return _write(path, content)


def log_output(
    run_id: str,
    plan_id: str,
    execution: ExecutionResult,
    copyable: str,
    planned_tools: tuple[str, ...] | list[str] = (),
    question_answers: str = "",
) -> str:
    now = datetime.now()
    path = _log_path(now, run_id, "output")
    summary_lines = [
        f"- Ferramenta executada: `{execution.kind}`",
        f"- Título: `{execution.title}`",
    ]
    if execution.messages:
        summary_lines.append(f"- Mensagens: `{len(execution.messages)}`")
    if execution.turbine_result:
        summary_lines.append("- Resultado: turbina de vapor")
    if execution.cycle_result:
        summary_lines.append("- Resultado: ciclo de refrigeracao")
    if execution.evaporator_result:
        summary_lines.append("- Resultado: evaporador ar + R134a")
    if execution.reservoir_result:
        summary_lines.append("- Resultado: refrigerador entre reservatorios")
    if execution.standard_cycle_result:
        summary_lines.append("- Resultado: ciclo padrao por pressoes")
    question_answers_section = question_answers.strip() or "## Respostas por questão\n\n- Nenhuma resposta por questão foi gerada."
    content = f"""# Output do exercício

- Run ID: `{run_id}`
- Plan ID: `{plan_id}`
- Data/hora: `{now.isoformat(timespec="seconds")}`
- Ferramenta planejada: `{", ".join(planned_tools) or "-"}`
- Ferramenta executada: `{execution.kind}`
- Resumo
{chr(10).join(summary_lines)}

## Mensagens

{_bullet_list(execution.messages)}

## Passos executados

{_bullet_list(execution.execution_steps)}

## Fatos canÃ´nicos usados

{_bullet_list(execution.canonical_facts)}

## Ferramentas avaliadas

{_bullet_list(execution.tool_readiness)}

## Objetivos nao resolvidos

{_bullet_list(execution.unresolved_goals)}

{question_answers_section}

## ValidaÃ§Ãµes fÃ­sicas

{_bullet_list(_execution_validations(execution))}

## Versão copiável

```markdown
{copyable.strip() or "[sem versão copiável disponível]"}
```
"""
    return _write(path, content)


def log_error(run_id: str, plan_id: str, stage: str, error: Exception) -> str:
    now = datetime.now()
    path = _log_path(now, run_id, "error")
    content = f"""# Erro no exercício

- Run ID: `{run_id}`
- Plan ID: `{plan_id}`
- Etapa: `{stage}`
- Data/hora: `{now.isoformat(timespec="seconds")}`

## Erro

```text
{type(error).__name__}: {error}
```
"""
    return _write(path, content)


def _log_path(now: datetime, run_id: str, suffix: str) -> Path:
    return LOG_ROOT / now.strftime("%Y-%m-%d") / f"{run_id}-{suffix}.md"


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return str(path)


def _bullet_list(items: tuple[str, ...] | list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- Nenhum."


def _planner_items(items: tuple[Any, ...] | list[Any]) -> str:
    if not items:
        return "- Nenhum."
    lines = []
    for item in items:
        note = f" ({item.observacao})" if getattr(item, "observacao", "") else ""
        unit = f" {item.unidade}" if getattr(item, "unidade", "") else ""
        lines.append(f"- {item.nome}: {item.valor}{unit}{note}")
    return "\n".join(lines)


def _planned_states(plan: ThermoPlan) -> str:
    if not plan.estados:
        return "- Nenhum."
    lines = []
    for state in plan.estados:
        known = "; ".join(f"{item.nome}={item.valor} {item.unidade}".strip() for item in state.dados_conhecidos)
        calculate = ", ".join(state.propriedades_a_calcular)
        parts = [state.descricao]
        if known:
            parts.append(f"dados: {known}")
        if calculate:
            parts.append(f"calcular: {calculate}")
        lines.append(f"- Estado {state.estado}: {' | '.join(parts)}")
    return "\n".join(lines)


def _tool_readiness(plan: ThermoPlan) -> str:
    lines = []
    for item in ranked_tool_readiness(plan):
        status = "pronta" if item.ready else "bloqueada"
        missing = f" | faltando: {', '.join(item.missing)}" if item.missing else ""
        lines.append(f"- {item.tool}: {status} | score={item.score}{missing}")
    return "\n".join(lines) if lines else "- Nenhum."


def _execution_validations(execution: ExecutionResult) -> tuple[str, ...]:
    if execution.cycle_result:
        return execution.cycle_result.validations
    if execution.turbine_result:
        return execution.turbine_result.validations
    if execution.standard_cycle_result:
        return execution.standard_cycle_result.validations
    return ()

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from heat_transfer_assistant import HeatTransferPlan
from heat_transfer_core import HeatTransferResult
from heat_transfer_facts import canonical_heat_fact_lines


LOG_ROOT = Path("logs")


def new_heat_transfer_run_id(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return current.strftime("%Y%m%d-%H%M%S-%f")


def log_heat_transfer_input(run_id: str, statement: str, files_payload: list[dict[str, Any]], model: str, plan: HeatTransferPlan) -> str:
    now = datetime.now()
    files = "\n".join(
        f"- `{item.get('name', 'arquivo')}` | tipo: `{item.get('content_type', '')}` | tamanho: {len(item.get('data', b''))} bytes"
        for item in files_payload
    ) or "- Nenhum arquivo enviado."
    content = f"""# Input - Transferência de Calor

- Run ID: `{run_id}`
- Data/hora: `{now.isoformat(timespec="seconds")}`
- Modelo OpenAI: `{model}`
- Regra: imagem e texto foram consolidados na interpretação.

## Entrada oficial consolidada

{plan.entrada_oficial.strip() or "[sem entrada oficial]"}

## Interpretação da imagem

{plan.interpretacao_imagem.strip() or "[sem imagem interpretada]"}

## Texto adicional

{plan.texto_usuario.strip() or statement.strip() or "[sem texto adicional]"}

## Diagnóstico

{plan.diagnostico_entrada.strip() or "[sem diagnóstico]"}

## Arquivos

{files}
"""
    return _write(_log_path(now, run_id, "heat-transfer-input"), content)


def log_heat_transfer_plan(run_id: str, plan: HeatTransferPlan, plan_id: str) -> str:
    now = datetime.now()
    content = f"""# Plano - Transferência de Calor

- Run ID: `{run_id}`
- Plan ID: `{plan_id}`
- Data/hora: `{now.isoformat(timespec="seconds")}`
- Categoria: `{plan.categoria}`
- Tipo: `{plan.tipo_problema}`
- Ferramentas: `{", ".join(plan.ferramentas_necessarias) or "-"}`
- Confiança: `{plan.confianca:.0%}`

## Dados conhecidos

{_items(plan.dados_conhecidos)}

## Fatos canônicos

{_items(plan.fatos_canonicos)}

## Fatos canônicos normalizados pelo app

{_bullets(canonical_heat_fact_lines(plan))}

## Geometria

{_items(plan.geometria)}

## Condições de contorno

{_items(plan.condicoes_contorno)}

## Dados faltantes

{_bullets(plan.dados_faltantes)}

## Questões

{_bullets(tuple(f"{item.item}: {item.objetivo}" for item in plan.questoes))}

## Plano de execução

{_bullets(plan.plano_execucao)}
"""
    return _write(_log_path(now, run_id, "heat-transfer-plan"), content)


def log_heat_transfer_output(
    run_id: str,
    plan_id: str,
    result: HeatTransferResult,
    copyable: str,
    question_answers: tuple[dict[str, object], ...] | list[dict[str, object]] = (),
) -> str:
    now = datetime.now()
    summary = "\n".join(f"- `{item.symbol}` = {item.value:.6g} {item.unit}" for item in result.results)
    questions = _question_answers_markdown(question_answers)
    content = f"""# Output - Transferência de Calor

- Run ID: `{run_id}`
- Plan ID: `{plan_id}`
- Data/hora: `{now.isoformat(timespec="seconds")}`
- Ferramenta executada: `{result.tool}`

## Resultados

{summary}

## Respostas por questão

{questions}

## Versão copiável

```markdown
{copyable.strip()}
```
"""
    return _write(_log_path(now, run_id, "heat-transfer-output"), content)


def log_heat_transfer_error(run_id: str, plan_id: str, stage: str, error: Exception) -> str:
    now = datetime.now()
    content = f"""# Erro - Transferência de Calor

- Run ID: `{run_id}`
- Plan ID: `{plan_id}`
- Etapa: `{stage}`
- Data/hora: `{now.isoformat(timespec="seconds")}`

## Erro

```text
{error}
```
"""
    return _write(_log_path(now, run_id, "heat-transfer-error"), content)


def _log_path(now: datetime, run_id: str, suffix: str) -> Path:
    return LOG_ROOT / now.strftime("%Y-%m-%d") / f"{run_id}-{suffix}.md"


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return str(path)


def _items(items: tuple[Any, ...]) -> str:
    if not items:
        return "- Nenhum."
    lines = []
    for item in items:
        value = f": {item.valor} {item.unidade}".strip() if item.valor or item.unidade else ""
        obs = f" ({item.observacao})" if item.observacao else ""
        lines.append(f"- {item.nome}{value}{obs}")
    return "\n".join(lines)


def _bullets(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- Nenhum."


def _question_answers_markdown(question_answers: tuple[dict[str, object], ...] | list[dict[str, object]]) -> str:
    if not question_answers:
        return "- Nenhuma questão planejada vinculada ao resultado."
    sections = []
    for answer in question_answers:
        results = "\n".join(f"  - `{item}`" for item in answer.get("resultados", ())) or "  - Sem resultado numérico."
        sections.append(
            f"""- **{answer.get('item', '-')}) {answer.get('objetivo', '-')}**
  - Status: `{answer.get('status', '-')}`
  - Origem: {answer.get('origem', '-')}
  - Resultados:
{results}"""
        )
    return "\n".join(sections)

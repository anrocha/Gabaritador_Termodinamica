from __future__ import annotations

from dataclasses import dataclass

from openai_assistant import ThermoPlan
from thermo_facts import ThermoFact, TOOL_SPECS, ToolReadiness, canonical_facts_from_plan, ranked_tool_readiness


@dataclass(frozen=True)
class ExecutionStep:
    tool: str
    tool_type: str
    status: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolResult:
    tool: str
    produced_facts: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()
    properties_origin: tuple[str, ...] = ()
    equations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionGraph:
    facts: tuple[ThermoFact, ...]
    goals: tuple[str, ...]
    steps: tuple[ExecutionStep, ...]
    dependencies: tuple[str, ...]
    produced_facts: tuple[str, ...]
    unresolved_goals: tuple[str, ...]
    tool_readiness: tuple[ToolReadiness, ...]


def build_execution_graph(
    plan: ThermoPlan,
    selected_tool: str,
    executed_kind: str,
    messages: tuple[str, ...] = (),
) -> ExecutionGraph:
    facts = canonical_facts_from_plan(plan)
    goals = _goals_from_plan(plan)
    readiness = ranked_tool_readiness(plan)
    steps = _planned_steps(selected_tool, executed_kind, facts, messages)
    produced = _produced_facts_from_steps(steps)
    unresolved = _unresolved_goals(goals, produced, messages)
    return ExecutionGraph(
        facts=facts,
        goals=goals,
        steps=steps,
        dependencies=_dependencies_from_readiness(readiness),
        produced_facts=produced,
        unresolved_goals=unresolved,
        tool_readiness=readiness,
    )


def graph_lines(graph: ExecutionGraph) -> tuple[str, ...]:
    lines = []
    for step in graph.steps:
        suffix = f" -> {', '.join(step.outputs)}" if step.outputs else ""
        if step.messages:
            suffix += f" | {'; '.join(step.messages)}"
        lines.append(f"{step.status}: {step.tool} ({step.tool_type}){suffix}")
    return tuple(lines)


def graph_readiness_lines(graph: ExecutionGraph) -> tuple[str, ...]:
    lines = []
    for item in graph.tool_readiness:
        status = "pronta" if item.ready else "bloqueada"
        missing = f" | faltando: {', '.join(item.missing)}" if item.missing else ""
        lines.append(f"{item.tool}: {status} | score={item.score}{missing}")
    return tuple(lines)


def graph_unresolved_lines(graph: ExecutionGraph) -> tuple[str, ...]:
    return graph.unresolved_goals or ()


def _goals_from_plan(plan: ThermoPlan) -> tuple[str, ...]:
    goals = [question.objetivo for question in plan.questoes if question.objetivo]
    if not goals:
        goals = list(plan.objetivos)
    return tuple(goals)


def _planned_steps(
    selected_tool: str,
    executed_kind: str,
    facts: tuple[ThermoFact, ...],
    messages: tuple[str, ...],
) -> tuple[ExecutionStep, ...]:
    if selected_tool == "ciclo_refrigeracao_simples":
        return (
            ExecutionStep("estado_saturado", "auxiliar", "planejado", ("fluid", "T_evap", "x1=1"), ("h1", "s1", "P_evap")),
            ExecutionStep("processo_isoentropico", "auxiliar", "planejado", ("P_cond", "s1"), ("h2s", "T2s")),
            ExecutionStep("estado_saturado", "auxiliar", "planejado", ("fluid", "P_cond", "x3=0"), ("h3", "s3", "T3")),
            ExecutionStep("processo_isoentalpico", "auxiliar", "planejado", ("h4=h3", "P_evap"), ("h4", "x4", "s4")),
            ExecutionStep("balanco_energia", "auxiliar", "planejado", ("cooling_capacity", "h1", "h4", "h2"), ("mass_flow", "compressor_power", "COP")),
            ExecutionStep(executed_kind, "principal", "executado" if not messages else "bloqueado", tuple(_fact_names(facts)), tuple(TOOL_SPECS[selected_tool].outputs), messages),
        )
    if selected_tool in TOOL_SPECS:
        spec = TOOL_SPECS[selected_tool]
        return (
            ExecutionStep(selected_tool, "principal", "executado" if not messages else "bloqueado", tuple(_fact_names(facts)), tuple(spec.outputs), messages),
        )
    return (
        ExecutionStep(executed_kind, "principal", "bloqueado", tuple(_fact_names(facts)), (), messages),
    )


def _produced_facts_from_steps(steps: tuple[ExecutionStep, ...]) -> tuple[str, ...]:
    produced = []
    for step in steps:
        if step.status in {"executado", "planejado"}:
            produced.extend(step.outputs)
    return tuple(dict.fromkeys(produced))


def _unresolved_goals(goals: tuple[str, ...], produced: tuple[str, ...], messages: tuple[str, ...]) -> tuple[str, ...]:
    if messages:
        return goals
    produced_text = " ".join(produced).lower()
    unresolved = []
    for goal in goals:
        normalized = goal.lower()
        if any(term in normalized for term in ("entalp", "temperatura", "titulo", "vazao", "potencia", "cop")):
            if not any(term in produced_text for term in ("states", "mass_flow", "compressor_power", "cop", "x4", "h1")):
                unresolved.append(goal)
    return tuple(unresolved)


def _dependencies_from_readiness(readiness: tuple[ToolReadiness, ...]) -> tuple[str, ...]:
    return tuple(
        f"{item.tool}: faltando {', '.join(item.missing)}"
        for item in readiness
        if item.missing
    )


def _fact_names(facts: tuple[ThermoFact, ...]) -> list[str]:
    return list(dict.fromkeys(fact.canonical_name for fact in facts))

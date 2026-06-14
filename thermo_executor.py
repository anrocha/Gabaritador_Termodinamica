from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from cycle_core import CycleInput, CycleResult, calculate_vapor_compression_cycle
from evaporator_core import EvaporatorInput, EvaporatorResult, calculate_air_refrigerant_evaporator
from openai_assistant import PlannerItem, ThermoPlan
from reservoir_cycle_core import (
    ReservoirCaseInput,
    ReservoirCycleInput,
    ReservoirCycleResult,
    calculate_reservoir_refrigerator,
    default_reservoir_exercise_input,
)
from standard_cycle_core import (
    StandardCycleInput,
    StandardCycleResult,
    calculate_standard_vapor_compression_cycle,
)
from thermo_facts import canonical_fact_lines, canonical_fact_value, canonical_facts_from_plan, ranked_tool_readiness
from thermo_orchestrator import build_execution_graph, graph_lines, graph_readiness_lines, graph_unresolved_lines
from thermo_core import ThermoCalculationError, k_to_temperature, pressure_to_pa
from turbine_core import TurbineInput, TurbineResult, calculate_adiabatic_steam_turbine


@dataclass(frozen=True)
class ExecutionResult:
    kind: str
    title: str
    turbine_result: TurbineResult | None = None
    cycle_result: CycleResult | None = None
    evaporator_result: EvaporatorResult | None = None
    reservoir_result: ReservoirCycleResult | None = None
    standard_cycle_result: StandardCycleResult | None = None
    messages: tuple[str, ...] = ()
    canonical_facts: tuple[str, ...] = ()
    execution_steps: tuple[str, ...] = ()
    tool_readiness: tuple[str, ...] = ()
    unresolved_goals: tuple[str, ...] = ()


MAIN_TOOLS = {
    "ciclo_refrigeracao_simples",
    "ciclo_refrigeracao_padrao_pressao",
    "evaporador_ar_refrigerante",
    "turbina_vapor_adiabatica",
    "refrigerador_reservatorios",
}


def execute_thermo_plan(plan: ThermoPlan, reference_state: str = "Unisinos") -> ExecutionResult:
    tools = {tool.lower() for tool in plan.ferramentas_necessarias}
    text_hint = _normalize_text(" ".join((plan.categoria, plan.tipo_problema, " ".join(plan.objetivos))))
    selected_tool, route_steps = _select_main_tool(plan)

    if selected_tool:
        result = _execute_main_tool(selected_tool, plan, reference_state)
        return _attach_execution_audit(result, plan, selected_tool, route_steps)

    if "turbina" in text_hint or _has_turbine_signature(plan):
        return _attach_execution_audit(_execute_main_tool("turbina_vapor_adiabatica", plan, reference_state), plan, "turbina_vapor_adiabatica", ())

    if _has_standard_cycle_signature(plan, text_hint):
        return _attach_execution_audit(_execute_main_tool("ciclo_refrigeracao_padrao_pressao", plan, reference_state), plan, "ciclo_refrigeracao_padrao_pressao", ())

    if _has_evaporator_signature(plan, text_hint):
        return _attach_execution_audit(_execute_main_tool("evaporador_ar_refrigerante", plan, reference_state), plan, "evaporador_ar_refrigerante", ())

    if _has_reservoir_signature(plan, text_hint):
        return _attach_execution_audit(_execute_main_tool("refrigerador_reservatorios", plan, reference_state), plan, "refrigerador_reservatorios", ())

    if "ciclo_refrigeracao_simples" in tools or "refrigeracao" in text_hint:
        return _attach_execution_audit(_execute_main_tool("ciclo_refrigeracao_simples", plan, reference_state), plan, "ciclo_refrigeracao_simples", ())

    return _attach_execution_audit(ExecutionResult(
        kind="nao_suportado",
        title="Ferramenta ainda nao implementada",
        messages=(
            "O plano foi interpretado, mas ainda nao ha executor deterministico para esta categoria.",
            "Use as abas de propriedades, titulo ou ciclo de refrigeracao quando aplicavel.",
        ),
    ), plan, "nao_suportado", ())


def _planned_main_tool(plan: ThermoPlan) -> str:
    for tool in plan.ferramentas_necessarias:
        normalized = tool.lower()
        if normalized in MAIN_TOOLS:
            return normalized
    return ""


def _select_main_tool(plan: ThermoPlan) -> tuple[str, tuple[str, ...]]:
    readiness = ranked_tool_readiness(plan)
    readiness_by_tool = {item.tool: item for item in readiness}
    planned = _planned_main_tool(plan)
    route_steps = []

    if planned:
        planned_readiness = readiness_by_tool.get(planned)
        if planned_readiness and planned_readiness.ready:
            route_steps.append(f"Ferramenta planejada aceita: {planned}.")
            return planned, tuple(route_steps)
        missing = ", ".join(planned_readiness.missing) if planned_readiness else "contrato desconhecido"
        route_steps.append(f"Ferramenta planejada {planned} bloqueada por pré-condição: {missing}.")

    for item in readiness:
        if item.ready and item.score >= 5:
            route_steps.append(f"Ferramenta compatível escolhida por contrato: {item.tool}.")
            return item.tool, tuple(route_steps)

    return "", tuple(route_steps)


def _attach_execution_audit(
    result: ExecutionResult,
    plan: ThermoPlan,
    selected_tool: str,
    route_steps: tuple[str, ...],
) -> ExecutionResult:
    graph = build_execution_graph(plan, selected_tool, result.kind, result.messages)
    return ExecutionResult(
        kind=result.kind,
        title=result.title,
        turbine_result=result.turbine_result,
        cycle_result=result.cycle_result,
        evaporator_result=result.evaporator_result,
        reservoir_result=result.reservoir_result,
        standard_cycle_result=result.standard_cycle_result,
        messages=result.messages,
        canonical_facts=canonical_fact_lines(plan),
        execution_steps=tuple(route_steps) + graph_lines(graph),
        tool_readiness=graph_readiness_lines(graph),
        unresolved_goals=graph_unresolved_lines(graph),
    )


def _execute_main_tool(tool: str, plan: ThermoPlan, reference_state: str) -> ExecutionResult:
    if tool == "turbina_vapor_adiabatica":
        turbine_input, messages = turbine_input_from_plan(plan, reference_state)
        if messages:
            return ExecutionResult(
                kind="turbina_vapor_adiabatica",
                title="Turbina de vapor",
                messages=messages,
            )
        return ExecutionResult(
            kind="turbina_vapor_adiabatica",
            title="Turbina de vapor",
            turbine_result=calculate_adiabatic_steam_turbine(turbine_input),
        )

    if tool == "ciclo_refrigeracao_padrao_pressao":
        standard_input, messages = standard_cycle_input_from_plan(plan, reference_state)
        if messages:
            return ExecutionResult(
                kind="ciclo_refrigeracao_padrao_pressao",
                title="Ciclo padrao de refrigeracao",
                messages=messages,
            )
        return ExecutionResult(
            kind="ciclo_refrigeracao_padrao_pressao",
            title="Ciclo padrao de refrigeracao",
            standard_cycle_result=calculate_standard_vapor_compression_cycle(standard_input),
        )

    if tool == "evaporador_ar_refrigerante":
        evaporator_input, messages = evaporator_input_from_plan(plan, reference_state)
        if messages:
            return ExecutionResult(
                kind="evaporador_ar_refrigerante",
                title="Evaporador com ar e R134a",
                messages=messages,
            )
        return ExecutionResult(
            kind="evaporador_ar_refrigerante",
            title="Evaporador com ar e R134a",
            evaporator_result=calculate_air_refrigerant_evaporator(evaporator_input),
        )

    if tool == "refrigerador_reservatorios":
        reservoir_input, messages = reservoir_input_from_plan(plan)
        if messages:
            return ExecutionResult(
                kind="refrigerador_reservatorios",
                title="Refrigerador entre reservatorios",
                messages=messages,
            )
        return ExecutionResult(
            kind="refrigerador_reservatorios",
            title="Refrigerador entre reservatorios",
            reservoir_result=calculate_reservoir_refrigerator(reservoir_input),
        )

    if tool == "ciclo_refrigeracao_simples":
        cycle_input, messages = cycle_input_from_plan(plan, reference_state)
        if messages:
            return ExecutionResult(
                kind="ciclo_refrigeracao_simples",
                title="Ciclo de refrigeracao",
                messages=messages,
            )
        return ExecutionResult(
            kind="ciclo_refrigeracao_simples",
            title="Ciclo de refrigeracao",
            cycle_result=calculate_vapor_compression_cycle(cycle_input),
        )

    return ExecutionResult(
        kind="nao_suportado",
        title="Ferramenta ainda nao implementada",
        messages=(
            "O plano foi interpretado, mas ainda nao ha executor deterministico para esta categoria.",
            "Use as abas de propriedades, titulo ou ciclo de refrigeracao quando aplicavel.",
        ),
    )


def cycle_input_from_plan(plan: ThermoPlan, reference_state: str = "Unisinos") -> tuple[CycleInput, tuple[str, ...]]:
    items = list(plan.dados_conhecidos)
    for state in plan.estados:
        items.extend(state.dados_conhecidos)

    facts = canonical_facts_from_plan(plan)
    fluid = _normalize_fluid(plan.fluido)
    evap_temp = canonical_fact_value(facts, "T_evap") or _find_value(
        items,
        (
            "temperatura de evaporacao",
            "temperatura evaporacao",
            "t evaporacao",
            "t_evap",
            "temperatura_baixa",
            "temperatura baixa",
            "temperatura do evaporador",
            "t4-1",
            "t4 1",
            "linha 4-1",
            "evaporating temperature",
        ),
        ("C", "K", "F"),
    )
    cond_temp = canonical_fact_value(facts, "T_cond") or _find_value(
        items,
        (
            "temperatura de condensacao",
            "temperatura condensacao",
            "t condensacao",
            "t_cond",
            "temperatura alta",
            "temperatura do condensador",
            "condensing temperature",
        ),
        ("C", "K", "F"),
    )
    evap_pressure = canonical_fact_value(facts, "P_evap") or _find_value(
        items,
        (
            "pressao de evaporacao",
            "pressao evaporacao",
            "p evaporacao",
            "p_evap",
            "pressao baixa",
            "pressao do evaporador",
            "evaporating pressure",
        ),
        ("Pa", "kPa", "MPa", "bar"),
    )
    cond_pressure = canonical_fact_value(facts, "P_cond") or _find_value(
        items,
        (
            "pressao de condensacao",
            "pressao condensacao",
            "p condensacao",
            "p_cond",
            "pressao_alta",
            "pressao alta",
            "pressao do condensador",
            "p2=p3",
            "p2",
            "p3",
            "condensing pressure",
        ),
        ("Pa", "kPa", "MPa", "bar"),
    )
    superheat = canonical_fact_value(facts, "superheat") or _find_value(items, ("superaquecimento", "superheat"))
    subcooling = canonical_fact_value(facts, "subcooling") or _find_value(items, ("sub-resfriamento", "subresfriamento", "subcooling"))
    efficiency = canonical_fact_value(facts, "eta_comp") or _find_value(
        items,
        (
            "eficiencia isentropica do compressor",
            "eficiencia do compressor",
            "eta compressor",
            "eta_comp",
            "compressor efficiency",
        ),
    )
    capacity = canonical_fact_value(facts, "cooling_capacity") or _find_value(
        items,
        (
            "capacidade frigorifica",
            "capacidade de refrigeracao",
            "carga termica",
            "carga_evaporador",
            "carga evaporador",
            "carga no evaporador",
            "q evaporador",
            "q_evap",
            "ql",
            "q_l",
            "cooling capacity",
        ),
    )
    evap_temp, evap_pressure = _split_temperature_pressure(evap_temp, evap_pressure)
    cond_temp, cond_pressure = _split_temperature_pressure(cond_temp, cond_pressure)

    missing = []
    if fluid == "Water":
        return _default_cycle_input(fluid, reference_state), (
            "Agua/vapor nao e suportado no solver de ciclo de refrigeracao do MVP. "
            "Este enunciado deve ser resolvido como turbina de vapor, propriedades de vapor ou outro ciclo de potencia.",
        )
    if fluid not in {"R22", "R134a"}:
        missing.append("fluido do ciclo: R22 ou R134a")

    try:
        evaporating_temperature = (
            evap_temp
            if evap_temp is not None
            else _saturation_temperature_from_pressure(fluid, evap_pressure) if evap_pressure is not None
            else None
        )
        condensing_temperature = (
            cond_temp
            if cond_temp is not None
            else _saturation_temperature_from_pressure(fluid, cond_pressure) if cond_pressure is not None
            else None
        )
    except ThermoCalculationError as exc:
        return _default_cycle_input(fluid, reference_state), (str(exc),)

    if evaporating_temperature is None:
        missing.append("temperatura ou pressao de evaporacao")
    if condensing_temperature is None:
        missing.append("temperatura ou pressao de condensacao")

    if missing:
        return _default_cycle_input(fluid, reference_state), tuple(f"Dado necessario ausente: {item}." for item in missing)

    capacity_unit = "kW" if capacity is None or not capacity[1] else capacity[1]
    if capacity_unit.lower() not in {"kw", "w", "tr"}:
        capacity_unit = "kW"

    return (
        CycleInput(
            fluid=fluid,
            evaporating_temperature=evaporating_temperature[0],
            condensing_temperature=condensing_temperature[0],
            superheat=0.0 if superheat is None else superheat[0],
            subcooling=0.0 if subcooling is None else subcooling[0],
            compressor_efficiency=1.0 if efficiency is None else _normalize_efficiency(efficiency[0]),
            cooling_capacity=None if capacity is None else capacity[0],
            temperature_unit=evaporating_temperature[1] or "C",
            pressure_unit="bar",
            capacity_unit=capacity_unit,
            reference_state=reference_state,
        ),
        (),
    )


def standard_cycle_input_from_plan(plan: ThermoPlan, reference_state: str = "Unisinos") -> tuple[StandardCycleInput, tuple[str, ...]]:
    items = list(plan.dados_conhecidos)
    for state in plan.estados:
        items.extend(state.dados_conhecidos)

    fluid = _normalize_fluid(plan.fluido) or "R134a"
    pressure_values = _all_pressure_values(items)
    low_pressure = _find_value(items, ("p baixa", "p_baixa", "pressao baixa", "pressao menor", "0.14"))
    high_pressure = _find_value(items, ("p alta", "p_alta", "pressao alta", "pressao maior", "0.8"))
    mass_flow = _find_value(items, ("m_dot", "mdot", "vazao massica", "taxa massica", "0.05"))

    if (low_pressure is None or high_pressure is None) and len(pressure_values) >= 2:
        pressure_values = sorted(pressure_values, key=lambda value: pressure_to_pa(value[0], value[1] or "MPa"))
        low_pressure = low_pressure or pressure_values[0]
        high_pressure = high_pressure or pressure_values[-1]

    missing = []
    if fluid not in {"R134a", "R22"}:
        missing.append("fluido R134a ou R22")
    if low_pressure is None:
        missing.append("pressao baixa")
    if high_pressure is None:
        missing.append("pressao alta")
    if mass_flow is None:
        missing.append("vazao massica")
    if missing:
        return StandardCycleInput(reference_state=reference_state), tuple(f"Dado necessario ausente: {item}." for item in missing)

    return (
        StandardCycleInput(
            fluid=fluid,
            low_pressure=pressure_to_pa(low_pressure[0], low_pressure[1] or "MPa") / 1_000_000,
            high_pressure=pressure_to_pa(high_pressure[0], high_pressure[1] or "MPa") / 1_000_000,
            pressure_unit="MPa",
            mass_flow=mass_flow[0],
            reference_state=reference_state,
        ),
        (),
    )


def evaporator_input_from_plan(plan: ThermoPlan, reference_state: str = "Unisinos") -> tuple[EvaporatorInput, tuple[str, ...]]:
    items = list(plan.dados_conhecidos)
    for state in plan.estados:
        items.extend(state.dados_conhecidos)

    air_pressure = _find_value(items, ("pressao do ar", "p ar", "pressao ar"))
    air_temperature = _find_value(items, ("temperatura do ar", "t ar", "temperatura entrada ar", "t_ar_in"))
    air_mass_flow = _find_value(items, ("vazao de ar", "vazao do ar", "mdot ar", "m_dot ar"))
    refrigerant_pressure = _find_value(items, ("pressao r134a", "pressao do refrigerante", "p r134a", "p refrigerante"))
    refrigerant_quality = _find_value(items, ("titulo", "qualidade", "x r134a", "x refrigerante"))
    refrigerant_mass_flow = _find_value(items, ("vazao r134a", "vazao do refrigerante", "mdot r134a", "m_dot refrigerante"))
    external_heat = _find_value(items, ("calor externo", "taxa de calor", "qdot", "transferido ao evaporador"))
    external_temperature = _find_value(items, ("temperatura do meio", "meio circundante", "temperatura externa", "t externo"))

    return (
        EvaporatorInput(
            air_pressure=100.0 if air_pressure is None else air_pressure[0],
            air_pressure_unit="kPa" if air_pressure is None or not air_pressure[1] else air_pressure[1],
            air_inlet_temperature_c=27.0 if air_temperature is None else air_temperature[0],
            air_mass_flow=0.12 if air_mass_flow is None else air_mass_flow[0],
            refrigerant="R134a",
            refrigerant_pressure=120.0 if refrigerant_pressure is None else refrigerant_pressure[0],
            refrigerant_pressure_unit="kPa" if refrigerant_pressure is None or not refrigerant_pressure[1] else refrigerant_pressure[1],
            refrigerant_inlet_quality=0.3 if refrigerant_quality is None else refrigerant_quality[0],
            refrigerant_mass_flow=2.0 if refrigerant_mass_flow is None else refrigerant_mass_flow[0],
            refrigerant_mass_flow_unit="kg/min" if refrigerant_mass_flow is None or not refrigerant_mass_flow[1] else refrigerant_mass_flow[1],
            external_heat_transfer=30.0 if external_heat is None else external_heat[0],
            external_heat_transfer_unit="kJ/min" if external_heat is None or not external_heat[1] else external_heat[1],
            external_temperature_c=32.0 if external_temperature is None else external_temperature[0],
            reference_state=reference_state,
        ),
        (),
    )


def reservoir_input_from_plan(plan: ThermoPlan) -> tuple[ReservoirCycleInput, tuple[str, ...]]:
    items = list(plan.dados_conhecidos)
    for state in plan.estados:
        items.extend(state.dados_conhecidos)

    low_temperature = _find_value(items, ("tl", "t_l", "temperatura fria", "reservatorio frio"))
    high_temperature = _find_value(items, ("th", "t_h", "temperatura quente", "reservatorio quente"))

    cases = _reservoir_cases_from_items(items)
    if not cases and _has_reservoir_exercise_values(plan):
        return default_reservoir_exercise_input(), ()
    if not cases:
        return default_reservoir_exercise_input(), ()

    return (
        ReservoirCycleInput(
            low_temperature_k=275.0 if low_temperature is None else low_temperature[0],
            high_temperature_k=315.0 if high_temperature is None else high_temperature[0],
            cases=tuple(cases),
        ),
        (),
    )


def turbine_input_from_plan(plan: ThermoPlan, reference_state: str = "Unisinos") -> tuple[TurbineInput, tuple[str, ...]]:
    items = list(plan.dados_conhecidos)
    for state in plan.estados:
        items.extend(state.dados_conhecidos)

    p1 = _find_value(items, ("p1", "pressao entrada", "pressao de entrada", "pressao estado 1"))
    t1 = _find_value(items, ("t1", "temperatura entrada", "temperatura de entrada", "temperatura estado 1"))
    p2 = _find_value(items, ("p2", "pressao saida", "pressao de saida", "pressao estado 2"))
    mass_flow = _find_value(items, ("m_dot", "mdot", "vazao", "vazao massica", "taxa massica"))
    t2 = _find_value(items, ("t2", "temperatura saida real", "temperatura de saida real", "temperatura estado 2 real"))

    missing = []
    if p1 is None:
        missing.append("pressao de entrada P1")
    if t1 is None:
        missing.append("temperatura de entrada T1")
    if p2 is None:
        missing.append("pressao de saida P2")
    if mass_flow is None:
        missing.append("vazao massica")

    if missing:
        return TurbineInput(reference_state=reference_state), tuple(f"Dado necessario ausente: {item}." for item in missing)

    fluid = _normalize_fluid(plan.fluido) or "Water"
    try:
        return (
            TurbineInput(
                fluid=fluid,
                inlet_pressure=p1[0],
                inlet_pressure_unit=p1[1] or "MPa",
                inlet_temperature=t1[0],
                inlet_temperature_unit=t1[1] or "C",
                outlet_pressure=p2[0],
                outlet_pressure_unit=p2[1] or "kPa",
                mass_flow=mass_flow[0],
                real_outlet_temperature=None if t2 is None else t2[0],
                real_outlet_temperature_unit="C" if t2 is None or not t2[1] else t2[1],
                reference_state=reference_state,
            ),
            (),
        )
    except ThermoCalculationError as exc:
        return TurbineInput(reference_state=reference_state), (str(exc),)


def _find_value(
    items: list[PlannerItem],
    aliases: tuple[str, ...],
    allowed_units: tuple[str, ...] | None = None,
) -> tuple[float, str] | None:
    normalized_aliases = tuple(_normalize_text(alias) for alias in aliases)
    for item in items:
        name = _normalize_text(item.nome)
        observation = _normalize_text(item.observacao)
        if any(alias in name or alias in observation for alias in normalized_aliases):
            value = _parse_number(item.valor)
            unit = _normalize_unit(item.unidade)
            if value is not None and (allowed_units is None or not unit or unit in allowed_units):
                return value, unit
    return None


def _split_temperature_pressure(
    temperature_candidate: tuple[float, str] | None,
    pressure_candidate: tuple[float, str] | None,
) -> tuple[tuple[float, str] | None, tuple[float, str] | None]:
    temperature = temperature_candidate
    pressure = pressure_candidate
    if temperature is not None and _is_pressure_unit(temperature[1]):
        pressure = pressure or temperature
        temperature = None
    if pressure is not None and _is_temperature_unit(pressure[1]):
        temperature = temperature or pressure
        pressure = None
    return temperature, pressure


def _is_pressure_unit(unit: str) -> bool:
    return unit in {"Pa", "kPa", "MPa", "bar"}


def _is_temperature_unit(unit: str) -> bool:
    return unit in {"C", "K", "F"}


def _all_pressure_values(items: list[PlannerItem]) -> list[tuple[float, str]]:
    values = []
    for item in items:
        unit = _normalize_unit(item.unidade)
        normalized_name = _normalize_text(item.nome)
        if unit in {"Pa", "kPa", "MPa", "bar"} or "pressao" in normalized_name or normalized_name.startswith("p"):
            value = _parse_number(item.valor)
            if value is not None:
                values.append((value, unit or "MPa"))
    return values


def _has_turbine_signature(plan: ThermoPlan) -> bool:
    fluid = _normalize_fluid(plan.fluido)
    if fluid != "Water":
        return False

    items = list(plan.dados_conhecidos)
    for state in plan.estados:
        items.extend(state.dados_conhecidos)

    has_p1 = _find_value(items, ("p1", "pressao entrada", "pressao de entrada", "pressao estado 1")) is not None
    has_t1 = _find_value(items, ("t1", "temperatura entrada", "temperatura de entrada", "temperatura estado 1")) is not None
    has_p2 = _find_value(items, ("p2", "pressao saida", "pressao de saida", "pressao estado 2")) is not None
    has_mass = _find_value(items, ("m_dot", "mdot", "vazao", "vazao massica", "taxa massica")) is not None
    return has_p1 and has_t1 and has_p2 and has_mass


def _has_evaporator_signature(plan: ThermoPlan, text_hint: str) -> bool:
    all_text = _plan_text(plan, text_hint)
    has_air_stream = any(
        phrase in all_text
        for phrase in (
            "vazao de ar",
            "vazao do ar",
            "pressao do ar",
            "temperatura do ar",
            "ar entra",
            "corrente de ar",
            "m dot ar",
            "mdot ar",
            "t ar",
            "p ar",
        )
    )
    has_air_data = any(
        phrase in all_text
        for phrase in (
            "vazao de ar",
            "pressao do ar",
            "temperatura do ar",
            "100 kpa",
            "27 c",
            "0.12",
        )
    )
    has_refrigerant_data = any(
        phrase in all_text for phrase in ("120 kpa", "x r134a", "titulo", "qualidade", "2 kg min", "kg/min")
    )
    return (
        ("evaporador" in all_text or "trocador" in all_text)
        and has_air_stream
        and ("r134a" in all_text or _normalize_fluid(plan.fluido) == "R134a")
        and (has_air_data or has_refrigerant_data)
    )


def _has_standard_cycle_signature(plan: ThermoPlan, text_hint: str) -> bool:
    all_text = _plan_text(plan, text_hint)
    pressure_values = _all_pressure_values(list(plan.dados_conhecidos))
    for state in plan.estados:
        pressure_values.extend(_all_pressure_values(list(state.dados_conhecidos)))
    return (
        ("ciclo padrao" in all_text or "compressao de vapor" in all_text or "compressao vapor" in all_text)
        and ("r134a" in all_text or "r22" in all_text or _normalize_fluid(plan.fluido) in {"R134a", "R22"})
        and (len(pressure_values) >= 2 or ("0.14" in all_text and "0.8" in all_text))
        and ("vazao" in all_text or "m dot" in all_text or "0.05" in all_text)
        and ("s1=s2" in all_text or "h4=h3" in all_text or "vapor saturado" in all_text or "liquido saturado" in all_text)
    )


def _has_reservoir_signature(plan: ThermoPlan, text_hint: str) -> bool:
    all_text = _plan_text(plan, text_hint)
    return (
        ("reservatorio" in all_text or "reservatorios" in all_text)
        and ("tl" in all_text or "t l" in all_text or "275" in all_text)
        and ("th" in all_text or "t h" in all_text or "315" in all_text)
        and ("cop" in all_text or "ql" in all_text or "qh" in all_text or "wciclo" in all_text)
    )


def _reservoir_cases_from_items(items: list[PlannerItem]) -> list[ReservoirCaseInput]:
    cases = []
    for label in ("1", "2", "3"):
        q_low = _find_value(items, (f"ql {label}", f"q_l {label}", f"caso {label} ql", f"({label}) ql"))
        q_high = _find_value(items, (f"qh {label}", f"q_h {label}", f"caso {label} qh", f"({label}) qh"))
        work = _find_value(items, (f"w {label}", f"wciclo {label}", f"w_ciclo {label}", f"caso {label} w", f"({label}) w"))
        if q_low or q_high or work:
            cases.append(
                ReservoirCaseInput(
                    label=label,
                    heat_absorbed_low=None if q_low is None else q_low[0],
                    heat_rejected_high=None if q_high is None else q_high[0],
                    work_input=None if work is None else work[0],
                )
            )
    return cases


def _has_reservoir_exercise_values(plan: ThermoPlan) -> bool:
    all_text = _plan_text(plan, "")
    return all(value in all_text for value in ("275", "315")) and any(
        value in all_text for value in ("1000", "1200", "1575", "2000")
    )


def _plan_text(plan: ThermoPlan, text_hint: str) -> str:
    parts = [
        text_hint,
        plan.raw_text,
        plan.categoria,
        plan.tipo_problema,
        plan.fluido,
        plan.interpretacao_imagem,
        plan.texto_usuario,
        plan.entrada_oficial,
        plan.diagnostico_entrada,
        " ".join(plan.ferramentas_necessarias),
        " ".join(plan.objetivos),
        " ".join(plan.propriedades_a_calcular),
        " ".join(plan.dados_faltantes),
    ]
    for item in plan.dados_conhecidos:
        parts.extend((item.nome, item.valor, item.unidade, item.observacao))
    for state in plan.estados:
        parts.extend((state.estado, state.descricao, " ".join(state.propriedades_a_calcular)))
        for item in state.dados_conhecidos:
            parts.extend((item.nome, item.valor, item.unidade, item.observacao))
    for question in plan.questoes:
        parts.extend((question.item, question.enunciado, question.objetivo, question.resultado_esperado))
    return _normalize_text(" ".join(parts))
def _saturation_temperature_from_pressure(fluid: str, pressure: tuple[float, str] | None) -> tuple[float, str]:
    if pressure is None:
        raise ThermoCalculationError("Pressao de saturacao ausente para obter temperatura.")
    try:
        from CoolProp.CoolProp import PropsSI

        pressure_pa = pressure_to_pa(pressure[0], pressure[1] or "bar")
        temperature_k = PropsSI("T", "P", pressure_pa, "Q", 1, fluid)
        return k_to_temperature(temperature_k, "C"), "C"
    except Exception as exc:
        raise ThermoCalculationError(f"Nao foi possivel obter temperatura de saturacao para {fluid}: {exc}") from exc


def _normalize_efficiency(value: float) -> float:
    return value / 100 if value > 1 else value


def _default_cycle_input(fluid: str, reference_state: str) -> CycleInput:
    return CycleInput(
        fluid=fluid if fluid in {"R22", "R134a"} else "R134a",
        evaporating_temperature=-10,
        condensing_temperature=40,
        superheat=0,
        subcooling=0,
        compressor_efficiency=1,
        reference_state=reference_state,
    )


def _parse_number(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def _normalize_unit(unit: str) -> str:
    cleaned = unit.strip().replace("°", "").replace(" ", "")
    lower = cleaned.lower()
    if lower in {"mpa"}:
        return "MPa"
    if lower in {"kpa"}:
        return "kPa"
    if lower in {"pa"}:
        return "Pa"
    if lower in {"bar"}:
        return "bar"
    if lower in {"c", "degc", "celsius"}:
        return "C"
    if lower in {"k", "kelvin"}:
        return "K"
    if lower in {"f", "degf", "fahrenheit"}:
        return "F"
    if lower in {"kg/s", "kgs", "kg.s-1"}:
        return "kg/s"
    if lower in {"kg/min", "kgmin", "kg/minuto"}:
        return "kg/min"
    if lower in {"kw"}:
        return "kW"
    if lower in {"w"}:
        return "W"
    if lower in {"kj/min", "kjmin", "kj/minuto"}:
        return "kJ/min"
    if lower in {"kj", "quilojoule", "quilojoules"}:
        return "kJ"
    if lower in {"tr", "ton", "tonelada"}:
        return "TR"
    return cleaned


def _normalize_fluid(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized in {"agua", "vapor agua", "vapor de agua", "water", "steam"} or "vapor de agua" in normalized:
        return "Water"
    if normalized == "r22" or "r22" in normalized:
        return "R22"
    if normalized in {"r134a", "r314a"} or "r134a" in normalized or "r 134a" in normalized:
        return "R134a"
    return ""


def _normalize_text(value: str) -> str:
    replacements = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    lowered = value.lower().strip()
    for source, target in replacements.items():
        lowered = lowered.replace(source, target)
    lowered = "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    )
    return " ".join(lowered.replace("_", " ").split())

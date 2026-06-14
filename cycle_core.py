from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thermo_core import (
    ThermoCalculationError,
    apply_reference_state,
    k_to_temperature,
    pa_to_pressure,
    temperature_to_k,
)


CYCLE_FLUIDS = ("R22", "R134a")


@dataclass(frozen=True)
class CycleInput:
    fluid: str
    evaporating_temperature: float
    condensing_temperature: float
    superheat: float
    subcooling: float
    compressor_efficiency: float
    cooling_capacity: float | None = None
    temperature_unit: str = "C"
    pressure_unit: str = "bar"
    capacity_unit: str = "kW"
    reference_state: str = "Unisinos"


@dataclass(frozen=True)
class CycleState:
    point: str
    description: str
    temperature: float
    pressure: float
    enthalpy: float
    entropy: float
    specific_volume: float
    quality: float | None
    region: str
    origin: str
    formula: str


@dataclass(frozen=True)
class CycleMetric:
    label: str
    value: float | None
    unit: str
    formula: str


@dataclass(frozen=True)
class CycleResult:
    input: CycleInput
    reference_state: str
    states: tuple[CycleState, ...]
    metrics: tuple[CycleMetric, ...]
    validations: tuple[str, ...]
    assumptions: tuple[str, ...]


def calculate_vapor_compression_cycle(cycle_input: CycleInput) -> CycleResult:
    _validate_cycle_input(cycle_input)

    try:
        from CoolProp.CoolProp import PropsSI

        reference_label = apply_reference_state(cycle_input.fluid, cycle_input.reference_state)
        evaporating_temperature_k = temperature_to_k(
            cycle_input.evaporating_temperature,
            cycle_input.temperature_unit,
        )
        condensing_temperature_k = temperature_to_k(
            cycle_input.condensing_temperature,
            cycle_input.temperature_unit,
        )

        if condensing_temperature_k <= evaporating_temperature_k:
            raise ThermoCalculationError("A temperatura de condensacao deve ser maior que a de evaporacao.")

        evaporating_pressure_pa = PropsSI("P", "T", evaporating_temperature_k, "Q", 1, cycle_input.fluid)
        condensing_pressure_pa = PropsSI("P", "T", condensing_temperature_k, "Q", 0, cycle_input.fluid)

        t1_k = evaporating_temperature_k + cycle_input.superheat
        p1_pa = evaporating_pressure_pa
        if cycle_input.superheat == 0:
            h1 = PropsSI("H", "P", p1_pa, "Q", 1, cycle_input.fluid)
            s1 = PropsSI("S", "P", p1_pa, "Q", 1, cycle_input.fluid)
        else:
            h1 = PropsSI("H", "T", t1_k, "P", p1_pa, cycle_input.fluid)
            s1 = PropsSI("S", "T", t1_k, "P", p1_pa, cycle_input.fluid)

        p2_pa = condensing_pressure_pa
        s2s = s1
        h2s = PropsSI("H", "P", p2_pa, "S", s2s, cycle_input.fluid)
        t2s_k = PropsSI("T", "P", p2_pa, "S", s2s, cycle_input.fluid)

        h2 = h1 + (h2s - h1) / cycle_input.compressor_efficiency
        t2_k = PropsSI("T", "P", p2_pa, "H", h2, cycle_input.fluid)
        s2 = PropsSI("S", "P", p2_pa, "H", h2, cycle_input.fluid)

        t3_k = condensing_temperature_k - cycle_input.subcooling
        p3_pa = condensing_pressure_pa
        if cycle_input.subcooling == 0:
            h3 = PropsSI("H", "P", p3_pa, "Q", 0, cycle_input.fluid)
            s3 = PropsSI("S", "P", p3_pa, "Q", 0, cycle_input.fluid)
        else:
            h3 = PropsSI("H", "T", t3_k, "P", p3_pa, cycle_input.fluid)
            s3 = PropsSI("S", "T", t3_k, "P", p3_pa, cycle_input.fluid)

        p4_pa = evaporating_pressure_pa
        h4 = h3
        t4_k = PropsSI("T", "P", p4_pa, "H", h4, cycle_input.fluid)
        s4 = PropsSI("S", "P", p4_pa, "H", h4, cycle_input.fluid)

        state_specs = (
            (
                "1",
                "Entrada do compressor",
                t1_k,
                p1_pa,
                h1,
                s1,
                "Vapor saturado na saida do evaporador"
                if cycle_input.superheat == 0
                else "Vapor superaquecido apos o evaporador",
                "P1 = P_sat(T_evap); x1 = 1"
                if cycle_input.superheat == 0
                else "T1 = T_evap + superaquecimento; P1 = P_sat(T_evap)",
            ),
            (
                "2s",
                "Saida isentropica do compressor",
                t2s_k,
                p2_pa,
                h2s,
                s2s,
                "Compressao ideal ate a pressao de condensacao",
                "s2s = s1; P2s = P_cond; h2s = h(P2s, s1)",
            ),
            (
                "2",
                "Saida real do compressor",
                t2_k,
                p2_pa,
                h2,
                s2,
                "Compressao real com eficiencia isentropica",
                "h2 = h1 + (h2s - h1) / eta_comp",
            ),
            (
                "3",
                "Saida do condensador",
                t3_k,
                p3_pa,
                h3,
                s3,
                "Liquido saturado na saida do condensador"
                if cycle_input.subcooling == 0
                else "Liquido sub-resfriado na pressao de condensacao",
                "P3 = P_sat(T_cond); x3 = 0"
                if cycle_input.subcooling == 0
                else "T3 = T_cond - sub-resfriamento; P3 = P_sat(T_cond)",
            ),
            (
                "4",
                "Saida da valvula de expansao",
                t4_k,
                p4_pa,
                h4,
                s4,
                "Expansao isoentalpica ate a pressao de evaporacao",
                "h4 = h3; P4 = P_evap",
            ),
        )

        states = tuple(
            _build_state(cycle_input, *state_spec)
            for state_spec in state_specs
        )

        q_evap = (h1 - h4) / 1000
        w_comp = (h2 - h1) / 1000
        q_cond = (h2 - h3) / 1000
        cop = q_evap / w_comp
        cop_carnot = evaporating_temperature_k / (condensing_temperature_k - evaporating_temperature_k)
        capacity_kw = _capacity_to_kw(cycle_input.cooling_capacity, cycle_input.capacity_unit)
        mass_flow = None if capacity_kw is None else capacity_kw / q_evap
        compressor_power = None if mass_flow is None else mass_flow * w_comp
        condenser_heat = None if mass_flow is None else mass_flow * q_cond

        metrics = (
            CycleMetric("Calor absorvido no evaporador", q_evap, "kJ/kg", "q_evap = h1 - h4"),
            CycleMetric("Trabalho especifico do compressor", w_comp, "kJ/kg", "w_comp = h2 - h1"),
            CycleMetric("Calor rejeitado no condensador", q_cond, "kJ/kg", "q_cond = h2 - h3"),
            CycleMetric("COP real de refrigeracao", cop, "-", "COP = q_evap / w_comp"),
            CycleMetric("COP de Carnot", cop_carnot, "-", "COP_Carnot = T_evap / (T_cond - T_evap)"),
            CycleMetric("Vazao massica", mass_flow, "kg/s", "m_dot = Q_evap / q_evap"),
            CycleMetric("Potencia do compressor", compressor_power, "kW", "W_dot = m_dot * w_comp"),
            CycleMetric("Calor no condensador", condenser_heat, "kW", "Q_cond = m_dot * q_cond"),
        )

        return CycleResult(
            input=cycle_input,
            reference_state=reference_label,
            states=states,
            metrics=metrics,
            validations=_validate_cycle_result(cop, cop_carnot, h1, h2, h3, h4, states),
            assumptions=(
                "Regime permanente.",
                "Variacoes de energia cinetica e potencial desprezadas.",
                "Compressor adiabatico com eficiencia isentropica informada.",
                "Valvula de expansao isoentalpica.",
                "Perdas de pressao nos trocadores desprezadas no MVP.",
            ),
        )
    except Exception as exc:
        if isinstance(exc, ThermoCalculationError):
            raise
        raise ThermoCalculationError(str(exc)) from exc


def cycle_state_rows(result: CycleResult) -> list[dict[str, Any]]:
    return [
        {
            "Estado": state.point,
            "Descricao": state.description,
            f"T [{result.input.temperature_unit}]": round(state.temperature, 5),
            f"P [{result.input.pressure_unit}]": round(state.pressure, 6),
            "h [kJ/kg]": round(state.enthalpy, 5),
            "s [kJ/(kg.K)]": round(state.entropy, 6),
            "v [m3/kg]": round(state.specific_volume, 8),
            "x": "" if state.quality is None else round(state.quality, 6),
            "Regiao": state.region,
        }
        for state in result.states
    ]


def cycle_metric_rows(result: CycleResult) -> list[dict[str, Any]]:
    return [
        {
            "Grandeza": metric.label,
            "Valor": "" if metric.value is None else round(metric.value, 6),
            "Unidade": metric.unit,
            "Formula": metric.formula,
        }
        for metric in result.metrics
    ]


def _build_state(
    cycle_input: CycleInput,
    point: str,
    description: str,
    temperature_k: float,
    pressure_pa: float,
    enthalpy_jkg: float,
    entropy_jkgk: float,
    origin: str,
    formula: str,
) -> CycleState:
    from CoolProp.CoolProp import PropsSI

    density = PropsSI("D", "P", pressure_pa, "H", enthalpy_jkg, cycle_input.fluid)
    quality_raw = PropsSI("Q", "P", pressure_pa, "H", enthalpy_jkg, cycle_input.fluid)
    quality = quality_raw if 0 <= quality_raw <= 1 else None

    return CycleState(
        point=point,
        description=description,
        temperature=k_to_temperature(temperature_k, cycle_input.temperature_unit),
        pressure=pa_to_pressure(pressure_pa, cycle_input.pressure_unit),
        enthalpy=enthalpy_jkg / 1000,
        entropy=entropy_jkgk / 1000,
        specific_volume=1 / density,
        quality=quality,
        region=_region_label(quality, point, origin),
        origin=origin,
        formula=formula,
    )


def _region_label(quality: float | None, point: str, origin: str) -> str:
    if quality is not None:
        if quality == 0:
            return "liquido saturado"
        if quality == 1:
            return "vapor saturado"
        return "mistura liquido-vapor"
    if "superaquecido" in origin.lower() or point in {"1", "2", "2s"}:
        return "vapor superaquecido"
    if "sub-resfriado" in origin.lower() or point == "3":
        return "liquido sub-resfriado"
    return "fora da regiao bifasica"


def _validate_cycle_input(cycle_input: CycleInput) -> None:
    if cycle_input.fluid not in CYCLE_FLUIDS:
        raise ThermoCalculationError(
            "No MVP de ciclos de refrigeracao, use R22 ou R134a. "
            "Agua/vapor deve ser resolvido nas abas de propriedades, titulo ou turbina."
        )
    if cycle_input.superheat < 0:
        raise ThermoCalculationError("O superaquecimento nao pode ser negativo.")
    if cycle_input.subcooling < 0:
        raise ThermoCalculationError("O sub-resfriamento nao pode ser negativo.")
    if not 0 < cycle_input.compressor_efficiency <= 1:
        raise ThermoCalculationError("A eficiencia isentropica deve estar entre 0 e 1.")
    if cycle_input.cooling_capacity is not None and cycle_input.cooling_capacity <= 0:
        raise ThermoCalculationError("A capacidade frigorifica deve ser positiva.")


def _validate_cycle_result(
    cop: float,
    cop_carnot: float,
    h1: float,
    h2: float,
    h3: float,
    h4: float,
    states: tuple[CycleState, ...],
) -> tuple[str, ...]:
    validations = []
    validations.append("OK: h2 > h1 no compressor." if h2 > h1 else "Atencao: h2 nao ficou maior que h1.")
    validations.append("OK: h4 = h3 na valvula de expansao." if abs(h4 - h3) < 1e-6 else "Atencao: h4 difere de h3.")
    validations.append("OK: COP real menor que COP de Carnot." if cop < cop_carnot else "Atencao: COP real maior ou igual ao de Carnot.")
    for state in states:
        if state.quality is not None and not 0 <= state.quality <= 1:
            validations.append(f"Atencao: titulo fora da faixa no estado {state.point}.")
    return tuple(validations)


def _capacity_to_kw(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    normalized_unit = unit.strip().lower()
    if normalized_unit == "kw":
        return value
    if normalized_unit == "w":
        return value / 1000
    if normalized_unit in {"tr", "ton", "tonelada"}:
        return value * 3.5168525
    raise ThermoCalculationError(f"Unidade de capacidade nao suportada: {unit}.")

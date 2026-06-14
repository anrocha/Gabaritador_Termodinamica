from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thermo_core import (
    ThermoCalculationError,
    apply_reference_state,
    k_to_temperature,
    pa_to_pressure,
    pressure_to_pa,
    temperature_to_k,
)


@dataclass(frozen=True)
class TurbineInput:
    fluid: str = "Water"
    inlet_pressure: float = 1.0
    inlet_pressure_unit: str = "MPa"
    inlet_temperature: float = 500.0
    inlet_temperature_unit: str = "C"
    outlet_pressure: float = 15.0
    outlet_pressure_unit: str = "kPa"
    mass_flow: float = 1.5
    real_outlet_temperature: float | None = None
    real_outlet_temperature_unit: str = "C"
    reference_state: str = "Unisinos"


@dataclass(frozen=True)
class TurbineState:
    point: str
    description: str
    temperature_c: float
    pressure_kpa: float
    enthalpy: float
    entropy: float
    specific_volume: float
    quality: float | None
    region: str
    formula: str
    property_source: str


@dataclass(frozen=True)
class TurbineMetric:
    label: str
    value: float | None
    unit: str
    formula: str


@dataclass(frozen=True)
class TurbineResult:
    input: TurbineInput
    reference_state: str
    states: tuple[TurbineState, ...]
    metrics: tuple[TurbineMetric, ...]
    assumptions: tuple[str, ...]
    validations: tuple[str, ...]
    conversion_notes: tuple[str, ...]


def calculate_adiabatic_steam_turbine(turbine_input: TurbineInput) -> TurbineResult:
    _validate_turbine_input(turbine_input)

    try:
        from CoolProp.CoolProp import PropsSI

        reference_label = apply_reference_state(turbine_input.fluid, turbine_input.reference_state)
        p1 = pressure_to_pa(turbine_input.inlet_pressure, turbine_input.inlet_pressure_unit)
        t1 = temperature_to_k(turbine_input.inlet_temperature, turbine_input.inlet_temperature_unit)
        p2 = pressure_to_pa(turbine_input.outlet_pressure, turbine_input.outlet_pressure_unit)

        h1 = PropsSI("H", "P", p1, "T", t1, turbine_input.fluid)
        s1 = PropsSI("S", "P", p1, "T", t1, turbine_input.fluid)

        s2s = s1
        h2s = PropsSI("H", "P", p2, "S", s2s, turbine_input.fluid)
        t2s = PropsSI("T", "P", p2, "S", s2s, turbine_input.fluid)

        state_1 = _build_turbine_state(
            turbine_input.fluid,
            "1",
            "Entrada da turbina",
            p1,
            t1,
            h1,
            s1,
            "Estado 1 por P1 e T1; propriedades h1 e s1 obtidas no CoolProp.",
            "CoolProp PropsSI: h1 = h(P1,T1), s1 = s(P1,T1), v1 = 1/rho(P1,T1).",
        )
        state_2s = _build_turbine_state(
            turbine_input.fluid,
            "2s",
            "Saida ideal isentropica",
            p2,
            t2s,
            h2s,
            s2s,
            "Estado 2s por P2 e s2s = s1; expansao ideal isentropica.",
            "CoolProp PropsSI: h2s = h(P2,s1), T2s = T(P2,s1), x2s = Q(P2,h2s).",
        )

        states: list[TurbineState] = [state_1, state_2s]
        maximum_specific_work = (h1 - h2s) / 1000
        maximum_power = turbine_input.mass_flow * maximum_specific_work
        real_specific_work = None
        real_power = None
        isentropic_efficiency = None

        if turbine_input.real_outlet_temperature is not None:
            t2 = temperature_to_k(turbine_input.real_outlet_temperature, turbine_input.real_outlet_temperature_unit)
            h2 = PropsSI("H", "P", p2, "T", t2, turbine_input.fluid)
            s2 = PropsSI("S", "P", p2, "T", t2, turbine_input.fluid)
            state_2 = _build_turbine_state(
                turbine_input.fluid,
                "2",
                "Saida real da turbina",
                p2,
                t2,
                h2,
                s2,
                "Estado 2 real por P2 e T2; propriedades h2 e s2 obtidas no CoolProp.",
                "CoolProp PropsSI: h2 = h(P2,T2), s2 = s(P2,T2), v2 = 1/rho(P2,T2).",
            )
            states.append(state_2)
            real_specific_work = (h1 - h2) / 1000
            real_power = turbine_input.mass_flow * real_specific_work
            isentropic_efficiency = real_specific_work / maximum_specific_work

        metrics = (
            TurbineMetric("Trabalho especifico maximo", maximum_specific_work, "kJ/kg", "w_max = h1 - h2s"),
            TurbineMetric("Potencia maxima", maximum_power, "kW", "W_dot_max = m_dot * (h1 - h2s)"),
            TurbineMetric("Trabalho especifico real", real_specific_work, "kJ/kg", "w_real = h1 - h2"),
            TurbineMetric("Potencia real", real_power, "kW", "W_dot_real = m_dot * (h1 - h2)"),
            TurbineMetric("Eficiencia isentropica da turbina", isentropic_efficiency, "-", "eta_t = (h1 - h2) / (h1 - h2s)"),
        )

        return TurbineResult(
            input=turbine_input,
            reference_state=reference_label,
            states=tuple(states),
            metrics=metrics,
            assumptions=(
                "Regime permanente.",
                "Turbina isolada, sem transferencia de calor.",
                "Variacoes de energia cinetica e potencial desprezadas.",
                "Para a potencia maxima, a expansao e considerada isentropica.",
            ),
            validations=_validate_turbine_result(states, maximum_power, isentropic_efficiency),
            conversion_notes=(
                "1 J/kg = 1 m2/s2.",
                "1 kJ/kg = 1000 J/kg.",
                "kg/s * kJ/kg = kJ/s = kW.",
                "1 MPa = 1000 kPa = 1.000.000 Pa.",
            ),
        )
    except Exception as exc:
        if isinstance(exc, ThermoCalculationError):
            raise
        raise ThermoCalculationError(str(exc)) from exc


def turbine_state_rows(result: TurbineResult) -> list[dict[str, Any]]:
    return [
        {
            "Estado": state.point,
            "Descricao": state.description,
            "T [C]": round(state.temperature_c, 5),
            "P [kPa]": round(state.pressure_kpa, 5),
            "h [kJ/kg]": round(state.enthalpy, 5),
            "s [kJ/(kg.K)]": round(state.entropy, 6),
            "v [m3/kg]": round(state.specific_volume, 8),
            "x": "" if state.quality is None else round(state.quality, 6),
            "Regiao": state.region,
            "Origem": state.property_source,
        }
        for state in result.states
    ]


def turbine_metric_rows(result: TurbineResult) -> list[dict[str, Any]]:
    return [
        {
            "Grandeza": metric.label,
            "Valor": "" if metric.value is None else round(metric.value, 6),
            "Unidade": metric.unit,
            "Formula": metric.formula,
        }
        for metric in result.metrics
    ]


def _build_turbine_state(
    fluid: str,
    point: str,
    description: str,
    pressure_pa: float,
    temperature_k: float,
    enthalpy_jkg: float,
    entropy_jkgk: float,
    formula: str,
    property_source: str,
) -> TurbineState:
    from CoolProp.CoolProp import PhaseSI, PropsSI

    density = PropsSI("D", "P", pressure_pa, "H", enthalpy_jkg, fluid)
    quality_raw = PropsSI("Q", "P", pressure_pa, "H", enthalpy_jkg, fluid)
    quality = quality_raw if 0 <= quality_raw <= 1 else None
    phase = PhaseSI("P", pressure_pa, "H", enthalpy_jkg, fluid)
    return TurbineState(
        point=point,
        description=description,
        temperature_c=k_to_temperature(temperature_k, "C"),
        pressure_kpa=pa_to_pressure(pressure_pa, "kPa"),
        enthalpy=enthalpy_jkg / 1000,
        entropy=entropy_jkgk / 1000,
        specific_volume=1 / density,
        quality=quality,
        region=_region_label(quality, phase),
        formula=formula,
        property_source=property_source,
    )


def _region_label(quality: float | None, phase: str) -> str:
    if quality is not None:
        if quality == 0:
            return "liquido saturado"
        if quality == 1:
            return "vapor saturado"
        return "mistura liquido-vapor"
    normalized = phase.replace("phase_", "").lower()
    if normalized == "gas":
        return "vapor superaquecido"
    if normalized == "supercritical_gas":
        return "vapor superaquecido"
    if normalized == "liquid":
        return "liquido comprimido/sub-resfriado"
    if normalized == "supercritical_liquid":
        return "liquido comprimido/sub-resfriado"
    if normalized == "supercritical":
        return "supercritico"
    return normalized


def _validate_turbine_input(turbine_input: TurbineInput) -> None:
    if turbine_input.fluid != "Water":
        raise ThermoCalculationError("No MVP de turbina, use Water para agua/vapor.")
    if turbine_input.mass_flow <= 0:
        raise ThermoCalculationError("A vazao massica deve ser positiva.")
    if pressure_to_pa(turbine_input.outlet_pressure, turbine_input.outlet_pressure_unit) >= pressure_to_pa(
        turbine_input.inlet_pressure,
        turbine_input.inlet_pressure_unit,
    ):
        raise ThermoCalculationError("A pressao de saida deve ser menor que a pressao de entrada na turbina.")


def _validate_turbine_result(
    states: tuple[TurbineState, ...],
    maximum_power: float,
    isentropic_efficiency: float | None,
) -> tuple[str, ...]:
    validations = ["OK: potencia maxima positiva." if maximum_power > 0 else "Atencao: potencia maxima nao positiva."]
    state_by_point = {state.point: state for state in states}
    if "2" in state_by_point:
        validations.append(
            "OK: entropia real de saida maior que a ideal."
            if state_by_point["2"].entropy >= state_by_point["2s"].entropy
            else "Atencao: entropia real menor que a ideal."
        )
    if isentropic_efficiency is not None:
        validations.append(
            "OK: eficiencia isentropica entre 0 e 1."
            if 0 <= isentropic_efficiency <= 1
            else "Atencao: eficiencia isentropica fora da faixa 0 a 1."
        )
    return tuple(validations)

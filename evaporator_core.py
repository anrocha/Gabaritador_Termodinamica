from __future__ import annotations

import math
from dataclasses import dataclass

from thermo_core import ThermoCalculationError, apply_reference_state, pressure_to_pa


AIR_CP = 1.005
AIR_R = 0.287


@dataclass(frozen=True)
class EvaporatorInput:
    air_pressure: float = 100.0
    air_pressure_unit: str = "kPa"
    air_inlet_temperature_c: float = 27.0
    air_mass_flow: float = 0.12
    refrigerant: str = "R134a"
    refrigerant_pressure: float = 120.0
    refrigerant_pressure_unit: str = "kPa"
    refrigerant_inlet_quality: float = 0.3
    refrigerant_mass_flow: float = 2.0
    refrigerant_mass_flow_unit: str = "kg/min"
    external_heat_transfer: float = 30.0
    external_heat_transfer_unit: str = "kJ/min"
    external_temperature_c: float = 32.0
    reference_state: str = "Unisinos"


@dataclass(frozen=True)
class EvaporatorState:
    stream: str
    point: str
    description: str
    temperature_c: float
    pressure_kpa: float
    enthalpy: float | None
    entropy: float
    quality: float | None
    formula: str
    property_source: str


@dataclass(frozen=True)
class EvaporatorCase:
    label: str
    description: str
    heat_transfer_kw: float
    heat_boundary_temperature_k: float | None
    air_outlet_temperature_c: float
    air_entropy_change_rate: float
    refrigerant_entropy_change_rate: float
    heat_entropy_transfer_rate: float
    entropy_generation_rate: float
    formula: str


@dataclass(frozen=True)
class EvaporatorResult:
    input: EvaporatorInput
    reference_state: str
    refrigerant_delta_h: float
    refrigerant_delta_s: float
    states: tuple[EvaporatorState, ...]
    cases: tuple[EvaporatorCase, ...]
    assumptions: tuple[str, ...]
    conversion_notes: tuple[str, ...]


def calculate_air_refrigerant_evaporator(evaporator_input: EvaporatorInput) -> EvaporatorResult:
    _validate_input(evaporator_input)

    try:
        from CoolProp.CoolProp import PropsSI

        reference_label = apply_reference_state(evaporator_input.refrigerant, evaporator_input.reference_state)
        refrigerant_pressure_pa = pressure_to_pa(
            evaporator_input.refrigerant_pressure,
            evaporator_input.refrigerant_pressure_unit,
        )
        refrigerant_pressure_kpa = pressure_to_pa(
            evaporator_input.refrigerant_pressure,
            evaporator_input.refrigerant_pressure_unit,
        ) / 1000
        air_pressure_kpa = pressure_to_pa(evaporator_input.air_pressure, evaporator_input.air_pressure_unit) / 1000

        inlet_quality = evaporator_input.refrigerant_inlet_quality
        h_ref_in = PropsSI("H", "P", refrigerant_pressure_pa, "Q", inlet_quality, evaporator_input.refrigerant) / 1000
        s_ref_in = PropsSI("S", "P", refrigerant_pressure_pa, "Q", inlet_quality, evaporator_input.refrigerant) / 1000
        t_ref_in = PropsSI("T", "P", refrigerant_pressure_pa, "Q", inlet_quality, evaporator_input.refrigerant) - 273.15

        h_ref_out = PropsSI("H", "P", refrigerant_pressure_pa, "Q", 1, evaporator_input.refrigerant) / 1000
        s_ref_out = PropsSI("S", "P", refrigerant_pressure_pa, "Q", 1, evaporator_input.refrigerant) / 1000
        t_ref_out = PropsSI("T", "P", refrigerant_pressure_pa, "Q", 1, evaporator_input.refrigerant) - 273.15

        refrigerant_mass_flow = _mass_flow_to_kg_s(
            evaporator_input.refrigerant_mass_flow,
            evaporator_input.refrigerant_mass_flow_unit,
        )
        external_heat_kw = _heat_rate_to_kw(
            evaporator_input.external_heat_transfer,
            evaporator_input.external_heat_transfer_unit,
        )

        delta_h_ref = h_ref_out - h_ref_in
        delta_s_ref = s_ref_out - s_ref_in

        isolated_case = _build_case(
            "b1",
            "Superficies externas isoladas",
            evaporator_input,
            refrigerant_mass_flow,
            delta_h_ref,
            delta_s_ref,
            0.0,
            None,
        )
        heat_transfer_case = _build_case(
            "b2",
            "Calor recebido do meio a 32 °C",
            evaporator_input,
            refrigerant_mass_flow,
            delta_h_ref,
            delta_s_ref,
            external_heat_kw,
            evaporator_input.external_temperature_c + 273.15,
        )

        states = (
            EvaporatorState(
                "Ar",
                "a1",
                "Entrada do ar no evaporador",
                evaporator_input.air_inlet_temperature_c,
                air_pressure_kpa,
                None,
                0.0,
                None,
                "Estado de referencia para o ar ideal; variacao de entropia usa cp ln(T2/T1).",
                "Ar tratado como gas ideal com cp constante; nao usa CoolProp.",
            ),
            EvaporatorState(
                "Ar",
                "a2-b1",
                "Saida do ar com superficies isoladas",
                isolated_case.air_outlet_temperature_c,
                air_pressure_kpa,
                None,
                AIR_CP * math.log((isolated_case.air_outlet_temperature_c + 273.15) / (evaporator_input.air_inlet_temperature_c + 273.15)),
                None,
                "T2 = T1 + (Qdot - mdot_ref*(h4-h3))/(mdot_ar*cp_ar).",
                "Calculado por balanco de energia com ar ideal.",
            ),
            EvaporatorState(
                "Ar",
                "a2-b2",
                "Saida do ar com calor externo",
                heat_transfer_case.air_outlet_temperature_c,
                air_pressure_kpa,
                None,
                AIR_CP * math.log((heat_transfer_case.air_outlet_temperature_c + 273.15) / (evaporator_input.air_inlet_temperature_c + 273.15)),
                None,
                "T2 = T1 + (Qdot - mdot_ref*(h4-h3))/(mdot_ar*cp_ar).",
                "Calculado por balanco de energia com ar ideal.",
            ),
            EvaporatorState(
                "R134a",
                "r3",
                "Entrada do refrigerante no evaporador",
                t_ref_in,
                refrigerant_pressure_kpa,
                h_ref_in,
                s_ref_in,
                inlet_quality,
                "h3 = hf + x3(hg-hf), s3 = sf + x3(sg-sf).",
                "CoolProp PropsSI em P=120 kPa e x=0,3.",
            ),
            EvaporatorState(
                "R134a",
                "r4",
                "Saida do refrigerante como vapor saturado",
                t_ref_out,
                refrigerant_pressure_kpa,
                h_ref_out,
                s_ref_out,
                1.0,
                "h4 = hg(P), s4 = sg(P).",
                "CoolProp PropsSI em P=120 kPa e x=1.",
            ),
        )

        return EvaporatorResult(
            input=evaporator_input,
            reference_state=reference_label,
            refrigerant_delta_h=delta_h_ref,
            refrigerant_delta_s=delta_s_ref,
            states=states,
            cases=(isolated_case, heat_transfer_case),
            assumptions=(
                "Regime permanente.",
                "Ar tratado como gas ideal com cp constante.",
                "Pressao do ar constante no evaporador.",
                "R134a entra como mistura saturada e sai como vapor saturado na mesma pressao.",
                "Variacoes de energia cinetica e potencial desprezadas.",
            ),
            conversion_notes=(
                "2 kg/min = 2/60 kg/s.",
                "30 kJ/min = 0,5 kJ/s = 0,5 kW.",
                "kg/s * kJ/kg = kJ/s = kW.",
                "kW/K = kJ/(s.K).",
            ),
        )
    except Exception as exc:
        if isinstance(exc, ThermoCalculationError):
            raise
        raise ThermoCalculationError(str(exc)) from exc


def _build_case(
    label: str,
    description: str,
    evaporator_input: EvaporatorInput,
    refrigerant_mass_flow: float,
    delta_h_ref: float,
    delta_s_ref: float,
    heat_transfer_kw: float,
    heat_boundary_temperature_k: float | None,
) -> EvaporatorCase:
    air_inlet_temperature_k = evaporator_input.air_inlet_temperature_c + 273.15
    air_outlet_temperature_k = air_inlet_temperature_k + (
        heat_transfer_kw - refrigerant_mass_flow * delta_h_ref
    ) / (evaporator_input.air_mass_flow * AIR_CP)
    if air_outlet_temperature_k <= 0:
        raise ThermoCalculationError("A temperatura de saida do ar ficou fisicamente invalida.")

    air_delta_s = AIR_CP * math.log(air_outlet_temperature_k / air_inlet_temperature_k)
    air_entropy_rate = evaporator_input.air_mass_flow * air_delta_s
    refrigerant_entropy_rate = refrigerant_mass_flow * delta_s_ref
    heat_entropy_rate = 0.0 if heat_boundary_temperature_k is None else heat_transfer_kw / heat_boundary_temperature_k
    entropy_generation = air_entropy_rate + refrigerant_entropy_rate - heat_entropy_rate

    return EvaporatorCase(
        label=label,
        description=description,
        heat_transfer_kw=heat_transfer_kw,
        heat_boundary_temperature_k=heat_boundary_temperature_k,
        air_outlet_temperature_c=air_outlet_temperature_k - 273.15,
        air_entropy_change_rate=air_entropy_rate,
        refrigerant_entropy_change_rate=refrigerant_entropy_rate,
        heat_entropy_transfer_rate=heat_entropy_rate,
        entropy_generation_rate=entropy_generation,
        formula="Sgen = mdot_ar*cp_ar*ln(T2/T1) + mdot_ref*(s4-s3) - Qdot/Tb",
    )


def evaporator_state_rows(result: EvaporatorResult) -> list[dict[str, str | float]]:
    rows = []
    for state in result.states:
        rows.append(
            {
                "Corrente": state.stream,
                "Estado": state.point,
                "Descricao": state.description,
                "T [°C]": round(state.temperature_c, 5),
                "P [kPa]": round(state.pressure_kpa, 5),
                "h [kJ/kg]": "" if state.enthalpy is None else round(state.enthalpy, 5),
                "s [kJ/(kg.K)]": round(state.entropy, 6),
                "x": "" if state.quality is None else round(state.quality, 6),
            }
        )
    return rows


def evaporator_case_rows(result: EvaporatorResult) -> list[dict[str, str | float]]:
    return [
        {
            "Caso": case.label,
            "Descricao": case.description,
            "Qdot [kW]": round(case.heat_transfer_kw, 6),
            "T saida ar [°C]": round(case.air_outlet_temperature_c, 5),
            "Sgen [kW/K]": round(case.entropy_generation_rate, 8),
        }
        for case in result.cases
    ]


def _validate_input(evaporator_input: EvaporatorInput) -> None:
    if evaporator_input.refrigerant != "R134a":
        raise ThermoCalculationError("Este solver de evaporador suporta R134a no MVP.")
    if not 0 <= evaporator_input.refrigerant_inlet_quality <= 1:
        raise ThermoCalculationError("O titulo do R134a deve estar entre 0 e 1.")
    if evaporator_input.air_mass_flow <= 0 or evaporator_input.refrigerant_mass_flow <= 0:
        raise ThermoCalculationError("As vazoes massicas devem ser positivas.")


def _mass_flow_to_kg_s(value: float, unit: str) -> float:
    normalized = unit.strip().lower().replace(" ", "")
    if normalized in {"kg/s", "kgs"}:
        return value
    if normalized in {"kg/min", "kgmin"}:
        return value / 60
    raise ThermoCalculationError(f"Unidade de vazao massica nao suportada: {unit}.")


def _heat_rate_to_kw(value: float, unit: str) -> float:
    normalized = unit.strip().lower().replace(" ", "")
    if normalized in {"kw", "kj/s", "kjs"}:
        return value
    if normalized in {"kj/min", "kjmin"}:
        return value / 60
    raise ThermoCalculationError(f"Unidade de taxa de calor nao suportada: {unit}.")

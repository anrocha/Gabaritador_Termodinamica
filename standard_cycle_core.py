from __future__ import annotations

from dataclasses import dataclass

from thermo_core import ThermoCalculationError, apply_reference_state, pa_to_pressure, pressure_to_pa


@dataclass(frozen=True)
class StandardCycleInput:
    fluid: str = "R134a"
    low_pressure: float = 0.14
    high_pressure: float = 0.8
    pressure_unit: str = "MPa"
    mass_flow: float = 0.05
    reference_state: str = "Unisinos"


@dataclass(frozen=True)
class StandardCycleState:
    point: str
    description: str
    temperature_c: float
    pressure: float
    enthalpy: float
    entropy: float
    quality: float | None
    region: str
    formula: str
    property_source: str


@dataclass(frozen=True)
class StandardCycleMetric:
    label: str
    value: float
    unit: str
    formula: str


@dataclass(frozen=True)
class StandardCycleResult:
    input: StandardCycleInput
    reference_state: str
    states: tuple[StandardCycleState, ...]
    metrics: tuple[StandardCycleMetric, ...]
    validations: tuple[str, ...]
    assumptions: tuple[str, ...]


def calculate_standard_vapor_compression_cycle(cycle_input: StandardCycleInput) -> StandardCycleResult:
    _validate_input(cycle_input)

    try:
        from CoolProp.CoolProp import PhaseSI, PropsSI

        reference_label = apply_reference_state(cycle_input.fluid, cycle_input.reference_state)
        p_low = pressure_to_pa(cycle_input.low_pressure, cycle_input.pressure_unit)
        p_high = pressure_to_pa(cycle_input.high_pressure, cycle_input.pressure_unit)

        h1 = PropsSI("H", "P", p_low, "Q", 1, cycle_input.fluid)
        s1 = PropsSI("S", "P", p_low, "Q", 1, cycle_input.fluid)
        t1 = PropsSI("T", "P", p_low, "Q", 1, cycle_input.fluid)

        s2 = s1
        h2 = PropsSI("H", "P", p_high, "S", s2, cycle_input.fluid)
        t2 = PropsSI("T", "P", p_high, "S", s2, cycle_input.fluid)

        h3 = PropsSI("H", "P", p_high, "Q", 0, cycle_input.fluid)
        s3 = PropsSI("S", "P", p_high, "Q", 0, cycle_input.fluid)
        t3 = PropsSI("T", "P", p_high, "Q", 0, cycle_input.fluid)

        h4 = h3
        t4 = PropsSI("T", "P", p_low, "H", h4, cycle_input.fluid)
        s4 = PropsSI("S", "P", p_low, "H", h4, cycle_input.fluid)
        q4 = PropsSI("Q", "P", p_low, "H", h4, cycle_input.fluid)

        states = (
            _build_state(
                cycle_input,
                "1",
                "Entrada do compressor: vapor saturado",
                p_low,
                t1,
                h1,
                s1,
                1.0,
                "x1 = 1; h1 = hg(Pbaixa); s1 = sg(Pbaixa)",
                "CoolProp PropsSI em P_baixa e x=1.",
            ),
            _build_state(
                cycle_input,
                "2",
                "Saida do compressor ideal isentropico",
                p_high,
                t2,
                h2,
                s2,
                _quality_or_none(cycle_input.fluid, p_high, h2),
                "s2 = s1; h2 = h(Palta,s1)",
                "CoolProp PropsSI em P_alta e s=s1.",
            ),
            _build_state(
                cycle_input,
                "3",
                "Saida do condensador: liquido saturado",
                p_high,
                t3,
                h3,
                s3,
                0.0,
                "x3 = 0; h3 = hf(Palta); s3 = sf(Palta)",
                "CoolProp PropsSI em P_alta e x=0.",
            ),
            _build_state(
                cycle_input,
                "4",
                "Entrada do evaporador apos valvula",
                p_low,
                t4,
                h4,
                s4,
                q4 if 0 <= q4 <= 1 else None,
                "h4 = h3; P4 = Pbaixa",
                "CoolProp PropsSI em P_baixa e h=h3.",
            ),
        )

        q_low = (h1 - h4) / 1000
        w_comp = (h2 - h1) / 1000
        q_high = (h2 - h3) / 1000
        qdot_low = cycle_input.mass_flow * q_low
        compressor_power = cycle_input.mass_flow * w_comp
        qdot_high = cycle_input.mass_flow * q_high
        cop = q_low / w_comp

        metrics = (
            StandardCycleMetric("Calor removido do espaco refrigerado", qdot_low, "kW", "Qdot_L = m_dot * (h1 - h4)"),
            StandardCycleMetric("Potencia do compressor", compressor_power, "kW", "Wdot = m_dot * (h2 - h1)"),
            StandardCycleMetric("Titulo na entrada do evaporador", states[3].quality if states[3].quality is not None else float("nan"), "-", "x4 = x(Pbaixa,h4)"),
            StandardCycleMetric("Calor rejeitado ao ambiente", qdot_high, "kW", "Qdot_H = m_dot * (h2 - h3)"),
            StandardCycleMetric("COP do refrigerador", cop, "-", "COP = (h1 - h4) / (h2 - h1)"),
        )

        return StandardCycleResult(
            input=cycle_input,
            reference_state=reference_label,
            states=states,
            metrics=metrics,
            validations=_validate_result(h1, h2, h3, h4, qdot_low, compressor_power, qdot_high, states[3].quality),
            assumptions=(
                "Ciclo padrao de refrigeracao por compressao de vapor.",
                "Compressor ideal isentropico.",
                "Estado 1: vapor saturado na pressao baixa.",
                "Estado 3: liquido saturado na pressao alta.",
                "Valvula de expansao isoentalpica.",
            ),
        )
    except Exception as exc:
        if isinstance(exc, ThermoCalculationError):
            raise
        raise ThermoCalculationError(str(exc)) from exc


def standard_cycle_state_rows(result: StandardCycleResult) -> list[dict[str, str | float]]:
    return [
        {
            "Estado": state.point,
            "Descricao": state.description,
            "T [°C]": round(state.temperature_c, 5),
            f"P [{result.input.pressure_unit}]": round(state.pressure, 6),
            "h [kJ/kg]": round(state.enthalpy, 5),
            "s [kJ/(kg.K)]": round(state.entropy, 6),
            "x": "" if state.quality is None else round(state.quality, 6),
            "Regiao": state.region,
        }
        for state in result.states
    ]


def standard_cycle_metric_rows(result: StandardCycleResult) -> list[dict[str, str | float]]:
    return [
        {
            "Grandeza": metric.label,
            "Valor": round(metric.value, 6),
            "Unidade": metric.unit,
        }
        for metric in result.metrics
    ]


def _build_state(
    cycle_input: StandardCycleInput,
    point: str,
    description: str,
    pressure_pa: float,
    temperature_k: float,
    enthalpy_jkg: float,
    entropy_jkgk: float,
    quality: float | None,
    formula: str,
    property_source: str,
) -> StandardCycleState:
    from CoolProp.CoolProp import PhaseSI

    phase = PhaseSI("P", pressure_pa, "H", enthalpy_jkg, cycle_input.fluid)
    return StandardCycleState(
        point=point,
        description=description,
        temperature_c=temperature_k - 273.15,
        pressure=pa_to_pressure(pressure_pa, cycle_input.pressure_unit),
        enthalpy=enthalpy_jkg / 1000,
        entropy=entropy_jkgk / 1000,
        quality=quality,
        region=_region_label(quality, phase),
        formula=formula,
        property_source=property_source,
    )


def _quality_or_none(fluid: str, pressure_pa: float, enthalpy_jkg: float) -> float | None:
    from CoolProp.CoolProp import PropsSI

    quality = PropsSI("Q", "P", pressure_pa, "H", enthalpy_jkg, fluid)
    return quality if 0 <= quality <= 1 else None


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
    if normalized == "liquid":
        return "liquido comprimido/sub-resfriado"
    return normalized


def _validate_input(cycle_input: StandardCycleInput) -> None:
    if cycle_input.fluid not in {"R134a", "R22"}:
        raise ThermoCalculationError("O ciclo padrao por pressoes suporta R134a ou R22.")
    if cycle_input.mass_flow <= 0:
        raise ThermoCalculationError("A vazao massica deve ser positiva.")
    if pressure_to_pa(cycle_input.high_pressure, cycle_input.pressure_unit) <= pressure_to_pa(
        cycle_input.low_pressure,
        cycle_input.pressure_unit,
    ):
        raise ThermoCalculationError("A pressao alta deve ser maior que a pressao baixa.")


def _validate_result(
    h1: float,
    h2: float,
    h3: float,
    h4: float,
    qdot_low: float,
    compressor_power: float,
    qdot_high: float,
    quality_4: float | None,
) -> tuple[str, ...]:
    validations = [
        "OK: h2 > h1 no compressor." if h2 > h1 else "Atencao: h2 nao ficou maior que h1.",
        "OK: h4 = h3 na valvula." if abs(h4 - h3) < 1e-6 else "Atencao: h4 difere de h3.",
        "OK: Qdot_H = Qdot_L + Wdot." if abs(qdot_high - qdot_low - compressor_power) < 1e-5 else "Atencao: balanco de energia nao fechou.",
    ]
    if quality_4 is not None:
        validations.append("OK: titulo x4 entre 0 e 1." if 0 <= quality_4 <= 1 else "Atencao: titulo x4 fora da faixa.")
    return tuple(validations)

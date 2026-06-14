from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class ThermoCalculationError(ValueError):
    """Raised when a thermodynamic state cannot be calculated."""


@dataclass(frozen=True)
class PropertyResult:
    label: str
    symbol: str
    value: float | None
    unit: str
    formula: str | None = None


@dataclass(frozen=True)
class StateResult:
    fluid: str
    reference_state: str
    temperature_k: float
    pressure_pa: float
    phase: str
    quality: float | None
    properties: tuple[PropertyResult, ...]


@dataclass(frozen=True)
class QualityResult:
    fluid: str
    reference_state: str
    constraint_label: str
    constraint_value: float
    property_label: str
    property_unit: str
    saturated_liquid: float
    saturated_vapor: float
    input_value: float
    quality: float
    phase_hint: str
    mixture_properties: tuple[PropertyResult, ...]


@dataclass(frozen=True)
class StateInputDefinition:
    label: str
    symbol: str
    coolprop_key: str
    unit: str
    default_value: float
    step: float
    min_value: float | None = None
    factor_to_si: float = 1


SUPPORTED_FLUIDS = (
    "Water",
    "R134a",
    "R22",
    "R410A",
    "Ammonia",
    "CarbonDioxide",
    "Nitrogen",
    "Oxygen",
    "Methane",
    "Propane",
)


PRESSURE_UNITS = ("Pa", "kPa", "MPa", "bar")
TEMPERATURE_UNITS = ("C", "K", "F")
REFERENCE_STATE_OPTIONS = ("Unisinos", "CoolProp padrao", "ASHRAE", "IIR", "NBP")


CENGEL_REFRIGERANT_FLUIDS = {
    "R134a",
    "R22",
    "R410A",
    "Ammonia",
    "CarbonDioxide",
    "Propane",
}


CENGEL_IDEAL_GAS_FLUIDS = {
    "Methane",
    "Nitrogen",
    "Oxygen",
}


PRESSURE_FACTORS_TO_PA = {
    "pa": 1,
    "kpa": 1_000,
    "mpa": 1_000_000,
    "bar": 100_000,
}


PROPERTY_DEFINITIONS = {
    "H": ("Entalpia especifica", "h", "kJ/kg", 1 / 1000),
    "U": ("Energia interna especifica", "u", "kJ/kg", 1 / 1000),
    "S": ("Entropia especifica", "s", "kJ/(kg.K)", 1 / 1000),
    "D": ("Massa especifica", "rho", "kg/m3", 1),
    "V": ("Volume especifico", "v", "m3/kg", 1),
    "CPMASS": ("Calor especifico cp", "cp", "kJ/(kg.K)", 1 / 1000),
    "CVMASS": ("Calor especifico cv", "cv", "kJ/(kg.K)", 1 / 1000),
    "A": ("Velocidade do som", "a", "m/s", 1),
    "VISCOSITY": ("Viscosidade dinamica", "mu", "Pa.s", 1),
    "CONDUCTIVITY": ("Condutividade termica", "k", "W/(m.K)", 1),
}


QUALITY_INPUTS = {
    "Entalpia especifica (h)": ("H", "kJ/kg", 1000),
    "Energia interna especifica (u)": ("U", "kJ/kg", 1000),
    "Volume especifico (v)": ("V", "m3/kg", 1),
    "Entropia especifica (s)": ("S", "kJ/(kg.K)", 1000),
}


STATE_INPUT_DEFINITIONS = {
    "T": StateInputDefinition("Temperatura", "T", "T", "temperatura selecionada", 100.0, 5.0),
    "P": StateInputDefinition("Pressao", "P", "P", "pressao selecionada", 1.01325, 0.1, 0.00001),
    "H": StateInputDefinition("Entalpia especifica", "h", "H", "kJ/kg", 2675.0, 10.0, factor_to_si=1000),
    "U": StateInputDefinition("Energia interna especifica", "u", "U", "kJ/kg", 2500.0, 10.0, factor_to_si=1000),
    "S": StateInputDefinition("Entropia especifica", "s", "S", "kJ/(kg.K)", 7.0, 0.1, factor_to_si=1000),
    "D": StateInputDefinition("Massa especifica", "rho", "D", "kg/m3", 1.0, 0.1, 0.000001),
    "V": StateInputDefinition("Volume especifico", "v", "D", "m3/kg", 1.0, 0.1, 0.000001),
}


PHASE_TRANSLATIONS = {
    "liquid": "liquido comprimido/sub-resfriado",
    "gas": "vapor superaquecido",
    "supercritical": "supercritico",
    "supercritical_gas": "gas supercritico",
    "supercritical_liquid": "liquido supercritico",
    "twophase": "mistura saturada",
    "unknown": "indefinida",
}


def available_fluids() -> tuple[str, ...]:
    try:
        from CoolProp.CoolProp import get_global_param_string

        fluids = get_global_param_string("FluidsList").split(",")
        preferred = [fluid for fluid in SUPPORTED_FLUIDS if fluid in fluids]
        remaining = sorted(fluid for fluid in fluids if fluid not in preferred)
        return tuple(preferred + remaining)
    except Exception:
        return SUPPORTED_FLUIDS


def pressure_to_pa(value: float, unit: str) -> float:
    normalized_unit = unit.strip().lower()
    if normalized_unit not in PRESSURE_FACTORS_TO_PA:
        raise ThermoCalculationError(f"Unidade de pressao nao suportada: {unit}.")

    pressure_pa = value * PRESSURE_FACTORS_TO_PA[normalized_unit]
    if pressure_pa <= 0:
        raise ThermoCalculationError("A pressao deve ser maior que zero.")
    return pressure_pa


def pa_to_pressure(value: float, unit: str) -> float:
    normalized_unit = unit.strip().lower()
    if normalized_unit not in PRESSURE_FACTORS_TO_PA:
        raise ThermoCalculationError(f"Unidade de pressao nao suportada: {unit}.")
    return value / PRESSURE_FACTORS_TO_PA[normalized_unit]


def temperature_to_k(value: float, unit: str) -> float:
    normalized_unit = unit.strip().lower()
    if normalized_unit in {"c", "degc", "celsius"}:
        temperature_k = value + 273.15
    elif normalized_unit in {"k", "kelvin"}:
        temperature_k = value
    elif normalized_unit in {"f", "degf", "fahrenheit"}:
        temperature_k = (value - 32) * 5 / 9 + 273.15
    else:
        raise ThermoCalculationError(f"Unidade de temperatura nao suportada: {unit}.")

    if temperature_k <= 0:
        raise ThermoCalculationError("A temperatura em Kelvin deve ser maior que zero.")
    return temperature_k


def k_to_temperature(value: float, unit: str) -> float:
    normalized_unit = unit.strip().lower()
    if normalized_unit in {"c", "degc", "celsius"}:
        return value - 273.15
    if normalized_unit in {"k", "kelvin"}:
        return value
    if normalized_unit in {"f", "degf", "fahrenheit"}:
        return (value - 273.15) * 9 / 5 + 32
    raise ThermoCalculationError(f"Unidade de temperatura nao suportada: {unit}.")


def reference_state_description(fluid: str, reference_state: str) -> str:
    resolved_state, description = resolve_reference_state(fluid, reference_state)
    if resolved_state == "DEF":
        return description
    return f"{description} ({resolved_state})"


def resolve_reference_state(fluid: str, reference_state: str) -> tuple[str, str]:
    if reference_state in {"Unisinos", "Cengel / faculdade"}:
        if fluid == "Water":
            return "DEF", "Unisinos agua/vapor: referencia padrao de vapor do CoolProp"
        if fluid in CENGEL_REFRIGERANT_FLUIDS:
            return "ASHRAE", "Unisinos refrigerantes: h = 0 e s = 0 a -40 C"
        if fluid in CENGEL_IDEAL_GAS_FLUIDS:
            return "DEF", "Unisinos gases ideais: CoolProp usa fluido real; use a tabela ideal para bater exatamente"
        return "DEF", "Unisinos: sem regra especifica cadastrada para este fluido"

    if reference_state == "CoolProp padrao":
        return "DEF", "CoolProp padrao"

    if reference_state in {"ASHRAE", "IIR", "NBP"}:
        return reference_state, reference_state

    raise ThermoCalculationError(f"Estado de referencia nao suportado: {reference_state}.")


def apply_reference_state(fluid: str, reference_state: str) -> str:
    from CoolProp.CoolProp import set_reference_state

    resolved_state, description = resolve_reference_state(fluid, reference_state)
    try:
        set_reference_state(fluid, resolved_state)
    except Exception as exc:
        raise ThermoCalculationError(
            f"Nao foi possivel aplicar a referencia {resolved_state} para {fluid}: {exc}"
        ) from exc
    return description


def calculate_state_from_tp(
    fluid: str,
    temperature: float,
    pressure: float,
    property_keys: Iterable[str] | None = None,
    temperature_unit: str = "C",
    pressure_unit: str = "bar",
    reference_state: str = "Unisinos",
) -> StateResult:
    temperature_k = temperature_to_k(temperature, temperature_unit)
    pressure_pa = pressure_to_pa(pressure, pressure_unit)
    keys = tuple(property_keys or PROPERTY_DEFINITIONS.keys())

    try:
        from CoolProp.CoolProp import PhaseSI, PropsSI

        reference_state_label = apply_reference_state(fluid, reference_state)
        phase_raw = PhaseSI("T", temperature_k, "P", pressure_pa, fluid)
        quality_raw = PropsSI("Q", "T", temperature_k, "P", pressure_pa, fluid)
        quality = quality_raw if 0 <= quality_raw <= 1 else None

        properties: list[PropertyResult] = []
        for key in keys:
            if key == "V":
                density = PropsSI("D", "T", temperature_k, "P", pressure_pa, fluid)
                value = 1 / density
            else:
                value = PropsSI(key, "T", temperature_k, "P", pressure_pa, fluid)

            label, symbol, unit, factor = PROPERTY_DEFINITIONS[key]
            properties.append(PropertyResult(label, symbol, value * factor, unit))

        return StateResult(
            fluid=fluid,
            reference_state=reference_state_label,
            temperature_k=temperature_k,
            pressure_pa=pressure_pa,
            phase=translate_phase(phase_raw),
            quality=quality,
            properties=tuple(properties),
        )
    except Exception as exc:
        raise ThermoCalculationError(str(exc)) from exc


def calculate_state_from_pair(
    fluid: str,
    first_property_key: str,
    first_value: float,
    second_property_key: str,
    second_value: float,
    property_keys: Iterable[str] | None = None,
    temperature_unit: str = "C",
    pressure_unit: str = "bar",
    reference_state: str = "Unisinos",
) -> StateResult:
    first_name, first_value_si = _state_pair_input_to_si(
        first_property_key,
        first_value,
        temperature_unit,
        pressure_unit,
    )
    second_name, second_value_si = _state_pair_input_to_si(
        second_property_key,
        second_value,
        temperature_unit,
        pressure_unit,
    )

    if first_property_key == second_property_key:
        raise ThermoCalculationError("Escolha duas propriedades diferentes.")
    if first_name == second_name:
        raise ThermoCalculationError("Escolha duas propriedades independentes.")

    keys = tuple(property_keys or PROPERTY_DEFINITIONS.keys())

    try:
        from CoolProp.CoolProp import PhaseSI, PropsSI

        reference_state_label = apply_reference_state(fluid, reference_state)
        temperature_k = PropsSI("T", first_name, first_value_si, second_name, second_value_si, fluid)
        pressure_pa = PropsSI("P", first_name, first_value_si, second_name, second_value_si, fluid)
        phase_raw = PhaseSI(first_name, first_value_si, second_name, second_value_si, fluid)
        quality_raw = PropsSI("Q", first_name, first_value_si, second_name, second_value_si, fluid)
        quality = quality_raw if 0 <= quality_raw <= 1 else None

        properties: list[PropertyResult] = []
        for key in keys:
            if key == "V":
                density = PropsSI("D", first_name, first_value_si, second_name, second_value_si, fluid)
                value = 1 / density
            else:
                value = PropsSI(key, first_name, first_value_si, second_name, second_value_si, fluid)

            label, symbol, unit, factor = PROPERTY_DEFINITIONS[key]
            properties.append(PropertyResult(label, symbol, value * factor, unit))

        return StateResult(
            fluid=fluid,
            reference_state=reference_state_label,
            temperature_k=temperature_k,
            pressure_pa=pressure_pa,
            phase=translate_phase(phase_raw),
            quality=quality,
            properties=tuple(properties),
        )
    except Exception as exc:
        if isinstance(exc, ThermoCalculationError):
            raise
        raise ThermoCalculationError(str(exc)) from exc


def _state_pair_input_to_si(
    property_key: str,
    value: float,
    temperature_unit: str,
    pressure_unit: str,
) -> tuple[str, float]:
    if property_key not in STATE_INPUT_DEFINITIONS:
        raise ThermoCalculationError(f"Propriedade de entrada nao suportada: {property_key}.")

    definition = STATE_INPUT_DEFINITIONS[property_key]
    if definition.min_value is not None and value < definition.min_value:
        raise ThermoCalculationError(f"{definition.label} deve ser maior que zero.")

    if property_key == "T":
        return definition.coolprop_key, temperature_to_k(value, temperature_unit)
    if property_key == "P":
        return definition.coolprop_key, pressure_to_pa(value, pressure_unit)
    if property_key == "V":
        return definition.coolprop_key, 1 / value
    return definition.coolprop_key, value * definition.factor_to_si


def calculate_quality(
    fluid: str,
    constraint_type: str,
    constraint_value: float,
    property_label: str,
    property_value_display: float,
    constraint_unit: str | None = None,
    reference_state: str = "Unisinos",
    output_temperature_unit: str = "C",
    output_pressure_unit: str = "bar",
) -> QualityResult:
    property_key, unit, input_factor = QUALITY_INPUTS[property_label]
    property_value_si = property_value_display * input_factor

    if constraint_type == "Pressao":
        input_name = "P"
        input_value_si = pressure_to_pa(constraint_value, constraint_unit or "bar")
        constraint_label = "Pressao"
        constraint_unit_value = constraint_value
    else:
        input_name = "T"
        input_value_si = temperature_to_k(constraint_value, constraint_unit or "C")
        constraint_label = "Temperatura"
        constraint_unit_value = constraint_value

    try:
        from CoolProp.CoolProp import PropsSI

        reference_state_label = apply_reference_state(fluid, reference_state)
        if property_key == "V":
            liquid_si = 1 / PropsSI("D", input_name, input_value_si, "Q", 0, fluid)
            vapor_si = 1 / PropsSI("D", input_name, input_value_si, "Q", 1, fluid)
        else:
            liquid_si = PropsSI(property_key, input_name, input_value_si, "Q", 0, fluid)
            vapor_si = PropsSI(property_key, input_name, input_value_si, "Q", 1, fluid)

        if vapor_si == liquid_si:
            raise ThermoCalculationError("Nao foi possivel calcular o titulo neste ponto.")

        quality = (property_value_si - liquid_si) / (vapor_si - liquid_si)
        phase_hint = quality_phase_hint(quality)
        mixture_properties = _linear_mixture_properties(
            fluid,
            input_name,
            input_value_si,
            quality,
            output_temperature_unit,
            output_pressure_unit,
        )

        display_factor = 1 / input_factor
        return QualityResult(
            fluid=fluid,
            reference_state=reference_state_label,
            constraint_label=constraint_label,
            constraint_value=constraint_unit_value,
            property_label=property_label,
            property_unit=unit,
            saturated_liquid=liquid_si * display_factor,
            saturated_vapor=vapor_si * display_factor,
            input_value=property_value_display,
            quality=quality,
            phase_hint=phase_hint,
            mixture_properties=mixture_properties,
        )
    except Exception as exc:
        if isinstance(exc, ThermoCalculationError):
            raise
        raise ThermoCalculationError(str(exc)) from exc


def _linear_mixture_properties(
    fluid: str,
    input_name: str,
    input_value_si: float,
    quality: float,
    temperature_unit: str,
    pressure_unit: str,
) -> tuple[PropertyResult, ...]:
    return (
        _linear_mixture_property("T", fluid, input_name, input_value_si, quality, temperature_unit, pressure_unit),
        _linear_mixture_property("P", fluid, input_name, input_value_si, quality, temperature_unit, pressure_unit),
        _linear_mixture_property("H", fluid, input_name, input_value_si, quality, temperature_unit, pressure_unit),
        _linear_mixture_property("U", fluid, input_name, input_value_si, quality, temperature_unit, pressure_unit),
        _linear_mixture_property("S", fluid, input_name, input_value_si, quality, temperature_unit, pressure_unit),
        _linear_mixture_property("V", fluid, input_name, input_value_si, quality, temperature_unit, pressure_unit),
    )


def _linear_mixture_property(
    key: str,
    fluid: str,
    input_name: str,
    input_value_si: float,
    quality: float,
    temperature_unit: str,
    pressure_unit: str,
) -> PropertyResult:
    from CoolProp.CoolProp import PropsSI

    if key == "T":
        temperature_k = (
            input_value_si
            if input_name == "T"
            else PropsSI("T", input_name, input_value_si, "Q", 0, fluid)
        )
        value = k_to_temperature(temperature_k, temperature_unit)
        return PropertyResult("Temperatura", "T", value, temperature_unit, f"T = {value:.6g} {temperature_unit}")

    if key == "P":
        pressure_pa = (
            input_value_si
            if input_name == "P"
            else PropsSI("P", input_name, input_value_si, "Q", 0, fluid)
        )
        value = pa_to_pressure(pressure_pa, pressure_unit)
        return PropertyResult("Pressao", "P", value, pressure_unit, f"P = {value:.6g} {pressure_unit}")

    if key == "V":
        liquid = 1 / PropsSI("D", input_name, input_value_si, "Q", 0, fluid)
        vapor = 1 / PropsSI("D", input_name, input_value_si, "Q", 1, fluid)
        value = liquid + quality * (vapor - liquid)
        formula = f"v = {liquid:.6g} + {quality:.6g} * ({vapor:.6g} - {liquid:.6g}) m3/kg"
        return PropertyResult("Volume especifico", "v", value, "m3/kg", formula)

    label, symbol, unit, factor = PROPERTY_DEFINITIONS[key]
    liquid = PropsSI(key, input_name, input_value_si, "Q", 0, fluid)
    vapor = PropsSI(key, input_name, input_value_si, "Q", 1, fluid)
    liquid_display = liquid * factor
    vapor_display = vapor * factor
    value = liquid_display + quality * (vapor_display - liquid_display)
    formula = (
        f"{symbol} = {liquid_display:.6g} + {quality:.6g} * "
        f"({vapor_display:.6g} - {liquid_display:.6g}) {unit}"
    )
    return PropertyResult(label, symbol, value, unit, formula)


def _property_at_quality(
    key: str,
    fluid: str,
    input_name: str,
    input_value_si: float,
    quality: float,
) -> PropertyResult:
    from CoolProp.CoolProp import PropsSI

    if key == "T":
        value = PropsSI("T", input_name, input_value_si, "Q", quality, fluid) - 273.15
        return PropertyResult("Temperatura", "T", value, "degC")

    if key == "P":
        value = PropsSI("P", input_name, input_value_si, "Q", quality, fluid) / 100_000
        return PropertyResult("Pressao", "P", value, "bar")

    if key == "V":
        density = PropsSI("D", input_name, input_value_si, "Q", quality, fluid)
        return PropertyResult("Volume especifico", "v", 1 / density, "m3/kg")

    label, symbol, unit, factor = PROPERTY_DEFINITIONS[key]
    value = PropsSI(key, input_name, input_value_si, "Q", quality, fluid)
    return PropertyResult(label, symbol, value * factor, unit)


def translate_phase(phase: str) -> str:
    normalized = phase.replace("phase_", "").lower()
    return PHASE_TRANSLATIONS.get(normalized, normalized)


def quality_phase_hint(quality: float) -> str:
    if quality < 0:
        return "valor abaixo de liquido saturado"
    if quality > 1:
        return "valor acima de vapor saturado"
    return "mistura saturada"

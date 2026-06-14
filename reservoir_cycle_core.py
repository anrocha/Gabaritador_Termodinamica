from __future__ import annotations

from dataclasses import dataclass

from thermo_core import ThermoCalculationError


@dataclass(frozen=True)
class ReservoirCycleInput:
    low_temperature_k: float = 275.0
    high_temperature_k: float = 315.0
    cases: tuple["ReservoirCaseInput", ...] = ()


@dataclass(frozen=True)
class ReservoirCaseInput:
    label: str
    heat_absorbed_low: float | None = None
    heat_rejected_high: float | None = None
    work_input: float | None = None
    unit: str = "kJ"


@dataclass(frozen=True)
class ReservoirCaseResult:
    label: str
    heat_absorbed_low: float
    heat_rejected_high: float
    work_input: float
    cop: float
    carnot_cop: float
    entropy_universe: float
    classification: str
    explanation: str


@dataclass(frozen=True)
class ReservoirCycleResult:
    input: ReservoirCycleInput
    cases: tuple[ReservoirCaseResult, ...]
    assumptions: tuple[str, ...]
    conversion_notes: tuple[str, ...]


def calculate_reservoir_refrigerator(cycle_input: ReservoirCycleInput) -> ReservoirCycleResult:
    _validate_input(cycle_input)
    carnot_cop = cycle_input.low_temperature_k / (cycle_input.high_temperature_k - cycle_input.low_temperature_k)

    cases = []
    for case_input in cycle_input.cases:
        q_low, q_high, work = _complete_energy_balance(case_input)
        cop = q_low / work
        entropy_universe = q_high / cycle_input.high_temperature_k - q_low / cycle_input.low_temperature_k
        classification = _classify_cycle(cop, carnot_cop, entropy_universe)
        cases.append(
            ReservoirCaseResult(
                label=case_input.label,
                heat_absorbed_low=q_low,
                heat_rejected_high=q_high,
                work_input=work,
                cop=cop,
                carnot_cop=carnot_cop,
                entropy_universe=entropy_universe,
                classification=classification,
                explanation=_classification_explanation(classification),
            )
        )

    return ReservoirCycleResult(
        input=cycle_input,
        cases=tuple(cases),
        assumptions=(
            "Ciclo de refrigeracao operando entre dois reservatorios termicos.",
            "Reservatorios mantem temperaturas constantes.",
            "Convencao: QL entra no ciclo, QH sai do ciclo e Wciclo e trabalho fornecido ao ciclo.",
            "Para refrigerador reversivel, COP_Carnot = TL/(TH-TL).",
        ),
        conversion_notes=(
            "Balanco de energia do ciclo: QH = QL + Wciclo.",
            "Variacao de entropia do universo: DeltaS_univ = QH/TH - QL/TL.",
            "DeltaS_univ < 0 indica processo impossivel pela segunda lei.",
        ),
    )


def default_reservoir_exercise_input() -> ReservoirCycleInput:
    return ReservoirCycleInput(
        low_temperature_k=275.0,
        high_temperature_k=315.0,
        cases=(
            ReservoirCaseInput("1", heat_absorbed_low=1000.0, work_input=80.0),
            ReservoirCaseInput("2", heat_absorbed_low=1200.0, heat_rejected_high=2000.0),
            ReservoirCaseInput("3", heat_rejected_high=1575.0, work_input=200.0),
        ),
    )


def reservoir_case_rows(result: ReservoirCycleResult) -> list[dict[str, str | float]]:
    return [
        {
            "Caso": case.label,
            "QL [kJ]": round(case.heat_absorbed_low, 6),
            "QH [kJ]": round(case.heat_rejected_high, 6),
            "Wciclo [kJ]": round(case.work_input, 6),
            "COP": round(case.cop, 6),
            "COP Carnot": round(case.carnot_cop, 6),
            "DeltaS_univ [kJ/K]": round(case.entropy_universe, 8),
            "Classificacao": case.classification,
        }
        for case in result.cases
    ]


def _complete_energy_balance(case_input: ReservoirCaseInput) -> tuple[float, float, float]:
    q_low = case_input.heat_absorbed_low
    q_high = case_input.heat_rejected_high
    work = case_input.work_input
    known_count = sum(value is not None for value in (q_low, q_high, work))
    if known_count < 2:
        raise ThermoCalculationError(f"O caso {case_input.label} precisa de pelo menos duas grandezas entre QL, QH e W.")

    if q_low is None:
        q_low = q_high - work
    elif q_high is None:
        q_high = q_low + work
    elif work is None:
        work = q_high - q_low

    if q_low is None or q_high is None or work is None:
        raise ThermoCalculationError(f"Nao foi possivel fechar o balanco de energia do caso {case_input.label}.")
    if q_low <= 0 or q_high <= 0 or work <= 0:
        raise ThermoCalculationError(f"As grandezas energeticas do caso {case_input.label} devem ser positivas.")
    return q_low, q_high, work


def _classify_cycle(cop: float, carnot_cop: float, entropy_universe: float) -> str:
    tolerance = 1e-6
    if entropy_universe < -tolerance or cop > carnot_cop + tolerance:
        return "impossivel"
    if abs(entropy_universe) <= tolerance and abs(cop - carnot_cop) <= tolerance:
        return "reversivel"
    return "irreversivel"


def _classification_explanation(classification: str) -> str:
    if classification == "impossivel":
        return "Viola a segunda lei: COP maior que Carnot ou DeltaS_univ negativo."
    if classification == "reversivel":
        return "Atinge o limite de Carnot e DeltaS_univ e nulo."
    return "Obedece a segunda lei, mas gera entropia positiva."


def _validate_input(cycle_input: ReservoirCycleInput) -> None:
    if cycle_input.low_temperature_k <= 0 or cycle_input.high_temperature_k <= 0:
        raise ThermoCalculationError("Temperaturas dos reservatorios devem estar em Kelvin positivo.")
    if cycle_input.high_temperature_k <= cycle_input.low_temperature_k:
        raise ThermoCalculationError("TH deve ser maior que TL.")
    if not cycle_input.cases:
        raise ThermoCalculationError("Informe pelo menos um caso de refrigerador.")

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from openai_assistant import PlannerItem, ThermoPlan


@dataclass(frozen=True)
class ThermoFact:
    name: str
    canonical_name: str
    value: str
    unit: str
    source: str
    state: str = ""
    confidence: float = 1.0
    raw_text: str = ""


@dataclass(frozen=True)
class ToolSpec:
    main_tool: str
    aliases: tuple[str, ...]
    required_all: tuple[str, ...] = ()
    required_any: tuple[tuple[str, ...], ...] = ()
    optional: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    diagrams: tuple[str, ...] = ()
    forbidden_context: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolReadiness:
    tool: str
    ready: bool
    missing: tuple[str, ...]
    score: int


TOOL_SPECS = {
    "ciclo_refrigeracao_simples": ToolSpec(
        main_tool="ciclo_refrigeracao_simples",
        aliases=("ciclo de refrigeracao", "compressao de vapor", "ciclo fechado"),
        required_all=("fluid",),
        required_any=(("T_evap", "P_evap"), ("T_cond", "P_cond")),
        optional=("superheat", "subcooling", "eta_comp", "cooling_capacity"),
        outputs=("states", "COP", "compressor_power", "mass_flow"),
        diagrams=("P-h",),
        forbidden_context=("corrente de ar", "turbina", "agua/vapor"),
    ),
    "ciclo_refrigeracao_padrao_pressao": ToolSpec(
        main_tool="ciclo_refrigeracao_padrao_pressao",
        aliases=("ciclo padrao", "s1=s2", "h4=h3"),
        required_all=("fluid", "P_low", "P_high", "mass_flow"),
        outputs=("QL", "W_comp", "x4", "QH", "COP"),
        diagrams=("T-s",),
    ),
    "evaporador_ar_refrigerante": ToolSpec(
        main_tool="evaporador_ar_refrigerante",
        aliases=("evaporador com ar", "trocador com ar", "corrente de ar"),
        required_all=("air_stream", "fluid"),
        required_any=(("air_mass_flow", "air_temperature", "air_pressure"), ("refrigerant_pressure", "refrigerant_quality")),
        outputs=("air_outlet_temperature", "S_gen"),
        forbidden_context=("ciclo fechado",),
    ),
    "turbina_vapor_adiabatica": ToolSpec(
        main_tool="turbina_vapor_adiabatica",
        aliases=("turbina", "vapor de agua"),
        required_all=("P1", "T1", "P2", "mass_flow"),
        optional=("T2_real",),
        outputs=("W_max", "eta_t", "states"),
        diagrams=("T-s",),
    ),
    "refrigerador_reservatorios": ToolSpec(
        main_tool="refrigerador_reservatorios",
        aliases=("reservatorios", "COP de carnot", "TL", "TH"),
        required_all=("T_low", "T_high"),
        required_any=(("Q_L", "Q_H", "W_cycle"),),
        outputs=("COP", "COP_Carnot", "DeltaS_univ"),
    ),
}


CANONICAL_ALIASES = {
    "T_evap": (
        "temperatura evaporacao",
        "temperatura de evaporacao",
        "temperatura baixa",
        "temperatura_baixa",
        "t baixa",
        "t evap",
        "t_evap",
        "t4 1",
        "t 4 1",
        "linha 4 1",
        "temperatura do evaporador",
        "temperatura no evaporador",
        "estado 1 vapor saturado",
        "ponto 1 vapor saturado",
    ),
    "P_evap": (
        "pressao evaporacao",
        "pressao de evaporacao",
        "pressao baixa",
        "pressao_baixa",
        "p baixa",
        "p evap",
        "p_evap",
        "pressao do evaporador",
    ),
    "T_cond": (
        "temperatura condensacao",
        "temperatura de condensacao",
        "temperatura alta",
        "t cond",
        "t_cond",
        "temperatura do condensador",
    ),
    "P_cond": (
        "pressao condensacao",
        "pressao de condensacao",
        "pressao alta",
        "pressao_alta",
        "p alta",
        "p cond",
        "p_cond",
        "pressao do condensador",
        "p2=p3",
        "p2 = p3",
        "ponto 3 liquido saturado",
        "estado 3 liquido saturado",
    ),
    "P_low": ("p baixa", "pressao baixa", "pressao menor", "p_low", "p_baixa"),
    "P_high": ("p alta", "pressao alta", "pressao maior", "p_high", "p_alta", "p2=p3"),
    "cooling_capacity": (
        "capacidade frigorifica",
        "capacidade refrigeracao",
        "capacidade de refrigeracao",
        "carga termica",
        "carga evaporador",
        "carga_evaporador",
        "carga no evaporador",
        "q evaporador",
        "q_evap",
        "q evap",
        "q_l",
        "ql",
    ),
    "mass_flow": ("vazao massica", "taxa massica", "m dot", "mdot", "m_dot"),
    "eta_comp": ("eficiencia compressor", "eficiencia do compressor", "eta comp", "eta_comp"),
    "superheat": ("superaquecimento", "superheat"),
    "subcooling": ("sub resfriamento", "sub-resfriamento", "subresfriamento", "subcooling"),
    "air_stream": ("corrente de ar", "ar entra", "vazao de ar", "pressao do ar", "temperatura do ar"),
    "air_mass_flow": ("vazao de ar", "vazao do ar", "mdot ar", "m_dot ar"),
    "air_temperature": ("temperatura do ar", "temperatura entrada ar", "t ar"),
    "air_pressure": ("pressao do ar", "p ar"),
    "refrigerant_pressure": ("pressao r134a", "pressao do refrigerante", "p r134a"),
    "refrigerant_quality": ("titulo", "qualidade", "x r134a", "x refrigerante"),
    "P1": ("p1", "pressao entrada", "pressao estado 1"),
    "T1": ("t1", "temperatura entrada", "temperatura estado 1"),
    "P2": ("p2", "pressao saida", "pressao estado 2"),
    "T2_real": ("t2 real", "temperatura saida real", "temperatura estado 2 real"),
    "T_low": ("tl", "t l", "temperatura fria", "reservatorio frio"),
    "T_high": ("th", "t h", "temperatura quente", "reservatorio quente"),
    "Q_L": ("ql", "q_l", "calor reservatorio frio"),
    "Q_H": ("qh", "q_h", "calor reservatorio quente"),
    "W_cycle": ("w ciclo", "wciclo", "w_ciclo", "trabalho ciclo"),
    "fluid": ("fluido", "refrigerante", "agua", "vapor", "r134a", "r22"),
}


def canonical_facts_from_plan(plan: ThermoPlan) -> tuple[ThermoFact, ...]:
    facts: list[ThermoFact] = []
    if plan.fluido:
        facts.append(
            ThermoFact(
                name="fluido",
                canonical_name="fluid",
                value=plan.fluido,
                unit="",
                source="plano",
                raw_text=plan.fluido,
            )
        )

    facts.extend(_facts_from_items(plan.dados_conhecidos, "dados_conhecidos", ""))
    for state in plan.estados:
        facts.extend(_facts_from_items(state.dados_conhecidos, "estado", state.estado, state.descricao))

    return tuple(_dedupe_facts(facts))


def tool_scores(plan: ThermoPlan, facts: Iterable[ThermoFact] | None = None) -> dict[str, int]:
    fact_names = {fact.canonical_name for fact in (tuple(facts) if facts is not None else canonical_facts_from_plan(plan))}
    text = _normalize_text(
        " ".join(
            (
                plan.categoria,
                plan.tipo_problema,
                plan.entrada_oficial,
                plan.interpretacao_imagem,
                " ".join(plan.ferramentas_necessarias),
                " ".join(plan.objetivos),
            )
        )
    )
    scores: dict[str, int] = {}
    for tool_name, spec in TOOL_SPECS.items():
        score = 0
        score += sum(3 for item in spec.required_all if item in fact_names)
        score += sum(2 for group in spec.required_any if any(item in fact_names for item in group))
        score += sum(1 for item in spec.optional if item in fact_names)
        score += sum(2 for alias in spec.aliases if _contains_alias(text, alias))
        score -= sum(5 for forbidden in spec.forbidden_context if _contains_alias(text, forbidden))
        scores[tool_name] = score
    return scores


def tool_readiness(plan: ThermoPlan, tool_name: str, facts: Iterable[ThermoFact] | None = None) -> ToolReadiness:
    fact_tuple = tuple(facts) if facts is not None else canonical_facts_from_plan(plan)
    fact_names = {fact.canonical_name for fact in fact_tuple}
    spec = TOOL_SPECS.get(tool_name)
    if spec is None:
        return ToolReadiness(tool_name, False, ("ferramenta desconhecida",), 0)

    missing = [item for item in spec.required_all if item not in fact_names]
    for group in spec.required_any:
        if not any(item in fact_names for item in group):
            missing.append(" ou ".join(group))

    score = tool_scores(plan, fact_tuple).get(tool_name, 0)
    return ToolReadiness(tool_name, not missing, tuple(missing), score)


def ranked_tool_readiness(plan: ThermoPlan) -> tuple[ToolReadiness, ...]:
    facts = canonical_facts_from_plan(plan)
    readiness = [tool_readiness(plan, tool_name, facts) for tool_name in TOOL_SPECS]
    return tuple(sorted(readiness, key=lambda item: (item.ready, item.score), reverse=True))


def canonical_fact_value(facts: Iterable[ThermoFact], canonical_name: str) -> tuple[float, str] | None:
    for fact in facts:
        if fact.canonical_name != canonical_name:
            continue
        value = _parse_number(fact.value)
        unit = _normalize_unit(fact.unit)
        if value is not None and _unit_compatible_with_canonical(canonical_name, unit):
            return value, unit
    return None


def canonical_fact_lines(plan: ThermoPlan) -> tuple[str, ...]:
    return tuple(
        f"{fact.canonical_name}: {fact.value} {fact.unit}".strip()
        + f" | origem={fact.source}"
        + (f" | estado={fact.state}" if fact.state else "")
        + (f" | bruto={fact.name}" if fact.name != fact.canonical_name else "")
        for fact in canonical_facts_from_plan(plan)
    )


def _facts_from_items(
    items: Iterable[PlannerItem],
    source: str,
    state: str,
    context: str = "",
) -> list[ThermoFact]:
    facts = []
    for item in items:
        canonical = _canonical_name(item, " ".join((state, context)))
        facts.append(
            ThermoFact(
                name=item.nome,
                canonical_name=canonical,
                value=item.valor,
                unit=item.unidade,
                source=source,
                state=state,
                raw_text=" ".join((item.nome, item.valor, item.unidade, item.observacao, context)).strip(),
            )
        )
    return facts


def _canonical_name(item: PlannerItem, context: str = "") -> str:
    text = _normalize_text(" ".join((item.nome, item.observacao, context)))
    name_text = _normalize_text(item.nome)
    unit = _normalize_unit(item.unidade)
    if _is_pressure_unit(unit):
        if any(_contains_alias(name_text, alias) for alias in CANONICAL_ALIASES["P_evap"]):
            return "P_evap"
        if any(_contains_alias(name_text, alias) for alias in CANONICAL_ALIASES["P_cond"]):
            return "P_cond"
        if any(_contains_alias(name_text, alias) for alias in CANONICAL_ALIASES["P_low"]):
            return "P_low"
        if any(_contains_alias(name_text, alias) for alias in CANONICAL_ALIASES["P_high"]):
            return "P_high"
    if _is_temperature_unit(unit):
        if any(_contains_alias(name_text, alias) for alias in CANONICAL_ALIASES["T_evap"]):
            return "T_evap"
        if any(_contains_alias(name_text, alias) for alias in CANONICAL_ALIASES["T_cond"]):
            return "T_cond"
    if _contains_alias(text, "fase") or _contains_alias(text, "titulo") or _contains_alias(text, "qualidade"):
        if _contains_alias(text, "vapor saturado") or _contains_alias(text, "liquido saturado"):
            return "phase"
    if _contains_alias(text, "temperatura") and _contains_alias(text, "1") and _contains_alias(text, "vapor saturado"):
        return "T_evap"
    if _contains_alias(text, "temperatura") and _contains_alias(text, "evaporador"):
        return "T_evap"
    if _contains_alias(text, "pressao") and (_contains_alias(text, "3") or _contains_alias(text, "2")) and _contains_alias(text, "liquido saturado"):
        return "P_cond"
    if _contains_alias(text, "pressao") and _contains_alias(text, "condensador"):
        return "P_cond"
    for canonical, aliases in CANONICAL_ALIASES.items():
        if any(_contains_alias(text, alias) for alias in aliases):
            return canonical
    return text.replace(" ", "_") or item.nome


def _extract_value_near_alias(text: str, aliases: tuple[str, ...]) -> tuple[str, str]:
    for alias in aliases:
        index = text.find(alias)
        if index < 0:
            continue
        window = text[max(0, index - 40) : index + len(alias) + 60]
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?\s*(mpa|kpa|pa|bar|kw|w|c|k|kg/s|kg/min)?", window)
        if match:
            return match.group(0).strip(), match.group(1) or ""
    return "", ""


def _dedupe_facts(facts: Iterable[ThermoFact]) -> list[ThermoFact]:
    seen = set()
    result = []
    for fact in facts:
        key = (fact.canonical_name, fact.state, fact.value, fact.unit)
        if key in seen:
            continue
        seen.add(key)
        result.append(fact)
    return result


def _parse_number(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def _normalize_unit(unit: str) -> str:
    cleaned = unit.strip().replace("°", "").replace(" ", "")
    lower = cleaned.lower()
    if lower == "mpa":
        return "MPa"
    if lower == "kpa":
        return "kPa"
    if lower == "pa":
        return "Pa"
    if lower == "bar":
        return "bar"
    if lower in {"c", "degc", "celsius"}:
        return "C"
    if lower in {"k", "kelvin"}:
        return "K"
    if lower == "kw":
        return "kW"
    if lower == "w":
        return "W"
    if lower in {"kg/s", "kgs"}:
        return "kg/s"
    if lower in {"kg/min", "kgmin"}:
        return "kg/min"
    return cleaned


def _is_pressure_unit(unit: str) -> bool:
    return unit in {"Pa", "kPa", "MPa", "bar"}


def _is_temperature_unit(unit: str) -> bool:
    return unit in {"C", "K", "F"}


def _unit_compatible_with_canonical(canonical_name: str, unit: str) -> bool:
    if canonical_name.startswith("T_"):
        return not unit or _is_temperature_unit(unit)
    if canonical_name.startswith("P_") or canonical_name in {"P1", "P2", "P_low", "P_high"}:
        return not unit or _is_pressure_unit(unit)
    if canonical_name in {"superheat", "subcooling"}:
        return not unit or _is_temperature_unit(unit)
    return True


def _normalize_text(value: str) -> str:
    lowered = value.lower().strip()
    lowered = "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    )
    lowered = lowered.replace("_", " ").replace("-", " ")
    return " ".join(lowered.split())


def _contains_alias(text: str, alias: str) -> bool:
    normalized_alias = _normalize_text(alias)
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])"
    return re.search(pattern, text) is not None

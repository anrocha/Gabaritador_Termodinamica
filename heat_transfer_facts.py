from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from heat_transfer_assistant import HeatTransferPlan, HeatTransferPlanItem


@dataclass(frozen=True)
class CanonicalHeatFact:
    name: str
    value: float
    unit: str
    source: str
    raw_name: str


def canonical_heat_facts(plan: HeatTransferPlan) -> dict[str, CanonicalHeatFact]:
    facts: dict[str, CanonicalHeatFact] = {}
    groups: tuple[tuple[str, tuple[HeatTransferPlanItem, ...]], ...] = (
        ("fatos_canonicos", plan.fatos_canonicos),
        ("dados_conhecidos", plan.dados_conhecidos),
        ("geometria", plan.geometria),
        ("condicoes_contorno", plan.condicoes_contorno),
    )
    for source, items in groups:
        for item in items:
            canonical_name = canonical_heat_name(item)
            if not canonical_name or canonical_name in facts:
                continue
            parsed = parse_heat_value(item)
            if parsed is None:
                continue
            value, unit = parsed
            converted = convert_heat_value(canonical_name, value, unit)
            if converted is None:
                continue
            facts[canonical_name] = CanonicalHeatFact(
                name=canonical_name,
                value=converted,
                unit=unit,
                source=source,
                raw_name=item.nome,
            )
    return facts


def canonical_heat_fact_lines(plan: HeatTransferPlan) -> tuple[str, ...]:
    lines = []
    for fact in canonical_heat_facts(plan).values():
        lines.append(f"{fact.name}: {fact.value:.6g} | unidade original={fact.unit or '-'} | origem={fact.source} | bruto={fact.raw_name}")
    return tuple(lines)


def canonical_heat_name(item: HeatTransferPlanItem) -> str:
    text = normalize_heat_text(" ".join((item.nome, item.observacao)))
    raw_name = normalize_heat_text(item.nome)
    if raw_name in {"k", "condutividade", "condutividade termica"} or "condutividade" in text:
        return "k"
    if raw_name in {"h", "coeficiente h"} or "coeficiente convectivo" in text or ("conveccao" in text and " h " in f" {text} "):
        return "h"
    if raw_name in {"a", "area", "area a"} or text.startswith("area"):
        return "A"
    if raw_name in {"l", "espessura", "thickness", "comprimento"} or "espessura" in text:
        return "L"
    if raw_name in {"p", "perimetro", "perimetro molhado"} or "perimetro" in text:
        return "P"
    if raw_name in {"ac", "a c", "a_c", "area secao", "area da secao"} or "secao transversal" in text:
        return "A_c"
    if raw_name in {"v", "volume"} or "volume" in text:
        return "V"
    if raw_name in {"rho", "densidade"} or "densidade" in text:
        return "rho"
    if raw_name in {"cp", "c p", "c_p", "calor especifico"} or "calor especifico" in text:
        return "c_p"
    if raw_name in {"vel", "velocidade", "velocidade media", "velocity"} or "velocidade" in text:
        return "velocity"
    if raw_name in {"mu", "viscosidade", "viscosidade dinamica"} or "viscosidade dinamica" in text:
        return "mu"
    if raw_name in {"d", "diametro", "diametro hidraulico"} or "diametro" in text:
        return "D"
    if raw_name in {"u", "coeficiente global", "coeficiente global u"} or "coeficiente global" in text:
        return "U"
    if raw_name in {"ua", "u a", "condutancia global"} or "condutancia global" in text or "produto ua" in text:
        return "UA"
    if raw_name in {"f", "fator correcao", "fator de correcao"} or "fator de correcao" in text:
        return "F"
    if raw_name in {"ch", "c h", "c_h", "capacidade quente"} or ("capacidade" in text and "quente" in text):
        return "C_h"
    if raw_name in {"cc", "c c", "c_c", "capacidade fria"} or ("capacidade" in text and "fria" in text):
        return "C_c"
    if raw_name in {"ri", "r i", "r_i", "raio interno"} or "raio interno" in text:
        return "r_i"
    if raw_name in {"ro", "r o", "r_o", "raio externo"} or "raio externo" in text:
        return "r_o"
    if raw_name in {"epsilon", "emissividade"} or "emissividade" in text:
        return "epsilon"
    if raw_name in {"t h in", "th in", "t_h_in", "temperatura quente entrada", "temperatura entrada quente"} or (
        "quente" in text and "entrada" in text
    ):
        return "T_h_in"
    if raw_name in {"t h out", "th out", "t_h_out", "temperatura quente saida", "temperatura saida quente"} or (
        "quente" in text and "saida" in text
    ):
        return "T_h_out"
    if raw_name in {"t c in", "tc in", "t_c_in", "temperatura fria entrada", "temperatura entrada fria"} or (
        "fria" in text and "entrada" in text
    ):
        return "T_c_in"
    if raw_name in {"t c out", "tc out", "t_c_out", "temperatura fria saida", "temperatura saida fria"} or (
        "fria" in text and "saida" in text
    ):
        return "T_c_out"
    if raw_name in {"t hot", "t_hot", "temperatura quente", "temperatura lado quente"} or (
        "quente" in text and "entrada" not in text and "saida" not in text
    ):
        return "T_hot"
    if raw_name in {"t cold", "t_cold", "temperatura fria", "temperatura lado frio"} or (
        "fria" in text and "entrada" not in text and "saida" not in text
    ):
        return "T_cold"
    if raw_name in {"t1", "t 1", "t_1", "temperatura 1"} or "t 1" in text or "temperatura 1" in text:
        return "T_1"
    if raw_name in {"t2", "t 2", "t_2", "temperatura 2"} or "t 2" in text or "temperatura 2" in text:
        return "T_2"
    if raw_name in {"ti", "t i", "t_i", "temperatura interna"} or "temperatura interna" in text:
        return "T_i"
    if raw_name in {"tb", "t b", "t_b", "temperatura base"} or "base" in text:
        return "T_b"
    if raw_name in {"to", "t o", "t_o", "temperatura externa"} or "temperatura externa" in text:
        return "T_o"
    if raw_name in {"ts", "t s", "t_s", "temperatura superficie"} or "superficie" in text:
        return "T_s"
    if raw_name in {"tinf", "t inf", "t_inf", "temperatura ambiente", "temperatura fluido"} or "ambiente" in text or "fluido" in text:
        return "T_inf"
    if raw_name in {"tsur", "t sur", "t_sur", "temperatura vizinhanca"} or "vizinhanca" in text:
        return "T_sur"
    if raw_name in {"t", "tempo"} or "tempo" in text:
        return "t"
    return ""


def parse_heat_value(item: HeatTransferPlanItem) -> tuple[float, str] | None:
    text = f"{item.valor} {item.unidade}".strip()
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", text)
    if not match:
        return None
    value = float(match.group(0).replace(",", "."))
    unit = normalize_heat_unit(item.unidade or text[match.end() :])
    return value, unit


def convert_heat_value(canonical_name: str, value: float, unit: str) -> float | None:
    if canonical_name.startswith("T_"):
        if unit in {"k", "kelvin"}:
            return value - 273.15
        if unit in {"c", "oc", "celsius", "grausc", ""}:
            return value
        return None
    if canonical_name in {"L", "r_i", "r_o", "P", "D"}:
        if unit in {"mm", "milimetro", "milimetros"}:
            return value / 1000.0
        if unit in {"cm", "centimetro", "centimetros"}:
            return value / 100.0
        if unit in {"m", "metro", "metros", ""}:
            return value
        return None
    if canonical_name in {"A", "A_c"}:
        if unit in {"mm2", "mm^2"}:
            return value / 1_000_000.0
        if unit in {"cm2", "cm^2"}:
            return value / 10_000.0
        if unit in {"m2", "m^2", ""}:
            return value
        return None
    if canonical_name == "V":
        if unit in {"cm3", "cm^3"}:
            return value / 1_000_000.0
        if unit in {"m3", "m^3", ""}:
            return value
        return None
    if canonical_name == "c_p":
        if unit in {"kj/kgk", "kj/(kg.k)", "kj/kg.k"}:
            return value * 1000.0
        if unit in {"j/kgk", "j/(kg.k)", "j/kg.k", ""}:
            return value
        return None
    if canonical_name == "t":
        if unit in {"min", "minuto", "minutos"}:
            return value * 60.0
        if unit in {"h", "hr", "hora", "horas"}:
            return value * 3600.0
        if unit in {"s", "segundo", "segundos", ""}:
            return value
        return None
    if canonical_name in {"C_h", "C_c", "UA"}:
        if unit in {"kw/k", "kwk"}:
            return value * 1000.0
        if unit in {"w/k", "wk", ""}:
            return value
        return None
    if canonical_name == "mu":
        if unit in {"mpa.s", "mpas"}:
            return value / 1000.0
        if unit in {"pa.s", "pas", "kg/ms", ""}:
            return value
        return None
    if canonical_name in {"k", "h", "U", "F", "epsilon", "rho", "velocity"}:
        return value
    return value


def normalize_heat_text(value: str) -> str:
    lowered = value.lower().strip()
    lowered = "".join(char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char))
    return " ".join(lowered.replace("_", " ").replace("-", " ").split())


def normalize_heat_unit(value: str) -> str:
    normalized = normalize_heat_text(value)
    return (
        normalized.replace("°", "")
        .replace("²", "2")
        .replace("³", "3")
        .replace(" ", "")
        .replace("w/(m.k)", "w/mk")
        .replace("w/(m2.k)", "w/m2k")
    )

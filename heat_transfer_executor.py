from __future__ import annotations

from heat_transfer_assistant import HeatTransferPlan
from heat_transfer_catalog import HEAT_TRANSFER_TOOLS, supported_tool_names
from heat_transfer_core import (
    HeatTransferCalculationError,
    HeatTransferResult,
    calculate_parallel_resistance_network,
    calculate_convection,
    calculate_cylinder_conduction,
    calculate_dittus_boelter_forced_convection,
    calculate_lmtd_heat_exchanger,
    calculate_lumped_capacitance,
    calculate_ntu_heat_exchanger,
    calculate_plane_conduction,
    calculate_radiation,
    calculate_sphere_conduction,
    calculate_straight_fin_adiabatic_tip,
    calculate_series_resistance_network,
)
from heat_transfer_quickwin import (
    calculate_external_flat_plate_convection,
    calculate_concentric_tube_vapor_heat_exchange,
    calculate_finned_surface_plate,
    calculate_internal_tube_convection,
    calculate_plane_transient_bidirectional,
    calculate_solar_plate_balance,
)
from heat_transfer_facts import CanonicalHeatFact, canonical_heat_facts, normalize_heat_text


def execute_heat_transfer_plan(plan: HeatTransferPlan) -> HeatTransferResult:
    facts = canonical_heat_facts(plan)
    tool = main_heat_transfer_tool(plan)
    if tool == "conducao_plana_1d":
        return calculate_plane_conduction(
            _required(facts, "k"),
            _required(facts, "A"),
            _required(facts, "L"),
            _required(facts, "T_1"),
            _required(facts, "T_2"),
        )
    if tool == "conducao_radial_cilindro":
        return calculate_cylinder_conduction(
            _required(facts, "k"),
            _required(facts, "L"),
            _required(facts, "r_i"),
            _required(facts, "r_o"),
            _required_any(facts, ("T_i", "T_1")),
            _required_any(facts, ("T_o", "T_2")),
        )
    if tool == "conducao_radial_esfera":
        return calculate_sphere_conduction(
            _required(facts, "k"),
            _required(facts, "r_i"),
            _required(facts, "r_o"),
            _required_any(facts, ("T_i", "T_1")),
            _required_any(facts, ("T_o", "T_2")),
        )
    if tool == "conveccao_newton":
        return calculate_convection(
            _required(facts, "h"),
            _required(facts, "A"),
            _required(facts, "T_s"),
            _required(facts, "T_inf"),
        )
    if tool == "radiacao_superficie_vizinhanca":
        return calculate_radiation(
            _required(facts, "epsilon"),
            _required(facts, "A"),
            _required(facts, "T_s"),
            _required(facts, "T_sur"),
        )
    if tool == "rede_resistencias_serie":
        return calculate_series_resistance_network(
            _resistance_list_from_plan(plan),
            _required_any(facts, ("T_hot", "T_1", "T_i", "T_s")),
            _required_any(facts, ("T_cold", "T_2", "T_o", "T_inf", "T_sur")),
        )
    if tool == "rede_resistencias_paralelo":
        return calculate_parallel_resistance_network(
            _resistance_list_from_plan(plan),
            _required_any(facts, ("T_hot", "T_1", "T_i", "T_s")),
            _required_any(facts, ("T_cold", "T_2", "T_o", "T_inf", "T_sur")),
        )
    if tool == "aleta_reta_ponta_adiabatica":
        return calculate_straight_fin_adiabatic_tip(
            _required(facts, "h"),
            _perimeter_from_plan(plan, facts),
            _required(facts, "k"),
            _cross_section_area_from_plan(plan, facts),
            _required(facts, "L"),
            _required_any(facts, ("T_b", "T_s", "T_1")),
            _required(facts, "T_inf"),
        )
    if tool == "aleta_superficie_aletada":
        return calculate_finned_surface_plate(
            _required(facts, "h"),
            _perimeter_from_plan(plan, facts),
            _required(facts, "k"),
            _cross_section_area_from_plan(plan, facts),
            _required(facts, "L"),
            _required_any(facts, ("A_base", "A")),
            _required_any(facts, ("N",)),
            _required_any(facts, ("T_b", "T_s", "T_1")),
            _required(facts, "T_inf"),
        )
    if tool == "capacitancia_concentrada":
        return calculate_lumped_capacitance(
            _required(facts, "h"),
            _required(facts, "A"),
            _required(facts, "rho"),
            _required(facts, "V"),
            _required(facts, "c_p"),
            _required(facts, "k"),
            _required(facts, "T_i"),
            _required(facts, "T_inf"),
            _required(facts, "t"),
        )
    if tool == "trocador_lmtd":
        return calculate_lmtd_heat_exchanger(
            _required(facts, "U"),
            _required(facts, "A"),
            _required(facts, "T_h_in"),
            _required(facts, "T_h_out"),
            _required(facts, "T_c_in"),
            _required(facts, "T_c_out"),
            _flow_type_from_plan(plan),
            _optional(facts, "F", 1.0),
        )
    if tool == "trocador_ntu":
        return calculate_ntu_heat_exchanger(
            _required(facts, "C_h"),
            _required(facts, "C_c"),
            _required(facts, "UA"),
            _required(facts, "T_h_in"),
            _required(facts, "T_c_in"),
            _flow_type_from_plan(plan),
        )
    if tool == "conveccao_forcada_dittus_boelter":
        return calculate_dittus_boelter_forced_convection(
            _required(facts, "rho"),
            _required(facts, "velocity"),
            _required(facts, "D"),
            _required(facts, "mu"),
            _required(facts, "c_p"),
            _required(facts, "k"),
            _heating_mode_from_plan(plan),
        )
    if tool == "conveccao_placa_plana_externa":
        return calculate_external_flat_plate_convection(
            _fluid_from_plan(plan, default="Air"),
            _required(facts, "V"),
            _required(facts, "L"),
            _required(facts, "W"),
            _required_any(facts, ("T_s", "T_1")),
            _required_any(facts, ("T_inf", "T_2")),
            _optional(facts, "pressure", 101325.0),
        )
    if tool == "conveccao_interna_tubo_iterativa":
        return calculate_internal_tube_convection(
            _fluid_from_plan(plan, default="Water"),
            _required(facts, "D"),
            _required(facts, "L"),
            _required(facts, "V"),
            _required_any(facts, ("T_in", "T_1")),
            _required_any(facts, ("T_w", "T_s", "T_2")),
            _optional(facts, "pressure", 101325.0),
        )
    if tool == "trocador_tubo_concentrico_vapor":
        return calculate_concentric_tube_vapor_heat_exchange(
            _fluid_from_plan(plan, default="Water"),
            _diameter_value(facts, ("D_i", "D"), "r_i"),
            _diameter_value(facts, ("D_o", "D_out", "D_ext"), "r_o"),
            _required(facts, "L"),
            _required(facts, "V"),
            _required_any(facts, ("T_in", "T_1")),
            _required_any(facts, ("T_steam", "T_hot", "T_s")),
            _required(facts, "k"),
            _optional(facts, "pressure", 101325.0),
        )
    if tool == "conducao_transiente_placa":
        return calculate_plane_transient_bidirectional(
            _required(facts, "k"),
            _required(facts, "rho"),
            _required(facts, "cp"),
            _required(facts, "L"),
            _required(facts, "A"),
            _required(facts, "h"),
            _required_any(facts, ("T_i", "T_1")),
            _required(facts, "T_inf"),
            _required(facts, "t"),
        )
    if tool == "asa_plana_radiacao_solar":
        return calculate_solar_plate_balance(
            _fluid_from_plan(plan, default="Air"),
            _required(facts, "V"),
            _required(facts, "L"),
            _required(facts, "W"),
            _required(facts, "q_solar"),
            _required(facts, "T_inf"),
            _optional(facts, "pressure", 101325.0),
        )
    raise HeatTransferCalculationError(
        "Ainda não há executor determinístico para a ferramenta planejada. "
        "Use uma ferramenta manual da Fase 1 ou ajuste o enunciado para condução, convecção ou radiação simples."
    )


def main_heat_transfer_tool(plan: HeatTransferPlan) -> str:
    joined = normalize_heat_text(
        " ".join(
            (
                plan.tipo_problema,
                plan.categoria,
                " ".join(plan.objetivos),
                " ".join(plan.ferramentas_necessarias),
                plan.entrada_oficial,
                plan.diagnostico_entrada,
            )
        )
    )
    normalized_tools = tuple(normalize_heat_text(item) for item in plan.ferramentas_necessarias)
    tool_scores = {tool.name: _heat_transfer_tool_score(tool, joined, normalized_tools) for tool in HEAT_TRANSFER_TOOLS}
    ranked_tools = sorted(tool_scores.items(), key=lambda item: (item[1], item[0]), reverse=True)

    if "aleta" in joined or "fin" in joined:
        if "base" in joined or "superficie" in joined or "numero" in joined or "quantidade" in joined or "aletas" in joined:
            return "aleta_superficie_aletada"
        return "aleta_reta_ponta_adiabatica"

    if "tubo" in joined and ("vapor" in joined or "steam" in joined or "condens" in joined):
        return "trocador_tubo_concentrico_vapor"

    if ranked_tools and ranked_tools[0][1] >= 4:
        best_tool = ranked_tools[0][0]
        if best_tool in supported_tool_names():
            return best_tool

    for supported_tool in supported_tool_names():
        normalized_supported = normalize_heat_text(supported_tool)
        if any(normalized_supported in tool for tool in normalized_tools):
            return supported_tool

    if "cilind" in joined:
        return "conducao_radial_cilindro"
    if "esfer" in joined:
        return "conducao_radial_esfera"
    if "transiente" in joined or "capacitancia" in joined or "biot" in joined:
        return "capacitancia_concentrada"
    if ("resist" in joined or "rede" in joined or "parede composta" in joined) and "paralel" in joined:
        return "rede_resistencias_paralelo"
    if "resist" in joined or "rede" in joined or "parede composta" in joined or "serie" in joined:
        return "rede_resistencias_serie"
    if "ntu" in joined or "efetividade" in joined:
        return "trocador_ntu"
    if "lmtd" in joined or "dtlm" in joined or "media logaritmica" in joined or "diferenca media logaritmica" in joined:
        return "trocador_lmtd"
    if "solar" in joined or "asa" in joined:
        return "asa_plana_radiacao_solar"
    if "placa plana" in joined or ("placa" in joined and "extern" in joined) or ("ar" in joined and "superficie plana" in joined):
        return "conveccao_placa_plana_externa"
    if "tubo" in joined and ("entrada" in joined or "saida" in joined or "pressao" in joined or "water" in joined or "agua" in joined):
        return "conveccao_interna_tubo_iterativa"
    if "transiente" in joined or "capacitancia" in joined or "biot" in joined or "fo" in joined:
        return "conducao_transiente_placa"
    if "dittus" in joined or "boelter" in joined or "nusselt" in joined or "reynolds" in joined or "prandtl" in joined:
        return "conveccao_forcada_dittus_boelter"
    if "convecc" in joined:
        return "conveccao_newton"
    if "radiac" in joined:
        return "radiacao_superficie_vizinhanca"
    if "conduc" in joined or "parede" in joined:
        return "conducao_plana_1d"
    return ranked_tools[0][0] if ranked_tools and ranked_tools[0][1] > 0 else ""


def _heat_transfer_tool_score(tool, joined: str, normalized_tools: tuple[str, ...]) -> int:
    score = 0
    name_tokens = normalize_heat_text(tool.name)
    label_tokens = normalize_heat_text(tool.label)
    category_tokens = normalize_heat_text(tool.category)
    description_tokens = normalize_heat_text(tool.description)

    if any(token and token in joined for token in (name_tokens, label_tokens, category_tokens)):
        score += 4
    if any(token in joined for token in description_tokens.split()[:8]):
        score += 1
    for hint in tool.selection_hints:
        if normalize_heat_text(hint) in joined:
            score += 3
    for required in tool.required:
        normalized_required = normalize_heat_text(required)
        if required in {"k", "h", "A", "A_c", "A_base", "P", "L", "T_1", "T_2", "T_s", "T_inf", "T_sur"} and normalized_required in joined:
            score += 1
    if any(normalize_heat_text(tool.name) in text for text in normalized_tools):
        score += 5
    return score


def _required(facts: dict[str, CanonicalHeatFact], name: str) -> float:
    if name not in facts:
        raise HeatTransferCalculationError(f"Dado necessário ausente: {name}.")
    return facts[name].value


def _required_any(facts: dict[str, CanonicalHeatFact], names: tuple[str, ...]) -> float:
    for name in names:
        if name in facts:
            return facts[name].value
    raise HeatTransferCalculationError(f"Dado necessário ausente: {' ou '.join(names)}.")


def _optional(facts: dict[str, CanonicalHeatFact], name: str, default: float) -> float:
    return facts[name].value if name in facts else default


def _perimeter_from_plan(plan: HeatTransferPlan, facts: dict[str, CanonicalHeatFact]) -> float:
    if "P" in facts:
        return facts["P"].value
    side = _square_section_side_from_plan(plan)
    if side is not None:
        return 4.0 * side
    raise HeatTransferCalculationError("Dado necessário ausente: P.")


def _cross_section_area_from_plan(plan: HeatTransferPlan, facts: dict[str, CanonicalHeatFact]) -> float:
    if "A_c" in facts:
        return facts["A_c"].value
    side = _square_section_side_from_plan(plan)
    if side is not None:
        return side * side
    raise HeatTransferCalculationError("Dado necessário ausente: A_c.")


def _square_section_side_from_plan(plan: HeatTransferPlan) -> float | None:
    candidates = tuple(plan.geometria) + tuple(plan.dados_conhecidos) + tuple(plan.fatos_canonicos)
    for item in candidates:
        text = normalize_heat_text(" ".join((item.nome, item.valor, item.unidade, item.observacao)))
        if "quadrada" not in text and "4 x 4" not in text and "4x4" not in text:
            continue
        numbers = _numbers_from_text(f"{item.valor} {item.unidade} {item.observacao} {item.nome}")
        if len(numbers) >= 2 and abs(numbers[0] - numbers[1]) < 1e-9:
            side = numbers[0]
            unit = normalize_heat_text(item.unidade)
            if unit in {"mm", "milimetro", "milimetros"}:
                return side / 1000.0
            if unit in {"cm", "centimetro", "centimetros"}:
                return side / 100.0
            if unit in {"m", "metro", "metros", ""}:
                return side
        if len(numbers) == 1 and "quadrada" in text:
            side = numbers[0]
            unit = normalize_heat_text(item.unidade)
            if unit in {"mm", "milimetro", "milimetros"}:
                return side / 1000.0
            if unit in {"cm", "centimetro", "centimetros"}:
                return side / 100.0
            if unit in {"m", "metro", "metros", ""}:
                return side
    return None


def _diameter_value(facts: dict[str, CanonicalHeatFact], diameter_names: tuple[str, ...], radius_name: str) -> float:
    for diameter_name in diameter_names:
        if diameter_name in facts:
            return facts[diameter_name].value
    if radius_name in facts:
        return 2.0 * facts[radius_name].value
    raise HeatTransferCalculationError(f"Dado necessário ausente: {' ou '.join((*diameter_names, radius_name))}.")


def _fluid_from_plan(plan: HeatTransferPlan, default: str = "Air") -> str:
    text = normalize_heat_text(
        " ".join(
            (
                plan.tipo_problema,
                plan.categoria,
                " ".join(plan.objetivos),
                " ".join(plan.ferramentas_necessarias),
                plan.entrada_oficial,
                plan.diagnostico_entrada,
            )
        )
    )
    if "water" in text or "agua" in text:
        return "Water"
    if "air" in text or "ar" in text:
        return "Air"
    return default


def _flow_type_from_plan(plan: HeatTransferPlan) -> str:
    joined = normalize_heat_text(
        " ".join(
            (
                plan.tipo_problema,
                plan.categoria,
                " ".join(plan.objetivos),
                " ".join(plan.ferramentas_necessarias),
                plan.entrada_oficial,
                plan.diagnostico_entrada,
            )
        )
    )
    if "paralel" in joined:
        return "paralelo"
    if "contra" in joined or "contracorr" in joined or "contraflux" in joined:
        return "contracorrente"
    raise HeatTransferCalculationError("Dado necessário ausente: tipo de escoamento do trocador (paralelo ou contracorrente).")


def _heating_mode_from_plan(plan: HeatTransferPlan) -> str:
    joined = normalize_heat_text(
        " ".join(
            (
                plan.tipo_problema,
                plan.categoria,
                " ".join(plan.objetivos),
                " ".join(plan.ferramentas_necessarias),
                plan.entrada_oficial,
                plan.diagnostico_entrada,
            )
        )
    )
    if "resfri" in joined or "cool" in joined:
        return "resfriamento"
    if "aquec" in joined or "heat" in joined:
        return "aquecimento"
    raise HeatTransferCalculationError("Dado necessário ausente: modo térmico para Dittus-Boelter (aquecimento ou resfriamento do fluido).")


def _resistance_list_from_plan(plan: HeatTransferPlan) -> tuple[float, ...]:
    values: list[float] = []
    items = plan.fatos_canonicos + plan.dados_conhecidos + plan.geometria + plan.condicoes_contorno
    for item in items:
        text = normalize_heat_text(" ".join((item.nome, item.observacao)))
        if "resist" not in text and not normalize_heat_text(item.nome).startswith("r"):
            continue
        numbers = _numbers_from_text(f"{item.valor} {item.unidade}")
        if numbers:
            values.extend(numbers)
    if not values:
        raise HeatTransferCalculationError("Dado necessário ausente: lista de resistências térmicas em K/W.")
    return tuple(values)


def _numbers_from_text(text: str) -> list[float]:
    import re

    return [float(match.replace(",", ".")) for match in re.findall(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", text)]

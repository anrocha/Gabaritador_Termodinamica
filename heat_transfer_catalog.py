from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeatTransferToolSpec:
    name: str
    label: str
    category: str
    required: tuple[str, ...]
    outputs: tuple[str, ...]
    description: str


HEAT_TRANSFER_TOOLS: tuple[HeatTransferToolSpec, ...] = (
    HeatTransferToolSpec(
        name="conducao_plana_1d",
        label="Condução plana 1D",
        category="condução",
        required=("k", "A", "L", "T_1", "T_2"),
        outputs=("R_cond", "q_dot", "q_flux"),
        description="Parede plana estacionária com condução unidimensional.",
    ),
    HeatTransferToolSpec(
        name="conducao_radial_cilindro",
        label="Condução radial em cilindro",
        category="condução",
        required=("k", "L", "r_i", "r_o", "T_i|T_1", "T_o|T_2"),
        outputs=("R_cil", "q_dot"),
        description="Parede cilíndrica ou tubo com condução radial estacionária.",
    ),
    HeatTransferToolSpec(
        name="conducao_radial_esfera",
        label="Condução radial em esfera",
        category="condução",
        required=("k", "r_i", "r_o", "T_i|T_1", "T_o|T_2"),
        outputs=("R_esf", "q_dot"),
        description="Casca esférica com condução radial estacionária.",
    ),
    HeatTransferToolSpec(
        name="conveccao_newton",
        label="Convecção",
        category="convecção",
        required=("h", "A", "T_s", "T_inf"),
        outputs=("R_conv", "q_dot"),
        description="Lei de Newton do resfriamento para superfície em contato com fluido.",
    ),
    HeatTransferToolSpec(
        name="radiacao_superficie_vizinhanca",
        label="Radiação superfície-vizinhança",
        category="radiação",
        required=("epsilon", "A", "T_s", "T_sur"),
        outputs=("q_dot_rad",),
        description="Troca radiativa entre superfície cinzenta e vizinhança grande.",
    ),
    HeatTransferToolSpec(
        name="rede_resistencias_serie",
        label="Rede de resistências em série",
        category="resistências térmicas",
        required=("R_list", "T_hot", "T_cold"),
        outputs=("R_eq", "q_dot"),
        description="Rede térmica com resistências em série entre dois níveis de temperatura.",
    ),
    HeatTransferToolSpec(
        name="rede_resistencias_paralelo",
        label="Rede de resistências em paralelo",
        category="resistências térmicas",
        required=("R_list", "T_hot", "T_cold"),
        outputs=("R_eq", "q_dot", "q_dot_i"),
        description="Rede térmica com ramos paralelos entre os mesmos nós quente e frio.",
    ),
    HeatTransferToolSpec(
        name="aleta_reta_ponta_adiabatica",
        label="Aleta reta - ponta adiabática",
        category="aletas",
        required=("h", "P", "k", "A_c", "L", "T_b", "T_inf"),
        outputs=("m", "A_f", "eta_f", "epsilon_f", "q_dot_fin"),
        description="Aleta reta de seção constante com ponta adiabática.",
    ),
    HeatTransferToolSpec(
        name="capacitancia_concentrada",
        label="Capacitância concentrada",
        category="transiente",
        required=("h", "A", "rho", "V", "c_p", "k", "T_i", "T_inf", "t"),
        outputs=("L_c", "Bi", "tau", "T_t", "Q"),
        description="Transiente lumped com validação obrigatória Bi < 0,1.",
    ),
    HeatTransferToolSpec(
        name="trocador_lmtd",
        label="Trocador de calor por LMTD",
        category="trocadores",
        required=("U", "A", "T_h_in", "T_h_out", "T_c_in", "T_c_out", "flow_type"),
        outputs=("Delta_T_1", "Delta_T_2", "Delta_T_lm", "q_dot"),
        description="Trocador de calor em regime permanente resolvido pela diferença média logarítmica de temperatura.",
    ),
    HeatTransferToolSpec(
        name="trocador_ntu",
        label="Trocador por Efetividade-NTU",
        category="trocadores",
        required=("C_h", "C_c", "UA", "T_h_in", "T_c_in", "flow_type"),
        outputs=("C_min", "C_r", "NTU", "epsilon_hx", "q_dot", "T_h_out", "T_c_out"),
        description="Trocador de calor resolvido por efetividade-NTU com correntes paralelas ou contracorrentes.",
    ),
    HeatTransferToolSpec(
        name="conveccao_forcada_dittus_boelter",
        label="Convecção forçada — Dittus-Boelter",
        category="correlações",
        required=("rho", "velocity", "D", "mu", "c_p", "k", "mode"),
        outputs=("Re", "Pr", "Nu", "h"),
        description="Correlação Dittus-Boelter para escoamento interno turbulento em tubo liso.",
    ),
    HeatTransferToolSpec(
        name="conveccao_placa_plana_externa",
        label="Convecção externa em placa plana",
        category="convecção",
        required=("fluid", "V", "L", "W", "T_s", "T_inf"),
        outputs=("Re_L", "Pr", "Nu_L", "h", "q_dot"),
        description="Convecção externa em placa plana com seleção de regime laminar, turbulento ou misto.",
    ),
    HeatTransferToolSpec(
        name="conveccao_interna_tubo_iterativa",
        label="Convecção interna em tubo iterativa",
        category="convecção",
        required=("fluid", "D", "L", "V", "T_in", "T_w"),
        outputs=("mdot", "Re", "Pr", "Nu", "h", "T_out", "q_dot", "delta_p"),
        description="Convecção interna em tubo com propriedades iteradas na temperatura média e queda de pressão estimada.",
    ),
    HeatTransferToolSpec(
        name="conducao_transiente_placa",
        label="Condução transiente em placa",
        category="transiente",
        required=("k", "rho", "cp", "L", "A", "h", "T_i", "T_inf", "t"),
        outputs=("L_c", "Bi", "Fo", "T_center", "T_surface", "Q"),
        description="Placa plana resfriada dos dois lados com critério de Biot e fallback para solução distribuída.",
    ),
    HeatTransferToolSpec(
        name="asa_plana_radiacao_solar",
        label="Asa/placa plana com radiação solar",
        category="convecção externa",
        required=("fluid", "V", "L", "W", "q_solar", "T_inf"),
        outputs=("h", "T_s", "q_dot"),
        description="Asa ou placa plana aquecida por radiação solar e resfriada por convecção nas duas faces.",
    ),
    HeatTransferToolSpec(
        name="aleta_superficie_aletada",
        label="Superficie aletada em placa",
        category="aletas",
        required=("h", "P", "k", "A_c", "L", "A_base", "N", "T_b", "T_inf"),
        outputs=("m", "A_f", "eta_f", "A_base_exp", "q_dot_fin", "q_total", "q_sem_aletas", "eta_o", "epsilon_o", "ganho_percentual"),
        description="Placa aletada com N aletas retas, area da base exposta e ganho global de transferencia de calor.",
    ),
    HeatTransferToolSpec(
        name="trocador_tubo_concentrico_vapor",
        label="Tubo concentric com vapor",
        category="trocadores",
        required=("fluid", "D_i", "D_o", "L", "V", "T_in", "T_steam", "k"),
        outputs=("R_cond", "T_wi", "h_i", "q_dot", "T_out", "R_th", "A_i"),
        description="Tubo concentric aquecido por vapor quase isotermo, acoplando conducao cilindrica e conveccao interna.",
    ),
)


def supported_tool_names() -> tuple[str, ...]:
    return tuple(tool.name for tool in HEAT_TRANSFER_TOOLS)


def get_tool_spec(name: str) -> HeatTransferToolSpec | None:
    normalized_name = name.strip().lower()
    return next((tool for tool in HEAT_TRANSFER_TOOLS if tool.name == normalized_name), None)


def heat_transfer_tool_catalog_prompt() -> str:
    lines = []
    for tool in HEAT_TRANSFER_TOOLS:
        required = ", ".join(tool.required)
        outputs = ", ".join(tool.outputs)
        lines.append(f"- {tool.name}: {tool.description} Entradas: {required}. Saídas: {outputs}.")
    return "\n".join(lines)

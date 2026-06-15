from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThermoTool:
    name: str
    description: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    diagrams: tuple[str, ...] = ()
    selection_hints: tuple[str, ...] = ()


THERMO_TOOLS = (
    ThermoTool(
        name="estado_por_tp",
        description="Calcula propriedades de um fluido a partir de temperatura e pressao.",
        inputs=("fluido", "temperatura", "pressao"),
        outputs=("h", "s", "u", "v", "rho", "cp", "cv", "fase", "titulo quando aplicavel"),
        selection_hints=("par de T e P", "propriedades de ponto", "estado simples"),
    ),
    ThermoTool(
        name="estado_por_par",
        description="Calcula um estado termodinamico a partir de duas propriedades independentes.",
        inputs=("fluido", "propriedade 1", "valor 1", "propriedade 2", "valor 2"),
        outputs=("T", "P", "h", "s", "u", "v", "rho", "fase", "titulo quando aplicavel"),
        selection_hints=("duas propriedades independentes", "estado geral", "propriedades de ponto"),
    ),
    ThermoTool(
        name="titulo_mistura",
        description="Calcula titulo em mistura saturada por interpolacao usando T_sat ou P_sat.",
        inputs=("fluido", "restricao de saturacao", "propriedade conhecida"),
        outputs=("x", "propriedades de liquido saturado", "propriedades de vapor saturado"),
        selection_hints=("mistura saturada", "qualidade", "titulo", "liquido + vapor"),
    ),
    ThermoTool(
        name="ciclo_refrigeracao_simples",
        description="Resolve ciclo de compressao de vapor simples para R22 ou R134a por T_evap/T_cond ou P_evap/P_cond. Use para ciclo fechado de refrigeracao; nao use para agua/vapor nem para trocador com ar como corrente separada.",
        inputs=("fluido", "T_evap", "T_cond", "superaquecimento", "sub-resfriamento", "eta_comp", "capacidade opcional"),
        outputs=("estados 1, 2s, 2, 3, 4", "COP", "potencia do compressor", "vazao massica"),
        diagrams=("P-h",),
        selection_hints=("ciclo fechado", "compressao de vapor", "R22", "R134a", "evaporador/condensador"),
    ),
    ThermoTool(
        name="ciclo_refrigeracao_padrao_pressao",
        description="Resolve ciclo padrao ideal de compressao de vapor com estados 1-2-3-4, duas pressoes, vazao massica, estado 1 vapor saturado, estado 3 liquido saturado, s1=s2 e h4=h3.",
        inputs=("fluido", "P_baixa", "P_alta", "vazao massica"),
        outputs=("QL", "W compressor", "x4", "QH", "COP", "estados 1, 2, 3, 4"),
        diagrams=("T-s",),
        selection_hints=("ciclo padrao", "s1=s2", "h4=h3", "duas pressoes", "vapor saturado", "liquido saturado"),
    ),
    ThermoTool(
        name="turbina_vapor_adiabatica",
        description="Resolve turbina isolada em regime permanente com agua/vapor.",
        inputs=("P1", "T1", "P2", "vazao massica", "T2 real opcional"),
        outputs=("h1", "s1", "h2s", "T2s", "x2s", "potencia maxima", "h2 real", "s2 real", "eta_t"),
        diagrams=("T-s",),
        selection_hints=("turbina", "vapor de agua", "vazao massica", "potencia", "expansao"),
    ),
    ThermoTool(
        name="evaporador_ar_refrigerante",
        description="Resolve evaporador/trocador com ar ideal como corrente separada e R134a em mistura saturada. Use somente quando o enunciado trouxer ar com dados proprios, como vazao, pressao ou temperatura.",
        inputs=("T_ar_in", "P_ar", "mdot_ar", "P_R134a", "x_R134a_in", "mdot_R134a", "Qdot externo opcional"),
        outputs=("T_ar_out", "propriedades do R134a", "Sgen isolado", "Sgen com calor externo"),
        selection_hints=("evaporador", "ar como corrente separada", "balanco de energia", "R134a", "troca de calor"),
    ),
    ThermoTool(
        name="refrigerador_reservatorios",
        description="Resolve refrigerador entre reservatorios termicos por balanco de energia, COP e segunda lei.",
        inputs=("TL", "TH", "QL", "QH", "Wciclo"),
        outputs=("grandeza faltante por energia", "COP", "COP_Carnot", "DeltaS_univ", "classificacao"),
        selection_hints=("reservatorios", "cop", "carnot", "segunda lei", "delta s"),
    ),
)


def tool_catalog_prompt() -> str:
    lines = ["Ferramentas deterministicas disponiveis no projeto:"]
    for tool in THERMO_TOOLS:
        lines.append(f"- {tool.name}: {tool.description}")
        lines.append(f"  Entradas: {', '.join(tool.inputs)}.")
        lines.append(f"  Saidas calculaveis: {', '.join(tool.outputs)}.")
        if tool.diagrams:
            lines.append(f"  Diagramas: {', '.join(tool.diagrams)}.")
        if tool.selection_hints:
            lines.append(f"  Gatilhos de selecao: {', '.join(tool.selection_hints)}.")
    return "\n".join(lines)

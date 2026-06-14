from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from tool_catalog import tool_catalog_prompt


@dataclass(frozen=True)
class AssistantDraft:
    problem_type: str = ""
    fluid: str = ""
    cycle_type: str = ""
    known_values: dict[str, Any] = field(default_factory=dict)
    requested_outputs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    missing_data: tuple[str, ...] = ()
    states: tuple[dict[str, Any], ...] = ()
    confidence: float = 0
    explanation_plan: tuple[str, ...] = ()
    raw_text: str = ""


@dataclass(frozen=True)
class PlannerItem:
    nome: str
    valor: str
    unidade: str
    observacao: str = ""


@dataclass(frozen=True)
class PlannedState:
    estado: str
    descricao: str
    dados_conhecidos: tuple[PlannerItem, ...] = ()
    propriedades_a_calcular: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlannedQuestion:
    item: str
    enunciado: str
    objetivo: str
    ferramentas_necessarias: tuple[str, ...] = ()
    propriedades_a_calcular: tuple[str, ...] = ()
    resultado_esperado: str = ""


@dataclass(frozen=True)
class ThermoPlan:
    categoria: str = ""
    tipo_problema: str = ""
    fluido: str = ""
    interpretacao_imagem: str = ""
    texto_usuario: str = ""
    entrada_oficial: str = ""
    diagnostico_entrada: str = ""
    ferramentas_necessarias: tuple[str, ...] = ()
    dados_conhecidos: tuple[PlannerItem, ...] = ()
    propriedades_a_calcular: tuple[str, ...] = ()
    dados_faltantes: tuple[str, ...] = ()
    estados: tuple[PlannedState, ...] = ()
    hipoteses: tuple[str, ...] = ()
    objetivos: tuple[str, ...] = ()
    questoes: tuple[PlannedQuestion, ...] = ()
    diagramas: tuple[str, ...] = ()
    plano_execucao: tuple[str, ...] = ()
    confianca: float = 0
    raw_text: str = ""


ASSISTANT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "problem_type": {"type": "string"},
        "fluid": {"type": "string"},
        "cycle_type": {"type": "string"},
        "known_values": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "evaporating_temperature_c": {"type": ["number", "null"]},
                "condensing_temperature_c": {"type": ["number", "null"]},
                "superheat_k": {"type": ["number", "null"]},
                "subcooling_k": {"type": ["number", "null"]},
                "compressor_efficiency": {"type": ["number", "null"]},
                "cooling_capacity_kw": {"type": ["number", "null"]},
                "cooling_capacity_w": {"type": ["number", "null"]},
                "evaporating_pressure_bar": {"type": ["number", "null"]},
                "condensing_pressure_bar": {"type": ["number", "null"]},
            },
            "required": [
                "evaporating_temperature_c",
                "condensing_temperature_c",
                "superheat_k",
                "subcooling_k",
                "compressor_efficiency",
                "cooling_capacity_kw",
                "cooling_capacity_w",
                "evaporating_pressure_bar",
                "condensing_pressure_bar",
            ],
        },
        "requested_outputs": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "states": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "point": {"type": "string"},
                    "description": {"type": "string"},
                    "known_properties": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["point", "description", "known_properties"],
            },
        },
        "confidence": {"type": "number"},
        "explanation_plan": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "problem_type",
        "fluid",
        "cycle_type",
        "known_values",
        "requested_outputs",
        "assumptions",
        "missing_data",
        "states",
        "confidence",
        "explanation_plan",
    ],
}


THERMO_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "categoria": {"type": "string"},
        "tipo_problema": {"type": "string"},
        "fluido": {"type": "string"},
        "interpretacao_imagem": {"type": "string"},
        "texto_usuario": {"type": "string"},
        "entrada_oficial": {"type": "string"},
        "diagnostico_entrada": {"type": "string"},
        "ferramentas_necessarias": {"type": "array", "items": {"type": "string"}},
        "dados_conhecidos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nome": {"type": "string"},
                    "valor": {"type": "string"},
                    "unidade": {"type": "string"},
                    "observacao": {"type": "string"},
                },
                "required": ["nome", "valor", "unidade", "observacao"],
            },
        },
        "propriedades_a_calcular": {"type": "array", "items": {"type": "string"}},
        "dados_faltantes": {"type": "array", "items": {"type": "string"}},
        "estados": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "estado": {"type": "string"},
                    "descricao": {"type": "string"},
                    "dados_conhecidos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "nome": {"type": "string"},
                                "valor": {"type": "string"},
                                "unidade": {"type": "string"},
                                "observacao": {"type": "string"},
                            },
                            "required": ["nome", "valor", "unidade", "observacao"],
                        },
                    },
                    "propriedades_a_calcular": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["estado", "descricao", "dados_conhecidos", "propriedades_a_calcular"],
            },
        },
        "hipoteses": {"type": "array", "items": {"type": "string"}},
        "objetivos": {"type": "array", "items": {"type": "string"}},
        "questoes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item": {"type": "string"},
                    "enunciado": {"type": "string"},
                    "objetivo": {"type": "string"},
                    "ferramentas_necessarias": {"type": "array", "items": {"type": "string"}},
                    "propriedades_a_calcular": {"type": "array", "items": {"type": "string"}},
                    "resultado_esperado": {"type": "string"},
                },
                "required": [
                    "item",
                    "enunciado",
                    "objetivo",
                    "ferramentas_necessarias",
                    "propriedades_a_calcular",
                    "resultado_esperado",
                ],
            },
        },
        "diagramas": {"type": "array", "items": {"type": "string"}},
        "plano_execucao": {"type": "array", "items": {"type": "string"}},
        "confianca": {"type": "number"},
    },
    "required": [
        "categoria",
        "tipo_problema",
        "fluido",
        "interpretacao_imagem",
        "texto_usuario",
        "entrada_oficial",
        "diagnostico_entrada",
        "ferramentas_necessarias",
        "dados_conhecidos",
        "propriedades_a_calcular",
        "dados_faltantes",
        "estados",
        "hipoteses",
        "objetivos",
        "questoes",
        "diagramas",
        "plano_execucao",
        "confianca",
    ],
}


def interpret_refrigeration_problem(
    statement: str,
    uploaded_files: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> AssistantDraft:
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("Configure a variavel de ambiente OPENAI_API_KEY para usar o assistente.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Instale a dependencia openai para usar o assistente.") from exc

    client = OpenAI(api_key=api_key)
    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    input_content: list[dict[str, Any]] = []

    if statement.strip():
        input_content.append({"type": "input_text", "text": statement.strip()})

    for uploaded_file in uploaded_files or []:
        content_type = uploaded_file.get("content_type", "")
        data = uploaded_file.get("data", b"")
        name = uploaded_file.get("name", "arquivo")
        if content_type.startswith("image/") and data:
            encoded = base64.b64encode(data).decode("ascii")
            input_content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{content_type};base64,{encoded}",
                }
            )
        elif content_type == "application/pdf" and data:
            text = extract_pdf_text(data)
            if text:
                input_content.append({"type": "input_text", "text": f"Texto extraido de {name}:\n{text}"})
            else:
                input_content.append(
                    {
                        "type": "input_text",
                        "text": f"O arquivo {name} e um PDF sem texto extraivel localmente. Marque dados faltantes.",
                    }
                )

    if not input_content:
        raise RuntimeError("Informe um enunciado em texto, imagem ou PDF antes de interpretar.")

    response = client.responses.create(
        model=selected_model,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": _developer_prompt(),
                    }
                ],
            },
            {"role": "user", "content": input_content},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "refrigeration_problem_draft",
                "schema": ASSISTANT_SCHEMA,
                "strict": True,
            }
        },
    )

    data = json.loads(_response_text(response))
    return assistant_draft_from_dict(data, statement)


def interpret_thermo_problem(
    statement: str,
    uploaded_files: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> ThermoPlan:
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("Configure a variavel de ambiente OPENAI_API_KEY para usar o assistente.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Instale a dependencia openai para usar o assistente.") from exc

    client = OpenAI(api_key=api_key)
    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    input_content = _build_input_content(statement, uploaded_files)
    response = client.responses.create(
        model=selected_model,
        input=[
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": _thermo_planner_prompt()}],
            },
            {"role": "user", "content": input_content},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "plano_termodinamica",
                "schema": THERMO_PLAN_SCHEMA,
                "strict": True,
            }
        },
    )
    data = json.loads(_response_text(response))
    return thermo_plan_from_dict(data, statement)


def _build_input_content(statement: str, uploaded_files: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    input_content: list[dict[str, Any]] = []
    input_content.append(
        {
            "type": "input_text",
            "text": (
                "Interprete a imagem e o texto como um unico enunciado. "
                "Leia texto, diagramas, legendas, rotulos, setas, anotacoes e observacoes pequenas. "
                "Use o texto digitado como complemento ou correcao explicita da imagem. "
                "Considere a figura como fonte primaria das relacoes entre estados e do tipo de ciclo. "
                "Nao repita como faltante o que ja estiver visivel ou dedutivel no desenho."
            ),
        }
    )
    if statement.strip():
        input_content.append({"type": "input_text", "text": statement.strip()})

    for uploaded_file in uploaded_files or []:
        content_type = uploaded_file.get("content_type", "")
        data = uploaded_file.get("data", b"")
        name = uploaded_file.get("name", "arquivo")
        if content_type.startswith("image/") and data:
            encoded = base64.b64encode(data).decode("ascii")
            input_content.append({"type": "input_image", "image_url": f"data:{content_type};base64,{encoded}"})
        elif content_type == "application/pdf" and data:
            text = extract_pdf_text(data)
            if text:
                input_content.append({"type": "input_text", "text": f"Texto extraido de {name}:\n{text}"})
            else:
                input_content.append(
                    {
                        "type": "input_text",
                        "text": f"O arquivo {name} e um PDF sem texto extraivel localmente. Use apenas os dados legiveis ou marque dados realmente faltantes.",
                    }
                )

    if not input_content:
        raise RuntimeError("Informe um enunciado em texto, imagem ou PDF antes de interpretar.")
    return input_content


def assistant_draft_from_dict(data: dict[str, Any], raw_text: str = "") -> AssistantDraft:
    return AssistantDraft(
        problem_type=str(data.get("problem_type", "")),
        fluid=str(data.get("fluid", "")),
        cycle_type=str(data.get("cycle_type", "")),
        known_values=dict(data.get("known_values") or {}),
        requested_outputs=tuple(str(item) for item in data.get("requested_outputs") or ()),
        assumptions=tuple(str(item) for item in data.get("assumptions") or ()),
        missing_data=_clean_missing_data(data.get("missing_data") or ()),
        states=tuple(dict(item) for item in data.get("states") or ()),
        confidence=float(data.get("confidence") or 0),
        explanation_plan=tuple(str(item) for item in data.get("explanation_plan") or ()),
        raw_text=raw_text,
    )


def thermo_plan_from_dict(data: dict[str, Any], raw_text: str = "") -> ThermoPlan:
    return ThermoPlan(
        categoria=str(data.get("categoria", "")),
        tipo_problema=str(data.get("tipo_problema", "")),
        fluido=str(data.get("fluido", "")),
        interpretacao_imagem=str(data.get("interpretacao_imagem", "")),
        texto_usuario=str(data.get("texto_usuario", "")),
        entrada_oficial=str(data.get("entrada_oficial", "")),
        diagnostico_entrada=str(data.get("diagnostico_entrada", "")),
        ferramentas_necessarias=tuple(str(item) for item in data.get("ferramentas_necessarias") or ()),
        dados_conhecidos=tuple(_planner_item_from_dict(item) for item in data.get("dados_conhecidos") or ()),
        propriedades_a_calcular=tuple(str(item) for item in data.get("propriedades_a_calcular") or ()),
        dados_faltantes=_clean_missing_data(data.get("dados_faltantes") or ()),
        estados=tuple(_planned_state_from_dict(item) for item in data.get("estados") or ()),
        hipoteses=tuple(str(item) for item in data.get("hipoteses") or ()),
        objetivos=tuple(str(item) for item in data.get("objetivos") or ()),
        questoes=tuple(_planned_question_from_dict(item) for item in data.get("questoes") or ()),
        diagramas=tuple(str(item) for item in data.get("diagramas") or ()),
        plano_execucao=tuple(str(item) for item in data.get("plano_execucao") or ()),
        confianca=float(data.get("confianca") or 0),
        raw_text=raw_text,
    )


def _planner_item_from_dict(data: dict[str, Any]) -> PlannerItem:
    return PlannerItem(
        nome=str(data.get("nome", "")),
        valor=str(data.get("valor", "")),
        unidade=str(data.get("unidade", "")),
        observacao=str(data.get("observacao", "")),
    )


def _planned_state_from_dict(data: dict[str, Any]) -> PlannedState:
    return PlannedState(
        estado=str(data.get("estado", "")),
        descricao=str(data.get("descricao", "")),
        dados_conhecidos=tuple(_planner_item_from_dict(item) for item in data.get("dados_conhecidos") or ()),
        propriedades_a_calcular=tuple(str(item) for item in data.get("propriedades_a_calcular") or ()),
    )


def _planned_question_from_dict(data: dict[str, Any]) -> PlannedQuestion:
    return PlannedQuestion(
        item=str(data.get("item", "")),
        enunciado=str(data.get("enunciado", "")),
        objetivo=str(data.get("objetivo", "")),
        ferramentas_necessarias=tuple(str(item) for item in data.get("ferramentas_necessarias") or ()),
        propriedades_a_calcular=tuple(str(item) for item in data.get("propriedades_a_calcular") or ()),
        resultado_esperado=str(data.get("resultado_esperado", "")),
    )


def _clean_missing_data(items: list[Any] | tuple[Any, ...]) -> tuple[str, ...]:
    computable_terms = (
        "enthalpy",
        "entropy",
        "specific volume",
        "quality",
        "steam_properties",
        "h2s",
        "h_real",
        "s_real",
        "t_saida",
        "temperatura de saida calculavel",
        "propriedades do vapor",
        "entalpia",
        "entropia",
        "volume especifico",
        "titulo",
    )
    cleaned = []
    for item in items:
        text = str(item).strip()
        normalized = text.lower().replace("_", " ")
        if any(term in normalized for term in computable_terms):
            continue
        text = " ".join(text.replace("_", " ").split())
        if text and text not in cleaned:
            cleaned.append(text)
    return tuple(cleaned)


def _get_openai_api_key() -> str | None:
    process_key = os.getenv("OPENAI_API_KEY")
    if process_key:
        return process_key

    if sys.platform.startswith("win"):
        for root_name in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
            key = _get_windows_environment_value(root_name, "OPENAI_API_KEY")
            if key:
                return key

    return None


def _get_windows_environment_value(root_name: str, variable_name: str) -> str | None:
    try:
        import winreg

        if root_name == "HKEY_CURRENT_USER":
            root = winreg.HKEY_CURRENT_USER
            path = "Environment"
        else:
            root = winreg.HKEY_LOCAL_MACHINE
            path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

        with winreg.OpenKey(root, path) as environment_key:
            value, _ = winreg.QueryValueEx(environment_key, variable_name)
            return str(value) if value else None
    except Exception:
        return None


def extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(page.strip() for page in pages if page.strip())
    except Exception:
        return ""


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    if isinstance(response, dict):
        output = response.get("output", [])
    else:
        output = getattr(response, "output", [])

    for item in output:
        content = item.get("content", []) if isinstance(item, dict) else getattr(item, "content", [])
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                return block["text"]
            text = getattr(block, "text", None)
            if text:
                return text
    raise RuntimeError("A resposta da OpenAI nao trouxe texto estruturado.")


def _developer_prompt() -> str:
    return """
Voce e um especialista em termodinamica para engenharia. Interprete enunciados de ciclos de refrigeracao.
Antes de calcular, classifique o problema, identifique estados, hipoteses, dados conhecidos e dados faltantes.
Retorne apenas JSON valido no schema solicitado.

Regras:
- Leia integralmente texto, imagem, diagramas, legendas, rotulos, setas e observacoes pequenas.
- Considere a figura como fonte primaria das relacoes entre estados e do tipo de ciclo.
- Se texto e imagem divergirem, registre o conflito de forma curta em portugues e use a informacao explicitamente fornecida no enunciado para desempate quando for claro.
- Nao marque como faltante algo que ja esteja visivel ou dedutivel na figura.
- Foque no ciclo de compressao de vapor simples quando o enunciado falar de ar-condicionado, R22 ou R134a.
- Normalize fluidos para R22, R134a ou Water quando forem equivalentes.
- Se o enunciado falar de turbina, vapor de agua, vapor d'agua, potencia produzida em turbina, P1/T1/P2 e vazao massica, classifique como problema fora desta aba; nao transforme em ciclo de refrigeracao.
- No MVP de ciclo de refrigeracao, Water nao deve ser usado como fluido de ciclo; agua/vapor pertence a propriedades, titulo ou turbina.
- Nao invente valores faltantes; coloque somente dados fisicos realmente ausentes em missing_data.
- Propriedades que o CoolProp calcula, como h, s, v, x, T de saturacao, h2s e estados por pares de propriedades, nunca entram em missing_data.
- Se o enunciado trouxer pressoes de evaporacao/condensacao em vez de temperaturas, preencha as pressoes; o app pode obter temperaturas de saturacao.
- Use compressor_efficiency em base decimal, por exemplo 0.8 para 80%.
- Use temperaturas em Celsius nas chaves *_temperature_c e diferencas em Kelvin nas chaves *_k.
- Se o problema trouxer capacidade em W ou kW, preencha a chave correspondente.
- Monte estados 1, 2s, 2, 3 e 4 quando o ciclo for compressao de vapor.
- A explicacao deve seguir: sistema fisico, fenomeno, hipoteses, modelo, propriedades, calculos, interpretacao.
""".strip()


def _thermo_planner_prompt() -> str:
    return f"""
Voce e um especialista em termodinamica para engenharia e responde sempre em portugues do Brasil.
Sua funcao e interpretar o enunciado, classificar o problema, identificar estados, escolher ferramentas do projeto e montar um plano de calculo.
Voce NAO deve calcular propriedades numericas que o CoolProp pode obter. Essas propriedades entram em propriedades_a_calcular.

{tool_catalog_prompt()}

Regras obrigatorias:
- Responda apenas JSON valido no schema solicitado.
- Use nomes de ferramentas exatamente como estao no catalogo.
- Classifique antes de calcular: sistema fisico, categoria, estados, hipoteses e objetivos.
- Leia integralmente texto, imagem, diagramas, legendas, rotulos, setas, e observacoes pequenas.
- Trate a figura como fonte primaria das relacoes entre estados e do tipo de ciclo.
- Combine imagem e texto em uma unica interpretacao; o texto digitado pode complementar ou corrigir a imagem.
- Se a figura ja definir o ciclo, nao peça ao usuario para repetir relacoes de estado que ja estao desenhadas.
- Se houver conflito claro entre imagem e texto, registre um diagnostico curto em portugues e priorize a informacao explicitamente indicada no enunciado.
- Preencha interpretacao_imagem com os dados, relacoes de estados, diagramas e perguntas lidos da imagem; se nao houver imagem, escreva "Sem imagem enviada".
- Preencha texto_usuario com o texto adicional digitado pelo usuario; se nao houver, escreva "Sem texto adicional".
- Preencha entrada_oficial com o enunciado consolidado que sera usado para resolver, combinando imagem e texto.
- Preencha diagnostico_entrada com complemento, conflito ou "Sem conflitos identificados".
- Em dados_conhecidos, prefira nomes canonicos quando aplicavel: fluido, temperatura_evaporacao, pressao_evaporacao, temperatura_condensacao, pressao_condensacao, capacidade_evaporador, vazao_massica, eficiencia_compressor.
- Para dados extraidos de diagrama, registre a relacao no campo observacao, por exemplo P2=P3, T4-1, estado 1 vapor saturado ou estado 3 liquido saturado.
- dados_faltantes deve conter somente informacoes impossiveis de obter por CoolProp ou equacoes do modelo.
- h, s, u, v, rho, x, T_saida, h2s, h_real e s_real sao propriedades calculaveis quando houver par de propriedades suficiente; nunca coloque esses itens como dados faltantes.
- Para turbina isolada/adiabatica em regime permanente, use turbina_vapor_adiabatica quando o fluido for agua/vapor.
- Enunciados com "turbina", "vapor de agua", "vapor d'agua", P1/T1/P2 e vazao massica sao problemas de turbina, nunca ciclo de refrigeracao.
- Para turbina, reconheca estado 1 de entrada, estado 2s isentropico ideal e estado 2 real se houver condicao real informada.
- Para refrigeracao, ar-condicionado, bomba de calor ou refrigerantes R22/R134a, use ciclo_refrigeracao_simples quando for ciclo de compressao de vapor simples.
- No MVP, ciclo_refrigeracao_simples aceita somente R22 e R134a; nao escolha esta ferramenta para agua/vapor.
- Para ciclo de refrigeracao, dados essenciais sao fluido e pelo menos temperatura ou pressao de evaporacao e condensacao; se o diagrama trouxer estado 1 vapor saturado com temperatura, isso e temperatura_evaporacao; se trouxer estado 3 liquido saturado com pressao, isso e pressao_condensacao.
- Para "ciclo padrao" de refrigeracao por compressao de vapor com duas pressoes, mdot, ponto 1 vapor saturado, estado 3 liquido saturado, s1=s2 e h4=h3, use ciclo_refrigeracao_padrao_pressao.
- Nao classifique ciclo padrao por pressoes como evaporador_ar_refrigerante.
- Para evaporador/trocador com ar e R134a, use evaporador_ar_refrigerante somente quando ar for uma corrente separada com dados proprios, como vazao de ar, pressao do ar ou temperatura do ar; nao use essa ferramenta apenas porque um ciclo tem evaporador.
- Valvula de expansao em ciclo de refrigeracao e processo isoentalpico: h4=h3. Nao descreva como isentropico.
- Se houver mais de uma ferramenta, liste primeiro a ferramenta principal executavel e depois ferramentas auxiliares de propriedades.
- Ferramentas auxiliares como estado_por_tp, estado_por_par e titulo_mistura ajudam a explicar propriedades, mas nao substituem a ferramenta principal do problema.
- Para refrigerador entre dois reservatorios TL/TH com QL, QH, Wciclo e COP, use refrigerador_reservatorios; esse tipo nao precisa de fluido e nao deve pedir R22/R134a.
- Para problemas de potencia/ciclos sem solver deterministico no catalogo, classifique corretamente e nao force a ferramenta de turbina ou refrigeracao.
- Quando o enunciado trouxer itens como a), b), c), crie uma entrada em questoes para cada item.
- Cada questao deve ter objetivo claro, ferramentas, propriedades a calcular e resultado esperado.
- Se o enunciado estiver em imagem, transcreva mentalmente os dados visiveis e registre apenas os dados realmente lidos.
- Todos os textos, observacoes, objetivos, hipoteses e passos devem estar em portugues.
""".strip()

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any

from heat_transfer_catalog import heat_transfer_tool_catalog_prompt
from openai_assistant import _get_openai_api_key, _response_text, extract_pdf_text


@dataclass(frozen=True)
class HeatTransferPlanItem:
    nome: str = ""
    valor: str = ""
    unidade: str = ""
    observacao: str = ""


@dataclass(frozen=True)
class HeatTransferQuestion:
    item: str = ""
    enunciado: str = ""
    objetivo: str = ""
    ferramentas_necessarias: tuple[str, ...] = ()
    propriedades_a_calcular: tuple[str, ...] = ()
    resultado_esperado: str = ""


@dataclass(frozen=True)
class HeatTransferPlan:
    categoria: str = ""
    tipo_problema: str = ""
    interpretacao_imagem: str = ""
    texto_usuario: str = ""
    entrada_oficial: str = ""
    diagnostico_entrada: str = ""
    ferramentas_necessarias: tuple[str, ...] = ()
    dados_conhecidos: tuple[HeatTransferPlanItem, ...] = ()
    dados_faltantes: tuple[str, ...] = ()
    fatos_canonicos: tuple[HeatTransferPlanItem, ...] = ()
    geometria: tuple[HeatTransferPlanItem, ...] = ()
    condicoes_contorno: tuple[HeatTransferPlanItem, ...] = ()
    hipoteses: tuple[str, ...] = ()
    objetivos: tuple[str, ...] = ()
    questoes: tuple[HeatTransferQuestion, ...] = ()
    diagramas: tuple[str, ...] = ()
    plano_execucao: tuple[str, ...] = ()
    confianca: float = 0.0
    raw_text: str = ""


ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "nome": {"type": "string"},
        "valor": {"type": "string"},
        "unidade": {"type": "string"},
        "observacao": {"type": "string"},
    },
    "required": ["nome", "valor", "unidade", "observacao"],
}

QUESTION_SCHEMA = {
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
}

HEAT_TRANSFER_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "categoria": {"type": "string"},
        "tipo_problema": {"type": "string"},
        "interpretacao_imagem": {"type": "string"},
        "texto_usuario": {"type": "string"},
        "entrada_oficial": {"type": "string"},
        "diagnostico_entrada": {"type": "string"},
        "ferramentas_necessarias": {"type": "array", "items": {"type": "string"}},
        "dados_conhecidos": {"type": "array", "items": ITEM_SCHEMA},
        "dados_faltantes": {"type": "array", "items": {"type": "string"}},
        "fatos_canonicos": {"type": "array", "items": ITEM_SCHEMA},
        "geometria": {"type": "array", "items": ITEM_SCHEMA},
        "condicoes_contorno": {"type": "array", "items": ITEM_SCHEMA},
        "hipoteses": {"type": "array", "items": {"type": "string"}},
        "objetivos": {"type": "array", "items": {"type": "string"}},
        "questoes": {"type": "array", "items": QUESTION_SCHEMA},
        "diagramas": {"type": "array", "items": {"type": "string"}},
        "plano_execucao": {"type": "array", "items": {"type": "string"}},
        "confianca": {"type": "number"},
    },
    "required": [
        "categoria",
        "tipo_problema",
        "interpretacao_imagem",
        "texto_usuario",
        "entrada_oficial",
        "diagnostico_entrada",
        "ferramentas_necessarias",
        "dados_conhecidos",
        "dados_faltantes",
        "fatos_canonicos",
        "geometria",
        "condicoes_contorno",
        "hipoteses",
        "objetivos",
        "questoes",
        "diagramas",
        "plano_execucao",
        "confianca",
    ],
}


def interpret_heat_transfer_problem(
    statement: str,
    uploaded_files: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> HeatTransferPlan:
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("Configure a variavel de ambiente OPENAI_API_KEY para usar o assistente.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Instale a dependencia openai para usar o assistente.") from exc

    client = OpenAI(api_key=api_key)
    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    response = client.responses.create(
        model=selected_model,
        input=[
            {"role": "developer", "content": [{"type": "input_text", "text": _heat_transfer_prompt()}]},
            {"role": "user", "content": _build_heat_transfer_input(statement, uploaded_files)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "plano_transferencia_calor",
                "schema": HEAT_TRANSFER_PLAN_SCHEMA,
                "strict": True,
            }
        },
    )
    return heat_transfer_plan_from_dict(json.loads(_response_text(response)), statement)


def heat_transfer_plan_from_dict(data: dict[str, Any], raw_text: str = "") -> HeatTransferPlan:
    return HeatTransferPlan(
        categoria=str(data.get("categoria", "")),
        tipo_problema=str(data.get("tipo_problema", "")),
        interpretacao_imagem=str(data.get("interpretacao_imagem", "")),
        texto_usuario=str(data.get("texto_usuario", "")),
        entrada_oficial=str(data.get("entrada_oficial", "")),
        diagnostico_entrada=str(data.get("diagnostico_entrada", "")),
        ferramentas_necessarias=tuple(str(item) for item in data.get("ferramentas_necessarias") or ()),
        dados_conhecidos=tuple(_item_from_dict(item) for item in data.get("dados_conhecidos") or ()),
        dados_faltantes=_clean_missing_heat_transfer_data(data.get("dados_faltantes") or ()),
        fatos_canonicos=tuple(_item_from_dict(item) for item in data.get("fatos_canonicos") or ()),
        geometria=tuple(_item_from_dict(item) for item in data.get("geometria") or ()),
        condicoes_contorno=tuple(_item_from_dict(item) for item in data.get("condicoes_contorno") or ()),
        hipoteses=tuple(str(item) for item in data.get("hipoteses") or ()),
        objetivos=tuple(str(item) for item in data.get("objetivos") or ()),
        questoes=tuple(_question_from_dict(item) for item in data.get("questoes") or ()),
        diagramas=tuple(str(item) for item in data.get("diagramas") or ()),
        plano_execucao=tuple(str(item) for item in data.get("plano_execucao") or ()),
        confianca=float(data.get("confianca") or 0),
        raw_text=raw_text,
    )


def _item_from_dict(data: dict[str, Any]) -> HeatTransferPlanItem:
    return HeatTransferPlanItem(
        nome=str(data.get("nome", "")),
        valor=str(data.get("valor", "")),
        unidade=str(data.get("unidade", "")),
        observacao=str(data.get("observacao", "")),
    )


def _question_from_dict(data: dict[str, Any]) -> HeatTransferQuestion:
    return HeatTransferQuestion(
        item=str(data.get("item", "")),
        enunciado=str(data.get("enunciado", "")),
        objetivo=str(data.get("objetivo", "")),
        ferramentas_necessarias=tuple(str(item) for item in data.get("ferramentas_necessarias") or ()),
        propriedades_a_calcular=tuple(str(item) for item in data.get("propriedades_a_calcular") or ()),
        resultado_esperado=str(data.get("resultado_esperado", "")),
    )


def _build_heat_transfer_input(statement: str, uploaded_files: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    input_content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                "Interprete texto e arquivos como um unico enunciado de Transferencia de Calor. "
                "Leia diagramas, geometrias, camadas, setas, legendas, unidades, dimensoes e observacoes pequenas. "
                "O usuario ja escolheu a aba de Transferencia de Calor; nao classifique como Termodinamica. "
                "Nao invente propriedades de material ausentes. Marque faltante apenas o que nao estiver visivel nem dedutivel."
            ),
        }
    ]
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
                input_content.append({"type": "input_text", "text": f"O PDF {name} nao teve texto extraivel localmente."})
    if len(input_content) == 1:
        raise RuntimeError("Informe um enunciado em texto, imagem ou PDF antes de interpretar.")
    return input_content


def _clean_missing_heat_transfer_data(items: list[Any] | tuple[Any, ...]) -> tuple[str, ...]:
    computable_terms = (
        "q_dot",
        "q dot fin",
        "q total",
        "q sem aletas",
        "q flux",
        "r th",
        "r total",
        "a c",
        "area da secao",
        "area da secao transversal",
        "perimetro da secao",
        "perimetro da secao da aleta",
        "numero de aletas",
        "bi",
        "fo",
        "ntu",
        "delta t lm",
        "eta f",
        "eta o",
        "epsilon o",
        "a f",
        "a base",
    )
    cleaned: list[str] = []
    for item in items:
        text = " ".join(str(item).replace("_", " ").split())
        if not text:
            continue
        normalized = text.lower()
        if any(term in normalized for term in computable_terms):
            continue
        if text not in cleaned:
            cleaned.append(text)
    return tuple(cleaned)


def _heat_transfer_prompt() -> str:
    return f"""
Voce e um especialista em Transferencia de Calor para engenharia e responde sempre em portugues do Brasil.
Sua funcao e interpretar enunciados, imagens e diagramas e montar um plano de calculo. Voce NAO calcula os valores finais.

Ferramentas deterministicas disponiveis neste MVP:
{heat_transfer_tool_catalog_prompt()}

Regras:
- Classifique o fenomeno antes da ferramenta.
- Extraia dados de texto, imagem, diagramas, geometrias, camadas, setas, legendas, dimensoes e unidades.
- Separe interpretacao_imagem, texto_usuario, entrada_oficial e diagnostico_entrada.
- Nao invente propriedades de material como k, h, epsilon, rho ou c_p.
- Grandezas calculaveis pela ferramenta, como q_dot, q_flux, R_th e Bi, nao entram em dados_faltantes.
- Para aletas e superficies aletadas, A_c, P, A_f, N, A_base, eta_f, eta_o, q_dot_fin, q_total e q_sem_aletas tambem sao derivaveis quando a geometria ja esta descrita.
- Se a secao da aleta for quadrada e a geometria indicar dimensoes como 4 x 4 mm, derive P e A_c a partir das dimensoes em vez de marcá-los como faltantes.
- Se imagem e texto divergirem, registre o conflito em diagnostico_entrada e priorize texto explicito do usuario.
- Use nomes canonicos: T_1, T_2, T_s, T_inf, T_sur, L, A, r_i, r_o, D, k, h, epsilon, q_dot, q_flux, R_th, Bi, Fo.
- Para placa aletada use aleta_superficie_aletada; para placa plana externa use conveccao_placa_plana_externa; para tubo interno use conveccao_interna_tubo_iterativa; para tubo concêntrico com vapor use trocador_tubo_concentrico_vapor; para placa transiente use conducao_transiente_placa; para asa/placa com sol use asa_plana_radiacao_solar.
- Classifique explicitamente geometria, tipo de transferencia, regime e correlacao antes de listar faltantes.
- Se o enunciado citar placa plana, tubo, transiente, Biot, Fourier, Reynolds, Nusselt, conveccao externa, conveccao interna ou radiacao solar, escolha a ferramenta especifica correspondente.
- Mantenha todas as respostas em portugues.
""".strip()

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from html import escape

import pandas as pd
import streamlit as st

from evaporator_core import EvaporatorResult, evaporator_case_rows, evaporator_state_rows
from exercise_logger import log_error, log_input, log_output, log_plan, new_run_id
from openai_assistant import PlannerItem, PlannedQuestion, PlannedState, ThermoPlan, interpret_thermo_problem
from reservoir_cycle_core import ReservoirCycleResult, reservoir_case_rows
from standard_cycle_core import (
    StandardCycleResult,
    standard_cycle_metric_rows,
    standard_cycle_state_rows,
)
from thermo_core import k_to_temperature, pa_to_pressure, pressure_to_pa
from thermo_executor import ExecutionResult, execute_thermo_plan
from thermo_facts import canonical_fact_value, canonical_facts_from_plan
from turbine_core import TurbineResult, turbine_metric_rows, turbine_state_rows


@dataclass(frozen=True)
class ExerciseUnitConfig:
    temperature_unit: str
    pressure_unit: str
    enthalpy_unit: str = "J/kg"
    entropy_unit: str = "J/(kg.K)"
    volume_unit: str = "m3/kg"
    power_unit: str = "W"
    mass_flow_unit: str = "kg/s"


@dataclass(frozen=True)
class QuestionAnswer:
    item: str
    objective: str
    status: str
    interpretation: str
    data_used: str
    formulas: tuple[str, ...]
    substitution: str
    result_text: str
    origins: tuple[str, ...] = ()


def render_exercise_tab(reference_state: str, temperature_unit: str = "K", pressure_unit: str = "Pa") -> None:
    unit_config = ExerciseUnitConfig(temperature_unit=temperature_unit, pressure_unit=pressure_unit)
    st.subheader("Gabaritador de exercicios")
    st.caption("A OpenAI interpreta o enunciado, escolhe as ferramentas internas e o projeto calcula com CoolProp.")

    if st.button("Limpar exercicio", use_container_width=True, key="exercise_clear"):
        _clear_exercise_state()
        st.rerun()

    plan = _render_planner_input()
    current_plan_id = _plan_id(plan) if isinstance(plan, ThermoPlan) else ""

    if isinstance(plan, ThermoPlan):
        st.caption(f"Exercicio atual: `{current_plan_id[:10]}`")
        _render_plan(plan)
        if st.button("Resolver com ferramentas internas", type="primary", use_container_width=True, key="exercise_execute"):
            try:
                with st.spinner("Calculando propriedades no CoolProp e montando a resolucao..."):
                    execution = execute_thermo_plan(plan, reference_state)
                    st.session_state["exercise_execution_result"] = execution
                    st.session_state["exercise_execution_plan_id"] = current_plan_id
                    output_path = log_output(
                        st.session_state.get("exercise_run_id") or new_run_id(),
                        current_plan_id,
                        execution,
                        _execution_copyable_markdown(execution, unit_config, plan),
                        plan.ferramentas_necessarias,
                        _question_answers_markdown(plan, execution, unit_config),
                    )
                    st.session_state["exercise_output_log_path"] = output_path
            except Exception as exc:
                error_path = log_error(
                    st.session_state.get("exercise_run_id") or new_run_id(),
                    current_plan_id,
                    "execucao",
                    exc,
                )
                st.session_state["exercise_error_log_path"] = error_path
                st.error(f"Nao foi possivel executar o plano: {exc}")

        execution = st.session_state.get("exercise_execution_result")
        execution_plan_id = st.session_state.get("exercise_execution_plan_id", "")
        if isinstance(execution, ExecutionResult) and execution_plan_id == current_plan_id:
            if st.session_state.get("exercise_output_log_path"):
                st.caption(f"Log de saída: `{st.session_state['exercise_output_log_path']}`")
            _render_execution_result(execution, unit_config, plan)
        elif isinstance(execution, ExecutionResult):
            st.info("Ha um novo plano pendente de resolucao. Clique em Resolver para evitar misturar com resultado anterior.")
    else:
        st.info("Cole um enunciado ou envie imagem/PDF para gerar o plano de resolucao.")


def _temperature_from_c(value_c: float, unit: str) -> float:
    return k_to_temperature(value_c + 273.15, unit)


def _temperature_from_k(value_k: float, unit: str) -> float:
    return k_to_temperature(value_k, unit)


def _enthalpy_si(value_kj_per_kg: float | None) -> float | None:
    return None if value_kj_per_kg is None else value_kj_per_kg * 1000.0


def _entropy_si(value_kj_per_kgk: float | None) -> float | None:
    return None if value_kj_per_kgk is None else value_kj_per_kgk * 1000.0


def _power_w(value_kw: float | None) -> float | None:
    return None if value_kw is None else value_kw * 1000.0


def _pressure_display(value: float, source_unit: str, target_unit: str) -> float:
    return pa_to_pressure(pressure_to_pa(value, source_unit), target_unit)


def _format_value(value: float | None, unit: str = "") -> str:
    if value is None:
        return "-"
    suffix = f" {unit}" if unit else ""
    return f"{value:.6g}{suffix}"


def _render_limited_pyplot(fig) -> None:
    left, center, right = st.columns([0.2, 0.6, 0.2])
    with center:
        st.pyplot(fig, use_container_width=True)


def _render_question_block(
    title: str,
    interpretation: str,
    data_used: str,
    formulas: tuple[str, ...],
    substitution: str,
    result_text: str,
    origins: tuple[str, ...] = (),
) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(f"**Interpretação:** {interpretation}")
        st.markdown(f"**Dados usados:** {data_used}")
        if formulas:
            st.markdown("**Fórmula:**")
            for formula in formulas:
                st.latex(formula)
        if substitution:
            st.markdown("**Substituição numérica:**")
            st.latex(substitution)
        _render_result_card("Resultado", result_text)
        if origins:
            with st.expander("Origem das propriedades", expanded=False):
                for origin in origins:
                    st.markdown(f"- {origin}")


def _clear_exercise_state() -> None:
    for key in (
        "exercise_statement",
        "exercise_files",
        "exercise_plan_result",
        "exercise_execution_result",
        "exercise_run_id",
        "exercise_input_log_path",
        "exercise_plan_log_path",
        "exercise_output_log_path",
        "exercise_error_log_path",
    ):
        st.session_state.pop(key, None)
    st.session_state.pop("exercise_execution_plan_id", None)
    st.session_state["exercise_widget_version"] = st.session_state.get("exercise_widget_version", 0) + 1


def _plan_id(plan: ThermoPlan | None) -> str:
    if not isinstance(plan, ThermoPlan):
        return ""
    payload = "|".join(
        (
            plan.raw_text,
            plan.categoria,
            plan.tipo_problema,
            plan.fluido,
            ",".join(plan.ferramentas_necessarias),
            ",".join(f"{item.nome}:{item.valor}:{item.unidade}" for item in plan.dados_conhecidos),
            ",".join(f"{state.estado}:{state.descricao}" for state in plan.estados),
            ",".join(question.objetivo for question in plan.questoes),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _render_log_links() -> None:
    paths = [
        ("Log de entrada", st.session_state.get("exercise_input_log_path")),
        ("Log do plano", st.session_state.get("exercise_plan_log_path")),
        ("Log de saída", st.session_state.get("exercise_output_log_path")),
        ("Log de erro", st.session_state.get("exercise_error_log_path")),
    ]
    visible = [(label, path) for label, path in paths if path]
    if not visible:
        return
    st.markdown("##### Logs desta execução")
    for label, path in visible:
        st.caption(f"{label}: `{path}`")


def _consolidated_input_summary(plan: ThermoPlan, statement: str, files_payload: list[dict[str, object]]) -> str:
    file_names = ", ".join(item.get("name", "arquivo") for item in files_payload) if files_payload else "nenhum arquivo"
    text_hint = statement.strip() or "[sem texto adicional]"
    questions = "; ".join(f"{question.item}: {question.objetivo}" for question in plan.questoes) if plan.questoes else "[sem questoes identificadas]"
    return (
        f"Interpretacao consolidada: categoria `{plan.categoria}`, tipo `{plan.tipo_problema}`, fluido `{plan.fluido}`. "
        f"Texto adicional: `{text_hint}`. "
        f"Arquivos: `{file_names}`. "
        f"Ferramentas: `{', '.join(plan.ferramentas_necessarias) or '-'}`. "
        f"Questoes: `{questions}`."
    )


def _render_compact_items(items: tuple[tuple[str, str], ...]) -> None:
    html = []
    for label, value in items:
        html.append(
            "<div class='compact-item'>"
            f"<div class='compact-label'>{escape(label)}</div>"
            f"<div class='compact-value'>{escape(value)}</div>"
            "</div>"
        )
    st.markdown(f"<div class='compact-list'>{''.join(html)}</div>", unsafe_allow_html=True)


def _render_planner_input() -> ThermoPlan | None:
    st.markdown("#### Enunciado")
    widget_version = st.session_state.get("exercise_widget_version", 0)
    statement = st.text_area(
        "Texto do problema",
        height=180,
        key=f"exercise_statement_{widget_version}",
        placeholder="Cole aqui o enunciado do exercicio...",
    )
    uploaded_files = st.file_uploader(
        "Imagem ou PDF",
        type=["png", "jpg", "jpeg", "webp", "pdf"],
        accept_multiple_files=True,
        key=f"exercise_files_{widget_version}",
    )
    model = st.text_input("Modelo OpenAI", value="gpt-4.1-mini", key="exercise_openai_model")

    if st.button("Interpretar e planejar", type="primary", use_container_width=True, key="exercise_plan"):
        st.session_state.pop("exercise_execution_result", None)
        st.session_state.pop("exercise_execution_plan_id", None)
        st.session_state.pop("exercise_output_log_path", None)
        st.session_state.pop("exercise_error_log_path", None)
        run_id = new_run_id()
        st.session_state["exercise_run_id"] = run_id
        files_payload = [
            {
                "name": uploaded_file.name,
                "content_type": uploaded_file.type,
                "data": uploaded_file.getvalue(),
            }
            for uploaded_file in uploaded_files or []
        ]
        model_name = model.strip() or "gpt-4.1-mini"
        try:
            with st.spinner("Interpretando enunciado, identificando estados e escolhendo ferramentas..."):
                plan_result = interpret_thermo_problem(
                    statement,
                    files_payload,
                    model=model_name,
                )
                st.session_state["exercise_plan_result"] = plan_result
                plan_id = _plan_id(plan_result)
                st.session_state["exercise_input_log_path"] = log_input(
                    run_id,
                    statement,
                    files_payload,
                    model_name,
                    plan_result,
                )
                st.session_state["exercise_plan_log_path"] = log_plan(run_id, plan_result, plan_id)
        except Exception as exc:
            st.session_state.pop("exercise_plan_result", None)
            st.session_state["exercise_error_log_path"] = log_error(run_id, "pendente", "interpretacao", exc)
            st.error(f"Nao foi possivel interpretar com a OpenAI: {exc}")

    plan = st.session_state.get("exercise_plan_result")
    _render_log_links()
    return plan if isinstance(plan, ThermoPlan) else None


def _render_plan(plan: ThermoPlan) -> None:
    st.markdown("#### Plano interpretado")
    _render_compact_items(
        (
            ("Categoria", plan.categoria or "-"),
            ("Tipo", plan.tipo_problema or "-"),
            ("Fluido", plan.fluido or "-"),
            ("Confianca", f"{plan.confianca:.0%}"),
        )
    )

    if plan.dados_faltantes:
        st.warning("Dados realmente faltantes: " + ", ".join(plan.dados_faltantes))
    else:
        st.success("Nenhum dado essencial faltante identificado.")

    if plan.ferramentas_necessarias:
        st.markdown("**Ferramentas escolhidas:** " + ", ".join(plan.ferramentas_necessarias))

    if plan.dados_conhecidos:
        st.markdown("##### Dados conhecidos")
        _render_compact_items(
            tuple(
                (
                    item.nome,
                    f"{item.valor} {item.unidade}".strip()
                    + (f" — {item.observacao}" if item.observacao else ""),
                )
                for item in plan.dados_conhecidos
            )
        )

    if plan.propriedades_a_calcular:
        st.markdown("##### Propriedades a calcular")
        st.write(", ".join(plan.propriedades_a_calcular))

    if plan.estados:
        st.markdown("##### Estados identificados")
        _render_compact_items(
            tuple(
                (
                    f"Estado {state.estado}",
                    f"{state.descricao}. Dados: "
                    + "; ".join(
                        f"{item.nome}={item.valor} {item.unidade}".strip() for item in state.dados_conhecidos
                    )
                    + ". Calcular: "
                    + (", ".join(state.propriedades_a_calcular) or "-"),
                )
                for state in plan.estados
            )
        )

    if plan.questoes:
        st.markdown("##### Questoes do enunciado")
        for question in plan.questoes:
            with st.container(border=True):
                st.markdown(f"**Item {question.item or '-'}**")
                st.markdown(question.objetivo or question.enunciado or "-")
                st.caption(
                    f"Ferramentas: {', '.join(question.ferramentas_necessarias) or '-'} | "
                    f"Calcular: {', '.join(question.propriedades_a_calcular) or '-'}"
                )

    if plan.hipoteses:
        st.markdown("##### Hipoteses")
        for item in plan.hipoteses:
            st.markdown(f"- {item}")

    if plan.plano_execucao:
        st.markdown("##### Sequencia de resolucao")
        for item in plan.plano_execucao:
            st.markdown(f"- {item}")


def _render_execution_result(execution: ExecutionResult, unit_config: ExerciseUnitConfig, plan: ThermoPlan | None = None) -> None:
    if execution.messages:
        for message in execution.messages:
            st.warning(message)
        return

    if execution.turbine_result:
        _render_turbine_result(execution.turbine_result, unit_config)
    elif execution.cycle_result:
        _render_cycle_result_for_exercise(execution.cycle_result, unit_config, plan)
    elif execution.evaporator_result:
        _render_evaporator_result(execution.evaporator_result)
    elif execution.reservoir_result:
        _render_reservoir_result(execution.reservoir_result)
    elif execution.standard_cycle_result:
        _render_standard_cycle_result(execution.standard_cycle_result, unit_config)
    else:
        st.info("O plano foi interpretado, mas esta ferramenta ainda nao tem renderizador.")


def _execution_copyable_markdown(execution: ExecutionResult, unit_config: ExerciseUnitConfig, plan: ThermoPlan | None = None) -> str:
    if execution.messages:
        return "\n".join(f"- {message}" for message in execution.messages)
    if execution.turbine_result:
        return _turbine_solution_markdown(execution.turbine_result, unit_config)
    if execution.cycle_result:
        question_section = _question_answers_markdown(plan, execution, unit_config)
        full_section = _cycle_solution_markdown_si(execution.cycle_result, unit_config)
        return f"{question_section}\n\n---\n\n{full_section}".strip()
    if execution.evaporator_result:
        return _evaporator_solution_markdown(execution.evaporator_result)
    if execution.reservoir_result:
        return _reservoir_solution_markdown(execution.reservoir_result)
    if execution.standard_cycle_result:
        return _standard_cycle_solution_markdown(execution.standard_cycle_result, unit_config)
    return "Resultado sem renderizador copiavel."


def build_question_answers(plan: ThermoPlan | None, execution: ExecutionResult, unit_config: ExerciseUnitConfig) -> tuple[QuestionAnswer, ...]:
    questions = tuple(plan.questoes) if isinstance(plan, ThermoPlan) and plan.questoes else ()
    if not questions:
        return ()
    if execution.cycle_result:
        return _cycle_question_answers(questions, execution.cycle_result, unit_config, plan)
    return tuple(
        QuestionAnswer(
            item=question.item or "-",
            objective=question.objetivo or question.enunciado or "-",
            status="bloqueado",
            interpretation="A questão foi identificada no enunciado, mas a ferramenta executada ainda não possui mapeamento item a item.",
            data_used="Nenhum dado foi associado automaticamente a esta questão.",
            formulas=(),
            substitution="",
            result_text="Item não resolvido automaticamente.",
        )
        for question in questions
    )


def _cycle_question_answers(questions: tuple[PlannedQuestion, ...], result, unit_config: ExerciseUnitConfig) -> tuple[QuestionAnswer, ...]:
    state_map = {state.point: state for state in result.states}
    metric_map = {metric.label: metric for metric in result.metrics}
    origins = tuple(f"Estado {state.point}: {state.origin}. {state.formula}" for state in result.states)
    h1 = _enthalpy_si(state_map["1"].enthalpy)
    h2 = _enthalpy_si(state_map["2"].enthalpy)
    h3 = _enthalpy_si(state_map["3"].enthalpy)
    h4 = _enthalpy_si(state_map["4"].enthalpy)
    q_evap = metric_map.get("Calor absorvido no evaporador")
    w_comp = metric_map.get("Trabalho especifico do compressor")
    mass_flow = metric_map.get("Vazao massica")
    power = metric_map.get("Potencia do compressor")
    cop = metric_map.get("COP real de refrigeracao")

    answers: list[QuestionAnswer] = []
    for question in questions:
        item = (question.item or "").strip().lower()
        objective = question.objetivo or question.enunciado or "-"
        objective_norm = objective.lower()

        if item == "a" or "entalp" in objective_norm:
            answers.append(
                QuestionAnswer(
                    item=question.item or "a",
                    objective=objective,
                    status="respondido",
                    interpretation="As entalpias definem os balanços de energia no evaporador, compressor e condensador.",
                    data_used="Estados calculados por CoolProp conforme as relações do ciclo.",
                    formulas=(r"h_i=h(P_i,T_i)\ \mathrm{ou}\ h_i=h(P_i,x_i)",),
                    substitution=rf"h_1={h1:.6g},\ h_2={h2:.6g},\ h_3={h3:.6g},\ h_4={h4:.6g}\ \mathrm{{J/kg}}",
                    result_text=f"h1={h1:.6g} J/kg; h2={h2:.6g} J/kg; h3={h3:.6g} J/kg; h4={h4:.6g} J/kg",
                    origins=origins,
                )
            )
            continue

        if item == "b" or "temperatura" in objective_norm:
            temperatures = []
            for point in ("1", "2", "3", "4"):
                state = state_map[point]
                temperatures.append(f"T{point}={_temperature_from_c(state.temperature, unit_config.temperature_unit):.6g} {unit_config.temperature_unit}")
            answers.append(
                QuestionAnswer(
                    item=question.item or "b",
                    objective=objective,
                    status="respondido",
                    interpretation="As temperaturas indicam as condições térmicas em cada ponto do ciclo.",
                    data_used=f"Unidade global selecionada: {unit_config.temperature_unit}.",
                    formulas=(r"T_i=T(P_i,h_i)\ \mathrm{ou}\ T_i=T(P_i,x_i)",),
                    substitution=r",\ ".join(temperatures),
                    result_text="; ".join(temperatures),
                    origins=origins,
                )
            )
            continue

        if item == "c" or "título" in objective_norm or "titulo" in objective_norm or "x4" in objective_norm:
            x4 = state_map["4"].quality
            answers.append(
                QuestionAnswer(
                    item=question.item or "c",
                    objective=objective,
                    status="respondido" if x4 is not None else "parcial",
                    interpretation="A válvula de expansão é isoentálpica; o título de entrada do evaporador vem de P4 e h4.",
                    data_used="Estado 4 calculado por CoolProp com P4=P_evap e h4=h3.",
                    formulas=(r"h_4=h_3", r"x_4=x(P_4,h_4)"),
                    substitution="" if x4 is None else rf"x_4={x4:.6g}",
                    result_text="x4 não aplicável" if x4 is None else f"x4={x4:.6g}",
                    origins=origins,
                )
            )
            continue

        if item == "d" or "vaz" in objective_norm or "mássica" in objective_norm or "massica" in objective_norm:
            if mass_flow and mass_flow.value is not None and q_evap and q_evap.value:
                answers.append(
                    QuestionAnswer(
                        item=question.item or "d",
                        objective=objective,
                        status="respondido",
                        interpretation="A vazão é obtida pela capacidade frigorífica dividida pelo efeito refrigerante específico.",
                        data_used="Capacidade do evaporador e entalpias dos estados 1 e 4.",
                        formulas=(r"\dot m=\frac{\dot Q_L}{h_1-h_4}",),
                        substitution=rf"\dot m=\frac{{\dot Q_L}}{{{h1:.6g}-{h4:.6g}}}={mass_flow.value:.6g}\ \mathrm{{kg/s}}",
                        result_text=f"m_dot={mass_flow.value:.6g} kg/s",
                        origins=origins,
                    )
                )
            else:
                answers.append(
                    QuestionAnswer(
                        item=question.item or "d",
                        objective=objective,
                        status="bloqueado",
                        interpretation="A vazão exige a capacidade frigorífica ou outra informação equivalente de escala.",
                        data_used="Entalpias dos estados 1 e 4 foram calculadas; falta a capacidade do evaporador.",
                        formulas=(r"\dot m=\frac{\dot Q_L}{h_1-h_4}",),
                        substitution="",
                        result_text="Item não resolvido automaticamente: capacidade frigorífica não disponível.",
                        origins=origins,
                    )
                )
            continue

        if item == "e" or "pot" in objective_norm or "compressor" in objective_norm:
            if power and power.value is not None and mass_flow and mass_flow.value is not None and w_comp and w_comp.value is not None:
                answers.append(
                    QuestionAnswer(
                        item=question.item or "e",
                        objective=objective,
                        status="respondido",
                        interpretation="A potência é a vazão mássica multiplicada pelo trabalho específico do compressor.",
                        data_used="Vazão mássica e entalpias dos estados 1 e 2.",
                        formulas=(r"\dot W_{comp}=\dot m(h_2-h_1)",),
                        substitution=rf"\dot W_{{comp}}={mass_flow.value:.6g}({h2:.6g}-{h1:.6g})={_power_w(power.value):.6g}\ \mathrm{{W}}",
                        result_text=f"W_comp={_power_w(power.value):.6g} W",
                        origins=origins,
                    )
                )
            else:
                answers.append(
                    QuestionAnswer(
                        item=question.item or "e",
                        objective=objective,
                        status="bloqueado",
                        interpretation="A potência do compressor exige a vazão mássica e o trabalho específico.",
                        data_used="O trabalho específico foi calculado; a potência fica bloqueada se a vazão não estiver disponível.",
                        formulas=(r"\dot W_{comp}=\dot m(h_2-h_1)",),
                        substitution="",
                        result_text="Item não resolvido automaticamente: vazão mássica indisponível.",
                        origins=origins,
                    )
                )
            continue

        if item == "f" or "cop" in objective_norm or "desempenho" in objective_norm:
            if cop and cop.value is not None:
                answers.append(
                    QuestionAnswer(
                        item=question.item or "f",
                        objective=objective,
                        status="respondido",
                        interpretation="O COP compara o efeito frigorífico com o trabalho de compressão.",
                        data_used="Efeito refrigerante e trabalho específico do compressor.",
                        formulas=(r"COP_R=\frac{h_1-h_4}{h_2-h_1}",),
                        substitution=rf"COP_R=\frac{{{h1:.6g}-{h4:.6g}}}{{{h2:.6g}-{h1:.6g}}}={cop.value:.6g}",
                        result_text=f"COP={cop.value:.6g}",
                        origins=origins,
                    )
                )
            else:
                answers.append(
                    QuestionAnswer(
                        item=question.item or "f",
                        objective=objective,
                        status="bloqueado",
                        interpretation="O COP exige efeito refrigerante e trabalho específico calculados.",
                        data_used="Estados termodinâmicos do ciclo.",
                        formulas=(r"COP_R=\frac{h_1-h_4}{h_2-h_1}",),
                        substitution="",
                        result_text="Item não resolvido automaticamente: métrica COP indisponível.",
                        origins=origins,
                    )
                )
            continue

        answers.append(
            QuestionAnswer(
                item=question.item or "-",
                objective=objective,
                status="bloqueado",
                interpretation="A questão foi identificada, mas ainda não há regra de associação com as métricas do ciclo simples.",
                data_used="Estados e métricas calculadas pelo ciclo de refrigeração.",
                formulas=(),
                substitution="",
                result_text="Item não resolvido automaticamente.",
                origins=origins,
            )
        )
    return tuple(answers)


def _render_question_answer(answer: QuestionAnswer) -> None:
    with st.container(border=True):
        st.markdown(f"**{answer.item}) {answer.objective}**")
        st.caption(f"Status: {answer.status}")
        st.markdown(f"**Interpretação:** {answer.interpretation}")
        st.markdown(f"**Dados usados:** {answer.data_used}")
        if answer.formulas:
            st.markdown("**Fórmula:**")
            for formula in answer.formulas:
                st.latex(formula)
        if answer.substitution:
            st.markdown("**Substituição numérica:**")
            st.latex(answer.substitution)
        _render_result_card("Resultado", answer.result_text)
        if answer.origins:
            with st.expander("Origem das propriedades", expanded=False):
                for origin in answer.origins:
                    st.markdown(f"- {origin}")


def _question_answers_markdown(plan: ThermoPlan | None, execution: ExecutionResult, unit_config: ExerciseUnitConfig) -> str:
    answers = build_question_answers(plan, execution, unit_config)
    if not answers:
        return "## Respostas por questão\n\n- Nenhuma questão planejada foi recebida."
    answered_count = sum(1 for answer in answers if answer.status == "respondido")
    blocked_items = ", ".join(answer.item for answer in answers if answer.status != "respondido") or "-"
    blocks = [
        "## Respostas por questão",
        (
            f"- Questões planejadas: `{len(answers)}`\n"
            f"- Questões respondidas: `{answered_count}`\n"
            f"- Itens bloqueados/parciais: `{blocked_items}`"
        ),
    ]
    for answer in answers:
        formulas = "\n".join(f"- ${formula}$" for formula in answer.formulas) or "- Sem fórmula associada."
        origins = "\n".join(f"- {origin}" for origin in answer.origins) or "- Sem origem associada."
        blocks.append(
            f"""
### {answer.item}) {answer.objective}

- Status: `{answer.status}`
- Interpretação: {answer.interpretation}
- Dados usados: {answer.data_used}
- Fórmulas:
{formulas}
- Substituição: {answer.substitution or "-"}
- Resultado: {answer.result_text}
- Origem das propriedades:
{origins}
""".strip()
        )
    return "\n\n".join(blocks)


def _render_cycle_result_for_exercise(result, unit_config: ExerciseUnitConfig, plan: ThermoPlan | None = None) -> None:
    st.markdown("#### Resultado calculado - Ciclo de refrigeração")
    st.caption(f"Ferramenta: `ciclo_refrigeracao_simples` | Referencia: {result.reference_state}")
    state_map = {state.point: state for state in result.states}
    metric_map = {metric.label: metric for metric in result.metrics}

    q_evap = metric_map.get("Calor absorvido no evaporador")
    w_comp = metric_map.get("Trabalho especifico do compressor")
    q_cond = metric_map.get("Calor rejeitado no condensador")
    cop = metric_map.get("COP real de refrigeracao")
    mass_flow = metric_map.get("Vazao massica")
    power = metric_map.get("Potencia do compressor")
    condenser_heat = metric_map.get("Calor no condensador")

    _render_compact_items(
        (
            ("q_evap", _format_value(_enthalpy_si(q_evap.value if q_evap else None), unit_config.enthalpy_unit)),
            ("w_comp", _format_value(_enthalpy_si(w_comp.value if w_comp else None), unit_config.enthalpy_unit)),
            ("W compressor", _format_value(_power_w(power.value if power else None), unit_config.power_unit)),
            ("COP", _format_value(cop.value if cop else None)),
        )
    )

    origins = tuple(f"Estado {state.point}: {state.origin}. {state.formula}" for state in result.states)
    h1 = _enthalpy_si(state_map["1"].enthalpy)
    h2 = _enthalpy_si(state_map["2"].enthalpy)
    h3 = _enthalpy_si(state_map["3"].enthalpy)
    h4 = _enthalpy_si(state_map["4"].enthalpy)

    answers = build_question_answers(
        plan,
        ExecutionResult(kind="ciclo_refrigeracao_simples", title="Ciclo de refrigeracao", cycle_result=result),
        unit_config,
    )
    if answers:
        st.markdown("##### Respostas por questão")
        for answer in answers:
            _render_question_answer(answer)
        st.markdown("##### Desenvolvimento complementar")

    _render_question_block(
        "a) Entalpias dos estados",
        "As entalpias definem os balanços de energia no evaporador, compressor e condensador.",
        "Estados calculados por CoolProp conforme saturação, superaquecimento, sub-resfriamento e compressão.",
        (r"h_i=h(P_i,T_i)\ \mathrm{ou}\ h_i=h(P_i,x_i)",),
        rf"h_1={h1:.6g},\ h_2={h2:.6g},\ h_3={h3:.6g},\ h_4={h4:.6g}\ \mathrm{{J/kg}}",
        f"h1={h1:.6g} J/kg; h2={h2:.6g} J/kg; h3={h3:.6g} J/kg; h4={h4:.6g} J/kg",
        origins,
    )

    temperatures = []
    for point in ("1", "2", "3", "4"):
        state = state_map[point]
        temperatures.append(f"T{point}={_temperature_from_c(state.temperature, unit_config.temperature_unit):.6g} {unit_config.temperature_unit}")
    _render_question_block(
        "b) Temperaturas dos estados",
        "As temperaturas indicam as condições térmicas em cada ponto do ciclo.",
        f"Unidade global selecionada: {unit_config.temperature_unit}.",
        (r"T_i=T(P_i,h_i)\ \mathrm{ou}\ T_i=T(P_i,x_i)",),
        r",\ ".join(temperatures),
        "; ".join(temperatures),
        origins,
    )

    x4 = state_map["4"].quality
    _render_question_block(
        "c) Título no ponto 4",
        "A válvula de expansão é isoentálpica; o título de entrada do evaporador vem de P4 e h4.",
        "Estado 4 calculado por CoolProp com P4=P_evap e h4=h3.",
        (r"h_4=h_3", r"x_4=x(P_4,h_4)"),
        rf"x_4={0 if x4 is None else x4:.6g}",
        "x4 não aplicável" if x4 is None else f"x4={x4:.6g}",
        origins,
    )

    if mass_flow and mass_flow.value is not None and q_evap and q_evap.value:
        _render_question_block(
            "d) Vazão mássica",
            "A vazão é obtida pela capacidade frigorífica dividida pelo efeito refrigerante específico.",
            "Capacidade do evaporador e entalpias dos estados 1 e 4.",
            (r"\dot m=\frac{\dot Q_L}{h_1-h_4}",),
            rf"\dot m=\frac{{\dot Q_L}}{{{h1:.6g}-{h4:.6g}}}={mass_flow.value:.6g}\ \mathrm{{kg/s}}",
            f"m_dot={mass_flow.value:.6g} kg/s",
            origins,
        )

    if power and power.value is not None and w_comp:
        _render_question_block(
            "e) Potência do compressor",
            "A potência é a vazão mássica multiplicada pelo trabalho específico do compressor.",
            "Vazão mássica e entalpias dos estados 1 e 2.",
            (r"\dot W_{comp}=\dot m(h_2-h_1)",),
            rf"\dot W_{{comp}}={mass_flow.value if mass_flow else 0:.6g}({h2:.6g}-{h1:.6g})={_power_w(power.value):.6g}\ \mathrm{{W}}",
            f"W_comp={_power_w(power.value):.6g} W",
            origins,
        )

    if cop:
        _render_question_block(
            "f) COP do refrigerador",
            "O COP compara o efeito frigorífico com o trabalho de compressão.",
            "Efeito refrigerante e trabalho específico do compressor.",
            (r"COP_R=\frac{h_1-h_4}{h_2-h_1}",),
            rf"COP_R=\frac{{{h1:.6g}-{h4:.6g}}}{{{h2:.6g}-{h1:.6g}}}={cop.value:.6g}",
            f"COP={cop.value:.6g}",
            origins,
        )

    st.markdown("##### Tabela de estados")
    st.dataframe(pd.DataFrame(_cycle_state_rows_si(result, unit_config)), use_container_width=True, hide_index=True)

    st.markdown("##### Indicadores")
    st.dataframe(pd.DataFrame(_cycle_metric_rows_si(result, unit_config)), use_container_width=True, hide_index=True)

    st.markdown("##### Fórmulas principais")
    st.latex(r"q_L=h_1-h_4")
    st.latex(r"w_{comp}=h_2-h_1")
    st.latex(r"\dot W_{comp}=\dot m(h_2-h_1)")
    st.latex(r"COP_R=\frac{q_L}{w_{comp}}")

    st.markdown("##### Diagrama P-h")
    try:
        _render_limited_pyplot(_build_cycle_ph_figure(result, unit_config))
    except Exception as exc:
        st.info(f"Nao foi possivel gerar o diagrama P-h: {exc}")

    st.markdown("##### Validação física")
    for validation in result.validations:
        if validation.startswith("OK"):
            st.success(validation)
        else:
            st.warning(validation)

    st.markdown("##### Versão copiável")
    st.code(_cycle_solution_markdown_si(result, unit_config), language="markdown")


def _cycle_state_rows_si(result, unit_config: ExerciseUnitConfig) -> list[dict[str, object]]:
    rows = []
    for state in result.states:
        rows.append(
            {
                "Estado": state.point,
                "Descrição": state.description,
                f"T [{unit_config.temperature_unit}]": round(_temperature_from_c(state.temperature, unit_config.temperature_unit), 6),
                f"P [{unit_config.pressure_unit}]": round(_pressure_display(state.pressure, result.input.pressure_unit, unit_config.pressure_unit), 6),
                f"h [{unit_config.enthalpy_unit}]": round(_enthalpy_si(state.enthalpy), 6),
                f"s [{unit_config.entropy_unit}]": round(_entropy_si(state.entropy), 6),
                f"v [{unit_config.volume_unit}]": round(state.specific_volume, 9),
                "x": "-" if state.quality is None else round(state.quality, 6),
                "Região": state.region,
            }
        )
    return rows


def _cycle_metric_rows_si(result, unit_config: ExerciseUnitConfig) -> list[dict[str, object]]:
    rows = []
    for metric in result.metrics:
        value = metric.value
        unit = metric.unit
        if unit == "kJ/kg":
            value = _enthalpy_si(value)
            unit = unit_config.enthalpy_unit
        elif unit == "kW":
            value = _power_w(value)
            unit = unit_config.power_unit
        elif unit == "kg/s":
            unit = unit_config.mass_flow_unit
        rows.append(
            {
                "Grandeza": metric.label,
                "Valor": None if value is None else round(value, 6),
                "Unidade": unit,
            }
        )
    return rows


def _standard_cycle_state_rows_si(result: StandardCycleResult, unit_config: ExerciseUnitConfig) -> list[dict[str, object]]:
    rows = []
    for state in result.states:
        rows.append(
            {
                "Estado": state.point,
                "Descrição": state.description,
                f"T [{unit_config.temperature_unit}]": round(_temperature_from_c(state.temperature_c, unit_config.temperature_unit), 6),
                f"P [{unit_config.pressure_unit}]": round(_pressure_display(state.pressure, result.input.pressure_unit, unit_config.pressure_unit), 6),
                f"h [{unit_config.enthalpy_unit}]": round(_enthalpy_si(state.enthalpy), 6),
                f"s [{unit_config.entropy_unit}]": round(_entropy_si(state.entropy), 6),
                "x": "-" if state.quality is None else round(state.quality, 6),
                "Região": state.region,
            }
        )
    return rows


def _standard_cycle_metric_rows_si(result: StandardCycleResult, unit_config: ExerciseUnitConfig) -> list[dict[str, object]]:
    rows = []
    for metric in result.metrics:
        value = metric.value
        unit = metric.unit
        if unit == "kJ/kg":
            value = _enthalpy_si(value)
            unit = unit_config.enthalpy_unit
        elif unit == "kW":
            value = _power_w(value)
            unit = unit_config.power_unit
        elif unit == "kg/s":
            unit = unit_config.mass_flow_unit
        rows.append(
            {
                "Grandeza": metric.label,
                "Valor": None if value is None else round(value, 6),
                "Unidade": unit,
            }
        )
    return rows


def _turbine_state_rows_si(result: TurbineResult, unit_config: ExerciseUnitConfig) -> list[dict[str, object]]:
    rows = []
    for state in result.states:
        rows.append(
            {
                "Estado": state.point,
                "Descrição": state.description,
                f"T [{unit_config.temperature_unit}]": round(_temperature_from_c(state.temperature_c, unit_config.temperature_unit), 6),
                f"P [{unit_config.pressure_unit}]": round(_pressure_display(state.pressure_kpa, "kPa", unit_config.pressure_unit), 6),
                f"h [{unit_config.enthalpy_unit}]": round(_enthalpy_si(state.enthalpy), 6),
                f"s [{unit_config.entropy_unit}]": round(_entropy_si(state.entropy), 6),
                f"v [{unit_config.volume_unit}]": round(state.specific_volume, 9),
                "x": "-" if state.quality is None else round(state.quality, 6),
                "Região": state.region,
            }
        )
    return rows


def _render_standard_cycle_result(result: StandardCycleResult, unit_config: ExerciseUnitConfig) -> None:
    st.markdown("#### Resultado calculado - Ciclo padrao por pressoes")
    st.caption(f"Ferramenta: `ciclo_refrigeracao_padrao_pressao` | Referencia: {result.reference_state}")
    metric_map = {metric.label: metric for metric in result.metrics}
    _render_compact_items(
        (
            ("QL", _format_value(_power_w(metric_map['Calor removido do espaco refrigerado'].value), unit_config.power_unit)),
            ("W compressor", _format_value(_power_w(metric_map['Potencia do compressor'].value), unit_config.power_unit)),
            ("x4", f"{metric_map['Titulo na entrada do evaporador'].value:.6g}"),
            ("COP", f"{metric_map['COP do refrigerador'].value:.6g}"),
        )
    )

    st.markdown("##### a) Taxa de remocao de calor e potencia do compressor")
    st.latex(r"\dot Q_L=\dot m(h_1-h_4)")
    st.latex(r"\dot W_{comp}=\dot m(h_2-h_1)")
    _render_result_card(
        "Resultado",
        f"QL = {_power_w(metric_map['Calor removido do espaco refrigerado'].value):.6g} W; "
        f"W = {_power_w(metric_map['Potencia do compressor'].value):.6g} W",
    )

    st.markdown("##### b) Titulo na entrada do evaporador")
    st.latex(r"x_4=x(P_{baixa},h_4),\quad h_4=h_3")
    _render_result_card("Resultado", f"x4 = {metric_map['Titulo na entrada do evaporador'].value:.6g}")

    st.markdown("##### c) Taxa de rejeicao de calor ao ambiente")
    st.latex(r"\dot Q_H=\dot m(h_2-h_3)")
    _render_result_card("Resultado", f"QH = {_power_w(metric_map['Calor rejeitado ao ambiente'].value):.6g} W")

    st.markdown("##### d) COP do refrigerador")
    st.latex(r"COP_R=\frac{h_1-h_4}{h_2-h_1}=\frac{\dot Q_L}{\dot W_{comp}}")
    _render_result_card("Resultado", f"COP = {metric_map['COP do refrigerador'].value:.6g}")

    st.markdown("##### Estados e indicadores")
    st.dataframe(pd.DataFrame(_standard_cycle_state_rows_si(result, unit_config)), use_container_width=True, hide_index=True)
    st.dataframe(pd.DataFrame(_standard_cycle_metric_rows_si(result, unit_config)), use_container_width=True, hide_index=True)

    st.markdown("##### Origem das propriedades")
    for state in result.states:
        with st.expander(f"Estado {state.point} - {state.description}", expanded=False):
            st.markdown(state.property_source)
            st.latex(_formula_to_latex(state.formula))

    st.markdown("##### e) Diagrama T-s")
    try:
        _render_limited_pyplot(_build_standard_ts_figure_si(result, unit_config))
    except Exception as exc:
        st.info(f"Nao foi possivel gerar o diagrama T-s: {exc}")

    st.markdown("##### Validacao fisica")
    for validation in result.validations:
        if validation.startswith("OK"):
            st.success(validation)
        else:
            st.warning(validation)

    st.markdown("##### Versao copiavel")
    st.code(_standard_cycle_solution_markdown(result, unit_config), language="markdown")


def _render_evaporator_result(result: EvaporatorResult) -> None:
    st.markdown("#### Resultado calculado - Evaporador com ar e R134a")
    st.caption(f"Referencia aplicada ao R134a: {result.reference_state}")
    case_b1 = result.cases[0]
    case_b2 = result.cases[1]
    _render_compact_items(
        (
            ("T saida ar b1", f"{case_b1.air_outlet_temperature_c:.5g} °C"),
            ("Sgen b1", f"{case_b1.entropy_generation_rate:.6g} kW/K"),
            ("T saida ar b2", f"{case_b2.air_outlet_temperature_c:.5g} °C"),
            ("Sgen b2", f"{case_b2.entropy_generation_rate:.6g} kW/K"),
        )
    )

    st.markdown("##### a) Temperatura de saida do ar")
    st.latex(r"\dot{m}_{ar}c_{p,ar}(T_2-T_1)+\dot{m}_{R134a}(h_4-h_3)=\dot{Q}")
    for case in result.cases:
        st.markdown(f"**{case.label}) {case.description}**")
        st.latex(
            rf"T_2=T_1+\frac{{\dot Q-\dot m_R(h_4-h_3)}}{{\dot m_{{ar}}c_p}}"
            rf"={case.air_outlet_temperature_c + 273.15:.5g}\ \mathrm{{K}}"
        )
        _render_result_card("Resultado", f"T_saida_ar = {case.air_outlet_temperature_c:.5g} °C")

    st.markdown("##### b) Taxa de geracao de entropia")
    st.latex(r"\dot{S}_{gen}=\dot{m}_{ar}c_{p,ar}\ln\left(\frac{T_2}{T_1}\right)+\dot{m}_R(s_4-s_3)-\frac{\dot{Q}}{T_b}")
    for case in result.cases:
        st.markdown(f"**{case.label}) {case.description}**")
        st.markdown(
            f"`ΔS_ar = {case.air_entropy_change_rate:.6g} kW/K`, "
            f"`ΔS_R134a = {case.refrigerant_entropy_change_rate:.6g} kW/K`, "
            f"`Q/Tb = {case.heat_entropy_transfer_rate:.6g} kW/K`."
        )
        _render_result_card("Resultado", f"S_gen = {case.entropy_generation_rate:.6g} kW/K")

    st.markdown("##### Estados e casos")
    st.dataframe(pd.DataFrame(evaporator_state_rows(result)), use_container_width=True, hide_index=True)
    st.dataframe(pd.DataFrame(evaporator_case_rows(result)), use_container_width=True, hide_index=True)
    _render_evaporator_sources(result)

    with st.expander("Simbolos e unidades", expanded=True):
        st.latex(r"\dot{m}_{ar}: \mathrm{vazao\ massica\ do\ ar}")
        st.latex(r"\dot{m}_R: \mathrm{vazao\ massica\ do\ R134a}")
        st.latex(r"\dot{S}_{gen}: \mathrm{taxa\ de\ geracao\ de\ entropia}")
        st.latex(r"\dot{Q}: \mathrm{calor\ transferido\ para\ o\ volume\ de\ controle}")
        for note in result.conversion_notes:
            st.markdown(f"- {note}")

    st.markdown("##### Versao copiavel")
    st.code(_evaporator_solution_markdown(result), language="markdown")


def _render_reservoir_result(result: ReservoirCycleResult) -> None:
    st.markdown("#### Resultado calculado - Refrigerador entre reservatorios")
    st.latex(r"COP_{Carnot}=\frac{T_L}{T_H-T_L}")
    st.latex(r"\Delta S_{univ}=\frac{Q_H}{T_H}-\frac{Q_L}{T_L}")
    _render_compact_items(
        tuple((f"Caso {case.label}", f"{case.classification} | COP={case.cop:.6g}") for case in result.cases)
    )

    for case in result.cases:
        with st.container(border=True):
            st.markdown(f"**Caso {case.label}: {case.classification}**")
            st.latex(r"Q_H=Q_L+W_{ciclo}")
            st.latex(rf"COP=\frac{{Q_L}}{{W_{{ciclo}}}}=\frac{{{case.heat_absorbed_low:.6g}}}{{{case.work_input:.6g}}}={case.cop:.6g}")
            st.latex(
                rf"\Delta S_{{univ}}=\frac{{{case.heat_rejected_high:.6g}}}{{{result.input.high_temperature_k:.6g}}}"
                rf"-\frac{{{case.heat_absorbed_low:.6g}}}{{{result.input.low_temperature_k:.6g}}}"
                rf"={case.entropy_universe:.6g}\ \mathrm{{kJ/K}}"
            )
            st.markdown(case.explanation)

    st.markdown("##### Tabela numerica")
    st.dataframe(pd.DataFrame(reservoir_case_rows(result)), use_container_width=True, hide_index=True)

    with st.expander("Simbolos e unidades", expanded=True):
        st.latex(r"Q_L: \mathrm{calor\ recebido\ do\ reservatorio\ frio}")
        st.latex(r"Q_H: \mathrm{calor\ rejeitado\ ao\ reservatorio\ quente}")
        st.latex(r"W_{ciclo}: \mathrm{trabalho\ recebido\ pelo\ ciclo}")
        st.latex(r"COP_R=\frac{Q_L}{W_{ciclo}}")
        for note in result.conversion_notes:
            st.markdown(f"- {note}")

    st.markdown("##### Versao copiavel")
    st.code(_reservoir_solution_markdown(result), language="markdown")


def _render_evaporator_sources(result: EvaporatorResult) -> None:
    st.markdown("##### Origem das propriedades")
    for state in result.states:
        with st.expander(f"{state.stream} - Estado {state.point}", expanded=False):
            st.markdown(state.property_source)
            st.latex(_formula_to_latex(state.formula))


def _evaporator_solution_markdown(result: EvaporatorResult) -> str:
    cases = "\n".join(
        f"- {case.label}: T_saida_ar = {case.air_outlet_temperature_c:.5g} °C; "
        f"S_gen = {case.entropy_generation_rate:.6g} kW/K."
        for case in result.cases
    )
    return f"""
Sistema: evaporador com ar ideal e R134a.

Formula de energia:
\\dot{{m}}_{{ar}} c_{{p,ar}} (T_2-T_1) + \\dot{{m}}_R (h_4-h_3) = \\dot{{Q}}

Formula de entropia:
\\dot{{S}}_{{gen}} = \\dot{{m}}_{{ar}} c_{{p,ar}} \\ln(T_2/T_1) + \\dot{{m}}_R(s_4-s_3) - \\dot{{Q}}/T_b

Resultados:
{cases}
""".strip()


def _reservoir_solution_markdown(result: ReservoirCycleResult) -> str:
    cases = "\n".join(
        f"- Caso {case.label}: QL={case.heat_absorbed_low:.6g} kJ, QH={case.heat_rejected_high:.6g} kJ, "
        f"W={case.work_input:.6g} kJ, COP={case.cop:.6g}, DeltaS_univ={case.entropy_universe:.6g} kJ/K, "
        f"classificacao={case.classification}."
        for case in result.cases
    )
    return f"""
Sistema: refrigerador entre reservatorios termicos.

COP_Carnot = TL/(TH-TL) = {result.cases[0].carnot_cop:.6g}
DeltaS_univ = QH/TH - QL/TL

Resultados:
{cases}
""".strip()


def _cycle_solution_markdown_si(result, unit_config: ExerciseUnitConfig) -> str:
    state_map = {state.point: state for state in result.states}
    metrics = {metric.label: metric for metric in result.metrics}
    mass_flow_value = metrics["Vazao massica"].value
    power_value = _power_w(metrics["Potencia do compressor"].value)
    mass_flow_text = "-" if mass_flow_value is None else f"{mass_flow_value:.6g}"
    power_text = "-" if power_value is None else f"{power_value:.6g}"
    return f"""
## Ciclo de refrigeração por compressão de vapor

### Estados
- Estado 1: $h_1={_enthalpy_si(state_map['1'].enthalpy):.6g}\\ \\mathrm{{J/kg}}$, $s_1={_entropy_si(state_map['1'].entropy):.6g}\\ \\mathrm{{J/(kg.K)}}$, $T_1={_temperature_from_c(state_map['1'].temperature, unit_config.temperature_unit):.6g}\\ {unit_config.temperature_unit}$.
- Estado 2: $h_2={_enthalpy_si(state_map['2'].enthalpy):.6g}\\ \\mathrm{{J/kg}}$, $s_2={_entropy_si(state_map['2'].entropy):.6g}\\ \\mathrm{{J/(kg.K)}}$, $T_2={_temperature_from_c(state_map['2'].temperature, unit_config.temperature_unit):.6g}\\ {unit_config.temperature_unit}$.
- Estado 3: $h_3={_enthalpy_si(state_map['3'].enthalpy):.6g}\\ \\mathrm{{J/kg}}$, $s_3={_entropy_si(state_map['3'].entropy):.6g}\\ \\mathrm{{J/(kg.K)}}$, $T_3={_temperature_from_c(state_map['3'].temperature, unit_config.temperature_unit):.6g}\\ {unit_config.temperature_unit}$.
- Estado 4: $h_4={_enthalpy_si(state_map['4'].enthalpy):.6g}\\ \\mathrm{{J/kg}}$, $s_4={_entropy_si(state_map['4'].entropy):.6g}\\ \\mathrm{{J/(kg.K)}}$, $x_4={state_map['4'].quality if state_map['4'].quality is not None else 'n/a'}$.

### Fórmulas
- $q_L=h_1-h_4$
- $w_{{comp}}=h_2-h_1$
- $\\dot m=\\dot Q_L/q_L$
- $\\dot W_{{comp}}=\\dot m\\,w_{{comp}}$
- $COP_R=q_L/w_{{comp}}$

### Resultados
- $q_L={_enthalpy_si(metrics['Calor absorvido no evaporador'].value):.6g}\\ \\mathrm{{J/kg}}$
- $w_{{comp}}={_enthalpy_si(metrics['Trabalho especifico do compressor'].value):.6g}\\ \\mathrm{{J/kg}}$
- $\\dot m={mass_flow_text}\\ \\mathrm{{kg/s}}$ se a capacidade foi informada.
- $\\dot W_{{comp}}={power_text}\\ \\mathrm{{W}}$ se a capacidade foi informada.
- $COP_R={metrics['COP real de refrigeracao'].value:.6g}$
""".strip()


def _standard_cycle_solution_markdown(result: StandardCycleResult, unit_config: ExerciseUnitConfig) -> str:
    metrics = {metric.label: metric for metric in result.metrics}
    return f"""
Ciclo padrao de refrigeracao por compressao de vapor.

Estados:
- 1: vapor saturado em P_baixa.
- 2: compressao isentropica, s2=s1.
- 3: liquido saturado em P_alta.
- 4: valvula de expansao, h4=h3.

Formulas:
$\\dot Q_L=\\dot m(h_1-h_4)$
$\\dot W=\\dot m(h_2-h_1)$
$x_4=x(P_baixa,h_4)$
$\\dot Q_H=\\dot m(h_2-h_3)$
$COP_R=(h_1-h_4)/(h_2-h_1)$

Resultados:
- $\\dot Q_L$ = {_power_w(metrics['Calor removido do espaco refrigerado'].value):.6g} W
- $\\dot W_{{comp}}$ = {_power_w(metrics['Potencia do compressor'].value):.6g} W
- $x_4$ = {metrics['Titulo na entrada do evaporador'].value:.6g}
- $\\dot Q_H$ = {_power_w(metrics['Calor rejeitado ao ambiente'].value):.6g} W
- $COP_R$ = {metrics['COP do refrigerador'].value:.6g}
""".strip()


def _render_turbine_result(result: TurbineResult, unit_config: ExerciseUnitConfig) -> None:
    st.markdown("#### Resultado calculado")
    metric_map = {metric.label: metric for metric in result.metrics}
    summary = [
        ("Potencia maxima", _power_w(metric_map["Potencia maxima"].value), "W"),
        ("Eficiencia isentropica", metric_map["Eficiencia isentropica da turbina"].value, "-"),
        ("Trabalho maximo", _enthalpy_si(metric_map["Trabalho especifico maximo"].value), "J/kg"),
        ("Potencia real", _power_w(metric_map["Potencia real"].value), "W"),
    ]
    card_html = []
    for label, value, unit in summary:
        value_text = "-" if value is None else f"{value:.5g}"
        card_html.append(
            "<div class='metric-card'>"
            f"<div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value_text} {unit}</div>"
            "</div>"
        )
    st.markdown(f"<div class='metric-grid'>{''.join(card_html)}</div>", unsafe_allow_html=True)
    st.caption(f"Referencia aplicada: {result.reference_state}")

    _render_turbine_questions(result, unit_config)

    with st.expander("Simbolos, unidades e origem das propriedades", expanded=True):
        _render_symbol_box(result)

    st.markdown("##### Tabela de estados")
    state_rows = _turbine_state_rows_si(result, unit_config)
    st.dataframe(
        pd.DataFrame([{key: value for key, value in row.items() if key != "Origem"} for row in state_rows]),
        use_container_width=True,
        hide_index=True,
    )
    _render_turbine_property_sources(result)

    st.markdown("##### Equacoes e resultados")
    _render_turbine_equations(result)

    st.markdown("##### Validacao fisica")
    for validation in result.validations:
        if validation.startswith("OK"):
            st.success(validation)
        else:
            st.warning(validation)

    st.markdown("##### Diagrama T-s")
    try:
        _render_limited_pyplot(_build_ts_figure_si(result, unit_config))
    except Exception as exc:
        st.info(f"Nao foi possivel gerar o diagrama T-s: {exc}")

    st.markdown("##### Versao copiavel")
    st.code(_turbine_solution_markdown(result, unit_config), language="markdown")


def _render_turbine_questions(result: TurbineResult, unit_config: ExerciseUnitConfig) -> None:
    state_map = {state.point: state for state in result.states}
    metric_map = {metric.label: metric for metric in result.metrics}
    st.markdown("##### Questoes resolvidas")

    with st.container(border=True):
        st.markdown("**a) Potencia maxima produzida e estados na condicao ideal**")
        st.markdown("Interpretação: a potência máxima ocorre quando a turbina opera de forma ideal e isentrópica.")
        st.markdown("Dados usados: estado 1 por `P1` e `T1`; estado `2s` por `P2` e `s2s = s1`; vazão mássica informada.")
        st.latex(r"s_{2s}=s_1")
        st.latex(r"\dot{W}_{max}=\dot{m}(h_1-h_{2s})")
        st.latex(
            rf"\dot{{W}}_{{max}}={result.input.mass_flow:.5g}"
            rf"({state_map['1'].enthalpy:.3f}-{state_map['2s'].enthalpy:.3f})"
            rf"={metric_map['Potencia maxima'].value:.5g}\ \mathrm{{kW}}"
        )
        st.markdown(
            f"Desenvolvimento: `h1 = {state_map['1'].enthalpy:.3f} kJ/kg`, "
            f"`h2s = {state_map['2s'].enthalpy:.3f} kJ/kg`, "
            f"`m_dot = {result.input.mass_flow:.5g} kg/s`."
        )
        _render_result_card(
            "Resultado",
            f"Potência máxima = {metric_map['Potencia maxima'].value:.5g} kW. "
            f"O estado 2s fica em {state_map['2s'].region}.",
        )

    if "2" in state_map and metric_map["Eficiencia isentropica da turbina"].value is not None:
        with st.container(border=True):
            st.markdown("**b) Eficiência isentrópica quando a saída real é conhecida**")
            st.markdown("Interpretação: a eficiência compara a queda real de entalpia com a queda ideal isentrópica.")
            st.markdown("Dados usados: estado real 2 por `P2` e `T2`; estado ideal 2s por `P2` e `s1`.")
            st.latex(r"\eta_t=\frac{h_1-h_2}{h_1-h_{2s}}")
            st.latex(
                rf"\eta_t=\frac{{{state_map['1'].enthalpy:.3f}-{state_map['2'].enthalpy:.3f}}}"
                rf"{{{state_map['1'].enthalpy:.3f}-{state_map['2s'].enthalpy:.3f}}}"
                rf"={metric_map['Eficiencia isentropica da turbina'].value:.5g}"
            )
            st.markdown(
                f"Desenvolvimento: `h2 = {state_map['2'].enthalpy:.3f} kJ/kg`; "
                f"`h1-h2 = {state_map['1'].enthalpy - state_map['2'].enthalpy:.3f} kJ/kg`; "
                f"`h1-h2s = {state_map['1'].enthalpy - state_map['2s'].enthalpy:.3f} kJ/kg`."
            )
            _render_result_card(
                "Resultado",
                f"Eficiência isentrópica da turbina = {metric_map['Eficiencia isentropica da turbina'].value:.5g}.",
            )

    with st.container(border=True):
        st.markdown("**c) Diagrama T-s e comparação ideal x real**")
        st.markdown("Interpretação: no processo ideal a entropia permanece constante; no processo real a entropia aumenta.")
        st.latex(r"\Delta s_{ideal}=0")
        if "2" in state_map:
            st.latex(r"\Delta s_{real}=s_2-s_1")
            st.markdown(
                f"Desenvolvimento: `s1 = {state_map['1'].entropy:.5f}`, "
                f"`s2s = {state_map['2s'].entropy:.5f}`, "
                f"`s2 = {state_map['2'].entropy:.5f}` kJ/(kg.K)."
            )
            _render_result_card("Resultado", "A curva real aparece deslocada para a direita no diagrama T-s.")
        else:
            _render_result_card("Resultado", "O diagrama mostra a expansão ideal vertical em T-s.")


def _render_turbine_property_sources(result: TurbineResult) -> None:
    st.markdown("##### Origem das propriedades")
    for state in result.states:
        with st.expander(f"Estado {state.point} - {state.description}", expanded=False):
            st.markdown(state.property_source)
            st.latex(_formula_to_latex(state.formula))


def _render_turbine_equations(result: TurbineResult) -> None:
    for metric in result.metrics:
        if metric.value is None:
            continue
        with st.container(border=True):
            st.markdown(f"**{metric.label}**")
            st.latex(_formula_to_latex(metric.formula))
            st.markdown(f"Resultado: `{metric.value:.6g} {metric.unit}`")


def _render_result_card(label: str, value: str) -> None:
    st.markdown(
        "<div class='result-card'>"
        f"<strong>{escape(label)}</strong>"
        f"<div class='result-value'>{escape(value)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _formula_to_latex(formula: str) -> str:
    mappings = {
        "w_max = h1 - h2s": r"w_{max}=h_1-h_{2s}",
        "W_dot_max = m_dot * (h1 - h2s)": r"\dot{W}_{max}=\dot{m}(h_1-h_{2s})",
        "w_real = h1 - h2": r"w_{real}=h_1-h_2",
        "W_dot_real = m_dot * (h1 - h2)": r"\dot{W}_{real}=\dot{m}(h_1-h_2)",
        "eta_t = (h1 - h2) / (h1 - h2s)": r"\eta_t=\frac{h_1-h_2}{h_1-h_{2s}}",
    }
    for key, value in mappings.items():
        if key in formula:
            return value
    if "h1 = h(P1,T1)" in formula:
        return r"h_1=h(P_1,T_1),\quad s_1=s(P_1,T_1)"
    if "h2s = h(P2,s1)" in formula:
        return r"h_{2s}=h(P_2,s_1),\quad T_{2s}=T(P_2,s_1)"
    if "h2 = h(P2,T2)" in formula:
        return r"h_2=h(P_2,T_2),\quad s_2=s(P_2,T_2)"
    if "h3" in formula and "hf" in formula:
        return r"h_3=h_f+x_3(h_g-h_f),\quad s_3=s_f+x_3(s_g-s_f)"
    if "h4" in formula and "hg" in formula:
        return r"h_4=h_g(P),\quad s_4=s_g(P)"
    if "x1 = 1" in formula:
        return r"x_1=1,\quad h_1=h_g(P_{baixa}),\quad s_1=s_g(P_{baixa})"
    if "s2 = s1" in formula:
        return r"s_2=s_1,\quad h_2=h(P_{alta},s_1)"
    if "x3 = 0" in formula:
        return r"x_3=0,\quad h_3=h_f(P_{alta}),\quad s_3=s_f(P_{alta})"
    if "h4 = h3" in formula:
        return r"h_4=h_3,\quad P_4=P_{baixa}"
    if "T2 = T1" in formula:
        return r"T_2=T_1+\frac{\dot Q-\dot m_R(h_4-h_3)}{\dot m_{ar}c_p}"
    if "Sgen" in formula:
        return r"\dot S_{gen}=\dot m_{ar}c_p\ln\left(\frac{T_2}{T_1}\right)+\dot m_R(s_4-s_3)-\frac{\dot Q}{T_b}"
    return r"\text{" + formula.replace("_", r"\_") + "}"


def _build_cycle_ph_figure(result, unit_config: ExerciseUnitConfig):
    import matplotlib.pyplot as plt
    from CoolProp.CoolProp import PropsSI

    fluid = result.input.fluid
    p_min = PropsSI(fluid, "ptriple") * 1.05
    p_max = PropsSI(fluid, "pcrit") * 0.98
    pressures = [p_min * (p_max / p_min) ** (index / 119) for index in range(120)]
    h_liq = [PropsSI("H", "P", pressure, "Q", 0, fluid) for pressure in pressures]
    h_vap = [PropsSI("H", "P", pressure, "Q", 1, fluid) for pressure in pressures]
    p_values = [pa_to_pressure(pressure, unit_config.pressure_unit) for pressure in pressures]

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=120)
    ax.plot(h_liq, p_values, color="#0057a6", linewidth=1.5, label="Liquido saturado")
    ax.plot(h_vap, p_values, color="#f58220", linewidth=1.5, label="Vapor saturado")

    state_map = {state.point: state for state in result.states}
    cycle_points = [state_map[key] for key in ("1", "2", "3", "4", "1")]
    ax.plot(
        [_enthalpy_si(state.enthalpy) for state in cycle_points],
        [_pressure_display(state.pressure, result.input.pressure_unit, unit_config.pressure_unit) for state in cycle_points],
        color="#111827",
        marker="o",
        linewidth=1.8,
        label="Ciclo",
    )

    for state in result.states:
        h_value = _enthalpy_si(state.enthalpy)
        p_value = _pressure_display(state.pressure, result.input.pressure_unit, unit_config.pressure_unit)
        quality_line = "" if state.quality is None else f"\nx={state.quality:.3g}"
        label = (
            f"{state.point}\n"
            f"P={p_value:.3g} {unit_config.pressure_unit}\n"
            f"T={_temperature_from_c(state.temperature, unit_config.temperature_unit):.3g} {unit_config.temperature_unit}\n"
            f"h={h_value:.3g} J/kg\n"
            f"s={_entropy_si(state.entropy):.3g} J/(kg.K)\n"
            f"v={state.specific_volume:.3g} m3/kg"
            f"{quality_line}"
        )
        ax.annotate(
            label,
            (h_value, p_value),
            textcoords="offset points",
            xytext=(7, 7),
            fontsize=7,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#d8e1ea", "alpha": 0.9},
        )

    ax.set_xlabel("Entalpia especifica h [J/kg]")
    ax.set_ylabel(f"Pressao P [{unit_config.pressure_unit}]")
    ax.set_title(f"Diagrama P-h - {fluid}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def _build_standard_ts_figure_si(result: StandardCycleResult, unit_config: ExerciseUnitConfig):
    import matplotlib.pyplot as plt
    from CoolProp.CoolProp import PropsSI

    fluid = result.input.fluid
    t_min = PropsSI(fluid, "Ttriple") + 1
    t_max = PropsSI(fluid, "Tcrit") - 1
    temperatures = [t_min + index * (t_max - t_min) / 119 for index in range(120)]
    s_liq = [PropsSI("S", "T", temperature, "Q", 0, fluid) for temperature in temperatures]
    s_vap = [PropsSI("S", "T", temperature, "Q", 1, fluid) for temperature in temperatures]
    t_values = [_temperature_from_k(temperature, unit_config.temperature_unit) for temperature in temperatures]

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=120)
    ax.plot(s_liq, t_values, color="#0057a6", linewidth=1.5, label="Liquido saturado")
    ax.plot(s_vap, t_values, color="#f58220", linewidth=1.5, label="Vapor saturado")

    state_map = {state.point: state for state in result.states}
    cycle_points = [state_map[key] for key in ("1", "2", "3", "4", "1")]
    ax.plot(
        [_entropy_si(state.entropy) for state in cycle_points],
        [_temperature_from_c(state.temperature_c, unit_config.temperature_unit) for state in cycle_points],
        color="#111827",
        marker="o",
        linewidth=1.8,
        label="Ciclo padrao",
    )

    for state in result.states:
        s_value = _entropy_si(state.entropy)
        t_value = _temperature_from_c(state.temperature_c, unit_config.temperature_unit)
        p_value = _pressure_display(state.pressure, result.input.pressure_unit, unit_config.pressure_unit)
        quality_line = "" if state.quality is None else f"\nx={state.quality:.3g}"
        label = (
            f"{state.point}\n"
            f"P={p_value:.3g} {unit_config.pressure_unit}\n"
            f"T={t_value:.3g} {unit_config.temperature_unit}\n"
            f"h={_enthalpy_si(state.enthalpy):.3g} J/kg\n"
            f"s={s_value:.3g} J/(kg.K)"
            f"{quality_line}"
        )
        ax.annotate(
            label,
            (s_value, t_value),
            textcoords="offset points",
            xytext=(7, 7),
            fontsize=7,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#d8e1ea", "alpha": 0.9},
        )

    ax.set_xlabel("Entropia especifica s [J/(kg.K)]")
    ax.set_ylabel(f"Temperatura T [{unit_config.temperature_unit}]")
    ax.set_title(f"Diagrama T-s - {fluid}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def _build_ts_figure_si(result: TurbineResult, unit_config: ExerciseUnitConfig):
    import matplotlib.pyplot as plt
    from CoolProp.CoolProp import PropsSI

    fluid = result.input.fluid
    t_min = PropsSI(fluid, "Ttriple") + 1
    t_max = PropsSI(fluid, "Tcrit") - 1
    temperatures = [t_min + index * (t_max - t_min) / 119 for index in range(120)]
    s_liq = [PropsSI("S", "T", temperature, "Q", 0, fluid) for temperature in temperatures]
    s_vap = [PropsSI("S", "T", temperature, "Q", 1, fluid) for temperature in temperatures]
    t_values = [_temperature_from_k(temperature, unit_config.temperature_unit) for temperature in temperatures]

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=120)
    ax.plot(s_liq, t_values, color="#0057a6", linewidth=1.5, label="Liquido saturado")
    ax.plot(s_vap, t_values, color="#f58220", linewidth=1.5, label="Vapor saturado")

    state_map = {state.point: state for state in result.states}
    ax.plot(
        [_entropy_si(state_map["1"].entropy), _entropy_si(state_map["2s"].entropy)],
        [
            _temperature_from_c(state_map["1"].temperature_c, unit_config.temperature_unit),
            _temperature_from_c(state_map["2s"].temperature_c, unit_config.temperature_unit),
        ],
        color="#111827",
        marker="o",
        linewidth=1.8,
        label="Expansao ideal",
    )
    if "2" in state_map:
        ax.plot(
            [_entropy_si(state_map["1"].entropy), _entropy_si(state_map["2"].entropy)],
            [
                _temperature_from_c(state_map["1"].temperature_c, unit_config.temperature_unit),
                _temperature_from_c(state_map["2"].temperature_c, unit_config.temperature_unit),
            ],
            color="#7c2d12",
            marker="o",
            linestyle="--",
            linewidth=1.8,
            label="Expansao real",
        )

    for state in result.states:
        s_value = _entropy_si(state.entropy)
        t_value = _temperature_from_c(state.temperature_c, unit_config.temperature_unit)
        p_value = _pressure_display(state.pressure_kpa, "kPa", unit_config.pressure_unit)
        quality_line = "" if state.quality is None else f"\nx={state.quality:.3g}"
        label = (
            f"{state.point}\n"
            f"P={p_value:.3g} {unit_config.pressure_unit}\n"
            f"T={t_value:.3g} {unit_config.temperature_unit}\n"
            f"h={_enthalpy_si(state.enthalpy):.3g} J/kg\n"
            f"s={s_value:.3g} J/(kg.K)\n"
            f"v={state.specific_volume:.3g} m3/kg"
            f"{quality_line}"
        )
        ax.annotate(
            label,
            (s_value, t_value),
            textcoords="offset points",
            xytext=(7, 7),
            fontsize=7,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#d8e1ea", "alpha": 0.9},
        )

    ax.set_xlabel("Entropia especifica s [J/(kg.K)]")
    ax.set_ylabel(f"Temperatura T [{unit_config.temperature_unit}]")
    ax.set_title("Diagrama T-s - Turbina")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def _build_standard_ts_figure(result: StandardCycleResult):
    import matplotlib.pyplot as plt
    from CoolProp.CoolProp import PropsSI

    fluid = result.input.fluid
    t_min = PropsSI(fluid, "Ttriple") + 1
    t_max = PropsSI(fluid, "Tcrit") - 1
    temperatures = [t_min + index * (t_max - t_min) / 119 for index in range(120)]
    s_liq = []
    s_vap = []
    t_values = []
    for temperature in temperatures:
        s_liq.append(PropsSI("S", "T", temperature, "Q", 0, fluid) / 1000)
        s_vap.append(PropsSI("S", "T", temperature, "Q", 1, fluid) / 1000)
        t_values.append(temperature - 273.15)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    ax.plot(s_liq, t_values, color="#0057a6", linewidth=1.5, label="Liquido saturado")
    ax.plot(s_vap, t_values, color="#f58220", linewidth=1.5, label="Vapor saturado")

    state_map = {state.point: state for state in result.states}
    cycle_points = [state_map[key] for key in ("1", "2", "3", "4", "1")]
    ax.plot(
        [state.entropy for state in cycle_points],
        [state.temperature_c for state in cycle_points],
        color="#111827",
        marker="o",
        linewidth=1.8,
        label="Ciclo padrao",
    )

    for state in result.states:
        quality_line = "" if state.quality is None else f"\nx={state.quality:.3g}"
        label = (
            f"{state.point}\n"
            f"P={state.pressure:.3g} {result.input.pressure_unit}\n"
            f"T={state.temperature_c:.3g} °C\n"
            f"s={state.entropy:.3g}"
            f"{quality_line}"
        )
        ax.annotate(
            label,
            (state.entropy, state.temperature_c),
            textcoords="offset points",
            xytext=(7, 7),
            fontsize=7.5,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#d8e1ea", "alpha": 0.9},
        )

    ax.set_xlabel("Entropia especifica s [kJ/(kg.K)]")
    ax.set_ylabel("Temperatura T [°C]")
    ax.set_title(f"Diagrama T-s - {fluid}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def _build_ts_figure(result: TurbineResult):
    import matplotlib.pyplot as plt
    from CoolProp.CoolProp import PropsSI

    fluid = result.input.fluid
    t_min = PropsSI(fluid, "Ttriple") + 1
    t_max = PropsSI(fluid, "Tcrit") - 1
    temperatures = [t_min + index * (t_max - t_min) / 119 for index in range(120)]
    s_liq = []
    s_vap = []
    t_values = []
    for temperature in temperatures:
        s_liq.append(PropsSI("S", "T", temperature, "Q", 0, fluid) / 1000)
        s_vap.append(PropsSI("S", "T", temperature, "Q", 1, fluid) / 1000)
        t_values.append(temperature - 273.15)

    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    ax.plot(s_liq, t_values, color="#0057a6", linewidth=1.5, label="Liquido saturado")
    ax.plot(s_vap, t_values, color="#f58220", linewidth=1.5, label="Vapor saturado")

    state_map = {state.point: state for state in result.states}
    ax.plot(
        [state_map["1"].entropy, state_map["2s"].entropy],
        [state_map["1"].temperature_c, state_map["2s"].temperature_c],
        color="#111827",
        marker="o",
        linewidth=1.8,
        label="Expansao ideal",
    )
    if "2" in state_map:
        ax.plot(
            [state_map["1"].entropy, state_map["2"].entropy],
            [state_map["1"].temperature_c, state_map["2"].temperature_c],
            color="#7c2d12",
            marker="o",
            linestyle="--",
            linewidth=1.8,
            label="Expansao real",
        )

    for state in result.states:
        quality_line = "" if state.quality is None else f"\nx={state.quality:.3g}"
        label = (
            f"{state.point}\n"
            f"P={state.pressure_kpa:.3g} kPa\n"
            f"T={state.temperature_c:.3g} °C\n"
            f"v={state.specific_volume:.3g} m³/kg\n"
            f"s={state.entropy:.3g}"
            f"{quality_line}"
        )
        ax.annotate(
            label,
            (state.entropy, state.temperature_c),
            textcoords="offset points",
            xytext=(7, 7),
            fontsize=7.5,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#d8e1ea", "alpha": 0.9},
        )

    ax.set_xlabel("Entropia especifica s [kJ/(kg.K)]")
    ax.set_ylabel("Temperatura T [C]")
    ax.set_title("Diagrama T-s - Turbina")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def _turbine_solution_markdown(result: TurbineResult, unit_config: ExerciseUnitConfig) -> str:
    assumptions = "\n".join(f"- {item}" for item in result.assumptions)
    states = "\n".join(
        f"- Estado {state.point}: {state.description}. {state.formula} "
        f"$h = {_enthalpy_si(state.enthalpy):.3f}\\ \\mathrm{{J/kg}}$, "
        f"$s = {_entropy_si(state.entropy):.5f}\\ \\mathrm{{J/(kg.K)}}$, "
        f"$T = {_temperature_from_c(state.temperature_c, unit_config.temperature_unit):.3f}\\ {unit_config.temperature_unit}$, "
        f"$P = {_pressure_display(state.pressure_kpa, 'kPa', unit_config.pressure_unit):.3f}\\ {unit_config.pressure_unit}$."
        for state in result.states
    )
    metrics = "\n".join(
        f"- {metric.label}: {metric.formula}"
        + (f" = {metric.value:.5g} {metric.unit}." if metric.value is not None else ".")
        for metric in result.metrics
    )
    conversions = "\n".join(f"- {note}" for note in result.conversion_notes)
    return f"""
**1. Sistema fisico:** turbina de vapor isolada operando em regime permanente.

**2. Hipoteses adotadas:**
{assumptions}

**3. Estados termodinamicos:**
{states}

**4. Modelo e calculos:**
{metrics}

**5. Conversoes usadas:**
{conversions}

**6. Interpretacao:** a potencia maxima ocorre na expansao isentropica, pois nao ha geracao de entropia no caso ideal. A condicao real apresenta maior entropia de saida e menor queda de entalpia aproveitavel.
""".strip()


def _render_symbol_box(result: TurbineResult) -> None:
    st.markdown("##### Simbolos e unidades")
    st.latex(r"P: \mathrm{pressao\ absoluta}")
    st.latex(r"T: \mathrm{temperatura}")
    st.latex(r"h: \mathrm{entalpia\ especifica}")
    st.latex(r"s: \mathrm{entropia\ especifica}")
    st.latex(r"v: \mathrm{volume\ especifico}")
    st.latex(r"x: \mathrm{titulo\ da\ mistura\ liquido\text{-}vapor}")
    st.latex(r"\dot{m}: \mathrm{vazao\ massica}")
    st.latex(r"\dot{W}: \mathrm{potencia}")
    st.latex(r"\eta_t: \mathrm{eficiencia\ isentropica\ da\ turbina}")
    st.markdown("##### Conversoes")
    for note in result.conversion_notes:
        st.markdown(f"- {note}")


def _planner_item_rows(items: tuple[PlannerItem, ...]) -> list[dict[str, str]]:
    return [
        {
            "Nome": item.nome,
            "Valor": item.valor,
            "Unidade": item.unidade,
            "Observacao": item.observacao,
        }
        for item in items
    ]


def _state_rows(states: tuple[PlannedState, ...]) -> list[dict[str, str]]:
    return [
        {
            "Estado": state.estado,
            "Descricao": state.descricao,
            "Dados conhecidos": "; ".join(f"{item.nome}={item.valor} {item.unidade}".strip() for item in state.dados_conhecidos),
            "Propriedades a calcular": ", ".join(state.propriedades_a_calcular),
        }
        for state in states
    ]


def _question_rows(questions: tuple[PlannedQuestion, ...]) -> list[dict[str, str]]:
    return [
        {
            "Item": question.item,
            "Enunciado": question.enunciado,
            "Objetivo": question.objetivo,
            "Ferramentas": ", ".join(question.ferramentas_necessarias),
            "Propriedades a calcular": ", ".join(question.propriedades_a_calcular),
            "Resultado esperado": question.resultado_esperado,
        }
        for question in questions
    ]

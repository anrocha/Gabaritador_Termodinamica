from __future__ import annotations

import hashlib
import re
from html import escape

import pandas as pd
import streamlit as st

from heat_transfer_assistant import HeatTransferPlan, interpret_heat_transfer_problem
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
from heat_transfer_diagrams import build_heat_transfer_figure
from heat_transfer_executor import execute_heat_transfer_plan
from heat_transfer_executor import main_heat_transfer_tool
from heat_transfer_facts import canonical_heat_facts, normalize_heat_text
from heat_transfer_logger import (
    log_heat_transfer_error,
    log_heat_transfer_input,
    log_heat_transfer_output,
    log_heat_transfer_plan,
    new_heat_transfer_run_id,
)


def render_heat_transfer_tab() -> None:
    st.markdown("### Gabaritador Transferência de Calor")
    st.caption(
        "MVP isolado para condução, convecção, radiação, aletas e transientes concentrados. A disciplina é escolhida pela aba; "
        "não há roteamento automático entre Termodinâmica e Transferência de Calor."
    )

    with st.expander("Escopo desta primeira versão", expanded=False):
        st.markdown(
            """
            - Resolve ferramentas determinísticas da Fase 1 e os primeiros modelos da Fase 2.
            - Usa SI para cálculo e exibição.
            - Usa OpenAI apenas para interpretar e planejar; os cálculos são determinísticos.
            - Não inventa propriedades de material: `k`, `h` e `epsilon` devem ser informados.
            """
        )

    assistant_result = _render_assistant_panel()
    if isinstance(assistant_result, HeatTransferResult):
        plan = st.session_state.get("ht_plan")
        _render_result(assistant_result, plan if isinstance(plan, HeatTransferPlan) else None)
        st.divider()

    left, right = st.columns([0.36, 0.64], gap="large")
    with left:
        result = _render_input_panel()
    with right:
        if result is None:
            _render_empty_state()
        else:
            _render_result(result)


def _render_input_panel() -> HeatTransferResult | None:
    st.subheader("Ferramenta determinística")
    tool = st.selectbox(
        "Modelo físico",
        (
            "Condução plana 1D",
            "Condução radial em cilindro",
            "Condução radial em esfera",
            "Convecção",
            "Radiação superfície-vizinhança",
            "Rede de resistências - série",
            "Rede de resistências - paralelo",
            "Aleta reta - ponta adiabática",
            "Capacitância concentrada",
            "Trocador LMTD",
            "Trocador Efetividade-NTU",
            "Convecção forçada - Dittus-Boelter",
        ),
        key="ht_tool",
    )

    try:
        if tool == "Condução plana 1D":
            return _plane_inputs()
        if tool == "Condução radial em cilindro":
            return _cylinder_inputs()
        if tool == "Condução radial em esfera":
            return _sphere_inputs()
        if tool == "Convecção":
            return _convection_inputs()
        if tool == "Radiação superfície-vizinhança":
            return _radiation_inputs()
        if tool == "Rede de resistências - série":
            return _resistance_network_inputs("serie")
        if tool == "Rede de resistências - paralelo":
            return _resistance_network_inputs("paralelo")
        if tool == "Aleta reta - ponta adiabática":
            return _fin_inputs()
        if tool == "Capacitância concentrada":
            return _lumped_inputs()
        if tool == "Trocador LMTD":
            return _lmtd_inputs()
        if tool == "Trocador Efetividade-NTU":
            return _ntu_inputs()
        return _dittus_boelter_inputs()
    except HeatTransferCalculationError as exc:
        st.error(f"Não foi possível calcular: {exc}")
        return None


def _plane_inputs() -> HeatTransferResult | None:
    conductivity = st.number_input("Condutividade k [W/(m.K)]", value=0.8, min_value=0.0, step=0.1, format="%.6f", key="ht_plane_k")
    area = st.number_input("Área A [m²]", value=1.0, min_value=0.0, step=0.1, format="%.6f", key="ht_plane_area")
    thickness = st.number_input("Espessura L [m]", value=0.1, min_value=0.0, step=0.01, format="%.6f", key="ht_plane_l")
    hot_temperature = st.number_input("Temperatura T1 [°C]", value=80.0, step=5.0, format="%.6f", key="ht_plane_t1")
    cold_temperature = st.number_input("Temperatura T2 [°C]", value=20.0, step=5.0, format="%.6f", key="ht_plane_t2")
    if st.button("Calcular condução plana", type="primary", use_container_width=True, key="ht_plane_calc"):
        return calculate_plane_conduction(conductivity, area, thickness, hot_temperature, cold_temperature)
    return None


def _cylinder_inputs() -> HeatTransferResult | None:
    conductivity = st.number_input("Condutividade k [W/(m.K)]", value=15.0, min_value=0.0, step=1.0, format="%.6f", key="ht_cyl_k")
    length = st.number_input("Comprimento L [m]", value=1.0, min_value=0.0, step=0.1, format="%.6f", key="ht_cyl_l")
    inner_radius = st.number_input("Raio interno ri [m]", value=0.02, min_value=0.0, step=0.005, format="%.6f", key="ht_cyl_ri")
    outer_radius = st.number_input("Raio externo ro [m]", value=0.04, min_value=0.0, step=0.005, format="%.6f", key="ht_cyl_ro")
    inner_temperature = st.number_input("Temperatura interna Ti [°C]", value=120.0, step=5.0, format="%.6f", key="ht_cyl_ti")
    outer_temperature = st.number_input("Temperatura externa To [°C]", value=30.0, step=5.0, format="%.6f", key="ht_cyl_to")
    if st.button("Calcular condução cilíndrica", type="primary", use_container_width=True, key="ht_cyl_calc"):
        return calculate_cylinder_conduction(conductivity, length, inner_radius, outer_radius, inner_temperature, outer_temperature)
    return None


def _sphere_inputs() -> HeatTransferResult | None:
    conductivity = st.number_input("Condutividade k [W/(m.K)]", value=1.5, min_value=0.0, step=0.1, format="%.6f", key="ht_sph_k")
    inner_radius = st.number_input("Raio interno ri [m]", value=0.05, min_value=0.0, step=0.005, format="%.6f", key="ht_sph_ri")
    outer_radius = st.number_input("Raio externo ro [m]", value=0.08, min_value=0.0, step=0.005, format="%.6f", key="ht_sph_ro")
    inner_temperature = st.number_input("Temperatura interna Ti [°C]", value=100.0, step=5.0, format="%.6f", key="ht_sph_ti")
    outer_temperature = st.number_input("Temperatura externa To [°C]", value=25.0, step=5.0, format="%.6f", key="ht_sph_to")
    if st.button("Calcular condução esférica", type="primary", use_container_width=True, key="ht_sph_calc"):
        return calculate_sphere_conduction(conductivity, inner_radius, outer_radius, inner_temperature, outer_temperature)
    return None


def _convection_inputs() -> HeatTransferResult | None:
    coefficient = st.number_input("Coeficiente h [W/(m².K)]", value=25.0, min_value=0.0, step=1.0, format="%.6f", key="ht_conv_h")
    area = st.number_input("Área A [m²]", value=1.0, min_value=0.0, step=0.1, format="%.6f", key="ht_conv_area")
    surface_temperature = st.number_input("Temperatura da superfície Ts [°C]", value=70.0, step=5.0, format="%.6f", key="ht_conv_ts")
    fluid_temperature = st.number_input("Temperatura do fluido T∞ [°C]", value=20.0, step=5.0, format="%.6f", key="ht_conv_tinf")
    if st.button("Calcular convecção", type="primary", use_container_width=True, key="ht_conv_calc"):
        return calculate_convection(coefficient, area, surface_temperature, fluid_temperature)
    return None


def _radiation_inputs() -> HeatTransferResult | None:
    emissivity = st.number_input("Emissividade epsilon [-]", value=0.8, min_value=0.0, max_value=1.0, step=0.05, format="%.6f", key="ht_rad_eps")
    area = st.number_input("Área A [m²]", value=1.0, min_value=0.0, step=0.1, format="%.6f", key="ht_rad_area")
    surface_temperature = st.number_input("Temperatura da superfície Ts [°C]", value=100.0, step=5.0, format="%.6f", key="ht_rad_ts")
    surroundings_temperature = st.number_input("Temperatura da vizinhança Tsur [°C]", value=25.0, step=5.0, format="%.6f", key="ht_rad_tsur")
    if st.button("Calcular radiação", type="primary", use_container_width=True, key="ht_rad_calc"):
        return calculate_radiation(emissivity, area, surface_temperature, surroundings_temperature)
    return None


def _resistance_network_inputs(mode: str) -> HeatTransferResult | None:
    mode_label = "série" if mode == "serie" else "paralelo"
    resistance_text = st.text_input(
        "Resistências térmicas R_i [K/W]",
        value="0.10, 0.20, 0.05",
        key=f"ht_res_{mode}_list",
        help="Informe valores separados por vírgula. Ex.: 0.10, 0.20, 0.05",
    )
    hot_temperature = st.number_input("Temperatura quente [°C]", value=80.0, step=5.0, format="%.6f", key=f"ht_res_{mode}_th")
    cold_temperature = st.number_input("Temperatura fria [°C]", value=20.0, step=5.0, format="%.6f", key=f"ht_res_{mode}_tc")
    if st.button(f"Calcular rede em {mode_label}", type="primary", use_container_width=True, key=f"ht_res_{mode}_calc"):
        resistances = _parse_float_list(resistance_text)
        if mode == "serie":
            return calculate_series_resistance_network(resistances, hot_temperature, cold_temperature)
        return calculate_parallel_resistance_network(resistances, hot_temperature, cold_temperature)
    return None


def _fin_inputs() -> HeatTransferResult | None:
    coefficient = st.number_input("Coeficiente h [W/(m².K)]", value=30.0, min_value=0.0, step=1.0, format="%.6f", key="ht_fin_h")
    perimeter = st.number_input("Perímetro molhado P [m]", value=0.08, min_value=0.0, step=0.005, format="%.6f", key="ht_fin_p")
    conductivity = st.number_input("Condutividade k [W/(m.K)]", value=200.0, min_value=0.0, step=5.0, format="%.6f", key="ht_fin_k")
    cross_section_area = st.number_input("Área da seção Ac [m²]", value=0.0004, min_value=0.0, step=0.0001, format="%.8f", key="ht_fin_ac")
    length = st.number_input("Comprimento L [m]", value=0.1, min_value=0.0, step=0.01, format="%.6f", key="ht_fin_l")
    base_temperature = st.number_input("Temperatura da base Tb [°C]", value=100.0, step=5.0, format="%.6f", key="ht_fin_tb")
    fluid_temperature = st.number_input("Temperatura do fluido T∞ [°C]", value=25.0, step=5.0, format="%.6f", key="ht_fin_tinf")
    if st.button("Calcular aleta", type="primary", use_container_width=True, key="ht_fin_calc"):
        return calculate_straight_fin_adiabatic_tip(
            coefficient,
            perimeter,
            conductivity,
            cross_section_area,
            length,
            base_temperature,
            fluid_temperature,
        )
    return None


def _lumped_inputs() -> HeatTransferResult | None:
    coefficient = st.number_input("Coeficiente h [W/(m².K)]", value=10.0, min_value=0.0, step=1.0, format="%.6f", key="ht_lumped_h")
    area = st.number_input("Área A [m²]", value=0.1, min_value=0.0, step=0.01, format="%.6f", key="ht_lumped_area")
    density = st.number_input("Densidade rho [kg/m³]", value=7800.0, min_value=0.0, step=100.0, format="%.6f", key="ht_lumped_rho")
    volume = st.number_input("Volume V [m³]", value=0.001, min_value=0.0, step=0.0001, format="%.8f", key="ht_lumped_v")
    specific_heat = st.number_input("Calor específico cp [J/(kg.K)]", value=500.0, min_value=0.0, step=10.0, format="%.6f", key="ht_lumped_cp")
    conductivity = st.number_input("Condutividade k [W/(m.K)]", value=50.0, min_value=0.0, step=1.0, format="%.6f", key="ht_lumped_k")
    initial_temperature = st.number_input("Temperatura inicial Ti [°C]", value=100.0, step=5.0, format="%.6f", key="ht_lumped_ti")
    fluid_temperature = st.number_input("Temperatura do fluido T∞ [°C]", value=20.0, step=5.0, format="%.6f", key="ht_lumped_tinf")
    time = st.number_input("Tempo t [s]", value=60.0, min_value=0.0, step=10.0, format="%.6f", key="ht_lumped_t")
    if st.button("Calcular transiente concentrado", type="primary", use_container_width=True, key="ht_lumped_calc"):
        return calculate_lumped_capacitance(
            coefficient,
            area,
            density,
            volume,
            specific_heat,
            conductivity,
            initial_temperature,
            fluid_temperature,
            time,
        )
    return None


def _lmtd_inputs() -> HeatTransferResult | None:
    flow_type = st.selectbox("Tipo de escoamento", ("contracorrente", "paralelo"), key="ht_lmtd_flow")
    overall_coefficient = st.number_input("Coeficiente global U [W/(m².K)]", value=250.0, min_value=0.0, step=10.0, format="%.6f", key="ht_lmtd_u")
    area = st.number_input("Área A [m²]", value=5.0, min_value=0.0, step=0.5, format="%.6f", key="ht_lmtd_area")
    hot_inlet = st.number_input("Entrada quente Th,in [°C]", value=90.0, step=5.0, format="%.6f", key="ht_lmtd_th_in")
    hot_outlet = st.number_input("Saída quente Th,out [°C]", value=60.0, step=5.0, format="%.6f", key="ht_lmtd_th_out")
    cold_inlet = st.number_input("Entrada fria Tc,in [°C]", value=20.0, step=5.0, format="%.6f", key="ht_lmtd_tc_in")
    cold_outlet = st.number_input("Saída fria Tc,out [°C]", value=45.0, step=5.0, format="%.6f", key="ht_lmtd_tc_out")
    correction_factor = st.number_input("Fator de correção F [-]", value=1.0, min_value=0.0, step=0.05, format="%.6f", key="ht_lmtd_f")
    if st.button("Calcular LMTD", type="primary", use_container_width=True, key="ht_lmtd_calc"):
        return calculate_lmtd_heat_exchanger(
            overall_coefficient,
            area,
            hot_inlet,
            hot_outlet,
            cold_inlet,
            cold_outlet,
            flow_type,
            correction_factor,
        )
    return None


def _ntu_inputs() -> HeatTransferResult | None:
    flow_type = st.selectbox("Tipo de escoamento", ("contracorrente", "paralelo"), key="ht_ntu_flow")
    hot_capacity_rate = st.number_input("Capacidade térmica quente Ch [W/K]", value=1200.0, min_value=0.0, step=50.0, format="%.6f", key="ht_ntu_ch")
    cold_capacity_rate = st.number_input("Capacidade térmica fria Cc [W/K]", value=900.0, min_value=0.0, step=50.0, format="%.6f", key="ht_ntu_cc")
    ua = st.number_input("Produto UA [W/K]", value=500.0, min_value=0.0, step=25.0, format="%.6f", key="ht_ntu_ua")
    hot_inlet = st.number_input("Entrada quente Th,in [°C]", value=90.0, step=5.0, format="%.6f", key="ht_ntu_th_in")
    cold_inlet = st.number_input("Entrada fria Tc,in [°C]", value=20.0, step=5.0, format="%.6f", key="ht_ntu_tc_in")
    if st.button("Calcular Efetividade-NTU", type="primary", use_container_width=True, key="ht_ntu_calc"):
        return calculate_ntu_heat_exchanger(
            hot_capacity_rate,
            cold_capacity_rate,
            ua,
            hot_inlet,
            cold_inlet,
            flow_type,
        )
    return None


def _dittus_boelter_inputs() -> HeatTransferResult | None:
    mode = st.selectbox("Condição térmica do fluido", ("aquecimento", "resfriamento"), key="ht_db_mode")
    density = st.number_input("Densidade rho [kg/m³]", value=997.0, min_value=0.0, step=10.0, format="%.6f", key="ht_db_rho")
    velocity = st.number_input("Velocidade média V [m/s]", value=2.0, min_value=0.0, step=0.1, format="%.6f", key="ht_db_velocity")
    diameter = st.number_input("Diâmetro D [m]", value=0.025, min_value=0.0, step=0.005, format="%.6f", key="ht_db_d")
    dynamic_viscosity = st.number_input("Viscosidade dinâmica mu [Pa.s]", value=0.00089, min_value=0.0, step=0.0001, format="%.8f", key="ht_db_mu")
    specific_heat = st.number_input("Calor específico cp [J/(kg.K)]", value=4180.0, min_value=0.0, step=50.0, format="%.6f", key="ht_db_cp")
    conductivity = st.number_input("Condutividade k [W/(m.K)]", value=0.6, min_value=0.0, step=0.05, format="%.6f", key="ht_db_k")
    if st.button("Calcular Dittus-Boelter", type="primary", use_container_width=True, key="ht_db_calc"):
        return calculate_dittus_boelter_forced_convection(
            density,
            velocity,
            diameter,
            dynamic_viscosity,
            specific_heat,
            conductivity,
            mode,
        )
    return None


def _render_empty_state() -> None:
    st.info("Escolha uma ferramenta, preencha os dados e clique em calcular.")
    st.markdown("#### Símbolos principais")
    st.latex(r"\dot q:\ \mathrm{taxa\ de\ transferencia\ de\ calor\ [W]}")
    st.latex(r"q'':\ \mathrm{fluxo\ de\ calor\ [W/m^2]}")
    st.latex(r"R_{th}:\ \mathrm{resistencia\ termica\ [K/W]}")
    st.latex(r"T_\infty:\ \mathrm{temperatura\ do\ fluido\ longe\ da\ superficie}")
    st.latex(r"Bi:\ \mathrm{numero\ de\ Biot\ para\ validar\ capacitancia\ concentrada}")


def _render_result(result: HeatTransferResult, plan: HeatTransferPlan | None = None) -> None:
    st.subheader(result.title)
    _render_metric_grid(result)
    question_answers = _build_heat_question_answers(plan, result)
    if question_answers:
        _render_question_answers(question_answers)
    else:
        _render_question_block(result)
    st.markdown("#### Tabela numérica")
    st.dataframe(pd.DataFrame(_quantity_rows(result)), use_container_width=True, hide_index=True)
    _render_diagram(result)
    with st.expander("Hipóteses e validações", expanded=True):
        st.markdown("**Hipóteses**")
        for assumption in result.assumptions:
            st.markdown(f"- {assumption}")
        st.markdown("**Validações**")
        for validation in result.validations:
            st.markdown(f"- {validation}")
    with st.expander("Versão copiável", expanded=False):
        copyable = _copyable_markdown(result, question_answers)
        st.code(copyable, language="markdown")
    _log_manual_output_if_possible(result, copyable, question_answers)


def _render_assistant_panel() -> HeatTransferResult | None:
    with st.container(border=True):
        st.markdown("#### Assistente de enunciado")
        st.caption("Interpreta texto, imagem ou PDF e gera um plano de Transferência de Calor. O cálculo ainda é executado pelas ferramentas determinísticas abaixo.")
        statement = st.text_area(
            "Enunciado ou observação complementar",
            key="ht_statement",
            height=130,
            placeholder="Cole o enunciado ou complemente os dados da imagem. Ex.: parede plana com k=..., L=..., T1=...",
        )
        files = st.file_uploader(
            "Imagem ou PDF do exercício",
            type=("png", "jpg", "jpeg", "pdf"),
            accept_multiple_files=True,
            key="ht_files",
        )
        model = st.text_input("Modelo OpenAI", value="gpt-4.1-mini", key="ht_model")
        actions = st.columns([0.5, 0.5])
        with actions[0]:
            interpret = st.button("Interpretar transferência de calor", type="primary", use_container_width=True, key="ht_interpret")
        with actions[1]:
            clear = st.button("Limpar heat transfer", use_container_width=True, key="ht_clear")

        if clear:
            for key in (
                "ht_plan",
                "ht_run_id",
                "ht_plan_id",
                "ht_input_log",
                "ht_plan_log",
                "ht_output_log",
                "ht_error_log",
                "ht_last_logged_tool",
                "ht_execution_result",
            ):
                st.session_state.pop(key, None)
            st.rerun()

        if interpret:
            payload = _uploaded_files_payload(files)
            run_id = new_heat_transfer_run_id()
            plan_id = _plan_id(statement, payload)
            try:
                with st.spinner("Interpretando enunciado de Transferência de Calor..."):
                    plan = interpret_heat_transfer_problem(statement, payload, model=model)
                st.session_state["ht_plan"] = plan
                st.session_state["ht_run_id"] = run_id
                st.session_state["ht_plan_id"] = plan_id
                st.session_state["ht_input_log"] = log_heat_transfer_input(run_id, statement, payload, model, plan)
                st.session_state["ht_plan_log"] = log_heat_transfer_plan(run_id, plan, plan_id)
                st.session_state.pop("ht_error_log", None)
                st.success("Plano de Transferência de Calor interpretado.")
            except Exception as exc:
                st.session_state["ht_run_id"] = run_id
                st.session_state["ht_plan_id"] = plan_id
                st.session_state["ht_error_log"] = log_heat_transfer_error(run_id, plan_id, "interpretacao", exc)
                st.error(f"Não foi possível interpretar: {exc}")

        plan = st.session_state.get("ht_plan")
        if isinstance(plan, HeatTransferPlan):
            _render_plan_summary(plan)
            if st.button("Aplicar dados do plano nos campos manuais", use_container_width=True, key="ht_apply_plan"):
                applied = _apply_plan_to_manual_widgets(plan)
                if applied:
                    st.success("Dados do plano aplicados aos campos manuais.")
                    st.rerun()
                st.warning("Não foi possível aplicar dados suficientes do plano aos campos manuais.")
            if st.button("Resolver plano com ferramentas internas", type="primary", use_container_width=True, key="ht_execute_plan"):
                try:
                    with st.spinner("Executando ferramenta determinística de Transferência de Calor..."):
                        st.session_state["ht_execution_result"] = execute_heat_transfer_plan(plan)
                    st.success("Plano resolvido com ferramenta interna.")
                except Exception as exc:
                    run_id = st.session_state.get("ht_run_id") or new_heat_transfer_run_id()
                    plan_id = st.session_state.get("ht_plan_id") or "sem-plano"
                    st.session_state["ht_error_log"] = log_heat_transfer_error(run_id, plan_id, "execucao", exc)
                    st.error(f"Não foi possível executar o plano: {exc}")
        _render_log_paths()
        result = st.session_state.get("ht_execution_result")
        return result if isinstance(result, HeatTransferResult) else None


def _render_plan_summary(plan: HeatTransferPlan) -> None:
    st.markdown("##### Plano interpretado")
    summary = [
        ("Categoria", plan.categoria or "-"),
        ("Tipo", plan.tipo_problema or "-"),
        ("Ferramentas", ", ".join(plan.ferramentas_necessarias) or "-"),
        ("Confiança", f"{plan.confianca:.0%}"),
    ]
    st.dataframe(pd.DataFrame(summary, columns=["Campo", "Valor"]), use_container_width=True, hide_index=True)
    if plan.entrada_oficial:
        with st.expander("Entrada oficial consolidada", expanded=False):
            st.markdown(plan.entrada_oficial)
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Dados conhecidos**")
        _render_plan_items(plan.dados_conhecidos)
        st.markdown("**Geometria**")
        _render_plan_items(plan.geometria)
    with cols[1]:
        st.markdown("**Dados faltantes reais**")
        if plan.dados_faltantes:
            for item in plan.dados_faltantes:
                st.markdown(f"- {item}")
        else:
            st.markdown("- Nenhum.")
        st.markdown("**Questões**")
        if plan.questoes:
            for question in plan.questoes:
                label = f"{question.item}) " if question.item else ""
                st.markdown(f"- {label}{question.objetivo or question.enunciado}")
        else:
            st.markdown("- Nenhuma questão identificada.")


def _render_plan_items(items: tuple[object, ...]) -> None:
    if not items:
        st.markdown("- Nenhum.")
        return
    for item in items:
        value = f": `{item.valor} {item.unidade}`".strip() if item.valor or item.unidade else ""
        obs = f" — {item.observacao}" if item.observacao else ""
        st.markdown(f"- **{item.nome}**{value}{obs}")


def _apply_plan_to_manual_widgets(plan: HeatTransferPlan) -> bool:
    facts = canonical_heat_facts(plan)
    tool = main_heat_transfer_tool(plan)
    if tool == "conducao_plana_1d":
        _set_widget_values(
            {
                "ht_tool": "Condução plana 1D",
                "ht_plane_k": _fact(facts, "k"),
                "ht_plane_area": _fact(facts, "A"),
                "ht_plane_l": _fact(facts, "L"),
                "ht_plane_t1": _fact(facts, "T_1"),
                "ht_plane_t2": _fact(facts, "T_2"),
            }
        )
        return True
    if tool == "conducao_radial_cilindro":
        _set_widget_values(
            {
                "ht_tool": "Condução radial em cilindro",
                "ht_cyl_k": _fact(facts, "k"),
                "ht_cyl_l": _fact(facts, "L"),
                "ht_cyl_ri": _fact(facts, "r_i"),
                "ht_cyl_ro": _fact(facts, "r_o"),
                "ht_cyl_ti": _fact(facts, "T_i", "T_1"),
                "ht_cyl_to": _fact(facts, "T_o", "T_2"),
            }
        )
        return True
    if tool == "conducao_radial_esfera":
        _set_widget_values(
            {
                "ht_tool": "Condução radial em esfera",
                "ht_sph_k": _fact(facts, "k"),
                "ht_sph_ri": _fact(facts, "r_i"),
                "ht_sph_ro": _fact(facts, "r_o"),
                "ht_sph_ti": _fact(facts, "T_i", "T_1"),
                "ht_sph_to": _fact(facts, "T_o", "T_2"),
            }
        )
        return True
    if tool == "conveccao_newton":
        _set_widget_values(
            {
                "ht_tool": "Convecção",
                "ht_conv_h": _fact(facts, "h"),
                "ht_conv_area": _fact(facts, "A"),
                "ht_conv_ts": _fact(facts, "T_s"),
                "ht_conv_tinf": _fact(facts, "T_inf"),
            }
        )
        return True
    if tool == "radiacao_superficie_vizinhanca":
        _set_widget_values(
            {
                "ht_tool": "Radiação superfície-vizinhança",
                "ht_rad_eps": _fact(facts, "epsilon"),
                "ht_rad_area": _fact(facts, "A"),
                "ht_rad_ts": _fact(facts, "T_s"),
                "ht_rad_tsur": _fact(facts, "T_sur"),
            }
        )
        return True
    if tool == "rede_resistencias_serie":
        _set_widget_values(
            {
                "ht_tool": "Rede de resistências - série",
                "ht_res_serie_list": _resistance_text_from_plan(plan),
                "ht_res_serie_th": _fact(facts, "T_hot", "T_1", "T_i", "T_s"),
                "ht_res_serie_tc": _fact(facts, "T_cold", "T_2", "T_o", "T_inf", "T_sur"),
            }
        )
        return True
    if tool == "rede_resistencias_paralelo":
        _set_widget_values(
            {
                "ht_tool": "Rede de resistências - paralelo",
                "ht_res_paralelo_list": _resistance_text_from_plan(plan),
                "ht_res_paralelo_th": _fact(facts, "T_hot", "T_1", "T_i", "T_s"),
                "ht_res_paralelo_tc": _fact(facts, "T_cold", "T_2", "T_o", "T_inf", "T_sur"),
            }
        )
        return True
    if tool == "aleta_reta_ponta_adiabatica":
        _set_widget_values(
            {
                "ht_tool": "Aleta reta - ponta adiabática",
                "ht_fin_h": _fact(facts, "h"),
                "ht_fin_p": _fact(facts, "P"),
                "ht_fin_k": _fact(facts, "k"),
                "ht_fin_ac": _fact(facts, "A_c"),
                "ht_fin_l": _fact(facts, "L"),
                "ht_fin_tb": _fact(facts, "T_b"),
                "ht_fin_tinf": _fact(facts, "T_inf"),
            }
        )
        return True
    if tool == "capacitancia_concentrada":
        _set_widget_values(
            {
                "ht_tool": "Capacitância concentrada",
                "ht_lumped_h": _fact(facts, "h"),
                "ht_lumped_area": _fact(facts, "A"),
                "ht_lumped_rho": _fact(facts, "rho"),
                "ht_lumped_v": _fact(facts, "V"),
                "ht_lumped_cp": _fact(facts, "c_p"),
                "ht_lumped_k": _fact(facts, "k"),
                "ht_lumped_ti": _fact(facts, "T_i", "T_1"),
                "ht_lumped_tinf": _fact(facts, "T_inf"),
                "ht_lumped_t": _fact(facts, "t"),
            }
        )
        return True
    if tool == "trocador_lmtd":
        _set_widget_values(
            {
                "ht_tool": "Trocador LMTD",
                "ht_lmtd_flow": _flow_type_for_widgets(plan),
                "ht_lmtd_u": _fact(facts, "U"),
                "ht_lmtd_area": _fact(facts, "A"),
                "ht_lmtd_th_in": _fact(facts, "T_h_in"),
                "ht_lmtd_th_out": _fact(facts, "T_h_out"),
                "ht_lmtd_tc_in": _fact(facts, "T_c_in"),
                "ht_lmtd_tc_out": _fact(facts, "T_c_out"),
                "ht_lmtd_f": _fact(facts, "F"),
            }
        )
        return True
    if tool == "trocador_ntu":
        _set_widget_values(
            {
                "ht_tool": "Trocador Efetividade-NTU",
                "ht_ntu_flow": _flow_type_for_widgets(plan),
                "ht_ntu_ch": _fact(facts, "C_h"),
                "ht_ntu_cc": _fact(facts, "C_c"),
                "ht_ntu_ua": _fact(facts, "UA"),
                "ht_ntu_th_in": _fact(facts, "T_h_in"),
                "ht_ntu_tc_in": _fact(facts, "T_c_in"),
            }
        )
        return True
    if tool == "conveccao_forcada_dittus_boelter":
        _set_widget_values(
            {
                "ht_tool": "Convecção forçada - Dittus-Boelter",
                "ht_db_mode": _heating_mode_for_widgets(plan),
                "ht_db_rho": _fact(facts, "rho"),
                "ht_db_velocity": _fact(facts, "velocity"),
                "ht_db_d": _fact(facts, "D"),
                "ht_db_mu": _fact(facts, "mu"),
                "ht_db_cp": _fact(facts, "c_p"),
                "ht_db_k": _fact(facts, "k"),
            }
        )
        return True
    return False


def _flow_type_for_widgets(plan: HeatTransferPlan) -> str | None:
    text = " ".join((plan.tipo_problema, plan.categoria, " ".join(plan.objetivos), plan.entrada_oficial)).lower()
    if "paralel" in text:
        return "paralelo"
    if "contra" in text:
        return "contracorrente"
    return None


def _heating_mode_for_widgets(plan: HeatTransferPlan) -> str | None:
    text = " ".join((plan.tipo_problema, plan.categoria, " ".join(plan.objetivos), plan.entrada_oficial)).lower()
    if "resfri" in text or "cool" in text:
        return "resfriamento"
    if "aquec" in text or "heat" in text:
        return "aquecimento"
    return None


def _resistance_text_from_plan(plan: HeatTransferPlan) -> str | None:
    values = []
    for item in plan.fatos_canonicos + plan.dados_conhecidos + plan.geometria + plan.condicoes_contorno:
        text = " ".join((item.nome, item.observacao)).lower()
        if "resist" not in text and not item.nome.lower().strip().startswith("r"):
            continue
        values.extend(_numbers_from_text(f"{item.valor} {item.unidade}"))
    if not values:
        return None
    return ", ".join(f"{value:.6g}" for value in values)


def _fact(facts, *names: str) -> float | None:
    for name in names:
        if name in facts:
            return facts[name].value
    return None


def _set_widget_values(values: dict[str, object | None]) -> None:
    for key, value in values.items():
        if value is not None:
            st.session_state[key] = value


def _parse_float_list(value: str) -> tuple[float, ...]:
    numbers = _numbers_from_text(value)
    if not numbers:
        raise HeatTransferCalculationError("Informe ao menos uma resistência térmica em K/W.")
    return tuple(numbers)


def _numbers_from_text(value: str) -> list[float]:
    return [float(match.replace(",", ".")) for match in re.findall(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", value)]


def _uploaded_files_payload(files) -> list[dict[str, object]]:
    payload = []
    for uploaded_file in files or []:
        payload.append(
            {
                "name": uploaded_file.name,
                "content_type": uploaded_file.type,
                "data": uploaded_file.getvalue(),
            }
        )
    return payload


def _plan_id(statement: str, payload: list[dict[str, object]]) -> str:
    file_part = "|".join(f"{item.get('name')}:{len(item.get('data', b''))}" for item in payload)
    seed = f"{statement.strip()}|{file_part}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _render_log_paths() -> None:
    paths = [
        ("Input", st.session_state.get("ht_input_log")),
        ("Plano", st.session_state.get("ht_plan_log")),
        ("Output", st.session_state.get("ht_output_log")),
        ("Erro", st.session_state.get("ht_error_log")),
    ]
    visible = [(label, path) for label, path in paths if path]
    if not visible:
        return
    with st.expander("Logs da transferência de calor", expanded=False):
        for label, path in visible:
            st.markdown(f"- **{label}:** `{path}`")


def _log_manual_output_if_possible(result: HeatTransferResult, copyable: str, question_answers: list[dict[str, object]] | None = None) -> None:
    run_id = st.session_state.get("ht_run_id")
    plan_id = st.session_state.get("ht_plan_id")
    if not run_id or not plan_id:
        return
    log_key = f"{plan_id}:{result.tool}"
    if st.session_state.get("ht_last_logged_tool") == log_key:
        return
    try:
        st.session_state["ht_output_log"] = log_heat_transfer_output(run_id, plan_id, result, copyable, question_answers or ())
        st.session_state["ht_last_logged_tool"] = log_key
    except Exception as exc:
        st.session_state["ht_error_log"] = log_heat_transfer_error(run_id, plan_id, "output_manual", exc)


def _render_metric_grid(result: HeatTransferResult) -> None:
    cards = []
    for quantity in result.results:
        cards.append(
            "<div class='metric-card'>"
            f"<div class='metric-label'>{escape(quantity.label)}</div>"
            f"<div class='metric-value'>{quantity.value:.6g}</div>"
            f"<div class='metric-detail'>{escape(quantity.unit)} | {escape(quantity.symbol)}</div>"
            "</div>"
        )
    st.markdown(f"<div class='metric-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def _render_question_block(result: HeatTransferResult) -> None:
    with st.container(border=True):
        st.markdown("#### Resolução didática")
        st.markdown(f"**Interpretação:** {result.interpretation}")
        st.markdown("**Dados usados:**")
        for item in result.data_used:
            st.markdown(f"- `{item}`")
        st.markdown("**Modelo físico e fórmulas:**")
        for formula in result.formulas:
            st.latex(formula)
        st.markdown("**Substituição numérica:**")
        for substitution in result.substitutions:
            st.latex(substitution)
        st.markdown("**Resultado:**")
        for quantity in result.results:
            st.markdown(f"- `{quantity.symbol}` = **{quantity.value:.6g} {quantity.unit}** — {quantity.description}")


def _build_heat_question_answers(plan: HeatTransferPlan | None, result: HeatTransferResult) -> list[dict[str, object]]:
    if not plan or not plan.questoes:
        return []
    answers: list[dict[str, object]] = []
    for index, question in enumerate(plan.questoes, start=1):
        item = question.item.strip() or str(index)
        objective = question.objetivo.strip() or question.enunciado.strip() or "Questão identificada no enunciado"
        selected_symbols = _symbols_for_heat_question(question, result)
        selected_quantities = _select_quantities_for_question(result, selected_symbols)
        selected_formulas = _select_lines_for_question(result.formulas, selected_symbols) or result.formulas
        selected_substitutions = _select_lines_for_question(result.substitutions, selected_symbols) or result.substitutions
        result_lines = tuple(f"{quantity.symbol}={quantity.value:.6g} {quantity.unit}" for quantity in selected_quantities)
        answers.append(
            {
                "item": item,
                "objetivo": objective,
                "status": "respondido",
                "interpretacao": _question_interpretation(question, result),
                "dados": result.data_used,
                "formulas": selected_formulas,
                "substituicoes": selected_substitutions,
                "resultados": result_lines,
                "origem": f"Ferramenta determinística `{result.tool}` com dados normalizados do plano.",
            }
        )
    return answers


def _symbols_for_heat_question(question, result: HeatTransferResult) -> set[str]:
    text = normalize_heat_text(
        " ".join(
            (
                question.item,
                question.enunciado,
                question.objetivo,
                question.resultado_esperado,
                " ".join(question.propriedades_a_calcular),
            )
        )
    )
    symbols: set[str] = set()
    rules: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        (("fluxo", "q''", "q fluxo"), ("q_flux",)),
        (("taxa de calor", "calor", "q dot", "qdot", "potencia termica"), ("q_dot", "q_dot_rad", "q_dot_fin")),
        (("resistencia", "r eq", "req"), ("R_eq", "R_cond", "R_cil", "R_esf", "R_conv")),
        (("temperatura", "saida", "entrada", "t out", "t in"), ("T_t", "T_h_out", "T_c_out", "T_h_in", "T_c_in")),
        (("lmtd", "dtlm", "media logaritmica", "delta t lm"), ("Delta_T_lm", "Delta_T_1", "Delta_T_2")),
        (("ntu",), ("NTU",)),
        (("efetividade", "epsilon"), ("epsilon_hx", "epsilon_f")),
        (("eficiencia", "eta"), ("eta_f",)),
        (("nusselt", "nu"), ("Nu",)),
        (("reynolds", "re"), ("Re",)),
        (("prandtl", "pr"), ("Pr",)),
        (("biot", "bi"), ("Bi",)),
        (("constante de tempo", "tau"), ("tau",)),
        (("energia",), ("Q",)),
        (("coeficiente convectivo", "coeficiente de conveccao", " h "), ("h",)),
        (("aleta", "parametro"), ("m", "A_f", "eta_f", "epsilon_f", "q_dot_fin")),
    )
    padded_text = f" {text} "
    for keywords, candidate_symbols in rules:
        if any(keyword in padded_text for keyword in keywords):
            symbols.update(candidate_symbols)
    existing_symbols = {quantity.symbol for quantity in result.results}
    explicit_symbols = {symbol for symbol in existing_symbols if normalize_heat_text(symbol) in padded_text}
    symbols.update(explicit_symbols)
    return symbols & existing_symbols


def _select_quantities_for_question(result: HeatTransferResult, symbols: set[str]) -> tuple[object, ...]:
    if not symbols:
        return result.results
    selected = tuple(quantity for quantity in result.results if quantity.symbol in symbols)
    return selected or result.results


def _select_lines_for_question(lines: tuple[str, ...], symbols: set[str]) -> tuple[str, ...]:
    if not symbols:
        return ()
    selected = []
    for line in lines:
        normalized_line = _formula_search_text(line)
        if any(_symbol_matches_line(symbol, normalized_line) for symbol in symbols):
            selected.append(line)
    return tuple(selected)


def _symbol_matches_line(symbol: str, normalized_line: str) -> bool:
    symbol_keywords = _symbol_keywords(symbol)
    return any(keyword in normalized_line for keyword in symbol_keywords)


def _symbol_keywords(symbol: str) -> tuple[str, ...]:
    normalized_symbol = normalize_heat_text(symbol)
    aliases = {
        "q_dot": ("dot q", "q dot", "q=", "q =", "calor"),
        "q_dot_rad": ("dot q rad", "rad"),
        "q_dot_fin": ("dot q f", "q f", "aleta"),
        "q_flux": ("q''", "fluxo"),
        "R_eq": ("r eq", "req"),
        "R_cond": ("r cond", "r_{cond}", "r cond"),
        "R_cil": ("r cil",),
        "R_esf": ("r esf",),
        "R_conv": ("r conv",),
        "Delta_T_lm": ("delta t lm", "lm"),
        "Delta_T_1": ("delta t 1",),
        "Delta_T_2": ("delta t 2",),
        "T_t": ("t(t)", "temperatura"),
        "T_h_out": ("t h out", "h out"),
        "T_c_out": ("t c out", "c out"),
        "epsilon_hx": ("varepsilon", "epsilon", "efetividade"),
        "epsilon_f": ("varepsilon f", "epsilon", "efetividade"),
        "eta_f": ("eta f", "eficiencia"),
        "Nu": ("nu", "nusselt"),
        "Re": ("re", "reynolds"),
        "Pr": ("pr", "prandtl"),
        "Bi": ("bi", "biot"),
    }
    return aliases.get(symbol, (normalized_symbol,))


def _formula_search_text(line: str) -> str:
    normalized = normalize_heat_text(line)
    replacements = {
        "\\": " ",
        "{": " ",
        "}": " ",
        "^": " ",
        "_": " ",
        "=": " = ",
        ",": " ",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return " ".join(normalized.split())


def _question_interpretation(question, result: HeatTransferResult) -> str:
    if question.resultado_esperado:
        return f"{result.interpretation} Resultado esperado no plano: {question.resultado_esperado}."
    return result.interpretation


def _render_question_answers(question_answers: list[dict[str, object]]) -> None:
    st.markdown("#### Respostas por questão")
    for answer in question_answers:
        title = f"{answer['item']}) {answer['objetivo']}"
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"Status: {answer['status']}")
            st.markdown(f"**Interpretação:** {answer['interpretacao']}")
            st.markdown("**Dados usados:**")
            for item in answer["dados"]:
                st.markdown(f"- `{item}`")
            st.markdown("**Fórmulas:**")
            for formula in answer["formulas"]:
                st.latex(formula)
            st.markdown("**Substituição numérica:**")
            for substitution in answer["substituicoes"]:
                st.latex(substitution)
            st.markdown("**Resultado:**")
            for result_line in answer["resultados"]:
                st.markdown(f"- `{result_line}`")
            st.markdown(f"**Origem:** {answer['origem']}")


def _render_diagram(result: HeatTransferResult) -> None:
    st.markdown("#### Diagrama físico")
    try:
        figure = build_heat_transfer_figure(result)
        if figure is None:
            st.info("Ainda não há diagrama para esta ferramenta.")
            return
        st.markdown("<div class='limited-plot'>", unsafe_allow_html=True)
        st.pyplot(figure, use_container_width=False)
        st.markdown("</div>", unsafe_allow_html=True)
    except Exception as exc:
        st.info(f"Não foi possível gerar o diagrama: {exc}")


def _quantity_rows(result: HeatTransferResult) -> list[dict[str, object]]:
    return [
        {
            "Grandeza": quantity.label,
            "Símbolo": quantity.symbol,
            "Valor": round(quantity.value, 8),
            "Unidade": quantity.unit,
            "Descrição": quantity.description,
        }
        for quantity in result.results
    ]


def _copyable_markdown(result: HeatTransferResult, question_answers: list[dict[str, object]] | None = None) -> str:
    data = "\n".join(f"- `{item}`" for item in result.data_used)
    formulas = "\n".join(f"- ${formula}$" for formula in result.formulas)
    substitutions = "\n".join(f"- ${item}$" for item in result.substitutions)
    results = "\n".join(f"- `${quantity.symbol}` = {quantity.value:.6g} {quantity.unit}" for quantity in result.results)
    validations = "\n".join(f"- {item}" for item in result.validations)
    assumptions = "\n".join(f"- {item}" for item in result.assumptions)
    question_section = _copyable_question_answers(question_answers or [])
    return f"""# {result.title}

## Interpretação
{result.interpretation}

{question_section}

## Dados usados
{data}

## Fórmulas
{formulas}

## Substituição numérica
{substitutions}

## Resultados
{results}

## Hipóteses
{assumptions}

## Validações
{validations}
""".strip()


def _copyable_question_answers(question_answers: list[dict[str, object]]) -> str:
    if not question_answers:
        return ""
    sections = ["## Respostas por questão"]
    for answer in question_answers:
        formulas = "\n".join(f"- ${formula}$" for formula in answer["formulas"])
        substitutions = "\n".join(f"- ${item}$" for item in answer["substituicoes"])
        results = "\n".join(f"- `{item}`" for item in answer["resultados"])
        sections.append(
            f"""### {answer['item']}) {answer['objetivo']}

- Status: {answer['status']}
- Interpretação: {answer['interpretacao']}

Fórmulas:
{formulas}

Substituição:
{substitutions}

Resultado:
{results}

Origem: {answer['origem']}
"""
        )
    return "\n".join(sections)

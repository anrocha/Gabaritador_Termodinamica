from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from cycle_core import (
    CYCLE_FLUIDS,
    CycleInput,
    CycleResult,
    calculate_vapor_compression_cycle,
    cycle_metric_rows,
    cycle_state_rows,
)
from openai_assistant import AssistantDraft, interpret_refrigeration_problem
from thermo_core import PRESSURE_UNITS, REFERENCE_STATE_OPTIONS, TEMPERATURE_UNITS, ThermoCalculationError


FLUID_LABELS = {
    "R22": "R22",
    "R134a": "R134a",
}


def render_cycle_tab(default_reference_state: str, default_temperature_unit: str, default_pressure_unit: str) -> None:
    st.subheader("Ciclo de refrigeracao")
    st.caption("MVP para ciclo de compressao de vapor simples com R22 ou R134a. Agua/vapor fica nas rotinas de propriedades e turbina.")

    _render_assistant_panel()

    cycle_input, calculate = _render_cycle_inputs(
        default_reference_state,
        default_temperature_unit,
        default_pressure_unit,
    )

    if calculate:
        try:
            with st.spinner("Calculando estados, propriedades e diagrama do ciclo..."):
                result = calculate_vapor_compression_cycle(cycle_input)
        except ThermoCalculationError as exc:
            st.error(f"Nao foi possivel resolver o ciclo: {exc}")
            return
        _render_cycle_result(result)
    else:
        st.info("Preencha ou interprete um enunciado, confirme os dados e calcule o ciclo.")


def _render_assistant_panel() -> None:
    with st.expander("Assistente por enunciado com OpenAI", expanded=False):
        st.caption("A IA interpreta o enunciado; o calculo final continua sendo feito com CoolProp.")
        statement = st.text_area(
            "Enunciado",
            height=160,
            key="cycle_statement",
            placeholder="Cole aqui o enunciado do problema de refrigeracao...",
        )
        uploaded_files = st.file_uploader(
            "Imagem ou PDF do enunciado",
            type=["png", "jpg", "jpeg", "webp", "pdf"],
            accept_multiple_files=True,
            key="cycle_files",
        )
        model = st.text_input("Modelo OpenAI", value="gpt-4.1-mini", key="cycle_openai_model")

        if st.button("Interpretar enunciado", type="primary", key="cycle_interpret"):
            files_payload = [
                {
                    "name": uploaded_file.name,
                    "content_type": uploaded_file.type,
                    "data": uploaded_file.getvalue(),
                }
                for uploaded_file in uploaded_files or []
            ]
            try:
                with st.spinner("Interpretando enunciado de refrigeracao com a OpenAI..."):
                    st.session_state["cycle_assistant_draft"] = interpret_refrigeration_problem(
                        statement,
                        files_payload,
                        model=model.strip() or None,
                    )
            except Exception as exc:
                st.error(f"Nao foi possivel interpretar com a OpenAI: {exc}")

        draft = st.session_state.get("cycle_assistant_draft")
        if isinstance(draft, AssistantDraft):
            _render_assistant_draft(draft)


def _render_assistant_draft(draft: AssistantDraft) -> None:
    st.markdown("#### Interpretacao sugerida")
    cols = st.columns(4)
    cols[0].metric("Tipo", draft.problem_type or "-")
    cols[1].metric("Fluido", draft.fluid or "-")
    cols[2].metric("Ciclo", draft.cycle_type or "-")
    cols[3].metric("Confianca", f"{draft.confidence:.0%}")

    if draft.missing_data:
        st.warning("Dados faltantes: " + ", ".join(draft.missing_data))

    if _draft_looks_like_water_or_turbine(draft):
        st.warning(
            "Este enunciado parece ser de agua/vapor ou turbina, nao de ciclo de refrigeracao com R22/R134a. "
            "Use a aba Gabaritador para resolver com a ferramenta de turbina/propriedades."
        )

    if draft.known_values:
        st.dataframe(
            pd.DataFrame(
                [{"Campo": key, "Valor": value} for key, value in draft.known_values.items() if value is not None]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if draft.assumptions:
        st.markdown("**Hipoteses identificadas:** " + "; ".join(draft.assumptions))

    if st.button("Aplicar dados sugeridos aos campos", key="cycle_apply_draft"):
        if _draft_looks_like_water_or_turbine(draft):
            st.error("Nao apliquei estes dados ao ciclo porque o fluido/problema nao e de refrigeracao R22/R134a.")
            return
        _apply_draft_to_session(draft)
        st.rerun()


def _apply_draft_to_session(draft: AssistantDraft) -> None:
    known = draft.known_values
    fluid = _normalize_fluid(draft.fluid)
    if fluid:
        st.session_state["cycle_fluid"] = fluid

    mappings = {
        "evaporating_temperature_c": "cycle_evap_temp",
        "condensing_temperature_c": "cycle_cond_temp",
        "superheat_k": "cycle_superheat",
        "subcooling_k": "cycle_subcooling",
        "compressor_efficiency": "cycle_eta",
        "cooling_capacity_kw": "cycle_capacity",
    }
    for source_key, session_key in mappings.items():
        value = known.get(source_key)
        if isinstance(value, int | float):
            st.session_state[session_key] = float(value)

    if isinstance(known.get("cooling_capacity_w"), int | float):
        st.session_state["cycle_capacity"] = float(known["cooling_capacity_w"])
        st.session_state["cycle_capacity_unit"] = "W"
    elif isinstance(known.get("cooling_capacity_kw"), int | float):
        st.session_state["cycle_capacity_unit"] = "kW"

    st.session_state["cycle_temperature_unit"] = "C"


def _render_cycle_inputs(
    default_reference_state: str,
    default_temperature_unit: str,
    default_pressure_unit: str,
) -> tuple[CycleInput, bool]:
    st.markdown("#### Dados confirmados")
    fluid = st.selectbox(
        "Fluido",
        CYCLE_FLUIDS,
        index=0,
        format_func=lambda value: FLUID_LABELS.get(value, value),
        key="cycle_fluid",
    )
    reference_state = st.selectbox(
        "Referencia",
        REFERENCE_STATE_OPTIONS,
        index=REFERENCE_STATE_OPTIONS.index(default_reference_state)
        if default_reference_state in REFERENCE_STATE_OPTIONS
        else 0,
        key="cycle_reference_state",
    )
    unit_cols = st.columns(2)
    with unit_cols[0]:
        temperature_unit = st.selectbox(
            "Unidade temperatura",
            TEMPERATURE_UNITS,
            index=TEMPERATURE_UNITS.index(default_temperature_unit)
            if default_temperature_unit in TEMPERATURE_UNITS
            else 0,
            key="cycle_temperature_unit",
        )
    with unit_cols[1]:
        pressure_unit = st.selectbox(
            "Unidade pressao",
            PRESSURE_UNITS,
            index=PRESSURE_UNITS.index(default_pressure_unit) if default_pressure_unit in PRESSURE_UNITS else 3,
            key="cycle_pressure_unit",
        )

    temp_cols = st.columns(2)
    with temp_cols[0]:
        evap_temp = st.number_input(
            f"Temperatura de evaporacao [{temperature_unit}]",
            value=-10.0,
            step=1.0,
            key="cycle_evap_temp",
        )
    with temp_cols[1]:
        cond_temp = st.number_input(
            f"Temperatura de condensacao [{temperature_unit}]",
            value=40.0,
            step=1.0,
            key="cycle_cond_temp",
        )

    thermal_cols = st.columns(2)
    with thermal_cols[0]:
        superheat = st.number_input("Superaquecimento [K]", value=5.0, min_value=0.0, step=1.0, key="cycle_superheat")
    with thermal_cols[1]:
        subcooling = st.number_input("Sub-resfriamento [K]", value=5.0, min_value=0.0, step=1.0, key="cycle_subcooling")

    compressor_efficiency = st.number_input(
        "Eficiencia isentropica do compressor",
        value=0.75,
        min_value=0.01,
        max_value=1.0,
        step=0.01,
        format="%.3f",
        key="cycle_eta",
    )

    capacity_cols = st.columns([0.65, 0.35])
    with capacity_cols[0]:
        cooling_capacity = st.number_input(
            "Capacidade frigorifica",
            value=10.0,
            min_value=0.0,
            step=1.0,
            key="cycle_capacity",
        )
    with capacity_cols[1]:
        capacity_unit = st.selectbox("Unidade", ["kW", "W", "TR"], key="cycle_capacity_unit")

    use_capacity = st.checkbox("Usar capacidade para calcular vazao e potencia", value=True, key="cycle_use_capacity")
    calculate = st.button("Calcular ciclo", type="primary", use_container_width=True, key="cycle_calculate")

    return (
        CycleInput(
            fluid=fluid,
            evaporating_temperature=evap_temp,
            condensing_temperature=cond_temp,
            superheat=superheat,
            subcooling=subcooling,
            compressor_efficiency=compressor_efficiency,
            cooling_capacity=cooling_capacity if use_capacity else None,
            temperature_unit=temperature_unit,
            pressure_unit=pressure_unit,
            capacity_unit=capacity_unit,
            reference_state=reference_state,
        ),
        calculate,
    )


def _render_cycle_result(result: CycleResult) -> None:
    st.markdown("#### Resultado do ciclo")
    _render_metric_summary(result)
    st.caption(f"Referencia aplicada: {result.reference_state}")

    st.markdown("##### Tabela de estados")
    st.dataframe(pd.DataFrame(cycle_state_rows(result)), use_container_width=True, hide_index=True)

    st.markdown("##### Indicadores e formulas")
    st.dataframe(pd.DataFrame(cycle_metric_rows(result)), use_container_width=True, hide_index=True)

    st.markdown("##### Validacao fisica")
    for validation in result.validations:
        if validation.startswith("OK"):
            st.success(validation)
        else:
            st.warning(validation)

    st.markdown("##### Diagrama P-h")
    try:
        st.pyplot(_build_ph_figure(result), use_container_width=True)
    except Exception as exc:
        st.info(f"Nao foi possivel gerar o diagrama P-h para este caso: {exc}")

    st.markdown("##### Resolucao copiavel")
    st.markdown(_solution_markdown(result))


def _render_metric_summary(result: CycleResult) -> None:
    metric_by_label = {metric.label: metric for metric in result.metrics}
    cards = [
        ("COP", metric_by_label["COP real de refrigeracao"].value, "-"),
        ("q_evap", metric_by_label["Calor absorvido no evaporador"].value, "kJ/kg"),
        ("w_comp", metric_by_label["Trabalho especifico do compressor"].value, "kJ/kg"),
        ("m_dot", metric_by_label["Vazao massica"].value, "kg/s"),
    ]
    html = []
    for label, value, unit in cards:
        value_text = "-" if value is None else f"{value:.5g}"
        html.append(
            "<div class='metric-card'>"
            f"<div class='metric-label'>{escape(label)}</div>"
            f"<div class='metric-value'>{escape(value_text)} {escape(unit)}</div>"
            "</div>"
        )
    st.markdown(f"<div class='metric-grid'>{''.join(html)}</div>", unsafe_allow_html=True)


def _build_ph_figure(result: CycleResult):
    import matplotlib.pyplot as plt
    from CoolProp.CoolProp import PropsSI
    from thermo_core import pa_to_pressure, temperature_to_k

    fluid = result.input.fluid
    t_min = PropsSI(fluid, "Ttriple") + 1
    t_max = PropsSI(fluid, "Tcrit") - 1
    temperatures = [t_min + index * (t_max - t_min) / 79 for index in range(80)]
    h_liq = []
    h_vap = []
    p_sat = []
    for temperature in temperatures:
        h_liq.append(PropsSI("H", "T", temperature, "Q", 0, fluid) / 1000)
        h_vap.append(PropsSI("H", "T", temperature, "Q", 1, fluid) / 1000)
        p_sat.append(pa_to_pressure(PropsSI("P", "T", temperature, "Q", 0, fluid), result.input.pressure_unit))

    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    ax.plot(h_liq, p_sat, color="#0057a6", linewidth=1.6, label="Liquido saturado")
    ax.plot(h_vap, p_sat, color="#f58220", linewidth=1.6, label="Vapor saturado")

    state_map = {state.point: state for state in result.states}
    cycle_points = [state_map[key] for key in ("1", "2", "3", "4", "1")]
    ax.plot(
        [state.enthalpy for state in cycle_points],
        [state.pressure for state in cycle_points],
        color="#111827",
        marker="o",
        linewidth=1.8,
        label="Ciclo",
    )
    ax.scatter([state_map["2s"].enthalpy], [state_map["2s"].pressure], color="#5b6472", marker="x", label="2s")

    for state in result.states:
        quality_line = "" if state.quality is None else f"\nx={state.quality:.3g}"
        label = (
            f"{state.point}\n"
            f"P={state.pressure:.3g} {result.input.pressure_unit}\n"
            f"T={state.temperature:.3g} {result.input.temperature_unit}\n"
            f"h={state.enthalpy:.3g}\n"
            f"s={state.entropy:.3g}"
            f"{quality_line}"
        )
        ax.annotate(
            label,
            (state.enthalpy, state.pressure),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=7.5,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#d8e1ea", "alpha": 0.9},
        )

    ax.set_yscale("log")
    ax.set_xlabel("Entalpia especifica h [kJ/kg]")
    ax.set_ylabel(f"Pressao P [{result.input.pressure_unit}]")
    ax.set_title(f"Diagrama P-h - {FLUID_LABELS.get(fluid, fluid)}")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def _solution_markdown(result: CycleResult) -> str:
    state_lines = "\n".join(
        f"- Estado {state.point}: {state.description}. {state.formula}. "
        f"h = {state.enthalpy:.3f} kJ/kg, s = {state.entropy:.5f} kJ/(kg.K), "
        f"P = {state.pressure:.5g} {result.input.pressure_unit}, "
        f"T = {state.temperature:.5g} {result.input.temperature_unit}."
        for state in result.states
    )
    metric_lines = "\n".join(
        f"- {metric.label}: {metric.formula}"
        + (f" = {metric.value:.5g} {metric.unit}." if metric.value is not None else ".")
        for metric in result.metrics
    )
    assumptions = "\n".join(f"- {assumption}" for assumption in result.assumptions)
    return f"""
**1. Sistema fisico:** ciclo de refrigeracao por compressao de vapor usando {FLUID_LABELS.get(result.input.fluid, result.input.fluid)}.

**2. Hipoteses adotadas:**
{assumptions}

**3. Estados termodinamicos:**
{state_lines}

**4. Equacoes e resultados:**
{metric_lines}

**5. Interpretacao:** o evaporador absorve calor em baixa pressao, o compressor eleva a pressao e a entalpia do vapor, o condensador rejeita calor em alta pressao e a valvula de expansao reduz a pressao mantendo a entalpia constante.
""".strip()


def _normalize_fluid(value: str) -> str | None:
    normalized = value.strip().lower().replace("-", "")
    if normalized in {"r22", "r 22"}:
        return "R22"
    if normalized in {"r134a", "r 134a", "r314a"}:
        return "R134a"
    return None


def _draft_looks_like_water_or_turbine(draft: AssistantDraft) -> bool:
    text = " ".join(
        [
            draft.problem_type,
            draft.fluid,
            draft.cycle_type,
            " ".join(draft.requested_outputs),
            " ".join(draft.assumptions),
        ]
    ).lower()
    return any(token in text for token in ("water", "agua", "água", "vapor", "turbina", "turbine"))

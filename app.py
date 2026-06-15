from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from cycle_rendering import render_cycle_tab
from exercise_rendering import render_exercise_tab
from heat_transfer_rendering import render_heat_transfer_tab
from thermo_core import (
    PROPERTY_DEFINITIONS,
    PRESSURE_UNITS,
    QUALITY_INPUTS,
    REFERENCE_STATE_OPTIONS,
    STATE_INPUT_DEFINITIONS,
    TEMPERATURE_UNITS,
    ThermoCalculationError,
    available_fluids,
    calculate_quality,
    calculate_state_from_pair,
    calculate_state_from_tp,
    k_to_temperature,
    pa_to_pressure,
    pressure_to_pa,
    reference_state_description,
    temperature_to_k,
)


st.set_page_config(
    page_title="Gabaritador de Termodinamica",
    page_icon="T",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    :root {
        color-scheme: light;
        --unisinos-blue: #0057a6;
        --unisinos-orange: #f58220;
        --unisinos-ink: #111827;
        --unisinos-muted: #5b6472;
        --unisinos-line: #d8e1ea;
        --unisinos-soft: #f4f8fc;
    }
    .stApp {
        background: linear-gradient(180deg, #f6f9fd 0%, #ffffff 34%);
        color: var(--unisinos-ink);
        overflow-x: hidden;
    }
    .main .block-container {
        padding-top: 1.1rem;
        padding-bottom: 1.5rem;
        max-width: 1120px;
    }
    h1, h2, h3 {
        letter-spacing: 0;
        color: var(--unisinos-ink);
    }
    label, p, span, div {
        color: var(--unisinos-ink);
    }
    [data-testid="stWidgetLabel"] p {
        color: #233449;
        font-weight: 650;
    }
    [data-baseweb="input"] input,
    [data-baseweb="select"] > div,
    [data-testid="stNumberInput"] input {
        background: #ffffff;
        color: var(--unisinos-ink);
        border-color: #a9bfd6;
        min-width: 0;
    }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--unisinos-line);
        padding: 0.85rem 1rem;
        border-radius: 8px;
        box-shadow: 0 8px 22px rgba(0, 87, 166, 0.06);
    }
    [data-testid="stMetricLabel"] {
        color: #294058;
        font-weight: 650;
    }
    [data-testid="stMetricValue"] {
        color: var(--unisinos-ink);
    }
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 0.75rem;
        margin-bottom: 0.8rem;
    }
    .metric-card {
        background: #ffffff;
        border: 1px solid var(--unisinos-line);
        border-radius: 8px;
        padding: 0.8rem 0.9rem;
        box-shadow: 0 8px 22px rgba(0, 87, 166, 0.06);
        min-width: 0;
        overflow-wrap: anywhere;
    }
    .metric-label {
        color: #294058;
        font-size: 0.82rem;
        font-weight: 750;
        line-height: 1.2;
        overflow-wrap: anywhere;
    }
    .metric-value {
        color: var(--unisinos-ink);
        font-size: clamp(1.05rem, 4.8vw, 1.75rem);
        line-height: 1.15;
        font-weight: 700;
        margin-top: 0.35rem;
        overflow-wrap: anywhere;
        word-break: break-word;
    }
    .metric-detail {
        color: var(--unisinos-muted);
        font-size: 0.78rem;
        line-height: 1.25;
        margin-top: 0.25rem;
        overflow-wrap: anywhere;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--unisinos-line);
        border-radius: 8px;
        max-width: 100%;
        overflow-x: auto;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-top: 4px solid var(--unisinos-blue) !important;
        border-left: 1px solid var(--unisinos-line) !important;
        border-right: 1px solid var(--unisinos-line) !important;
        border-bottom: 1px solid var(--unisinos-line) !important;
        border-radius: 8px !important;
        background: #ffffff !important;
        box-shadow: 0 10px 28px rgba(0, 87, 166, 0.08);
    }
    [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: #ffffff;
        border: 1px solid var(--unisinos-line);
        border-radius: 8px;
        padding: 0.45rem;
        margin: 0.5rem 0 1rem;
        box-shadow: 0 8px 20px rgba(0, 87, 166, 0.05);
        max-width: 100%;
    }
    button[data-baseweb="tab"] {
        background: #eaf2fb;
        border-radius: 7px;
        color: var(--unisinos-blue);
        font-weight: 750;
        padding: 0.65rem 1rem;
        min-height: 2.65rem;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: var(--unisinos-blue);
        color: #ffffff;
    }
    button[data-baseweb="tab"] p {
        color: inherit;
        font-weight: inherit;
    }
    .status-note {
        border-left: 4px solid var(--unisinos-orange);
        background: #fff7ed;
        color: #301d0b;
        padding: 0.8rem 1rem;
        margin: 0.25rem 0 1rem;
        border-radius: 0 8px 8px 0;
    }
    .control-panel {
        border-top: 4px solid var(--unisinos-blue);
        background: #ffffff;
        border-radius: 8px;
        border-left: 1px solid var(--unisinos-line);
        border-right: 1px solid var(--unisinos-line);
        border-bottom: 1px solid var(--unisinos-line);
        padding: 0.9rem 1rem 0.6rem;
        margin: 0.75rem 0 1rem;
        box-shadow: 0 10px 28px rgba(0, 87, 166, 0.08);
    }
    .unit-box,
    .formula-panel {
        border: 1px solid var(--unisinos-line);
        background: #ffffff;
        color: var(--unisinos-ink);
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 8px;
    }
    .unit-box {
        background: var(--unisinos-soft);
    }
    .unit-badge {
        border: 1px solid #a9bfd6;
        background: #f8fbff;
        min-height: 2.5rem;
        border-radius: 8px;
        padding: 0.52rem 0.75rem;
        margin-top: 1.72rem;
        font-weight: 750;
        color: var(--unisinos-blue);
        display: flex;
        align-items: center;
        min-width: 0;
        overflow-wrap: anywhere;
    }
    .unit-badge small {
        color: var(--unisinos-muted);
        font-weight: 650;
        margin-right: 0.35rem;
    }
    .formula-panel strong {
        display: block;
        color: #003f7a;
        margin-bottom: 0.4rem;
    }
    .formula-panel code {
        display: block;
        background: #f5f8fb;
        color: var(--unisinos-ink);
        padding: 0.45rem 0.55rem;
        margin: 0.35rem 0 0.7rem;
        border-radius: 6px;
        font-size: clamp(0.72rem, 2.7vw, 0.9rem);
        line-height: 1.45;
        white-space: normal;
        overflow-wrap: anywhere;
        word-break: break-word;
    }
    .footer-credit {
        border-top: 1px solid var(--unisinos-line);
        margin-top: 2rem;
        padding: 1.1rem 0 0.4rem;
        color: var(--unisinos-muted);
        text-align: center;
        font-size: 0.92rem;
    }
    .footer-credit a {
        color: var(--unisinos-blue);
        font-weight: 700;
        text-decoration: none;
        border-bottom: 2px solid rgba(245, 130, 32, 0.55);
    }
    .footer-credit a:hover {
        color: #003f7a;
        border-bottom-color: var(--unisinos-orange);
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background: var(--unisinos-blue);
        border-color: var(--unisinos-blue);
        color: #ffffff !important;
        font-weight: 800 !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background: #003f7a;
        border-color: #003f7a;
        color: #ffffff !important;
    }
    div[data-testid="stButton"] button[kind="primary"] p,
    div[data-testid="stButton"] button[kind="primary"] span {
        color: #ffffff !important;
        font-weight: 800 !important;
    }
    .stButton button[data-testid="baseButton-primary"],
    .stButton button[data-testid="baseButton-primary"] *,
    button[data-testid="baseButton-primary"],
    button[data-testid="baseButton-primary"] *,
    button[kind="primary"],
    button[kind="primary"] * {
        color: #ffffff !important;
        font-weight: 800 !important;
    }
    button[data-testid="baseButton-primary"],
    button[kind="primary"] {
        background: var(--unisinos-blue) !important;
        border-color: var(--unisinos-blue) !important;
    }
    .result-card {
        border-left: 4px solid var(--unisinos-blue);
        background: #f8fbff;
        border-radius: 8px;
        border-top: 1px solid var(--unisinos-line);
        border-right: 1px solid var(--unisinos-line);
        border-bottom: 1px solid var(--unisinos-line);
        padding: 0.85rem 1rem;
        margin: 0.8rem 0;
        overflow-wrap: anywhere;
        word-break: normal;
    }
    .result-card strong {
        color: #003f7a;
    }
    .result-value {
        color: var(--unisinos-ink);
        font-size: clamp(1.05rem, 3.2vw, 1.45rem);
        font-weight: 850;
        line-height: 1.2;
        margin-top: 0.25rem;
    }
    .compact-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.65rem;
        margin: 0.6rem 0 1rem;
    }
    .compact-item {
        background: #ffffff;
        border: 1px solid var(--unisinos-line);
        border-radius: 8px;
        padding: 0.7rem 0.8rem;
        overflow-wrap: anywhere;
    }
    .compact-label {
        color: #294058;
        font-size: 0.78rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        margin-bottom: 0.22rem;
    }
    .compact-value {
        color: var(--unisinos-ink);
        font-size: 0.94rem;
        line-height: 1.35;
    }
    .question-block {
        background: #ffffff;
        border: 1px solid var(--unisinos-line);
        border-top: 4px solid var(--unisinos-blue);
        border-radius: 8px;
        padding: 0.95rem 1rem;
        margin: 0.9rem 0 1.1rem;
        box-shadow: 0 8px 22px rgba(0, 87, 166, 0.05);
        overflow-wrap: anywhere;
    }
    .symbol-box {
        border-top: 4px solid var(--unisinos-orange);
        background: #ffffff;
        border-left: 1px solid var(--unisinos-line);
        border-right: 1px solid var(--unisinos-line);
        border-bottom: 1px solid var(--unisinos-line);
        border-radius: 8px;
        padding: 0.9rem 1rem;
        margin: 0.25rem 0 1rem;
        box-shadow: 0 8px 22px rgba(0, 87, 166, 0.06);
        overflow-wrap: anywhere;
    }
    .symbol-box strong {
        display: block;
        color: #003f7a;
        margin-bottom: 0.55rem;
    }
    .symbol-box p {
        font-size: 0.9rem;
        line-height: 1.35;
        margin: 0.35rem 0;
        overflow-wrap: anywhere;
    }
    div[data-testid="stMarkdownContainer"] {
        overflow-wrap: anywhere;
        word-break: normal;
    }
    @media (max-width: 900px) {
        .main .block-container {
            padding-left: 0.85rem;
            padding-right: 0.85rem;
            padding-top: 0.85rem;
        }
        h1 {
            font-size: 1.65rem;
            line-height: 1.15;
        }
        h3 {
            font-size: 1.1rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            box-shadow: 0 6px 18px rgba(0, 87, 166, 0.06);
        }
        .metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.6rem;
        }
        .metric-card {
            padding: 0.7rem 0.75rem;
            box-shadow: 0 5px 16px rgba(0, 87, 166, 0.05);
        }
        .metric-value {
            font-size: clamp(1rem, 4vw, 1.35rem);
        }
        .control-panel,
        .formula-panel,
        .unit-box {
            padding: 0.75rem;
        }
        [data-baseweb="tab-list"] {
            display: flex;
            flex-wrap: nowrap;
            overflow-x: auto;
            overflow-y: hidden;
            padding: 0.35rem;
            gap: 0.35rem;
            scrollbar-width: thin;
            -webkit-overflow-scrolling: touch;
        }
        button[data-baseweb="tab"] {
            flex: 0 0 auto;
            min-width: max-content;
            justify-content: center;
            padding: 0.55rem 0.75rem;
            min-height: 2.45rem;
            white-space: nowrap;
        }
        .unit-badge {
            margin-top: 1.55rem;
            min-height: 2.25rem;
            padding: 0.45rem 0.6rem;
            font-size: 0.9rem;
        }
        .formula-panel code,
        .status-note,
        .footer-credit {
            overflow-wrap: anywhere;
            word-break: break-word;
        }
    }
    @media (max-width: 640px) {
        .main .block-container {
            padding-left: 0.65rem;
            padding-right: 0.65rem;
        }
        h1 {
            font-size: 1.45rem;
        }
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        [data-testid="stWidgetLabel"] p {
            font-size: 0.9rem;
            line-height: 1.25;
        }
        [data-baseweb="tab-list"] {
            margin-bottom: 0.75rem;
        }
        button[data-baseweb="tab"] {
            padding: 0.48rem 0.65rem;
            min-height: 2.35rem;
            font-size: 0.9rem;
        }
        .metric-grid {
            grid-template-columns: 1fr;
        }
        .compact-list {
            grid-template-columns: 1fr;
            gap: 0.5rem;
        }
        .question-block,
        .result-card,
        .compact-item,
        .symbol-box {
            padding: 0.7rem;
            max-width: 100%;
            overflow-x: hidden;
        }
        .metric-card {
            padding: 0.65rem 0.7rem;
        }
        .metric-value {
            font-size: clamp(1rem, 6vw, 1.25rem);
        }
        .unit-badge {
            margin-top: 0;
            min-height: 2rem;
            padding: 0.35rem 0.55rem;
        }
        .unit-badge small {
            display: inline;
            margin-right: 0.25rem;
        }
        .formula-panel {
            margin: 0.75rem 0;
        }
        .formula-panel code {
            padding: 0.4rem 0.45rem;
            font-size: 0.78rem;
        }
        .footer-credit {
            font-size: 0.82rem;
            line-height: 1.45;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


SYMBOL_DISPLAY = {
    "rho": "ρ (rho)",
    "mu": "μ (mu)",
    "alpha": "α (alpha)",
    "lambda": "λ (lambda)",
}


def property_dataframe(results) -> pd.DataFrame:
    rows = []
    include_formula = any(getattr(item, "formula", None) for item in results)
    for item in results:
        row = {
            "Propriedade": item.label,
            "Símbolo": SYMBOL_DISPLAY.get(item.symbol, item.symbol),
            "Valor": None if item.value is None else round(item.value, 6),
            "Unidade": item.unit,
        }
        if include_formula:
            row["Fórmula"] = item.formula or ""
        rows.append(row)
    return pd.DataFrame(rows)


def format_number(value: float) -> str:
    return f"{value:.6g}"


def render_metric_cards(cards: list[tuple[str, str, str | None]]) -> None:
    html_cards = []
    for label, value, detail in cards:
        detail_html = f"<div class='metric-detail'>{escape(detail)}</div>" if detail else ""
        html_cards.append(
            "<div class='metric-card'>"
            f"<div class='metric-label'>{escape(label)}</div>"
            f"<div class='metric-value'>{escape(value)}</div>"
            f"{detail_html}"
            "</div>"
        )
    st.markdown(f"<div class='metric-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)


def quality_property_symbol(property_label: str) -> str:
    property_key, _, _ = QUALITY_INPUTS[property_label]
    if property_key == "V":
        return "v"
    return PROPERTY_DEFINITIONS[property_key][1]


def render_quality_formula(result, constraint_type: str, constraint_value: float, constraint_unit: str) -> None:
    symbol = quality_property_symbol(result.property_label)
    constraint_symbol = "P_sat" if constraint_type == "Pressao" else "T_sat"
    st.markdown(
        f"""
        <div class="formula-panel">
            <strong>Formula: titulo por propriedade saturada</strong>
            <code>{constraint_symbol} = {format_number(constraint_value)} {constraint_unit}</code>
            <code>x = ({symbol} - {symbol}_f) / ({symbol}_g - {symbol}_f)</code>
            <code>x = ({format_number(result.input_value)} {result.property_unit} - {format_number(result.saturated_liquid)} {result.property_unit}) /
            ({format_number(result.saturated_vapor)} {result.property_unit} - {format_number(result.saturated_liquid)} {result.property_unit})
            = {format_number(result.quality)}</code>
            <strong>Formula: interpolacao de propriedade da mistura</strong>
            <code>y = y_f + x(y_g - y_f)</code>
            <code>As linhas da tabela abaixo usam esse mesmo x e mostram a formula aplicada em cada propriedade.</code>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_unit_equivalences(temperature_k: float | None = None, pressure_pa: float | None = None) -> None:
    rows = []
    if temperature_k is not None:
        for unit in TEMPERATURE_UNITS:
            rows.append({"Grandeza": "Temperatura", "Unidade": unit, "Valor": round(k_to_temperature(temperature_k, unit), 6)})
    if pressure_pa is not None:
        for unit in PRESSURE_UNITS:
            rows.append({"Grandeza": "Pressao", "Unidade": unit, "Valor": round(pa_to_pressure(pressure_pa, unit), 6)})

    if rows:
        with st.expander("Ver equivalencias em outras unidades", expanded=False):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_unit_badge(label: str, unit: str) -> None:
    st.markdown(
        f"<div class='unit-badge'><small>{label}</small>{unit}</div>",
        unsafe_allow_html=True,
    )


def state_input_unit(property_key: str, temperature_unit: str, pressure_unit: str) -> str:
    if property_key == "T":
        return temperature_unit
    if property_key == "P":
        return pressure_unit
    return STATE_INPUT_DEFINITIONS[property_key].unit


def state_input_label(property_key: str) -> str:
    definition = STATE_INPUT_DEFINITIONS[property_key]
    return f"{definition.label} ({definition.symbol})"


def render_shared_controls(fluids: tuple[str, ...]) -> tuple[str, str, str, str]:
    with st.container(border=True):
        st.markdown("#### Configuracao global")
        control_cols = st.columns([0.34, 0.26, 0.2, 0.2])
        with control_cols[0]:
            fluid = st.selectbox(
                "Fluido",
                fluids,
                index=fluids.index("Water") if "Water" in fluids else 0,
                key="fluid",
            )
        with control_cols[1]:
            reference_state = st.selectbox("Referencia", REFERENCE_STATE_OPTIONS, index=0, key="reference_state")
        with control_cols[2]:
            temperature_unit = st.selectbox("Unidade temperatura", TEMPERATURE_UNITS, index=0, key="temperature_unit")
        with control_cols[3]:
            pressure_unit = st.selectbox("Unidade pressao", PRESSURE_UNITS, index=3, key="pressure_unit")
        st.caption(reference_state_description(fluid, reference_state))
    return fluid, reference_state, temperature_unit, pressure_unit


def render_footer() -> None:
    st.markdown(
        """
        <div class="footer-credit">
            Desenvolvido por <strong>Andre Rocha</strong> ·
            <a href="https://www.linkedin.com/in/1andrerocha1" target="_blank">LinkedIn</a> ·
            <a href="https://www.andrerocha.tech" target="_blank">andrerocha.tech</a> ·
            <a href="https://www.rockan.com.br" target="_blank">Rockan Consultoria</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.title("Gabaritador de Termodinamica")
    st.caption("Propriedades termodinamicas com CoolProp, referencias Unisinos e calculo de titulo.")


def render_state_tab(fluid: str, reference_state: str, temperature_unit: str, pressure_unit: str) -> None:
    left, right = st.columns([0.34, 0.66], gap="large")

    with left:
        st.subheader("Estado por T e P")
        temperature_cols = st.columns([0.7, 0.3])
        with temperature_cols[0]:
            temperature = st.number_input("Temperatura", value=100.0, step=5.0, key="state_temperature")
        with temperature_cols[1]:
            render_unit_badge("Unidade", temperature_unit)

        pressure_cols = st.columns([0.7, 0.3])
        with pressure_cols[0]:
            pressure = st.number_input("Pressao", value=1.01325, min_value=0.00001, step=0.1, format="%.6f", key="state_pressure")
        with pressure_cols[1]:
            render_unit_badge("Unidade", pressure_unit)

        selected_properties = st.multiselect(
            "Propriedades",
            options=list(PROPERTY_DEFINITIONS.keys()),
            default=["D", "V", "H", "U", "S", "CPMASS"],
            format_func=lambda key: PROPERTY_DEFINITIONS[key][0],
            key="state_properties",
        )
        calculate = st.button("Calcular propriedades", type="primary", use_container_width=True, key="state_calculate")

    with right:
        if calculate:
            try:
                result = calculate_state_from_tp(
                    fluid,
                    temperature,
                    pressure,
                    selected_properties,
                    temperature_unit=temperature_unit,
                    pressure_unit=pressure_unit,
                    reference_state=reference_state,
                )
            except ThermoCalculationError as exc:
                st.error(f"Nao foi possivel calcular este estado: {exc}")
                return

            render_metric_cards(
                [
                    ("Fluido", result.fluid, None),
                    (
                        "Temperatura",
                        f"{k_to_temperature(result.temperature_k, temperature_unit):.5g} {temperature_unit}",
                        f"{result.temperature_k:.2f} K",
                    ),
                    (
                        "Pressao",
                        f"{pa_to_pressure(result.pressure_pa, pressure_unit):.5g} {pressure_unit}",
                        f"{result.pressure_pa:.5g} Pa",
                    ),
                    ("Fase", result.phase, None),
                ]
            )
            st.caption(f"Referencia aplicada: {result.reference_state}")

            if result.quality is not None:
                st.markdown(
                    f"<div class='status-note'>Titulo calculado diretamente pelo par T/P: x = {result.quality:.5f}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("O par T/P nao esta em mistura saturada; o titulo nao se aplica neste estado.")

            st.dataframe(property_dataframe(result.properties), use_container_width=True, hide_index=True)
            render_unit_equivalences(result.temperature_k, result.pressure_pa)
        else:
            st.info("Informe temperatura e pressao para calcular as propriedades do fluido selecionado.")


def render_pair_state_tab(fluid: str, reference_state: str, temperature_unit: str, pressure_unit: str) -> None:
    left, right = st.columns([0.34, 0.66], gap="large")
    input_options = list(STATE_INPUT_DEFINITIONS.keys())

    with left:
        st.subheader("Estado por duas propriedades")
        first_property = st.selectbox(
            "Propriedade 1",
            input_options,
            index=input_options.index("P"),
            format_func=state_input_label,
            key="pair_first_property",
        )
        first_definition = STATE_INPUT_DEFINITIONS[first_property]
        first_unit = state_input_unit(first_property, temperature_unit, pressure_unit)
        first_cols = st.columns([0.7, 0.3])
        with first_cols[0]:
            first_value = st.number_input(
                f"Valor 1 [{first_unit}]",
                value=first_definition.default_value,
                min_value=first_definition.min_value,
                step=first_definition.step,
                format="%.6f",
                key="pair_first_value",
            )
        with first_cols[1]:
            render_unit_badge("Unidade", first_unit)

        second_property = st.selectbox(
            "Propriedade 2",
            input_options,
            index=input_options.index("S"),
            format_func=state_input_label,
            key="pair_second_property",
        )
        second_definition = STATE_INPUT_DEFINITIONS[second_property]
        second_unit = state_input_unit(second_property, temperature_unit, pressure_unit)
        second_cols = st.columns([0.7, 0.3])
        with second_cols[0]:
            second_value = st.number_input(
                f"Valor 2 [{second_unit}]",
                value=second_definition.default_value,
                min_value=second_definition.min_value,
                step=second_definition.step,
                format="%.6f",
                key="pair_second_value",
            )
        with second_cols[1]:
            render_unit_badge("Unidade", second_unit)

        selected_properties = st.multiselect(
            "Propriedades de saida",
            options=list(PROPERTY_DEFINITIONS.keys()),
            default=["D", "V", "H", "U", "S", "CPMASS"],
            format_func=lambda key: PROPERTY_DEFINITIONS[key][0],
            key="pair_state_properties",
        )
        calculate = st.button("Calcular estado", type="primary", use_container_width=True, key="pair_calculate")

    with right:
        if calculate:
            try:
                result = calculate_state_from_pair(
                    fluid,
                    first_property,
                    first_value,
                    second_property,
                    second_value,
                    selected_properties,
                    temperature_unit=temperature_unit,
                    pressure_unit=pressure_unit,
                    reference_state=reference_state,
                )
            except ThermoCalculationError as exc:
                st.error(f"Nao foi possivel calcular este estado: {exc}")
                return

            render_metric_cards(
                [
                    ("Fluido", result.fluid, None),
                    (
                        "Temperatura",
                        f"{k_to_temperature(result.temperature_k, temperature_unit):.5g} {temperature_unit}",
                        f"{result.temperature_k:.2f} K",
                    ),
                    (
                        "Pressao",
                        f"{pa_to_pressure(result.pressure_pa, pressure_unit):.5g} {pressure_unit}",
                        f"{result.pressure_pa:.5g} Pa",
                    ),
                    ("Fase", result.phase, None),
                ]
            )
            st.caption(f"Referencia aplicada: {result.reference_state}")

            if result.quality is not None:
                st.markdown(
                    f"<div class='status-note'>Titulo calculado pelo par informado: x = {result.quality:.5f}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("O estado calculado nao esta em mistura saturada; o titulo nao se aplica neste ponto.")

            st.dataframe(property_dataframe(result.properties), use_container_width=True, hide_index=True)
            render_unit_equivalences(result.temperature_k, result.pressure_pa)
        else:
            st.info("Escolha duas propriedades independentes, como P+s, P+h, T+s, T+h, T+v ou P+rho.")


def render_quality_tab(fluid: str, reference_state: str, temperature_unit: str, pressure_unit: str) -> None:
    left, right = st.columns([0.34, 0.66], gap="large")

    with left:
        st.subheader("Titulo em mistura")
        constraint_type = st.radio("Restricao de saturacao", ["Pressao", "Temperatura"], horizontal=True, key="quality_constraint_type")
        if constraint_type == "Pressao":
            constraint_cols = st.columns([0.7, 0.3])
            with constraint_cols[0]:
                constraint_value = st.number_input(
                    "Pressao de saturacao",
                    value=1.01325,
                    min_value=0.00001,
                    step=0.1,
                    format="%.6f",
                    key="quality_pressure",
                )
            with constraint_cols[1]:
                constraint_unit = pressure_unit
                render_unit_badge("Unidade", constraint_unit)
        else:
            constraint_cols = st.columns([0.7, 0.3])
            with constraint_cols[0]:
                constraint_value = st.number_input("Temperatura de saturacao", value=100.0, step=5.0, key="quality_temperature")
            with constraint_cols[1]:
                constraint_unit = temperature_unit
                render_unit_badge("Unidade", constraint_unit)

        property_label = st.selectbox("Propriedade conhecida", list(QUALITY_INPUTS.keys()), key="quality_property")
        _, unit, _ = QUALITY_INPUTS[property_label]
        property_value = st.number_input(f"Valor conhecido [{unit}]", value=1500.0, step=10.0, format="%.6f", key="quality_value")
        calculate = st.button("Calcular titulo", type="primary", use_container_width=True, key="quality_calculate")

    with right:
        if calculate:
            try:
                result = calculate_quality(
                    fluid,
                    constraint_type,
                    constraint_value,
                    property_label,
                    property_value,
                    constraint_unit=constraint_unit,
                    reference_state=reference_state,
                    output_temperature_unit=temperature_unit,
                    output_pressure_unit=pressure_unit,
                )
            except ThermoCalculationError as exc:
                st.error(f"Nao foi possivel calcular o titulo: {exc}")
                return

            render_metric_cards(
                [
                    ("Titulo x", f"{result.quality:.5f}", None),
                    ("Diagnostico", result.phase_hint, None),
                    ("Liquido saturado", f"{result.saturated_liquid:.5g} {result.property_unit}", None),
                    ("Vapor saturado", f"{result.saturated_vapor:.5g} {result.property_unit}", None),
                ]
            )
            st.caption(f"Referencia aplicada: {result.reference_state}")

            if not 0 <= result.quality <= 1:
                st.warning("O valor informado esta fora da faixa saturada. Confira a propriedade ou use o modo T/P.")

            render_quality_formula(result, constraint_type, constraint_value, constraint_unit)

            saturation_df = pd.DataFrame(
                [
                    {"Ponto": "Liquido saturado", "Valor": round(result.saturated_liquid, 6), "Unidade": result.property_unit},
                    {"Ponto": "Entrada", "Valor": round(result.input_value, 6), "Unidade": result.property_unit},
                    {"Ponto": "Vapor saturado", "Valor": round(result.saturated_vapor, 6), "Unidade": result.property_unit},
                ]
            )
            st.dataframe(saturation_df, use_container_width=True, hide_index=True)
            st.subheader("Propriedades no titulo calculado")
            st.dataframe(property_dataframe(result.mixture_properties), use_container_width=True, hide_index=True)
            temperature_result = next((item.value for item in result.mixture_properties if item.symbol == "T"), None)
            pressure_result = next((item.value for item in result.mixture_properties if item.symbol == "P"), None)
            render_unit_equivalences(
                None if temperature_result is None else temperature_to_k(temperature_result, temperature_unit),
                None if pressure_result is None else pressure_to_pa(pressure_result, pressure_unit),
            )
        else:
            st.info("Informe uma pressao ou temperatura de saturacao e uma propriedade extensiva especifica.")


def main() -> None:
    render_header()
    try:
        fluids = available_fluids()
    except Exception:
        fluids = ("Water",)

    fluid, reference_state, temperature_unit, pressure_unit = render_shared_controls(fluids)
    state_tab, pair_state_tab, quality_tab, cycle_tab, heat_transfer_tab, exercise_tab = st.tabs(
        [
            "Propriedades T/P",
            "Estado por par",
            "Titulo de mistura",
            "Ciclo de refrigeracao",
            "Transferência de Calor",
            "Gabaritador",
        ]
    )
    with state_tab:
        render_state_tab(fluid, reference_state, temperature_unit, pressure_unit)
    with pair_state_tab:
        render_pair_state_tab(fluid, reference_state, temperature_unit, pressure_unit)
    with quality_tab:
        render_quality_tab(fluid, reference_state, temperature_unit, pressure_unit)
    with cycle_tab:
        render_cycle_tab(reference_state, temperature_unit, pressure_unit)
    with heat_transfer_tab:
        render_heat_transfer_tab(reference_state, temperature_unit, pressure_unit)
    with exercise_tab:
        render_exercise_tab(reference_state, temperature_unit, pressure_unit)
    render_footer()


if __name__ == "__main__":
    main()

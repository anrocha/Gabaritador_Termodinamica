from __future__ import annotations

import re
from math import cos, exp, pi, sin

import matplotlib.pyplot as plt

from heat_transfer_core import HeatTransferResult


def build_heat_transfer_figure(result: HeatTransferResult):
    if result.tool == "conducao_plana_1d":
        return _plane_temperature_figure(result)
    if result.tool == "conducao_radial_cilindro":
        return _radial_geometry_figure(result, "cilindro")
    if result.tool == "conducao_radial_esfera":
        return _radial_geometry_figure(result, "esfera")
    if result.tool == "conveccao_newton":
        return _surface_exchange_figure(result, "convecção")
    if result.tool == "radiacao_superficie_vizinhanca":
        return _surface_exchange_figure(result, "radiação")
    if result.tool == "rede_resistencias_serie":
        return _thermal_resistance_network_figure(result, "serie")
    if result.tool == "rede_resistencias_paralelo":
        return _thermal_resistance_network_figure(result, "paralelo")
    if result.tool == "aleta_reta_ponta_adiabatica":
        return _fin_figure(result)
    if result.tool == "aleta_superficie_aletada":
        return _finned_surface_figure(result)
    if result.tool == "capacitancia_concentrada":
        return _lumped_capacitance_figure(result)
    if result.tool == "trocador_lmtd":
        return _lmtd_heat_exchanger_figure(result)
    if result.tool == "trocador_ntu":
        return _ntu_heat_exchanger_figure(result)
    if result.tool == "conveccao_forcada_dittus_boelter":
        return _dimensionless_numbers_figure(result)
    if result.tool == "conveccao_placa_plana_externa":
        return _flat_plate_convection_figure(result)
    if result.tool == "conveccao_interna_tubo_iterativa":
        return _tube_internal_convection_figure(result)
    if result.tool == "trocador_tubo_concentrico_vapor":
        return _concentric_tube_vapor_figure(result)
    if result.tool == "conducao_transiente_placa":
        return _transient_plate_figure(result)
    if result.tool == "asa_plana_radiacao_solar":
        return _solar_plate_figure(result)
    return None


def _plane_temperature_figure(result: HeatTransferResult):
    values = _data_dict(result)
    thickness = values.get("L", 1.0)
    hot_temperature = values.get("T_1", 1.0)
    cold_temperature = values.get("T_2", 0.0)
    resistance = _result_value(result, "R_cond")
    heat_rate = _result_value(result, "q_dot")

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.6), gridspec_kw={"width_ratios": [1.15, 0.85]})
    x_values = [0.0, thickness]
    temperatures = [hot_temperature, cold_temperature]
    axes[0].plot(x_values, temperatures, color="#0057a6", linewidth=3)
    axes[0].scatter(x_values, temperatures, color="#f58220", zorder=4)
    axes[0].set_title("Perfil de temperatura")
    axes[0].set_xlabel("x [m]")
    axes[0].set_ylabel("T [°C]")
    axes[0].grid(True, alpha=0.25)
    axes[0].annotate(f"T1={hot_temperature:.3g} °C", (0, hot_temperature), textcoords="offset points", xytext=(8, 8))
    axes[0].annotate(f"T2={cold_temperature:.3g} °C", (thickness, cold_temperature), textcoords="offset points", xytext=(-72, 8))

    axes[1].axis("off")
    axes[1].set_title("Rede térmica")
    axes[1].plot([0.1, 0.9], [0.55, 0.55], color="#111827", linewidth=2)
    axes[1].scatter([0.1, 0.9], [0.55, 0.55], color="#0057a6", s=80)
    axes[1].text(0.1, 0.68, "$T_1$", ha="center", fontsize=12)
    axes[1].text(0.9, 0.68, "$T_2$", ha="center", fontsize=12)
    axes[1].text(0.5, 0.63, "$R_{cond}$", ha="center", fontsize=12)
    axes[1].text(0.5, 0.41, f"R={resistance:.3g} K/W\nq={heat_rate:.3g} W", ha="center", fontsize=10)
    axes[1].set_xlim(0, 1)
    axes[1].set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _radial_geometry_figure(result: HeatTransferResult, geometry: str):
    values = _data_dict(result)
    inner_radius = values.get("r_i", 0.5)
    outer_radius = values.get("r_o", 1.0)
    inner_temperature = values.get("T_i", values.get("T_1", 0.0))
    outer_temperature = values.get("T_o", values.get("T_2", 0.0))
    heat_rate = _result_value(result, "q_dot")
    radius_ratio = outer_radius / inner_radius if inner_radius else 2.0
    inner_draw = 0.35
    outer_draw = min(0.9, inner_draw * radius_ratio)

    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    ax.set_aspect("equal")
    ax.axis("off")
    theta = [2 * pi * i / 240 for i in range(241)]
    for radius, color, label in (
        (outer_draw, "#d8e1ea", "$r_o$"),
        (inner_draw, "#ffffff", "$r_i$"),
    ):
        x_values = [radius * cos(t) for t in theta]
        y_values = [radius * sin(t) for t in theta]
        ax.fill(x_values, y_values, color=color, edgecolor="#0057a6", linewidth=2)
        ax.text(radius / 2, 0.05 + radius / 2, label, color="#003f7a", fontsize=12)
    ax.annotate("", xy=(1.08, 0), xytext=(0.15, 0), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2.5})
    ax.text(0, -1.02, f"{geometry.capitalize()} radial", ha="center", fontsize=12, weight="bold")
    ax.text(0, -1.18, f"Ti={inner_temperature:.3g} °C | To={outer_temperature:.3g} °C | q={heat_rate:.3g} W", ha="center", fontsize=10)
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    _style_figure(fig)
    return fig


def _surface_exchange_figure(result: HeatTransferResult, mode: str):
    values = _data_dict(result)
    surface_temperature = values.get("T_s", 0.0)
    ambient_temperature = values.get("T_inf", values.get("T_sur", 0.0))
    heat_rate = _result_value(result, "q_dot") or _result_value(result, "q_dot_rad")

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.12, 0.25), 0.18, 0.5, facecolor="#d8e1ea", edgecolor="#0057a6", linewidth=2))
    for y_pos in (0.35, 0.5, 0.65):
        ax.annotate("", xy=(0.82, y_pos), xytext=(0.32, y_pos), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2.3})
    ax.text(0.21, 0.8, "$T_s$", ha="center", fontsize=13)
    ax.text(0.82, 0.75, "$T_\\infty$" if mode == "convecção" else "$T_{sur}$", ha="center", fontsize=13)
    ax.text(0.53, 0.18, f"{mode.capitalize()} | q={heat_rate:.3g} W", ha="center", fontsize=11, weight="bold")
    ax.text(0.21, 0.14, f"{surface_temperature:.3g} °C", ha="center", fontsize=10)
    ax.text(0.82, 0.14, f"{ambient_temperature:.3g} °C", ha="center", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _thermal_resistance_network_figure(result: HeatTransferResult, mode: str):
    values = _data_dict(result)
    hot_temperature = values.get("T_hot", values.get("T_1", 0.0))
    cold_temperature = values.get("T_cold", values.get("T_2", 0.0))
    heat_rate = _result_value(result, "q_dot")
    resistance_equivalent = _result_value(result, "R_eq")
    resistances = _list_from_data(result, "R_list")
    count = max(len(resistances), 1)

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.axis("off")
    ax.scatter([0.08, 0.92], [0.5, 0.5], color="#0057a6", s=90)
    ax.text(0.08, 0.66, f"Tq={hot_temperature:.3g} °C", ha="center", fontsize=10)
    ax.text(0.92, 0.66, f"Tf={cold_temperature:.3g} °C", ha="center", fontsize=10)
    if mode == "serie":
        ax.plot([0.08, 0.18], [0.5, 0.5], color="#111827", linewidth=2)
        ax.plot([0.82, 0.92], [0.5, 0.5], color="#111827", linewidth=2)
        width = 0.58 / count
        for index in range(count):
            x_pos = 0.2 + index * width
            ax.add_patch(plt.Rectangle((x_pos, 0.42), width * 0.75, 0.16, facecolor="#eef4fb", edgecolor="#0057a6", linewidth=1.8))
            ax.text(x_pos + width * 0.375, 0.62, f"R{index+1}", ha="center", fontsize=9)
        ax.plot([0.18, 0.82], [0.5, 0.5], color="#111827", linewidth=1.4, alpha=0.45)
    else:
        y_positions = [0.25 + 0.5 * i / max(count - 1, 1) for i in range(count)] if count > 1 else [0.5]
        ax.plot([0.08, 0.2], [0.5, 0.5], color="#111827", linewidth=2)
        ax.plot([0.8, 0.92], [0.5, 0.5], color="#111827", linewidth=2)
        for index, y_pos in enumerate(y_positions):
            ax.plot([0.2, 0.32], [0.5, y_pos], color="#111827", linewidth=1.3)
            ax.plot([0.68, 0.8], [y_pos, 0.5], color="#111827", linewidth=1.3)
            ax.add_patch(plt.Rectangle((0.34, y_pos - 0.045), 0.32, 0.09, facecolor="#eef4fb", edgecolor="#0057a6", linewidth=1.6))
            ax.text(0.5, y_pos + 0.07, f"R{index+1}", ha="center", fontsize=9)
    ax.annotate("", xy=(0.78, 0.82), xytext=(0.22, 0.82), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2.3})
    ax.text(0.5, 0.08, f"Req={resistance_equivalent:.3g} K/W | q={heat_rate:.3g} W", ha="center", fontsize=10, weight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _fin_figure(result: HeatTransferResult):
    values = _data_dict(result)
    length = values.get("L", 0.1)
    base_temperature = values.get("T_b", 0.0)
    fluid_temperature = values.get("T_inf", 0.0)
    heat_rate = _result_value(result, "q_dot_fin")
    efficiency = _result_value(result, "eta_f")

    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.08, 0.2), 0.08, 0.6, facecolor="#0057a6", edgecolor="#003f7a", linewidth=2))
    ax.add_patch(plt.Rectangle((0.16, 0.42), 0.62, 0.16, facecolor="#d8e1ea", edgecolor="#0057a6", linewidth=2))
    for x_pos in (0.28, 0.45, 0.62):
        ax.annotate("", xy=(x_pos, 0.78), xytext=(x_pos, 0.6), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2})
        ax.annotate("", xy=(x_pos, 0.22), xytext=(x_pos, 0.4), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2})
    ax.text(0.12, 0.84, "$T_b$", ha="center", fontsize=13)
    ax.text(0.47, 0.88, "$T_\\infty$", ha="center", fontsize=13)
    ax.text(0.47, 0.08, f"L={length:.3g} m | q={heat_rate:.3g} W | ηf={efficiency:.3g}", ha="center", fontsize=10, weight="bold")
    ax.text(0.12, 0.1, f"{base_temperature:.3g} °C", ha="center", fontsize=10)
    ax.text(0.82, 0.5, "ponta\nadiabática", ha="center", fontsize=10)
    ax.text(0.47, 0.78, f"{fluid_temperature:.3g} °C", ha="center", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _lumped_capacitance_figure(result: HeatTransferResult):
    values = _data_dict(result)
    initial_temperature = values.get("T_i", values.get("T_1", 0.0))
    fluid_temperature = values.get("T_inf", 0.0)
    time = values.get("t", 1.0)
    tau = _result_value(result, "tau") or max(time, 1.0)
    target_temperature = _result_value(result, "T_t")
    biot = _result_value(result, "Bi")
    max_time = max(time, 4 * tau, 1.0)
    times = [max_time * i / 120 for i in range(121)]
    temperatures = [
        fluid_temperature + (initial_temperature - fluid_temperature) * exp(-current_time / tau)
        for current_time in times
    ]

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(times, temperatures, color="#0057a6", linewidth=3)
    ax.scatter([time], [target_temperature], color="#f58220", zorder=4)
    ax.axhline(fluid_temperature, color="#64748b", linestyle="--", linewidth=1.5)
    ax.annotate(f"T(t)={target_temperature:.3g} °C", (time, target_temperature), textcoords="offset points", xytext=(8, 8))
    ax.text(0.02, 0.06, f"Bi={biot:.3g} | τ={tau:.3g} s", transform=ax.transAxes, fontsize=10, weight="bold")
    ax.set_title("Resposta transiente por capacitância concentrada")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("T [°C]")
    ax.grid(True, alpha=0.25)
    _style_figure(fig)
    return fig


def _lmtd_heat_exchanger_figure(result: HeatTransferResult):
    values = _data_dict(result)
    hot_inlet = values.get("T_h_in", 0.0)
    hot_outlet = values.get("T_h_out", 0.0)
    cold_inlet = values.get("T_c_in", 0.0)
    cold_outlet = values.get("T_c_out", 0.0)
    heat_rate = _result_value(result, "q_dot")
    lmtd = _result_value(result, "Delta_T_lm")
    is_parallel = any("flow_type=paralelo" in item for item in result.data_used)

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.18, 0.28), 0.64, 0.44, facecolor="#eef4fb", edgecolor="#0057a6", linewidth=2))
    ax.text(0.5, 0.52, "Trocador de calor", ha="center", fontsize=12, weight="bold")
    ax.annotate("", xy=(0.82, 0.74), xytext=(0.08, 0.74), arrowprops={"arrowstyle": "->", "color": "#b91c1c", "lw": 2.5})
    if is_parallel:
        ax.annotate("", xy=(0.82, 0.2), xytext=(0.08, 0.2), arrowprops={"arrowstyle": "->", "color": "#0057a6", "lw": 2.5})
        ax.text(0.08, 0.12, f"Tc,in={cold_inlet:.3g} °C", ha="left", fontsize=9)
        ax.text(0.82, 0.12, f"Tc,out={cold_outlet:.3g} °C", ha="right", fontsize=9)
    else:
        ax.annotate("", xy=(0.08, 0.2), xytext=(0.82, 0.2), arrowprops={"arrowstyle": "->", "color": "#0057a6", "lw": 2.5})
        ax.text(0.82, 0.12, f"Tc,in={cold_inlet:.3g} °C", ha="right", fontsize=9)
        ax.text(0.08, 0.12, f"Tc,out={cold_outlet:.3g} °C", ha="left", fontsize=9)
    ax.text(0.08, 0.82, f"Th,in={hot_inlet:.3g} °C", ha="left", fontsize=9)
    ax.text(0.82, 0.82, f"Th,out={hot_outlet:.3g} °C", ha="right", fontsize=9)
    ax.text(0.5, 0.03, f"ΔTlm={lmtd:.3g} K | q={heat_rate:.3g} W", ha="center", fontsize=10, weight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _ntu_heat_exchanger_figure(result: HeatTransferResult):
    values = _data_dict(result)
    hot_inlet = values.get("T_h_in", 0.0)
    cold_inlet = values.get("T_c_in", 0.0)
    hot_outlet = _result_value(result, "T_h_out")
    cold_outlet = _result_value(result, "T_c_out")
    heat_rate = _result_value(result, "q_dot")
    effectiveness = _result_value(result, "epsilon_hx")
    ntu = _result_value(result, "NTU")
    is_parallel = any("flow_type=paralelo" in item for item in result.data_used)

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.18, 0.28), 0.64, 0.44, facecolor="#eef4fb", edgecolor="#0057a6", linewidth=2))
    ax.text(0.5, 0.52, "Efetividade-NTU", ha="center", fontsize=12, weight="bold")
    ax.annotate("", xy=(0.82, 0.74), xytext=(0.08, 0.74), arrowprops={"arrowstyle": "->", "color": "#b91c1c", "lw": 2.5})
    if is_parallel:
        ax.annotate("", xy=(0.82, 0.2), xytext=(0.08, 0.2), arrowprops={"arrowstyle": "->", "color": "#0057a6", "lw": 2.5})
        ax.text(0.08, 0.12, f"Tc,in={cold_inlet:.3g} °C", ha="left", fontsize=9)
        ax.text(0.82, 0.12, f"Tc,out={cold_outlet:.3g} °C", ha="right", fontsize=9)
    else:
        ax.annotate("", xy=(0.08, 0.2), xytext=(0.82, 0.2), arrowprops={"arrowstyle": "->", "color": "#0057a6", "lw": 2.5})
        ax.text(0.82, 0.12, f"Tc,in={cold_inlet:.3g} °C", ha="right", fontsize=9)
        ax.text(0.08, 0.12, f"Tc,out={cold_outlet:.3g} °C", ha="left", fontsize=9)
    ax.text(0.08, 0.82, f"Th,in={hot_inlet:.3g} °C", ha="left", fontsize=9)
    ax.text(0.82, 0.82, f"Th,out={hot_outlet:.3g} °C", ha="right", fontsize=9)
    ax.text(0.5, 0.03, f"NTU={ntu:.3g} | ε={effectiveness:.3g} | q={heat_rate:.3g} W", ha="center", fontsize=10, weight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _dimensionless_numbers_figure(result: HeatTransferResult):
    reynolds = _result_value(result, "Re")
    prandtl = _result_value(result, "Pr")
    nusselt = _result_value(result, "Nu")
    coefficient = _result_value(result, "h")
    labels = ["Re", "Pr", "Nu"]
    values = [max(reynolds, 1e-12), max(prandtl, 1e-12), max(nusselt, 1e-12)]

    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    bars = ax.bar(labels, values, color=["#0057a6", "#64748b", "#f58220"])
    ax.set_yscale("log")
    ax.set_title("Números adimensionais de convecção")
    ax.set_ylabel("valor [-] em escala log")
    ax.grid(True, axis="y", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.3g}", ha="center", va="bottom", fontsize=9)
    ax.text(0.5, -0.22, f"h={coefficient:.3g} W/(m².K)", transform=ax.transAxes, ha="center", fontsize=10, weight="bold")
    _style_figure(fig)
    return fig


def _finned_surface_figure(result: HeatTransferResult):
    values = _data_dict(result)
    base_temperature = values.get("T_b", 0.0)
    fluid_temperature = values.get("T_inf", 0.0)
    fin_count = int(round(values.get("N", 0.0)))
    heat_rate = _result_value(result, "q_total")
    q_sem = _result_value(result, "q_sem_aletas")
    eta_o = _result_value(result, "eta_o")
    ganho = _result_value(result, "ganho_percentual")
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.12, 0.22), 0.66, 0.2, facecolor="#d8e1ea", edgecolor="#0057a6", linewidth=2))
    fin_positions = [0.18 + 0.56 * i / max(fin_count - 1, 1) for i in range(min(fin_count, 9))] if fin_count else [0.4]
    for x_pos in fin_positions:
        ax.add_patch(plt.Rectangle((x_pos, 0.42), 0.02, 0.32, facecolor="#eef4fb", edgecolor="#0057a6", linewidth=1.2))
        ax.annotate("", xy=(x_pos + 0.01, 0.84), xytext=(x_pos + 0.01, 0.74), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 1.6})
        ax.annotate("", xy=(x_pos + 0.01, 0.2), xytext=(x_pos + 0.01, 0.36), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 1.4})
    ax.text(0.45, 0.12, f"49 aletas | q_total={heat_rate:.3g} W | q_sem={q_sem:.3g} W", ha="center", fontsize=10, weight="bold")
    ax.text(0.45, 0.9, f"eta_o={eta_o:.3g} | ganho={ganho:.3g}%", ha="center", fontsize=10)
    ax.text(0.12, 0.48, f"Tb={base_temperature:.3g} °C", ha="left", fontsize=10)
    ax.text(0.84, 0.48, f"Tinf={fluid_temperature:.3g} °C", ha="right", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _flat_plate_convection_figure(result: HeatTransferResult):
    values = _data_dict(result)
    length = values.get("L", 1.0)
    width = values.get("W", 1.0)
    t_surface = values.get("T_s", 0.0)
    t_inf = values.get("T_inf", 0.0)
    reynolds = _result_value(result, "Re_L")
    h = _result_value(result, "h")
    x_cr = next((item for item in result.validations if "x_cr" in item or "x_cr =" in item), "")

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.12, 0.38), 0.58, 0.18, facecolor="#d8e1ea", edgecolor="#0057a6", linewidth=2))
    ax.annotate("", xy=(0.82, 0.67), xytext=(0.08, 0.67), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2.5})
    ax.text(0.41, 0.64, "placa plana", ha="center", fontsize=12, weight="bold")
    ax.text(0.12, 0.25, f"L={length:.3g} m | W={width:.3g} m", ha="left", fontsize=10)
    ax.text(0.12, 0.14, f"Re={reynolds:.3g} | h={h:.3g} W/(m².K)", ha="left", fontsize=10)
    ax.text(0.82, 0.56, f"T∞={t_inf:.3g} °C", ha="right", fontsize=10)
    ax.text(0.82, 0.46, f"Ts={t_surface:.3g} °C", ha="right", fontsize=10)
    if x_cr:
        ax.text(0.5, 0.08, x_cr, ha="center", fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _tube_internal_convection_figure(result: HeatTransferResult):
    values = _data_dict(result)
    diameter = values.get("D", 1.0)
    length = values.get("L", 1.0)
    t_in = values.get("T_in", 0.0)
    t_out = values.get("T_out", 0.0)
    t_w = values.get("T_w", 0.0)
    delta_p = _result_value(result, "delta_p")
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.12, 0.36), 0.62, 0.24, facecolor="#eef4fb", edgecolor="#0057a6", linewidth=2))
    ax.add_patch(plt.Rectangle((0.18, 0.42), 0.5, 0.12, facecolor="#ffffff", edgecolor="#64748b", linewidth=1.5))
    ax.annotate("", xy=(0.78, 0.78), xytext=(0.08, 0.78), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2.5})
    ax.text(0.43, 0.69, "tubo interno", ha="center", fontsize=12, weight="bold")
    ax.text(0.13, 0.24, f"D={diameter:.3g} m | L={length:.3g} m", ha="left", fontsize=10)
    ax.text(0.13, 0.14, f"Tin={t_in:.3g} °C | Tout={t_out:.3g} °C | Tw={t_w:.3g} °C", ha="left", fontsize=10)
    ax.text(0.78, 0.12, f"Δp={delta_p:.3g} Pa", ha="right", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _concentric_tube_vapor_figure(result: HeatTransferResult):
    values = _data_dict(result)
    diameter_inner = values.get("D_i", values.get("D", 0.0))
    diameter_outer = values.get("D_o", values.get("D_ext", 0.0))
    t_in = values.get("T_in", 0.0)
    t_out = _result_value(result, "T_out")
    t_wi = _result_value(result, "T_wi")
    q_dot = _result_value(result, "q_dot")
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    ax.set_aspect("equal")
    ax.axis("off")
    theta = [2 * pi * i / 240 for i in range(241)]
    inner_radius = 0.26
    outer_radius = 0.42
    for radius, color, label in (
        (outer_radius, "#d8e1ea", "$D_o$"),
        (inner_radius, "#ffffff", "$D_i$"),
    ):
        x_values = [radius * cos(t) for t in theta]
        y_values = [radius * sin(t) for t in theta]
        ax.fill(x_values, y_values, color=color, edgecolor="#0057a6", linewidth=2)
        ax.text(radius / 2.0, 0.04, label, color="#003f7a", fontsize=12)
    ax.annotate("", xy=(0.95, 0), xytext=(0.42, 0), arrowprops={"arrowstyle": "->", "color": "#f58220", "lw": 2.5})
    ax.text(0, 0.56, "vapor", ha="center", fontsize=11, weight="bold")
    ax.text(0, -0.62, f"Tin={t_in:.3g} °C | Tout={t_out:.3g} °C | Twi={t_wi:.3g} °C", ha="center", fontsize=10)
    ax.text(0, -0.76, f"D_i={diameter_inner:.3g} m | D_o={diameter_outer:.3g} m | q={q_dot:.3g} W", ha="center", fontsize=10, weight="bold")
    ax.set_xlim(-1.0, 1.0)
    ax.set_ylim(-0.95, 0.95)
    _style_figure(fig)
    return fig


def _transient_plate_figure(result: HeatTransferResult):
    values = _data_dict(result)
    t_i = values.get("T_i", values.get("T_1", 0.0))
    t_inf = values.get("T_inf", 0.0)
    t_center = _result_value(result, "T_center")
    t_surface = _result_value(result, "T_surface")
    bi = _result_value(result, "Bi")
    fo = _result_value(result, "Fo")

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    x_values = [0.0, 0.5, 1.0]
    temperature_profile = [t_surface, t_center, t_surface]
    ax.plot(x_values, temperature_profile, color="#0057a6", linewidth=3)
    ax.scatter(x_values, temperature_profile, color="#f58220", zorder=4)
    ax.set_title("Perfil de temperatura na placa")
    ax.set_xlabel("x/Lc [-]")
    ax.set_ylabel("T [°C]")
    ax.grid(True, alpha=0.25)
    ax.text(0.02, 0.95, f"Bi={bi:.3g} | Fo={fo:.3g}", transform=ax.transAxes, fontsize=10, weight="bold")
    ax.text(0.02, 0.88, f"Ti={t_i:.3g} °C | Tinf={t_inf:.3g} °C", transform=ax.transAxes, fontsize=9)
    ax.text(0.5, 0.08, f"Tcenter={t_center:.3g} °C | Tsurface={t_surface:.3g} °C", transform=ax.transAxes, ha="center", fontsize=9)
    _style_figure(fig)
    return fig


def _solar_plate_figure(result: HeatTransferResult):
    values = _data_dict(result)
    t_inf = values.get("T_inf", 0.0)
    t_s = _result_value(result, "T_s")
    h = _result_value(result, "h")
    q_dot = _result_value(result, "q_dot")

    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.14, 0.34), 0.58, 0.22, facecolor="#d8e1ea", edgecolor="#0057a6", linewidth=2))
    ax.annotate("", xy=(0.45, 0.82), xytext=(0.45, 0.58), arrowprops={"arrowstyle": "->", "color": "#f59e0b", "lw": 2.5})
    ax.annotate("", xy=(0.84, 0.45), xytext=(0.72, 0.45), arrowprops={"arrowstyle": "->", "color": "#0057a6", "lw": 2.5})
    ax.annotate("", xy=(0.84, 0.55), xytext=(0.72, 0.55), arrowprops={"arrowstyle": "->", "color": "#0057a6", "lw": 2.5})
    ax.text(0.45, 0.86, "radiação solar", ha="center", fontsize=11, weight="bold")
    ax.text(0.45, 0.22, f"Ts={t_s:.3g} °C | Tinf={t_inf:.3g} °C", ha="center", fontsize=10)
    ax.text(0.45, 0.12, f"h={h:.3g} W/(m².K) | q={q_dot:.3g} W", ha="center", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _style_figure(fig)
    return fig


def _data_dict(result: HeatTransferResult) -> dict[str, float]:
    data = {}
    for item in result.data_used:
        if "=" not in item:
            continue
        name, rest = item.split("=", 1)
        value_text = rest.strip().split(" ", 1)[0].replace(",", ".")
        try:
            data[name.strip()] = float(value_text)
        except ValueError:
            continue
    return data


def _result_value(result: HeatTransferResult, symbol: str) -> float:
    quantity = next((item for item in result.results if item.symbol == symbol), None)
    return 0.0 if quantity is None else quantity.value


def _list_from_data(result: HeatTransferResult, name: str) -> list[float]:
    for item in result.data_used:
        if not item.startswith(f"{name}="):
            continue
        return [float(match.replace(",", ".")) for match in re.findall(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", item.split("=", 1)[1])]
    return []


def _style_figure(fig) -> None:
    fig.patch.set_facecolor("#ffffff")
    fig.tight_layout()

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isclose, log, pi, sqrt, tanh


SIGMA = 5.670374419e-8


class HeatTransferCalculationError(ValueError):
    pass


@dataclass(frozen=True)
class HeatTransferQuantity:
    label: str
    symbol: str
    value: float
    unit: str
    description: str


@dataclass(frozen=True)
class HeatTransferResult:
    tool: str
    title: str
    interpretation: str
    data_used: tuple[str, ...]
    formulas: tuple[str, ...]
    substitutions: tuple[str, ...]
    results: tuple[HeatTransferQuantity, ...]
    validations: tuple[str, ...]
    assumptions: tuple[str, ...]


def calculate_plane_conduction(
    conductivity: float,
    area: float,
    thickness: float,
    hot_temperature_c: float,
    cold_temperature_c: float,
) -> HeatTransferResult:
    _ensure_positive(conductivity, "condutividade térmica")
    _ensure_positive(area, "área")
    _ensure_positive(thickness, "espessura")
    delta_t = hot_temperature_c - cold_temperature_c
    resistance = thickness / (conductivity * area)
    heat_rate = delta_t / resistance
    heat_flux = heat_rate / area
    return HeatTransferResult(
        tool="conducao_plana_1d",
        title="Condução 1D estacionária em parede plana",
        interpretation="O calor atravessa a parede por condução, do lado mais quente para o lado mais frio.",
        data_used=(
            f"k={conductivity:.6g} W/(m.K)",
            f"A={area:.6g} m²",
            f"L={thickness:.6g} m",
            f"T_1={hot_temperature_c:.6g} °C",
            f"T_2={cold_temperature_c:.6g} °C",
        ),
        formulas=(r"R_{cond}=\frac{L}{kA}", r"\dot q=\frac{T_1-T_2}{R_{cond}}", r"q''=\frac{\dot q}{A}"),
        substitutions=(
            rf"R_{{cond}}=\frac{{{thickness:.6g}}}{{{conductivity:.6g}\cdot {area:.6g}}}={resistance:.6g}\ \mathrm{{K/W}}",
            rf"\dot q=\frac{{{hot_temperature_c:.6g}-{cold_temperature_c:.6g}}}{{{resistance:.6g}}}={heat_rate:.6g}\ \mathrm{{W}}",
            rf"q''=\frac{{{heat_rate:.6g}}}{{{area:.6g}}}={heat_flux:.6g}\ \mathrm{{W/m^2}}",
        ),
        results=(
            HeatTransferQuantity("Resistência térmica", "R_cond", resistance, "K/W", "Resistência da parede à condução."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido por unidade de tempo."),
            HeatTransferQuantity("Fluxo de calor", "q_flux", heat_flux, "W/m²", "Taxa de calor por área."),
        ),
        validations=_common_validations(delta_t, heat_rate),
        assumptions=("Regime permanente.", "Condução unidimensional.", "Condutividade térmica constante."),
    )


def calculate_cylinder_conduction(
    conductivity: float,
    length: float,
    inner_radius: float,
    outer_radius: float,
    inner_temperature_c: float,
    outer_temperature_c: float,
) -> HeatTransferResult:
    _ensure_positive(conductivity, "condutividade térmica")
    _ensure_positive(length, "comprimento")
    _ensure_positive(inner_radius, "raio interno")
    _ensure_positive(outer_radius, "raio externo")
    if outer_radius <= inner_radius:
        raise HeatTransferCalculationError("O raio externo deve ser maior que o raio interno.")
    delta_t = inner_temperature_c - outer_temperature_c
    resistance = log(outer_radius / inner_radius) / (2.0 * pi * conductivity * length)
    heat_rate = delta_t / resistance
    return HeatTransferResult(
        tool="conducao_radial_cilindro",
        title="Condução radial estacionária em cilindro",
        interpretation="O calor atravessa a parede cilíndrica radialmente entre os raios interno e externo.",
        data_used=(
            f"k={conductivity:.6g} W/(m.K)",
            f"L={length:.6g} m",
            f"r_i={inner_radius:.6g} m",
            f"r_o={outer_radius:.6g} m",
            f"T_i={inner_temperature_c:.6g} °C",
            f"T_o={outer_temperature_c:.6g} °C",
        ),
        formulas=(r"R_{cil}=\frac{\ln(r_o/r_i)}{2\pi kL}", r"\dot q=\frac{T_i-T_o}{R_{cil}}"),
        substitutions=(
            rf"R_{{cil}}=\frac{{\ln({outer_radius:.6g}/{inner_radius:.6g})}}{{2\pi\cdot {conductivity:.6g}\cdot {length:.6g}}}={resistance:.6g}\ \mathrm{{K/W}}",
            rf"\dot q=\frac{{{inner_temperature_c:.6g}-{outer_temperature_c:.6g}}}{{{resistance:.6g}}}={heat_rate:.6g}\ \mathrm{{W}}",
        ),
        results=(
            HeatTransferQuantity("Resistência térmica", "R_cil", resistance, "K/W", "Resistência radial da parede cilíndrica."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido por unidade de tempo."),
        ),
        validations=_common_validations(delta_t, heat_rate),
        assumptions=("Regime permanente.", "Condução radial unidimensional.", "Condutividade térmica constante."),
    )


def calculate_sphere_conduction(
    conductivity: float,
    inner_radius: float,
    outer_radius: float,
    inner_temperature_c: float,
    outer_temperature_c: float,
) -> HeatTransferResult:
    _ensure_positive(conductivity, "condutividade térmica")
    _ensure_positive(inner_radius, "raio interno")
    _ensure_positive(outer_radius, "raio externo")
    if outer_radius <= inner_radius:
        raise HeatTransferCalculationError("O raio externo deve ser maior que o raio interno.")
    delta_t = inner_temperature_c - outer_temperature_c
    resistance = (1.0 / inner_radius - 1.0 / outer_radius) / (4.0 * pi * conductivity)
    heat_rate = delta_t / resistance
    return HeatTransferResult(
        tool="conducao_radial_esfera",
        title="Condução radial estacionária em esfera",
        interpretation="O calor atravessa a casca esférica radialmente entre os raios interno e externo.",
        data_used=(
            f"k={conductivity:.6g} W/(m.K)",
            f"r_i={inner_radius:.6g} m",
            f"r_o={outer_radius:.6g} m",
            f"T_i={inner_temperature_c:.6g} °C",
            f"T_o={outer_temperature_c:.6g} °C",
        ),
        formulas=(r"R_{esf}=\frac{1}{4\pi k}\left(\frac{1}{r_i}-\frac{1}{r_o}\right)", r"\dot q=\frac{T_i-T_o}{R_{esf}}"),
        substitutions=(
            rf"R_{{esf}}=\frac{{1}}{{4\pi\cdot {conductivity:.6g}}}\left(\frac{{1}}{{{inner_radius:.6g}}}-\frac{{1}}{{{outer_radius:.6g}}}\right)={resistance:.6g}\ \mathrm{{K/W}}",
            rf"\dot q=\frac{{{inner_temperature_c:.6g}-{outer_temperature_c:.6g}}}{{{resistance:.6g}}}={heat_rate:.6g}\ \mathrm{{W}}",
        ),
        results=(
            HeatTransferQuantity("Resistência térmica", "R_esf", resistance, "K/W", "Resistência radial da casca esférica."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido por unidade de tempo."),
        ),
        validations=_common_validations(delta_t, heat_rate),
        assumptions=("Regime permanente.", "Condução radial unidimensional.", "Condutividade térmica constante."),
    )


def calculate_convection(
    heat_transfer_coefficient: float,
    area: float,
    surface_temperature_c: float,
    fluid_temperature_c: float,
) -> HeatTransferResult:
    _ensure_positive(heat_transfer_coefficient, "coeficiente convectivo")
    _ensure_positive(area, "área")
    delta_t = surface_temperature_c - fluid_temperature_c
    resistance = 1.0 / (heat_transfer_coefficient * area)
    heat_rate = delta_t / resistance
    return HeatTransferResult(
        tool="conveccao_newton",
        title="Convecção pela Lei de Newton do resfriamento",
        interpretation="A superfície troca calor com o fluido adjacente por convecção.",
        data_used=(
            f"h={heat_transfer_coefficient:.6g} W/(m².K)",
            f"A={area:.6g} m²",
            f"T_s={surface_temperature_c:.6g} °C",
            f"T_inf={fluid_temperature_c:.6g} °C",
        ),
        formulas=(r"R_{conv}=\frac{1}{hA}", r"\dot q=hA(T_s-T_\infty)"),
        substitutions=(
            rf"R_{{conv}}=\frac{{1}}{{{heat_transfer_coefficient:.6g}\cdot {area:.6g}}}={resistance:.6g}\ \mathrm{{K/W}}",
            rf"\dot q={heat_transfer_coefficient:.6g}\cdot {area:.6g}({surface_temperature_c:.6g}-{fluid_temperature_c:.6g})={heat_rate:.6g}\ \mathrm{{W}}",
        ),
        results=(
            HeatTransferQuantity("Resistência térmica", "R_conv", resistance, "K/W", "Resistência convectiva."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido por convecção."),
        ),
        validations=_common_validations(delta_t, heat_rate),
        assumptions=("Coeficiente convectivo uniforme.", "Temperatura do fluido longe da superfície conhecida."),
    )


def calculate_radiation(
    emissivity: float,
    area: float,
    surface_temperature_c: float,
    surroundings_temperature_c: float,
) -> HeatTransferResult:
    if emissivity < 0 or emissivity > 1:
        raise HeatTransferCalculationError("A emissividade deve ficar entre 0 e 1.")
    _ensure_positive(area, "área")
    surface_temperature_k = surface_temperature_c + 273.15
    surroundings_temperature_k = surroundings_temperature_c + 273.15
    if surface_temperature_k <= 0 or surroundings_temperature_k <= 0:
        raise HeatTransferCalculationError("Temperaturas absolutas devem ser maiores que 0 K.")
    heat_rate = emissivity * SIGMA * area * (surface_temperature_k**4 - surroundings_temperature_k**4)
    return HeatTransferResult(
        tool="radiacao_superficie_vizinhanca",
        title="Radiação térmica superfície-vizinhança",
        interpretation="A superfície troca energia por radiação com uma vizinhança grande a temperatura uniforme.",
        data_used=(
            f"epsilon={emissivity:.6g} [-]",
            f"A={area:.6g} m²",
            f"T_s={surface_temperature_k:.6g} K",
            f"T_sur={surroundings_temperature_k:.6g} K",
        ),
        formulas=(r"\dot q_{rad}=\varepsilon\sigma A(T_s^4-T_{sur}^4)",),
        substitutions=(
            rf"\dot q_{{rad}}={emissivity:.6g}\cdot {SIGMA:.6g}\cdot {area:.6g}({surface_temperature_k:.6g}^4-{surroundings_temperature_k:.6g}^4)={heat_rate:.6g}\ \mathrm{{W}}",
        ),
        results=(
            HeatTransferQuantity("Taxa de calor por radiação", "q_dot_rad", heat_rate, "W", "Calor líquido transferido por radiação."),
        ),
        validations=_common_validations(surface_temperature_k - surroundings_temperature_k, heat_rate),
        assumptions=("Superfície cinzenta e difusa.", "Vizinhança grande a temperatura uniforme.", "Temperaturas convertidas para Kelvin no cálculo."),
    )


def calculate_straight_fin_adiabatic_tip(
    heat_transfer_coefficient: float,
    perimeter: float,
    conductivity: float,
    cross_section_area: float,
    length: float,
    base_temperature_c: float,
    fluid_temperature_c: float,
) -> HeatTransferResult:
    _ensure_positive(heat_transfer_coefficient, "coeficiente convectivo")
    _ensure_positive(perimeter, "perímetro")
    _ensure_positive(conductivity, "condutividade térmica")
    _ensure_positive(cross_section_area, "área da seção transversal")
    _ensure_positive(length, "comprimento da aleta")
    theta_b = base_temperature_c - fluid_temperature_c
    m_value = sqrt(heat_transfer_coefficient * perimeter / (conductivity * cross_section_area))
    ml_value = m_value * length
    fin_area = perimeter * length
    efficiency = tanh(ml_value) / ml_value
    heat_rate = sqrt(heat_transfer_coefficient * perimeter * conductivity * cross_section_area) * theta_b * tanh(ml_value)
    effectiveness = heat_rate / (heat_transfer_coefficient * cross_section_area * theta_b) if abs(theta_b) > 1e-12 else 0.0
    return HeatTransferResult(
        tool="aleta_reta_ponta_adiabatica",
        title="Aleta reta de seção constante com ponta adiabática",
        interpretation="A aleta amplia a área de troca térmica e conduz calor da base para a superfície exposta ao fluido.",
        data_used=(
            f"h={heat_transfer_coefficient:.6g} W/(m².K)",
            f"P={perimeter:.6g} m",
            f"k={conductivity:.6g} W/(m.K)",
            f"A_c={cross_section_area:.6g} m²",
            f"L={length:.6g} m",
            f"T_b={base_temperature_c:.6g} °C",
            f"T_inf={fluid_temperature_c:.6g} °C",
        ),
        formulas=(
            r"m=\sqrt{\frac{hP}{kA_c}}",
            r"\eta_f=\frac{\tanh(mL)}{mL}",
            r"\dot q_f=\sqrt{hPkA_c}(T_b-T_\infty)\tanh(mL)",
            r"\varepsilon_f=\frac{\dot q_f}{hA_c(T_b-T_\infty)}",
        ),
        substitutions=(
            rf"m=\sqrt{{\frac{{{heat_transfer_coefficient:.6g}\cdot {perimeter:.6g}}}{{{conductivity:.6g}\cdot {cross_section_area:.6g}}}}}={m_value:.6g}\ \mathrm{{1/m}}",
            rf"\eta_f=\frac{{\tanh({ml_value:.6g})}}{{{ml_value:.6g}}}={efficiency:.6g}",
            rf"\dot q_f=\sqrt{{{heat_transfer_coefficient:.6g}\cdot {perimeter:.6g}\cdot {conductivity:.6g}\cdot {cross_section_area:.6g}}}({base_temperature_c:.6g}-{fluid_temperature_c:.6g})\tanh({ml_value:.6g})={heat_rate:.6g}\ \mathrm{{W}}",
            rf"\varepsilon_f=\frac{{{heat_rate:.6g}}}{{{heat_transfer_coefficient:.6g}\cdot {cross_section_area:.6g}\cdot ({base_temperature_c:.6g}-{fluid_temperature_c:.6g})}}={effectiveness:.6g}",
        ),
        results=(
            HeatTransferQuantity("Parâmetro da aleta", "m", m_value, "1/m", "Controla o decaimento de temperatura ao longo da aleta."),
            HeatTransferQuantity("Área lateral da aleta", "A_f", fin_area, "m²", "Área exposta à convecção."),
            HeatTransferQuantity("Eficiência da aleta", "eta_f", efficiency, "-", "Razão entre calor real e calor se toda a aleta estivesse à temperatura da base."),
            HeatTransferQuantity("Efetividade da aleta", "epsilon_f", effectiveness, "-", "Ganho em relação à área da base sem aleta."),
            HeatTransferQuantity("Taxa de calor da aleta", "q_dot_fin", heat_rate, "W", "Calor dissipado pela aleta."),
        ),
        validations=(
            f"mL = {ml_value:.6g}.",
            f"Eficiência calculada entre 0 e 1: {0 <= efficiency <= 1}.",
            f"Efetividade maior que 1 indica que a aleta aumenta a transferência de calor: {effectiveness > 1}.",
        ),
        assumptions=("Regime permanente.", "Aleta reta de seção constante.", "Ponta adiabática.", "Propriedades constantes."),
    )


def calculate_lumped_capacitance(
    heat_transfer_coefficient: float,
    area: float,
    density: float,
    volume: float,
    specific_heat: float,
    conductivity: float,
    initial_temperature_c: float,
    fluid_temperature_c: float,
    time_s: float,
) -> HeatTransferResult:
    _ensure_positive(heat_transfer_coefficient, "coeficiente convectivo")
    _ensure_positive(area, "área")
    _ensure_positive(density, "densidade")
    _ensure_positive(volume, "volume")
    _ensure_positive(specific_heat, "calor específico")
    _ensure_positive(conductivity, "condutividade térmica")
    if time_s < 0:
        raise HeatTransferCalculationError("O tempo não pode ser negativo.")
    characteristic_length = volume / area
    biot = heat_transfer_coefficient * characteristic_length / conductivity
    if biot >= 0.1:
        raise HeatTransferCalculationError(
            f"Capacitância concentrada inválida: Bi={biot:.6g} >= 0,1. Use modelo transiente distribuído."
        )
    tau = density * volume * specific_heat / (heat_transfer_coefficient * area)
    temperature_t = fluid_temperature_c + (initial_temperature_c - fluid_temperature_c) * exp(-time_s / tau)
    heat_transferred = density * volume * specific_heat * (initial_temperature_c - temperature_t)
    return HeatTransferResult(
        tool="capacitancia_concentrada",
        title="Transiente por capacitância concentrada",
        interpretation="O corpo é tratado com temperatura espacialmente uniforme, variando apenas com o tempo.",
        data_used=(
            f"h={heat_transfer_coefficient:.6g} W/(m².K)",
            f"A={area:.6g} m²",
            f"rho={density:.6g} kg/m³",
            f"V={volume:.6g} m³",
            f"c_p={specific_heat:.6g} J/(kg.K)",
            f"k={conductivity:.6g} W/(m.K)",
            f"T_i={initial_temperature_c:.6g} °C",
            f"T_inf={fluid_temperature_c:.6g} °C",
            f"t={time_s:.6g} s",
        ),
        formulas=(
            r"L_c=\frac{V}{A}",
            r"Bi=\frac{hL_c}{k}",
            r"\tau=\frac{\rho V c_p}{hA}",
            r"T(t)=T_\infty+(T_i-T_\infty)e^{-t/\tau}",
            r"Q=\rho Vc_p(T_i-T(t))",
        ),
        substitutions=(
            rf"L_c=\frac{{{volume:.6g}}}{{{area:.6g}}}={characteristic_length:.6g}\ \mathrm{{m}}",
            rf"Bi=\frac{{{heat_transfer_coefficient:.6g}\cdot {characteristic_length:.6g}}}{{{conductivity:.6g}}}={biot:.6g}",
            rf"\tau=\frac{{{density:.6g}\cdot {volume:.6g}\cdot {specific_heat:.6g}}}{{{heat_transfer_coefficient:.6g}\cdot {area:.6g}}}={tau:.6g}\ \mathrm{{s}}",
            rf"T(t)={fluid_temperature_c:.6g}+({initial_temperature_c:.6g}-{fluid_temperature_c:.6g})e^{{-{time_s:.6g}/{tau:.6g}}}={temperature_t:.6g}\ \mathrm{{^\circ C}}",
            rf"Q={density:.6g}\cdot {volume:.6g}\cdot {specific_heat:.6g}({initial_temperature_c:.6g}-{temperature_t:.6g})={heat_transferred:.6g}\ \mathrm{{J}}",
        ),
        results=(
            HeatTransferQuantity("Comprimento característico", "L_c", characteristic_length, "m", "Razão volume/área."),
            HeatTransferQuantity("Número de Biot", "Bi", biot, "-", "Valida a hipótese de temperatura interna uniforme."),
            HeatTransferQuantity("Constante de tempo", "tau", tau, "s", "Escala temporal da resposta térmica."),
            HeatTransferQuantity("Temperatura no tempo", "T_t", temperature_t, "°C", "Temperatura do corpo no instante informado."),
            HeatTransferQuantity("Energia transferida", "Q", heat_transferred, "J", "Energia sensível perdida ou recebida pelo corpo."),
        ),
        validations=(
            f"Bi = {biot:.6g} < 0,1; modelo de capacitância concentrada válido.",
            "Temperatura calculada permanece entre a temperatura inicial e a temperatura do fluido quando não há geração interna.",
        ),
        assumptions=("Temperatura interna uniforme.", "Propriedades constantes.", "Sem geração interna de calor."),
    )


def calculate_lmtd_heat_exchanger(
    overall_coefficient: float,
    area: float,
    hot_inlet_temperature_c: float,
    hot_outlet_temperature_c: float,
    cold_inlet_temperature_c: float,
    cold_outlet_temperature_c: float,
    flow_type: str,
    correction_factor: float = 1.0,
) -> HeatTransferResult:
    _ensure_positive(overall_coefficient, "coeficiente global U")
    _ensure_positive(area, "área")
    _ensure_positive(correction_factor, "fator de correção")
    normalized_flow = _normalize_flow_type(flow_type)
    if normalized_flow == "paralelo":
        delta_t_1 = hot_inlet_temperature_c - cold_inlet_temperature_c
        delta_t_2 = hot_outlet_temperature_c - cold_outlet_temperature_c
        flow_label = "paralelo"
    elif normalized_flow == "contracorrente":
        delta_t_1 = hot_inlet_temperature_c - cold_outlet_temperature_c
        delta_t_2 = hot_outlet_temperature_c - cold_inlet_temperature_c
        flow_label = "contracorrente"
    else:
        raise HeatTransferCalculationError("Tipo de escoamento deve ser 'paralelo' ou 'contracorrente'.")
    if delta_t_1 <= 0 or delta_t_2 <= 0:
        raise HeatTransferCalculationError(
            "LMTD inválido: as diferenças de temperatura entre correntes quente e fria devem ser positivas nas duas extremidades."
        )
    lmtd = _log_mean_temperature_difference(delta_t_1, delta_t_2)
    heat_rate = overall_coefficient * area * correction_factor * lmtd
    return HeatTransferResult(
        tool="trocador_lmtd",
        title="Trocador de calor por LMTD",
        interpretation="O trocador é resolvido pela diferença média logarítmica de temperatura entre as correntes quente e fria.",
        data_used=(
            f"U={overall_coefficient:.6g} W/(m².K)",
            f"A={area:.6g} m²",
            f"T_h_in={hot_inlet_temperature_c:.6g} °C",
            f"T_h_out={hot_outlet_temperature_c:.6g} °C",
            f"T_c_in={cold_inlet_temperature_c:.6g} °C",
            f"T_c_out={cold_outlet_temperature_c:.6g} °C",
            f"F={correction_factor:.6g} -",
            f"flow_type={flow_label}",
        ),
        formulas=(
            r"\Delta T_{lm}=\frac{\Delta T_1-\Delta T_2}{\ln(\Delta T_1/\Delta T_2)}",
            r"\dot q=UAF\Delta T_{lm}",
        ),
        substitutions=(
            rf"\Delta T_1={delta_t_1:.6g}\ \mathrm{{K}},\quad \Delta T_2={delta_t_2:.6g}\ \mathrm{{K}}",
            rf"\Delta T_{{lm}}=\frac{{{delta_t_1:.6g}-{delta_t_2:.6g}}}{{\ln({delta_t_1:.6g}/{delta_t_2:.6g})}}={lmtd:.6g}\ \mathrm{{K}}",
            rf"\dot q={overall_coefficient:.6g}\cdot {area:.6g}\cdot {correction_factor:.6g}\cdot {lmtd:.6g}={heat_rate:.6g}\ \mathrm{{W}}",
        ),
        results=(
            HeatTransferQuantity("Diferença terminal 1", "Delta_T_1", delta_t_1, "K", "Diferença de temperatura em uma extremidade do trocador."),
            HeatTransferQuantity("Diferença terminal 2", "Delta_T_2", delta_t_2, "K", "Diferença de temperatura na outra extremidade do trocador."),
            HeatTransferQuantity("Diferença média logarítmica", "Delta_T_lm", lmtd, "K", "Diferença média efetiva para troca de calor."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido entre as correntes."),
        ),
        validations=(
            f"ΔT1 = {delta_t_1:.6g} K e ΔT2 = {delta_t_2:.6g} K são positivos.",
            f"Tipo de escoamento usado: {flow_label}.",
            f"Fator de correção F = {correction_factor:.6g}.",
        ),
        assumptions=("Regime permanente.", "Coeficiente global U constante.", "Sem perda de calor para o ambiente.", "Sem mudança de fase não modelada explicitamente."),
    )


def calculate_ntu_heat_exchanger(
    hot_capacity_rate: float,
    cold_capacity_rate: float,
    ua: float,
    hot_inlet_temperature_c: float,
    cold_inlet_temperature_c: float,
    flow_type: str,
) -> HeatTransferResult:
    _ensure_positive(hot_capacity_rate, "capacidade térmica da corrente quente")
    _ensure_positive(cold_capacity_rate, "capacidade térmica da corrente fria")
    _ensure_positive(ua, "UA")
    normalized_flow = _normalize_flow_type(flow_type)
    if normalized_flow not in {"paralelo", "contracorrente"}:
        raise HeatTransferCalculationError("Tipo de escoamento deve ser 'paralelo' ou 'contracorrente'.")
    delta_t_inlet = hot_inlet_temperature_c - cold_inlet_temperature_c
    if delta_t_inlet <= 0:
        raise HeatTransferCalculationError("NTU inválido: a entrada quente deve estar acima da entrada fria.")
    c_min = min(hot_capacity_rate, cold_capacity_rate)
    c_max = max(hot_capacity_rate, cold_capacity_rate)
    c_ratio = c_min / c_max
    ntu = ua / c_min
    effectiveness = _heat_exchanger_effectiveness(ntu, c_ratio, normalized_flow)
    heat_rate_max = c_min * delta_t_inlet
    heat_rate = effectiveness * heat_rate_max
    hot_outlet_temperature_c = hot_inlet_temperature_c - heat_rate / hot_capacity_rate
    cold_outlet_temperature_c = cold_inlet_temperature_c + heat_rate / cold_capacity_rate
    return HeatTransferResult(
        tool="trocador_ntu",
        title="Trocador de calor por Efetividade-NTU",
        interpretation="O trocador é resolvido pela efetividade térmica, usando as capacidades térmicas das correntes e o produto UA.",
        data_used=(
            f"C_h={hot_capacity_rate:.6g} W/K",
            f"C_c={cold_capacity_rate:.6g} W/K",
            f"UA={ua:.6g} W/K",
            f"T_h_in={hot_inlet_temperature_c:.6g} °C",
            f"T_c_in={cold_inlet_temperature_c:.6g} °C",
            f"flow_type={normalized_flow}",
        ),
        formulas=(
            r"C_{min}=\min(C_h,C_c)",
            r"C_r=\frac{C_{min}}{C_{max}}",
            r"NTU=\frac{UA}{C_{min}}",
            r"\dot q=\varepsilon C_{min}(T_{h,in}-T_{c,in})",
            r"T_{h,out}=T_{h,in}-\frac{\dot q}{C_h}",
            r"T_{c,out}=T_{c,in}+\frac{\dot q}{C_c}",
        ),
        substitutions=(
            rf"C_{{min}}=\min({hot_capacity_rate:.6g},{cold_capacity_rate:.6g})={c_min:.6g}\ \mathrm{{W/K}}",
            rf"C_r=\frac{{{c_min:.6g}}}{{{c_max:.6g}}}={c_ratio:.6g}",
            rf"NTU=\frac{{{ua:.6g}}}{{{c_min:.6g}}}={ntu:.6g}",
            rf"\varepsilon={effectiveness:.6g}\quad(\mathrm{{{normalized_flow}}})",
            rf"\dot q={effectiveness:.6g}\cdot {c_min:.6g}({hot_inlet_temperature_c:.6g}-{cold_inlet_temperature_c:.6g})={heat_rate:.6g}\ \mathrm{{W}}",
            rf"T_{{h,out}}={hot_inlet_temperature_c:.6g}-\frac{{{heat_rate:.6g}}}{{{hot_capacity_rate:.6g}}}={hot_outlet_temperature_c:.6g}\ \mathrm{{^\circ C}}",
            rf"T_{{c,out}}={cold_inlet_temperature_c:.6g}+\frac{{{heat_rate:.6g}}}{{{cold_capacity_rate:.6g}}}={cold_outlet_temperature_c:.6g}\ \mathrm{{^\circ C}}",
        ),
        results=(
            HeatTransferQuantity("Capacidade térmica mínima", "C_min", c_min, "W/K", "Menor capacidade térmica entre as correntes."),
            HeatTransferQuantity("Razão de capacidades", "C_r", c_ratio, "-", "Razão Cmin/Cmax."),
            HeatTransferQuantity("Número de unidades de transferência", "NTU", ntu, "-", "Intensidade adimensional de troca térmica."),
            HeatTransferQuantity("Efetividade", "epsilon_hx", effectiveness, "-", "Fração do calor máximo possível transferida."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido entre as correntes."),
            HeatTransferQuantity("Saída quente", "T_h_out", hot_outlet_temperature_c, "°C", "Temperatura de saída da corrente quente."),
            HeatTransferQuantity("Saída fria", "T_c_out", cold_outlet_temperature_c, "°C", "Temperatura de saída da corrente fria."),
        ),
        validations=(
            f"0 <= efetividade <= 1: {0 <= effectiveness <= 1}.",
            f"T_h,out = {hot_outlet_temperature_c:.6g} °C e T_c,out = {cold_outlet_temperature_c:.6g} °C.",
            f"Tipo de escoamento usado: {normalized_flow}.",
        ),
        assumptions=("Regime permanente.", "UA constante.", "Sem perda de calor para o ambiente.", "Calores específicos constantes nas capacidades informadas."),
    )


def calculate_series_resistance_network(
    resistances: tuple[float, ...],
    hot_temperature_c: float,
    cold_temperature_c: float,
) -> HeatTransferResult:
    _ensure_resistance_list(resistances)
    total_resistance = sum(resistances)
    delta_t = hot_temperature_c - cold_temperature_c
    heat_rate = delta_t / total_resistance
    drops = tuple(heat_rate * resistance for resistance in resistances)
    node_temperatures = [hot_temperature_c]
    current_temperature = hot_temperature_c
    for drop in drops:
        current_temperature -= drop
        node_temperatures.append(current_temperature)
    resistance_text = ", ".join(f"{value:.6g}" for value in resistances)
    node_text = ", ".join(f"{value:.6g}" for value in node_temperatures)
    return HeatTransferResult(
        tool="rede_resistencias_serie",
        title="Rede de resistências térmicas em série",
        interpretation="As resistências térmicas estão no mesmo caminho de calor; a resistência equivalente é a soma direta.",
        data_used=(
            f"R_list={resistance_text} K/W",
            f"T_hot={hot_temperature_c:.6g} °C",
            f"T_cold={cold_temperature_c:.6g} °C",
            f"T_nodes={node_text} °C",
        ),
        formulas=(
            r"R_{eq}=\sum_i R_i",
            r"\dot q=\frac{T_{hot}-T_{cold}}{R_{eq}}",
            r"\Delta T_i=\dot q R_i",
        ),
        substitutions=(
            rf"R_{{eq}}={'+'.join(f'{value:.6g}' for value in resistances)}={total_resistance:.6g}\ \mathrm{{K/W}}",
            rf"\dot q=\frac{{{hot_temperature_c:.6g}-{cold_temperature_c:.6g}}}{{{total_resistance:.6g}}}={heat_rate:.6g}\ \mathrm{{W}}",
            rf"T_{{nodes}}=\left({node_text}\right)\ \mathrm{{^\circ C}}",
        ),
        results=(
            HeatTransferQuantity("Resistência equivalente", "R_eq", total_resistance, "K/W", "Soma das resistências em série."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido pelo caminho em série."),
        ),
        validations=_common_validations(delta_t, heat_rate),
        assumptions=("Regime permanente.", "Fluxo unidimensional equivalente.", "Resistências informadas já estão em K/W."),
    )


def calculate_parallel_resistance_network(
    resistances: tuple[float, ...],
    hot_temperature_c: float,
    cold_temperature_c: float,
) -> HeatTransferResult:
    _ensure_resistance_list(resistances)
    conductance = sum(1.0 / resistance for resistance in resistances)
    total_resistance = 1.0 / conductance
    delta_t = hot_temperature_c - cold_temperature_c
    branch_heat_rates = tuple(delta_t / resistance for resistance in resistances)
    heat_rate = sum(branch_heat_rates)
    resistance_text = ", ".join(f"{value:.6g}" for value in resistances)
    branch_text = ", ".join(f"{value:.6g}" for value in branch_heat_rates)
    result_quantities = [
        HeatTransferQuantity("Resistência equivalente", "R_eq", total_resistance, "K/W", "Inverso da soma das condutâncias térmicas."),
        HeatTransferQuantity("Taxa de calor total", "q_dot", heat_rate, "W", "Soma do calor em todos os ramos paralelos."),
    ]
    for index, branch_heat_rate in enumerate(branch_heat_rates, start=1):
        result_quantities.append(
            HeatTransferQuantity(f"Taxa de calor no ramo {index}", f"q_dot_{index}", branch_heat_rate, "W", "Calor transferido em um ramo paralelo.")
        )
    return HeatTransferResult(
        tool="rede_resistencias_paralelo",
        title="Rede de resistências térmicas em paralelo",
        interpretation="As resistências térmicas conectam os mesmos dois níveis de temperatura; somam-se as condutâncias.",
        data_used=(
            f"R_list={resistance_text} K/W",
            f"T_hot={hot_temperature_c:.6g} °C",
            f"T_cold={cold_temperature_c:.6g} °C",
            f"q_branches={branch_text} W",
        ),
        formulas=(
            r"\frac{1}{R_{eq}}=\sum_i\frac{1}{R_i}",
            r"\dot q_i=\frac{T_{hot}-T_{cold}}{R_i}",
            r"\dot q=\sum_i \dot q_i",
        ),
        substitutions=(
            rf"\frac{{1}}{{R_{{eq}}}}={'+'.join(f'1/{value:.6g}' for value in resistances)}={conductance:.6g}\ \mathrm{{W/K}}",
            rf"R_{{eq}}={total_resistance:.6g}\ \mathrm{{K/W}}",
            rf"\dot q_i=\left({branch_text}\right)\ \mathrm{{W}},\quad \dot q={heat_rate:.6g}\ \mathrm{{W}}",
        ),
        results=tuple(result_quantities),
        validations=_common_validations(delta_t, heat_rate),
        assumptions=("Regime permanente.", "Todos os ramos compartilham os mesmos nós quente e frio.", "Resistências informadas já estão em K/W."),
    )


def calculate_dittus_boelter_forced_convection(
    density: float,
    velocity: float,
    diameter: float,
    dynamic_viscosity: float,
    specific_heat: float,
    conductivity: float,
    mode: str,
) -> HeatTransferResult:
    _ensure_positive(density, "densidade")
    _ensure_positive(velocity, "velocidade")
    _ensure_positive(diameter, "diâmetro característico")
    _ensure_positive(dynamic_viscosity, "viscosidade dinâmica")
    _ensure_positive(specific_heat, "calor específico")
    _ensure_positive(conductivity, "condutividade térmica")
    normalized_mode = mode.strip().lower()
    if normalized_mode in {"aquecimento", "heating", "fluido aquecido"}:
        exponent = 0.4
        mode_label = "aquecimento do fluido"
    elif normalized_mode in {"resfriamento", "cooling", "fluido resfriado"}:
        exponent = 0.3
        mode_label = "resfriamento do fluido"
    else:
        raise HeatTransferCalculationError("Modo deve ser 'aquecimento' ou 'resfriamento' para Dittus-Boelter.")
    reynolds = density * velocity * diameter / dynamic_viscosity
    prandtl = specific_heat * dynamic_viscosity / conductivity
    nusselt = 0.023 * reynolds**0.8 * prandtl**exponent
    heat_transfer_coefficient = nusselt * conductivity / diameter
    return HeatTransferResult(
        tool="conveccao_forcada_dittus_boelter",
        title="Convecção forçada interna — Dittus-Boelter",
        interpretation="Calcula números adimensionais e coeficiente convectivo para escoamento interno turbulento em tubo liso.",
        data_used=(
            f"rho={density:.6g} kg/m³",
            f"velocity={velocity:.6g} m/s",
            f"D={diameter:.6g} m",
            f"mu={dynamic_viscosity:.6g} Pa.s",
            f"c_p={specific_heat:.6g} J/(kg.K)",
            f"k={conductivity:.6g} W/(m.K)",
            f"mode={mode_label}",
        ),
        formulas=(
            r"Re=\frac{\rho VD}{\mu}",
            r"Pr=\frac{c_p\mu}{k}",
            r"Nu=0,023Re^{0,8}Pr^n",
            r"h=\frac{Nu\,k}{D}",
        ),
        substitutions=(
            rf"Re=\frac{{{density:.6g}\cdot {velocity:.6g}\cdot {diameter:.6g}}}{{{dynamic_viscosity:.6g}}}={reynolds:.6g}",
            rf"Pr=\frac{{{specific_heat:.6g}\cdot {dynamic_viscosity:.6g}}}{{{conductivity:.6g}}}={prandtl:.6g}",
            rf"Nu=0,023({reynolds:.6g})^{{0,8}}({prandtl:.6g})^{{{exponent:.1f}}}={nusselt:.6g}",
            rf"h=\frac{{{nusselt:.6g}\cdot {conductivity:.6g}}}{{{diameter:.6g}}}={heat_transfer_coefficient:.6g}\ \mathrm{{W/(m^2.K)}}",
        ),
        results=(
            HeatTransferQuantity("Número de Reynolds", "Re", reynolds, "-", "Classifica o regime de escoamento."),
            HeatTransferQuantity("Número de Prandtl", "Pr", prandtl, "-", "Relaciona difusividade de momento e térmica."),
            HeatTransferQuantity("Número de Nusselt", "Nu", nusselt, "-", "Coeficiente convectivo adimensional."),
            HeatTransferQuantity("Coeficiente convectivo", "h", heat_transfer_coefficient, "W/(m².K)", "Coeficiente de convecção estimado pela correlação."),
        ),
        validations=(
            f"Re = {reynolds:.6g}; Dittus-Boelter é recomendado para escoamento turbulento interno, tipicamente Re >= 10000: {reynolds >= 10000}.",
            f"Pr = {prandtl:.6g}; faixa usual aproximada 0,7 <= Pr <= 160: {0.7 <= prandtl <= 160}.",
            "Use apenas para tubo liso, escoamento plenamente desenvolvido e propriedades avaliadas em temperatura apropriada.",
        ),
        assumptions=("Escoamento interno turbulento.", "Tubo liso.", "Propriedades constantes.", "Sem efeitos de entrada dominantes."),
    )


def _heat_exchanger_effectiveness(ntu: float, c_ratio: float, flow_type: str) -> float:
    if flow_type == "paralelo":
        return (1 - exp(-ntu * (1 + c_ratio))) / (1 + c_ratio)
    if isclose(c_ratio, 1.0, rel_tol=1e-9, abs_tol=1e-12):
        return ntu / (1 + ntu)
    numerator = 1 - exp(-ntu * (1 - c_ratio))
    denominator = 1 - c_ratio * exp(-ntu * (1 - c_ratio))
    return numerator / denominator


def _normalize_flow_type(flow_type: str) -> str:
    normalized = flow_type.strip().lower().replace(" ", "")
    if normalized in {"paralelo", "correntesparalelas", "parallel"}:
        return "paralelo"
    if normalized in {"contracorrente", "contracorrentes", "contrafluxo", "counterflow", "countercurrent"}:
        return "contracorrente"
    return normalized


def _log_mean_temperature_difference(delta_t_1: float, delta_t_2: float) -> float:
    if isclose(delta_t_1, delta_t_2, rel_tol=1e-9, abs_tol=1e-12):
        return delta_t_1
    return (delta_t_1 - delta_t_2) / log(delta_t_1 / delta_t_2)


def _ensure_positive(value: float, label: str) -> None:
    if value <= 0:
        raise HeatTransferCalculationError(f"{label.capitalize()} deve ser maior que zero.")


def _ensure_resistance_list(resistances: tuple[float, ...]) -> None:
    if not resistances:
        raise HeatTransferCalculationError("Informe pelo menos uma resistência térmica.")
    for index, resistance in enumerate(resistances, start=1):
        _ensure_positive(resistance, f"resistência térmica R{index}")


def _common_validations(delta_t: float, heat_rate: float) -> tuple[str, ...]:
    direction = "do primeiro reservatório/superfície para o segundo" if heat_rate >= 0 else "no sentido oposto ao informado"
    return (
        f"Delta T = {delta_t:.6g} K. O sinal indica transferência {direction}.",
        "Unidades internas em SI; diferenças de temperatura em °C e K têm mesmo valor numérico.",
    )

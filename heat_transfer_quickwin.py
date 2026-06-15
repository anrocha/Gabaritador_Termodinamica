from __future__ import annotations

from dataclasses import dataclass
from math import cos, exp, log, pi, sin, sqrt, tan

from heat_transfer_core import (
    HeatTransferCalculationError,
    HeatTransferQuantity,
    HeatTransferResult,
    calculate_straight_fin_adiabatic_tip,
)


def calculate_external_flat_plate_convection(
    fluid: str,
    velocity: float,
    length: float,
    width: float,
    surface_temperature_c: float,
    fluid_temperature_c: float,
    pressure_pa: float = 101325.0,
) -> HeatTransferResult:
    _ensure_positive(velocity, "velocidade")
    _ensure_positive(length, "comprimento")
    _ensure_positive(width, "largura")
    _ensure_positive(pressure_pa, "pressao")
    film_temperature_c = 0.5 * (surface_temperature_c + fluid_temperature_c)
    props = _fluid_properties(fluid, film_temperature_c, pressure_pa)
    reynolds = props["rho"] * velocity * length / props["mu"]
    prandtl = props["cp"] * props["mu"] / props["k"]
    if reynolds < 5.0e5:
        regime = "laminar"
        nusselt = 0.664 * reynolds**0.5 * prandtl ** (1.0 / 3.0)
    elif reynolds > 1.0e6:
        regime = "turbulento"
        nusselt = (0.037 * reynolds**0.8 - 871.0) * prandtl ** (1.0 / 3.0)
    else:
        regime = "misto"
        nusselt = (0.037 * reynolds**0.8 - 871.0) * prandtl ** (1.0 / 3.0)
    h = nusselt * props["k"] / length
    area = length * width
    q_dot = h * area * (surface_temperature_c - fluid_temperature_c)
    x_cr = 5.0e5 * props["mu"] / (props["rho"] * velocity)
    return HeatTransferResult(
        tool="conveccao_placa_plana_externa",
        title="Conveccao externa em placa plana",
        interpretation="A placa troca calor com o escoamento externo; a correlacao depende do regime.",
        data_used=(
            f"fluid={fluid}",
            f"V={velocity:.6g} m/s",
            f"L={length:.6g} m",
            f"W={width:.6g} m",
            f"T_s={surface_temperature_c:.6g} C",
            f"T_inf={fluid_temperature_c:.6g} C",
            f"P={pressure_pa:.6g} Pa",
            f"Tf={film_temperature_c:.6g} C",
            f"rho={props['rho']:.6g} kg/m^3",
            f"mu={props['mu']:.6g} Pa.s",
            f"nu={props['nu']:.6g} m^2/s",
            f"k={props['k']:.6g} W/(m.K)",
            f"cp={props['cp']:.6g} J/(kg.K)",
            f"Pr={prandtl:.6g} -",
            f"regime={regime}",
        ),
        formulas=(
            r"Re_L=\frac{\rho V L}{\mu}",
            r"Nu_L=0.664Re_L^{1/2}Pr^{1/3}",
            r"Nu_L=(0.037Re_L^{0.8}-871)Pr^{1/3}",
            r"h=\frac{Nu_Lk}{L}",
            r"\dot q=hA(T_s-T_\infty)",
        ),
        substitutions=(
            rf"Re_L=\frac{{{props['rho']:.6g}\cdot {velocity:.6g}\cdot {length:.6g}}}{{{props['mu']:.6g}}}={reynolds:.6g}",
            rf"Pr=\frac{{{props['cp']:.6g}\cdot {props['mu']:.6g}}}{{{props['k']:.6g}}}={prandtl:.6g}",
            rf"Nu_L={nusselt:.6g}\quad(\mathrm{{{regime}}})",
            rf"h=\frac{{{nusselt:.6g}\cdot {props['k']:.6g}}}{{{length:.6g}}}={h:.6g}\ \mathrm{{W/(m^2.K)}}",
            rf"\dot q={h:.6g}\cdot {area:.6g}\cdot ({surface_temperature_c:.6g}-{fluid_temperature_c:.6g})={q_dot:.6g}\ \mathrm{{W}}",
        ),
        results=(
            HeatTransferQuantity("Reynolds da placa", "Re_L", reynolds, "-", "Numero de Reynolds com o comprimento da placa."),
            HeatTransferQuantity("Prandtl", "Pr", prandtl, "-", "Propriedade adimensional do fluido."),
            HeatTransferQuantity("Nusselt da placa", "Nu_L", nusselt, "-", "Correlação media da placa plana."),
            HeatTransferQuantity("Coeficiente convectivo", "h", h, "W/(m².K)", "Troca convectiva media na placa."),
            HeatTransferQuantity("Taxa de calor", "q_dot", q_dot, "W", "Calor transferido pela placa."),
        ),
        validations=(
            f"Re_L = {reynolds:.6g}. Transicao considerada em 5e5; x_cr = {x_cr:.6g} m.",
            f"Regime classificado como {regime}.",
        ),
        assumptions=("Propriedades avaliadas na temperatura de filme.", "Escoamento paralelo a placa.", "Placa lisa e isoterma."),
    )


def calculate_internal_tube_convection(
    fluid: str,
    diameter: float,
    length: float,
    velocity: float,
    inlet_temperature_c: float,
    wall_temperature_c: float,
    pressure_pa: float = 101325.0,
) -> HeatTransferResult:
    _ensure_positive(diameter, "diametro")
    _ensure_positive(length, "comprimento")
    _ensure_positive(velocity, "velocidade")
    _ensure_positive(pressure_pa, "pressao")
    outlet_temperature_c = inlet_temperature_c
    q_dot = 0.0
    for _ in range(30):
        film_temperature_c = 0.5 * (inlet_temperature_c + outlet_temperature_c)
        props = _fluid_properties(fluid, film_temperature_c, pressure_pa)
        area_flow = pi * diameter**2 / 4.0
        mdot = props["rho"] * velocity * area_flow
        reynolds = props["rho"] * velocity * diameter / props["mu"]
        prandtl = props["cp"] * props["mu"] / props["k"]
        entrance_h = 0.05 * reynolds * diameter
        entrance_t = entrance_h * prandtl
        if reynolds < 2300:
            regime = "laminar"
            if length < max(entrance_h, entrance_t):
                nusselt = max(1.86 * (reynolds * prandtl * diameter / length) ** (1.0 / 3.0), 3.66)
            else:
                nusselt = 3.66
        elif reynolds > 10000:
            regime = "turbulento"
            nusselt = 0.023 * reynolds**0.8 * prandtl**0.4
        else:
            regime = "misto"
            laminar_nu = max(1.86 * (reynolds * prandtl * diameter / length) ** (1.0 / 3.0), 3.66)
            turbulent_nu = 0.023 * reynolds**0.8 * prandtl**0.4
            mix = (reynolds - 2300.0) / (10000.0 - 2300.0)
            nusselt = (1.0 - mix) * laminar_nu + mix * turbulent_nu
        h = nusselt * props["k"] / diameter
        q_dot = h * pi * diameter * length * (wall_temperature_c - film_temperature_c)
        new_outlet_temperature_c = inlet_temperature_c + q_dot / (mdot * props["cp"])
        if abs(new_outlet_temperature_c - outlet_temperature_c) < 1e-6:
            outlet_temperature_c = new_outlet_temperature_c
            break
        outlet_temperature_c = new_outlet_temperature_c
    film_temperature_c = 0.5 * (inlet_temperature_c + outlet_temperature_c)
    props = _fluid_properties(fluid, film_temperature_c, pressure_pa)
    area_flow = pi * diameter**2 / 4.0
    mdot = props["rho"] * velocity * area_flow
    reynolds = props["rho"] * velocity * diameter / props["mu"]
    prandtl = props["cp"] * props["mu"] / props["k"]
    entrance_h = 0.05 * reynolds * diameter
    entrance_t = entrance_h * prandtl
    if reynolds < 2300:
        regime = "laminar"
        if length < max(entrance_h, entrance_t):
            nusselt = max(1.86 * (reynolds * prandtl * diameter / length) ** (1.0 / 3.0), 3.66)
        else:
            nusselt = 3.66
    elif reynolds > 10000:
        regime = "turbulento"
        nusselt = 0.023 * reynolds**0.8 * prandtl**0.4
    else:
        regime = "misto"
        laminar_nu = max(1.86 * (reynolds * prandtl * diameter / length) ** (1.0 / 3.0), 3.66)
        turbulent_nu = 0.023 * reynolds**0.8 * prandtl**0.4
        mix = (reynolds - 2300.0) / (10000.0 - 2300.0)
        nusselt = (1.0 - mix) * laminar_nu + mix * turbulent_nu
    h = nusselt * props["k"] / diameter
    friction_factor = 64.0 / reynolds if reynolds < 2300 else 0.3164 / reynolds**0.25
    pressure_drop = friction_factor * (length / diameter) * props["rho"] * velocity**2 / 2.0
    q_dot = mdot * props["cp"] * (outlet_temperature_c - inlet_temperature_c)
    return HeatTransferResult(
        tool="conveccao_interna_tubo_iterativa",
        title="Conveccao interna em tubo com iteracao",
        interpretation="A corrente interna troca calor com a parede do tubo e as propriedades sao atualizadas iterativamente.",
        data_used=(
            f"fluid={fluid}",
            f"D={diameter:.6g} m",
            f"L={length:.6g} m",
            f"V={velocity:.6g} m/s",
            f"T_in={inlet_temperature_c:.6g} C",
            f"T_w={wall_temperature_c:.6g} C",
            f"P={pressure_pa:.6g} Pa",
            f"rho={props['rho']:.6g} kg/m^3",
            f"mu={props['mu']:.6g} Pa.s",
            f"k={props['k']:.6g} W/(m.K)",
            f"cp={props['cp']:.6g} J/(kg.K)",
            f"Pr={prandtl:.6g} -",
            f"Re={reynolds:.6g} -",
            f"regime={regime}",
        ),
        formulas=(
            r"\dot m=\rho VA_c",
            r"Re=\frac{\rho VD}{\mu}",
            r"Nu=3.66 \ \mathrm{ou}\ 0.023Re^{0.8}Pr^{0.4}",
            r"h=\frac{Nuk}{D}",
            r"\dot q=\dot m c_p (T_{out}-T_{in})",
            r"\Delta p=f\frac{L}{D}\frac{\rho V^2}{2}",
        ),
        substitutions=(
            rf"\dot m={mdot:.6g}\ \mathrm{{kg/s}}",
            rf"Re=\frac{{{props['rho']:.6g}\cdot {velocity:.6g}\cdot {diameter:.6g}}}{{{props['mu']:.6g}}}={reynolds:.6g}",
            rf"Nu={nusselt:.6g}\quad(\mathrm{{{regime}}})",
            rf"h=\frac{{{nusselt:.6g}\cdot {props['k']:.6g}}}{{{diameter:.6g}}}={h:.6g}\ \mathrm{{W/(m^2.K)}}",
            rf"T_{{out}}={outlet_temperature_c:.6g}\ \mathrm{{^\circ C}}",
            rf"\dot q={q_dot:.6g}\ \mathrm{{W}}",
            rf"\Delta p={pressure_drop:.6g}\ \mathrm{{Pa}}",
        ),
        results=(
            HeatTransferQuantity("Vazao massica", "mdot", mdot, "kg/s", "Vazao massica obtida da velocidade e da area interna."),
            HeatTransferQuantity("Reynolds", "Re", reynolds, "-", "Classificacao do regime interno."),
            HeatTransferQuantity("Prandtl", "Pr", prandtl, "-", "Numero de Prandtl da corrente."),
            HeatTransferQuantity("Nusselt", "Nu", nusselt, "-", "Correlação de conveccao interna."),
            HeatTransferQuantity("Coeficiente convectivo", "h", h, "W/(m².K)", "Coeficiente medio interno."),
            HeatTransferQuantity("Temperatura de saida", "T_out", outlet_temperature_c, "°C", "Temperatura media de saida da corrente."),
            HeatTransferQuantity("Taxa de calor", "q_dot", q_dot, "W", "Taxa de calor trocada com a parede."),
            HeatTransferQuantity("Queda de pressão", "delta_p", pressure_drop, "Pa", "Estimativa de perda de carga por atrito."),
        ),
        validations=(
            f"Comprimentos de entrada: x_h = {entrance_h:.6g} m e x_t = {entrance_t:.6g} m.",
            f"Regime classificado como {regime}.",
            "Correlação simplificada para tubo liso com propriedades iteradas na temperatura media.",
        ),
        assumptions=("Tubo liso.", "Escoamento interno forçado.", "Parede a temperatura aproximadamente constante.", "Propriedades avaliadas iterativamente."),
    )


def calculate_plane_transient_bidirectional(
    conductivity: float,
    density: float,
    specific_heat: float,
    thickness: float,
    area: float,
    heat_transfer_coefficient: float,
    initial_temperature_c: float,
    fluid_temperature_c: float,
    time_s: float,
) -> HeatTransferResult:
    _ensure_positive(conductivity, "condutividade termica")
    _ensure_positive(density, "densidade")
    _ensure_positive(specific_heat, "calor especifico")
    _ensure_positive(thickness, "espessura")
    _ensure_positive(area, "area")
    _ensure_positive(heat_transfer_coefficient, "coeficiente convectivo")
    if time_s < 0:
        raise HeatTransferCalculationError("O tempo nao pode ser negativo.")
    characteristic_length = thickness / 2.0
    biot = heat_transfer_coefficient * characteristic_length / conductivity
    volume = area * thickness
    surface_area = 2.0 * area
    alpha = conductivity / (density * specific_heat)
    fo = alpha * time_s / (characteristic_length**2)
    if biot < 0.1:
        tau = density * volume * specific_heat / (heat_transfer_coefficient * surface_area)
        temperature_center = fluid_temperature_c + (initial_temperature_c - fluid_temperature_c) * exp(-time_s / tau)
        temperature_surface = temperature_center
        model = "capacitancia_concentrada"
    else:
        mu_1 = _first_plane_wall_root(biot)
        a_1 = 4.0 * sin(mu_1) / (2.0 * mu_1 + sin(2.0 * mu_1))
        center_ratio = a_1 * exp(-(mu_1**2) * fo)
        surface_ratio = center_ratio * cos(mu_1)
        temperature_center = fluid_temperature_c + (initial_temperature_c - fluid_temperature_c) * center_ratio
        temperature_surface = fluid_temperature_c + (initial_temperature_c - fluid_temperature_c) * surface_ratio
        model = "placa_plana_transiente"
    heat_removed = density * volume * specific_heat * (initial_temperature_c - temperature_center)
    return HeatTransferResult(
        tool="conducao_transiente_placa",
        title="Conducao transiente em placa plana",
        interpretation="A placa resfria ou aquece com simetria nas duas faces. O modelo muda conforme o numero de Biot.",
        data_used=(
            f"k={conductivity:.6g} W/(m.K)",
            f"rho={density:.6g} kg/m^3",
            f"cp={specific_heat:.6g} J/(kg.K)",
            f"L={thickness:.6g} m",
            f"A={area:.6g} m^2",
            f"h={heat_transfer_coefficient:.6g} W/(m^2.K)",
            f"T_i={initial_temperature_c:.6g} C",
            f"T_inf={fluid_temperature_c:.6g} C",
            f"t={time_s:.6g} s",
            f"model={model}",
        ),
        formulas=(
            r"L_c=\frac{L}{2}",
            r"Bi=\frac{hL_c}{k}",
            r"Fo=\frac{\alpha t}{L_c^2}",
            r"T_c(t)=T_\infty+(T_i-T_\infty)\theta_c",
            r"T_s(t)=T_\infty+(T_i-T_\infty)\theta_s",
        ),
        substitutions=(
            rf"L_c={characteristic_length:.6g}\ \mathrm{{m}}",
            rf"Bi=\frac{{{heat_transfer_coefficient:.6g}\cdot {characteristic_length:.6g}}}{{{conductivity:.6g}}}={biot:.6g}",
            rf"Fo=\frac{{{alpha:.6g}\cdot {time_s:.6g}}}{{{characteristic_length:.6g}^2}}={fo:.6g}",
            rf"T_c={temperature_center:.6g}\ \mathrm{{^\circ C}}",
            rf"T_s={temperature_surface:.6g}\ \mathrm{{^\circ C}}",
            rf"Q={heat_removed:.6g}\ \mathrm{{J}}",
        ),
        results=(
            HeatTransferQuantity("Comprimento caracteristico", "L_c", characteristic_length, "m", "Metade da espessura da placa."),
            HeatTransferQuantity("Numero de Biot", "Bi", biot, "-", "Criterio de validade do modelo lumped."),
            HeatTransferQuantity("Numero de Fourier", "Fo", fo, "-", "Tempo adimensional do transiente."),
            HeatTransferQuantity("Temperatura no centro", "T_center", temperature_center, "°C", "Temperatura na linha central da placa."),
            HeatTransferQuantity("Temperatura na superficie", "T_surface", temperature_surface, "°C", "Temperatura na superficie exposta."),
            HeatTransferQuantity("Energia removida", "Q", heat_removed, "J", "Energia sensivel removida da placa."),
        ),
        validations=(
            f"Bi = {biot:.6g}. {'Capacitancia global valida.' if biot < 0.1 else 'Usado modelo distribuido de placa plana.'}",
            "Modelo simetrico com conveccao nas duas faces.",
        ),
        assumptions=("Propriedades constantes.", "Sem geracao interna.", "Superficies equivalentes nas duas faces."),
    )


def calculate_solar_plate_balance(
    fluid: str,
    velocity: float,
    length: float,
    width: float,
    solar_heat_flux_w_m2: float,
    fluid_temperature_c: float,
    pressure_pa: float = 101325.0,
) -> HeatTransferResult:
    _ensure_positive(velocity, "velocidade")
    _ensure_positive(length, "comprimento")
    _ensure_positive(width, "largura")
    _ensure_positive(solar_heat_flux_w_m2, "fluxo solar")
    _ensure_positive(pressure_pa, "pressao")
    surface_temperature_c = fluid_temperature_c
    h = 0.0
    for _ in range(30):
        film_temperature_c = 0.5 * (surface_temperature_c + fluid_temperature_c)
        props = _fluid_properties(fluid, film_temperature_c, pressure_pa)
        reynolds = props["rho"] * velocity * length / props["mu"]
        prandtl = props["cp"] * props["mu"] / props["k"]
        if reynolds < 5.0e5:
            nusselt = 0.664 * reynolds**0.5 * prandtl ** (1.0 / 3.0)
        else:
            nusselt = (0.037 * reynolds**0.8 - 871.0) * prandtl ** (1.0 / 3.0)
        h = nusselt * props["k"] / length
        new_surface_temperature = fluid_temperature_c + solar_heat_flux_w_m2 / (2.0 * h)
        if abs(new_surface_temperature - surface_temperature_c) < 1e-6:
            surface_temperature_c = new_surface_temperature
            break
        surface_temperature_c = new_surface_temperature
    area = length * width
    convective_heat_rate = 2.0 * h * area * (surface_temperature_c - fluid_temperature_c)
    return HeatTransferResult(
        tool="asa_plana_radiacao_solar",
        title="Asa/placa plana com radiacao solar",
        interpretation="A radiacao solar aquece a placa e a conveccao remove calor nas duas faces expostas ao ar.",
        data_used=(
            f"fluid={fluid}",
            f"V={velocity:.6g} m/s",
            f"L={length:.6g} m",
            f"W={width:.6g} m",
            f"q_solar={solar_heat_flux_w_m2:.6g} W/m^2",
            f"T_inf={fluid_temperature_c:.6g} C",
            f"P={pressure_pa:.6g} Pa",
            f"h={h:.6g} W/(m^2.K)",
        ),
        formulas=(
            r"q''_{solar}=2h(T_s-T_\infty)",
            r"T_s=T_\infty+\frac{q''_{solar}}{2h}",
        ),
        substitutions=(
            rf"T_s={surface_temperature_c:.6g}\ \mathrm{{^\circ C}}",
            rf"\dot q_{{conv}}={convective_heat_rate:.6g}\ \mathrm{{W}}",
        ),
        results=(
            HeatTransferQuantity("Coeficiente convectivo", "h", h, "W/(m².K)", "Coeficiente de conveccao nas duas faces."),
            HeatTransferQuantity("Temperatura da superficie", "T_s", surface_temperature_c, "°C", "Temperatura em equilibrio com a radiacao solar."),
            HeatTransferQuantity("Taxa convectiva", "q_dot", convective_heat_rate, "W", "Calor removido por convecção nas duas faces."),
        ),
        validations=("A formulação assume escoamento paralelo à placa e irradiância uniforme.", "Convecção aplicada nas duas faces."),
        assumptions=("Propriedades avaliadas na temperatura de filme.", "Placa isoterma.", "Sem radiação térmica adicional além do fluxo solar informado."),
    )


def calculate_finned_surface_plate(
    heat_transfer_coefficient: float,
    perimeter: float,
    conductivity: float,
    cross_section_area: float,
    length: float,
    base_area: float,
    fin_count: float,
    base_temperature_c: float,
    fluid_temperature_c: float,
) -> HeatTransferResult:
    _ensure_positive(heat_transfer_coefficient, "coeficiente convectivo")
    _ensure_positive(perimeter, "perimetro")
    _ensure_positive(conductivity, "condutividade termica")
    _ensure_positive(cross_section_area, "area da secao transversal")
    _ensure_positive(length, "comprimento da aleta")
    _ensure_positive(base_area, "area da base")
    _ensure_positive(fin_count, "numero de aletas")
    fin_quantity = int(round(fin_count))
    if abs(fin_quantity - fin_count) > 1e-6:
        raise HeatTransferCalculationError("O numero de aletas deve ser inteiro.")
    if fin_quantity <= 0:
        raise HeatTransferCalculationError("O numero de aletas deve ser positivo.")

    single_fin = calculate_straight_fin_adiabatic_tip(
        heat_transfer_coefficient,
        perimeter,
        conductivity,
        cross_section_area,
        length,
        base_temperature_c,
        fluid_temperature_c,
    )
    theta_b = base_temperature_c - fluid_temperature_c
    fin_area = _quantity_value(single_fin, "A_f")
    fin_efficiency = _quantity_value(single_fin, "eta_f")
    fin_heat_rate = _quantity_value(single_fin, "q_dot_fin")
    base_exposed_area = base_area - fin_quantity * cross_section_area
    if base_exposed_area < 0:
        raise HeatTransferCalculationError("A area da base nao pode ser menor que a soma das areas de raiz das aletas.")
    total_exposed_area = base_exposed_area + fin_quantity * fin_area
    heat_with_fins = fin_quantity * fin_heat_rate + heat_transfer_coefficient * base_exposed_area * theta_b
    heat_without_fins = heat_transfer_coefficient * base_area * theta_b
    overall_efficiency = heat_with_fins / (heat_transfer_coefficient * total_exposed_area * theta_b) if abs(theta_b) > 1e-12 and total_exposed_area > 0 else 0.0
    overall_effectiveness = heat_with_fins / heat_without_fins if abs(heat_without_fins) > 1e-12 else 0.0
    gain_percentage = (overall_effectiveness - 1.0) * 100.0 if abs(heat_without_fins) > 1e-12 else 0.0
    return HeatTransferResult(
        tool="aleta_superficie_aletada",
        title="Superficie aletada em placa plana",
        interpretation="A superficie combina aletas retas e a base exposta para estimar o ganho total em transferencia de calor.",
        data_used=(
            f"h={heat_transfer_coefficient:.6g} W/(m^2.K)",
            f"P={perimeter:.6g} m",
            f"k={conductivity:.6g} W/(m.K)",
            f"A_c={cross_section_area:.6g} m^2",
            f"L={length:.6g} m",
            f"A_base={base_area:.6g} m^2",
            f"N={fin_quantity:.6g} -",
            f"T_b={base_temperature_c:.6g} C",
            f"T_inf={fluid_temperature_c:.6g} C",
        ),
        formulas=(
            r"m=\sqrt{\frac{hP}{kA_c}}",
            r"A_{b,exp}=A_{base}-NA_c",
            r"q_{total}=N\dot q_f+hA_{b,exp}(T_b-T_\infty)",
            r"q_{sem}=hA_{base}(T_b-T_\infty)",
            r"\eta_o=\frac{q_{total}}{hA_t(T_b-T_\infty)}",
            r"\epsilon_o=\frac{q_{total}}{q_{sem}}",
        ),
        substitutions=(
            rf"A_{{b,exp}}={base_area:.6g}-{fin_quantity:.6g}\cdot {cross_section_area:.6g}={base_exposed_area:.6g}\ \mathrm{{m^2}}",
            rf"N\dot q_f={fin_quantity:.6g}\cdot {fin_heat_rate:.6g}={fin_quantity * fin_heat_rate:.6g}\ \mathrm{{W}}",
            rf"q_{{total}}={fin_quantity * fin_heat_rate:.6g}+{heat_transfer_coefficient:.6g}\cdot {base_exposed_area:.6g}\cdot {theta_b:.6g}={heat_with_fins:.6g}\ \mathrm{{W}}",
            rf"q_{{sem}}={heat_transfer_coefficient:.6g}\cdot {base_area:.6g}\cdot {theta_b:.6g}={heat_without_fins:.6g}\ \mathrm{{W}}",
            rf"\eta_o=\frac{{{heat_with_fins:.6g}}}{{{heat_transfer_coefficient:.6g}\cdot {total_exposed_area:.6g}\cdot {theta_b:.6g}}}={overall_efficiency:.6g}",
            rf"\epsilon_o=\frac{{{heat_with_fins:.6g}}}{{{heat_without_fins:.6g}}}={overall_effectiveness:.6g}",
        ),
        results=(
            HeatTransferQuantity("Parametro da aleta", "m", _quantity_value(single_fin, "m"), "1/m", "Controla o decaimento de temperatura ao longo da aleta."),
            HeatTransferQuantity("Area lateral da aleta", "A_f", fin_area, "m^2", "Area exposta a conveccao por aleta."),
            HeatTransferQuantity("Eficiencia da aleta", "eta_f", fin_efficiency, "-", "Razao entre calor real e calor ideal da aleta."),
            HeatTransferQuantity("Area exposta da base", "A_base_exp", base_exposed_area, "m^2", "Area da base ainda exposta ao fluido."),
            HeatTransferQuantity("Calor de uma aleta", "q_dot_fin", fin_heat_rate, "W", "Calor dissipado por uma unica aleta."),
            HeatTransferQuantity("Calor total com aletas", "q_total", heat_with_fins, "W", "Calor total dissipado pela superficie aletada."),
            HeatTransferQuantity("Calor sem aletas", "q_sem_aletas", heat_without_fins, "W", "Calor dissipado pela base sem aletas."),
            HeatTransferQuantity("Eficiencia global da superficie", "eta_o", overall_efficiency, "-", "Eficiencia global da superficie aletada."),
            HeatTransferQuantity("Efetividade global da superficie", "epsilon_o", overall_effectiveness, "-", "Ganho relativo em relacao a base nua."),
            HeatTransferQuantity("Ganho percentual", "ganho_percentual", gain_percentage, "%", "Aumento percentual em relacao a base sem aletas."),
        ),
        validations=(
            f"N = {fin_quantity}.",
            f"A_base_exp = {base_exposed_area:.6g} m^2.",
            f"eta_o = {overall_efficiency:.6g}.",
            f"Ganho percentual = {gain_percentage:.6g} %.",
        ),
        assumptions=("Regime permanente.", "Aletas retas de secao constante.", "Ponta adiabatica.", "Propriedades constantes.", "A base exposta usa a area da raiz das aletas como ocupacao geometrica."),
    )


def calculate_concentric_tube_vapor_heat_exchange(
    fluid: str,
    inner_diameter: float,
    outer_diameter: float,
    length: float,
    velocity: float,
    inlet_temperature_c: float,
    steam_temperature_c: float,
    conductivity: float,
    pressure_pa: float = 101325.0,
) -> HeatTransferResult:
    _ensure_positive(inner_diameter, "diametro interno")
    _ensure_positive(outer_diameter, "diametro externo")
    _ensure_positive(length, "comprimento")
    _ensure_positive(velocity, "velocidade")
    _ensure_positive(conductivity, "condutividade termica")
    _ensure_positive(pressure_pa, "pressao")
    if outer_diameter <= inner_diameter:
        raise HeatTransferCalculationError("O diametro externo deve ser maior que o diametro interno.")
    if abs(steam_temperature_c - inlet_temperature_c) < 1e-9:
        return HeatTransferResult(
            tool="trocador_tubo_concentrico_vapor",
            title="Tubo concentric com vapor em temperatura quase constante",
            interpretation="Sem diferenca de temperatura util entre o vapor e o fluido interno nao ha troca de calor liquida.",
            data_used=(
                f"fluid={fluid}",
                f"D_i={inner_diameter:.6g} m",
                f"D_o={outer_diameter:.6g} m",
                f"L={length:.6g} m",
                f"V={velocity:.6g} m/s",
                f"T_in={inlet_temperature_c:.6g} C",
                f"T_steam={steam_temperature_c:.6g} C",
                f"k={conductivity:.6g} W/(m.K)",
                f"P={pressure_pa:.6g} Pa",
            ),
            formulas=(r"R_{cond}=\frac{\ln(r_o/r_i)}{2\pi kL}", r"\dot q=0"),
            substitutions=(r"\Delta T=0",),
            results=(HeatTransferQuantity("Taxa de calor", "q_dot", 0.0, "W", "Sem fluxo liquido de calor."),),
            validations=("Delta T nulo entre vapor e fluido interno.",),
            assumptions=("Sem diferenca de temperatura motriz.",),
        )
    inner_radius = inner_diameter / 2.0
    outer_radius = outer_diameter / 2.0
    conduction_resistance = log(outer_radius / inner_radius) / (2.0 * pi * conductivity * length)
    if conduction_resistance <= 0:
        raise HeatTransferCalculationError("Resistencia de conducao invalida.")

    lower_bound = min(inlet_temperature_c, steam_temperature_c)
    upper_bound = max(inlet_temperature_c, steam_temperature_c)

    def residual(wall_temperature_c: float) -> float:
        internal_result = calculate_internal_tube_convection(
            fluid,
            inner_diameter,
            length,
            velocity,
            inlet_temperature_c,
            wall_temperature_c,
            pressure_pa,
        )
        q_internal = _quantity_value(internal_result, "q_dot")
        q_conduction = (steam_temperature_c - wall_temperature_c) / conduction_resistance
        return q_conduction - q_internal

    wall_temperature_c = _solve_bracketed_root(residual, lower_bound, upper_bound)
    internal_result = calculate_internal_tube_convection(
        fluid,
        inner_diameter,
        length,
        velocity,
        inlet_temperature_c,
        wall_temperature_c,
        pressure_pa,
    )
    heat_rate = _quantity_value(internal_result, "q_dot")
    h_internal = _quantity_value(internal_result, "h")
    outlet_temperature_c = _quantity_value(internal_result, "T_out")
    heat_rate_check = (steam_temperature_c - wall_temperature_c) / conduction_resistance
    area_inner = pi * inner_diameter * length
    effective_resistance = (steam_temperature_c - inlet_temperature_c) / heat_rate if abs(heat_rate) > 1e-12 else float("inf")
    return HeatTransferResult(
        tool="trocador_tubo_concentrico_vapor",
        title="Tubo concentric com vapor em temperatura quase constante",
        interpretation="O vapor fornece energia a temperatura quase constante atraves da parede cilidrica e da conveccao interna do fluido.",
        data_used=(
            f"fluid={fluid}",
            f"D_i={inner_diameter:.6g} m",
            f"D_o={outer_diameter:.6g} m",
            f"L={length:.6g} m",
            f"V={velocity:.6g} m/s",
            f"T_in={inlet_temperature_c:.6g} C",
            f"T_steam={steam_temperature_c:.6g} C",
            f"k={conductivity:.6g} W/(m.K)",
            f"P={pressure_pa:.6g} Pa",
            f"R_cond={conduction_resistance:.6g} K/W",
        ),
        formulas=(
            r"R_{cond}=\frac{\ln(r_o/r_i)}{2\pi kL}",
            r"\dot q=\frac{T_{steam}-T_{w,i}}{R_{cond}}",
            r"\dot q=\dot q_{int}(T_{w,i})",
        ),
        substitutions=(
            rf"R_{{cond}}=\frac{{\ln({outer_radius:.6g}/{inner_radius:.6g})}}{{2\pi\cdot {conductivity:.6g}\cdot {length:.6g}}}={conduction_resistance:.6g}\ \mathrm{{K/W}}",
            rf"T_{{w,i}}={wall_temperature_c:.6g}\ \mathrm{{^\circ C}}",
            rf"\dot q_{{cond}}=\frac{{{steam_temperature_c:.6g}-{wall_temperature_c:.6g}}}{{{conduction_resistance:.6g}}}={heat_rate_check:.6g}\ \mathrm{{W}}",
            rf"\dot q_{{int}}={heat_rate:.6g}\ \mathrm{{W}}",
            rf"T_{{out}}={outlet_temperature_c:.6g}\ \mathrm{{^\circ C}}",
        ),
        results=(
            HeatTransferQuantity("Resistencia cilindrica", "R_cond", conduction_resistance, "K/W", "Resistencia termica da parede cilindrica."),
            HeatTransferQuantity("Temperatura da parede interna", "T_wi", wall_temperature_c, "C", "Temperatura da parede em contato com o fluido interno."),
            HeatTransferQuantity("Coeficiente interno", "h_i", h_internal, "W/(m^2.K)", "Coeficiente convectivo interno obtido iterativamente."),
            HeatTransferQuantity("Taxa de calor", "q_dot", heat_rate, "W", "Calor transferido pelo tubo."),
            HeatTransferQuantity("Temperatura de saida", "T_out", outlet_temperature_c, "C", "Temperatura de saida do fluido interno."),
            HeatTransferQuantity("Resistencia efetiva total", "R_th", effective_resistance, "K/W", "Resistencia termica efetiva entre vapor e entrada do fluido."),
            HeatTransferQuantity("Area interna", "A_i", area_inner, "m^2", "Area interna molhada."),
        ),
        validations=(
            f"Balanceamento de calor: {heat_rate_check:.6g} W pela conducao e {heat_rate:.6g} W pela conveccao interna.",
            f"T_wi entre a entrada do fluido e o vapor: {min(inlet_temperature_c, steam_temperature_c):.6g} C a {max(inlet_temperature_c, steam_temperature_c):.6g} C.",
        ),
        assumptions=("Vapor em temperatura aproximadamente constante.", "Parede cilindrica uniforme.", "Propriedades internas avaliadas iterativamente.", "Escoamento interno forcado."),
    )


def _quantity_value(result: HeatTransferResult, symbol: str) -> float:
    for quantity in result.results:
        if quantity.symbol == symbol:
            return quantity.value
    raise HeatTransferCalculationError(f"Resultado intermediario nao encontrado: {symbol}.")


def _solve_bracketed_root(function, lower: float, upper: float, iterations: int = 80) -> float:
    lower_value = function(lower)
    upper_value = function(upper)
    if lower_value == 0:
        return lower
    if upper_value == 0:
        return upper
    if lower_value * upper_value > 0:
        raise HeatTransferCalculationError("Nao foi possivel isolar uma raiz para o acoplamento termico.")
    left = lower
    right = upper
    for _ in range(iterations):
        middle = 0.5 * (left + right)
        middle_value = function(middle)
        if abs(middle_value) < 1e-9 or abs(right - left) < 1e-9:
            return middle
        if lower_value * middle_value <= 0:
            right = middle
            upper_value = middle_value
        else:
            left = middle
            lower_value = middle_value
    return 0.5 * (left + right)


def _fluid_properties(fluid: str, temperature_c: float, pressure_pa: float) -> dict[str, float]:
    from CoolProp.CoolProp import PropsSI

    fluid_name = fluid.strip() or "Air"
    temperature_k = temperature_c + 273.15
    rho = PropsSI("D", "T", temperature_k, "P", pressure_pa, fluid_name)
    mu = PropsSI("V", "T", temperature_k, "P", pressure_pa, fluid_name)
    k = PropsSI("L", "T", temperature_k, "P", pressure_pa, fluid_name)
    cp = PropsSI("C", "T", temperature_k, "P", pressure_pa, fluid_name)
    pr = PropsSI("PRANDTL", "T", temperature_k, "P", pressure_pa, fluid_name)
    return {"rho": rho, "mu": mu, "nu": mu / rho, "k": k, "cp": cp, "Pr": pr}


def _first_plane_wall_root(biot: float) -> float:
    left = 1e-9
    right = pi / 2.0 - 1e-9
    for _ in range(120):
        middle = 0.5 * (left + right)
        f_middle = middle * tan(middle) - biot
        if abs(f_middle) < 1e-10:
            return middle
        f_left = left * tan(left) - biot
        if f_left * f_middle <= 0:
            right = middle
        else:
            left = middle
    return 0.5 * (left + right)


def _ensure_positive(value: float, label: str) -> None:
    if value <= 0:
        raise HeatTransferCalculationError(f"{label.capitalize()} deve ser maior que zero.")

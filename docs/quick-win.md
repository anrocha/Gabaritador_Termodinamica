# Avaliação para Aplicação IA — Provas de Transferência de Calor

Base analisada: questões e formulário das provas enviadas. :contentReference[oaicite:0]{index=0}

## 1. Classificação das questões

| Prova | Questão | Classe principal | Subclasse | Modelo físico |
|---|---:|---|---|---|
| GB 26/11/2025 | 1 | Convecção com aletas | Aleta reta de seção constante | Regime permanente, base isotérmica |
| GB 26/11/2025 | 2 | Convecção externa forçada | Placa plana | Escoamento do ar sobre superfície plana |
| GB 26/11/2025 | 3 | Convecção interna + condução cilíndrica | Trocador tubo concêntrico | Água interna aquecida por vapor saturado |
| Prova 18/06/2025 | 1 | Condução transiente | Placa plana resfriada dos dois lados | Verificar Bi, usar capacitância global ou efeitos espaciais |
| Prova 18/06/2025 | 2 | Convecção interna forçada | Escoamento em tubo | Regime, entrada térmica/hidrodinâmica, perda de calor e pressão |
| Prova 18/06/2025 | 3 | Convecção externa + balanço de energia | Asa como placa plana | Radiação solar absorvida + perda convectiva |
| Formulário | Teóricas | Conceitos | Bi, Fo, Re, Nu, Pr, entrada, convecção interna/externa | Explicação e seleção de método |

---

## 2. Módulos que a aplicação deve ter

## 2.1 Aletas

### Entradas
- Material da aleta: alumínio
- `k`
- Geometria da aleta: seção quadrada, lado `b`
- Comprimento `L`
- Número de aletas `N`
- Área da base
- Temperatura da base `Tb`
- Temperatura ambiente `Tinf`
- Coeficiente convectivo `h`

### Cálculos
- Área da seção: `Ac`
- Perímetro: `P`
- Comprimento corrigido: `Lc = L + Ac/P`
- Parâmetro da aleta: `m = sqrt(hP/kAc)`
- Eficiência da aleta: `eta_f = tanh(mLc)/(mLc)`
- Área de uma aleta: `Af`
- Área total aletada
- Eficiência global da superfície
- Taxa total com aletas
- Taxa sem aletas
- Comparação percentual

### Diagramas necessários
- Vista superior da placa com matriz de aletas
- Corte lateral mostrando `L`, `Tb`, `Tinf`, `h`
- Esquema de áreas: área da base exposta e área das aletas

---

## 2.2 Convecção externa sobre placa plana

### Entradas
- Fluido: ar
- Velocidade `V`
- Comprimento da placa `L`
- Largura `W`
- Temperatura da superfície `Ts`
- Temperatura do fluido `Tinf`
- Pressão, quando fornecida

### CoolProp
Calcular propriedades do ar na temperatura de filme:

`Tf = (Ts + Tinf)/2`

Propriedades necessárias:
- `rho`
- `mu`
- `nu`
- `k`
- `cp`
- `Pr`

### Cálculos
- `ReL = V L / nu`
- Classificação: laminar, turbulento ou misto
- `NuL`
- `h = NuL k / L`
- `q = h A (Ts - Tinf)`

### Diagramas/gráficos
- Placa plana com direção do escoamento
- Camada limite térmica e hidrodinâmica
- Gráfico opcional: `h(x)` ou `Nu_x` ao longo de `x`
- Indicação do ponto de transição `Recrit = 5e5`

---

## 2.3 Convecção interna em tubo

### Entradas
- Fluido: água
- Diâmetro interno `D`
- Comprimento `L`
- Velocidade média `u`
- Temperatura de entrada `Tin`
- Temperatura de parede ou ambiente externo
- Material e espessura da parede, quando houver

### CoolProp
Usar propriedades da água na temperatura média estimada:

`Tm = (Tin + Tout)/2`

Como `Tout` geralmente é desconhecida, a aplicação deve iterar.

Propriedades:
- `rho`
- `mu`
- `k`
- `cp`
- `Pr`

### Cálculos
- Área de escoamento
- Vazão mássica `mdot = rho u Ac`
- Reynolds `Re = rho u D / mu`
- Regime: laminar, transição ou turbulento
- Comprimentos de entrada:
  - `xh = 0,05 Re D`
  - `xt = xh Pr`
- Seleção automática da correlação de Nusselt
- `h = Nu k / D`
- `q = mdot cp (Tin - Tout)` ou `q = UA ΔTm`
- Perda de pressão:
  - fator de atrito `f`
  - `Δp = f (L/D) rho u²/2`

### Diagramas
- Tubo com entrada, saída, parede e fluido
- Perfil térmico `Tm(x)`
- Perfil qualitativo de camada limite
- Circuito térmico se houver parede e convecção externa

---

## 2.4 Trocador tubo concêntrico com vapor

### Entradas
- Água:
  - `Tin`
  - velocidade
  - diâmetro interno
- Tubo:
  - `Di`
  - `Do`
  - `k_tubo`
  - `L`
- Vapor:
  - temperatura de condensação constante `Ts = 127 °C`
- Isolamento externo

### CoolProp
Para água:
- propriedades em `Tm`
- iterar com `Tout`

Para vapor:
- neste problema, usar `Ts` como temperatura de parede externa constante.
- CoolProp pode validar propriedades de saturação se for dada pressão ou temperatura de saturação.

### Resistências térmicas
Circuito:

`vapor condensando → parede externa do tubo → condução cilíndrica → convecção interna da água`

Como a condensação mantém a superfície interna/externa do lado do vapor em temperatura quase constante, pode-se desprezar ou modelar `Rcondensação` se `h_vapor` não for dado.

Resistências:
- `Rconv,i = 1/(hi Ai)`
- `Rcond = ln(Do/Di)/(2πkL)`
- opcional: `Rconv,o = 1/(ho Ao)`

`UA = 1 / ΣR`

### Cálculos
- `hi`
- `UA`
- `Tout` pela equação:
  - `(Ts - Tout)/(Ts - Tin) = exp(-UA/(mdot cp))`
- `q = mdot cp (Tout - Tin)`

### Diagramas
- Corte transversal do tubo concêntrico
- Circuito de resistências térmicas
- Gráfico `T_água(x)` aproximando-se de `Ts`

---

## 2.5 Condução transiente em placa

### Entradas
- Material: aço
- `rho`
- `cp`
- `k`
- Espessura total
- Temperatura inicial `Ti`
- Temperatura ambiente `Tinf`
- `h`
- Tempo `t`
- Condição: resfriamento pelos dois lados

### Cálculos
- Comprimento característico:
  - para placa: `Lc = V/A_s`
  - para placa plana com dois lados: `Lc = espessura/2`
- `Bi = h Lc/k`
- Se `Bi < 0,1`: capacitância global
- Se `Bi > 0,1`: método espacial / solução de placa plana
- `Fo = αt/Lc²`
- Temperatura da superfície
- Temperatura no centro
- Verificar se temperatura mínima é menor que valor solicitado

### CoolProp
Não usar CoolProp para sólido, exceto se a aplicação tiver banco próprio de materiais.
Para aço, alumínio e cobre, usar banco interno de propriedades.

### Gráficos
- Temperatura versus tempo
- Perfil `T(x)` na placa
- Comparação capacitância global versus solução espacial

---

## 2.6 Asa de avião como placa plana

### Entradas
- Fluido: ar
- Velocidade `V`
- Pressão `P`
- Temperatura ambiente `Tinf`
- Comprimento `L`
- Radiação absorvida `q''solar`
- Condutividade, viscosidade cinemática e Pr, se dados

### CoolProp
Se propriedades não forem fornecidas:
- calcular ar em `Tfilm`
- usar pressão informada

### Cálculos
- `ReL`
- regime de escoamento
- `NuL`
- `h`
- balanço de energia na asa:

`q''solar = 2 h (Ts - Tinf)`

porque há convecção nas duas faces.

Logo:

`Ts = Tinf + q''solar/(2h)`

### Diagramas
- Placa com escoamento externo
- Radiação solar entrando
- Convecção saindo nas duas faces
- Gráfico de balanço energético

---

## 3. Integração com CoolProp

## 3.1 Fluidos necessários
- `Air`
- `Water`
- opcional: `Water` saturado para vapor

## 3.2 Chamadas típicas

### Ar
```python
PropsSI("D", "T", T, "P", P, "Air")
PropsSI("V", "T", T, "P", P, "Air")  # viscosidade dinâmica
PropsSI("L", "T", T, "P", P, "Air")  # condutividade térmica
PropsSI("C", "T", T, "P", P, "Air")  # cp
PropsSI("PRANDTL", "T", T, "P", P, "Air")
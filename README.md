# Gabaritador de Termodinamica

MVP em Streamlit para consultar propriedades termodinamicas com CoolProp e calcular titulo de misturas saturadas.

## Funcionalidades

- Seleciona o fluido a partir da lista do CoolProp.
- Permite escolher o estado de referencia usado nas tabelas, com `Unisinos` como padrao.
- Calcula propriedades a partir de temperatura em `C`, `K` ou `F` e pressao em `Pa`, `kPa`, `MPa` ou `bar`.
- Calcula estado a partir de duas propriedades conhecidas, como `P + s`, `P + h`, `T + s`, `T + h`, `T + v` e `P + rho`.
- Mantem fluido, referencia e unidades selecionadas ao trocar entre as telas.
- Mostra temperatura e pressao calculadas na unidade selecionada e oferece uma caixa de equivalencias.
- Identifica fase e mostra titulo quando o par `T/P` estiver na regiao bifasica.
- Calcula titulo `x` por interpolacao saturada usando pressao ou temperatura e uma propriedade conhecida:
  - entalpia especifica `h`
  - energia interna especifica `u`
  - volume especifico `v`
  - entropia especifica `s`
- Mostra a formula do titulo e a substituicao numerica usada no calculo.

## Como rodar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Observacoes de modelagem

- CoolProp usa SI internamente; a interface converte temperatura, pressao, `kJ/kg` e `kJ/(kg.K)`.
- No modo de estado por par, as entradas aceitas sao `T`, `P`, `h`, `u`, `s`, `rho` e `v`; o volume especifico `v` e convertido internamente para massa especifica.
- O titulo so e fisicamente valido quando `0 <= x <= 1`.
- Quando `x < 0` ou `x > 1`, o app mostra diagnostico de valor fora da faixa saturada.
- Para mistura saturada, o app usa `x = (y - y_f) / (y_g - y_f)` e `y = y_f + x(y_g - y_f)`.
- O modo `Unisinos` aplica:
  - agua/vapor: referencia padrao de vapor do CoolProp.
  - refrigerantes cadastrados, como `R134a`: `ASHRAE`, com `h = 0` e `s = 0` a `-40 C`.
  - gases ideais: CoolProp continua usando modelo de fluido real; para bater exatamente com tabelas de gas ideal do Cengel, sera necessario um modulo especifico de gases ideais.

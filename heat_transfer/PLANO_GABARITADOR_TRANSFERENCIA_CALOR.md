# Plano do Gabaritador de Transferência de Calor

## Visão Geral

Construir um Gabaritador de Transferência de Calor com a mesma filosofia do Gabaritador de Termodinâmica:

- A OpenAI interpreta enunciados, imagens, diagramas, legendas e texto complementar.
- Ferramentas determinísticas executam os cálculos.
- A interface mostra a resolução item por item, com fórmulas, substituição numérica, unidades, origem dos dados e validações físicas.
- Logs compactos registram entrada, plano e saída para auditoria.

Não foi encontrada uma skill pronta confiável de `heat transfer` no catálogo local nem em busca pública. As referências úteis para skills são:

- `https://github.com/openai/skills`
- `https://agentskills.io/specification`

Por isso, a abordagem recomendada é criar uma skill local do projeto: `.agents/skills/especialista-transferencia-calor/SKILL.md`.

## Decisão de Integração no App

O Gabaritador de Transferência de Calor deve ficar isolado em uma aba própria chamada `Gabaritador Transferência de Calor`.

A aba atual do assistente de exercícios deve ser renomeada para `Gabaritador Termodinâmica`.

Essa separação é intencional: o usuário escolhe a matéria antes de enviar o enunciado, reduzindo complexidade, evitando roteamento autônomo entre disciplinas diferentes e mantendo prompts, ferramentas, normalizadores, executores, renderizadores e logs separados por domínio.

No MVP, não haverá uma aba única tentando decidir automaticamente entre Termodinâmica e Transferência de Calor.

## Objetivos

- Resolver exercícios típicos de Transferência de Calor de forma incremental.
- Evitar resolver caso por caso com heurísticas frágeis.
- Separar interpretação, normalização, cálculo, renderização e logs.
- Isolar a disciplina em uma aba própria para evitar roteamento autônomo entre Termodinâmica e Transferência de Calor.
- Preservar a arquitetura atual do app.
- Tratar imagem e texto como uma única entrada consolidada.
- Não inventar propriedades de materiais ausentes.

## Arquitetura Proposta

Adicionar módulos novos sem alterar destrutivamente os módulos de Termodinâmica:

- `heat_transfer_core.py`: equações determinísticas, modelos físicos e funções puras.
- `heat_transfer_facts.py`: fatos canônicos, aliases, unidades e normalização.
- `heat_transfer_catalog.py`: catálogo de ferramentas e contratos.
- `heat_transfer_executor.py`: roteamento, validação de pré-condições e execução.
- `heat_transfer_rendering.py`: renderização didática, tabelas, gráficos e respostas por item.

Reaproveitar módulos existentes:

- `openai_assistant.py`: interpretação multimodal e plano estruturado.
- `exercise_logger.py`: logs compactos de input, plano, output e erro.
- `exercise_rendering.py`: padrão de respostas por questão e blocos didáticos.
- `app.py`: renomear a aba atual para `Gabaritador Termodinâmica` e criar uma nova aba isolada `Gabaritador Transferência de Calor`.

Decisão de produto: o usuário escolhe explicitamente a disciplina pela aba. A OpenAI não deve decidir autonomamente entre Termodinâmica e Transferência de Calor.

## Fluxo de Execução

1. Usuário envia texto, imagem ou ambos.
2. OpenAI extrai:
   - fenômeno físico;
   - geometria;
   - condições de contorno;
   - propriedades conhecidas;
   - objetivos do enunciado;
   - dados lidos da imagem e do texto.
3. `heat_transfer_facts.py` normaliza nomes e unidades.
4. `heat_transfer_executor.py` escolhe ferramenta principal e ferramentas auxiliares.
5. `heat_transfer_core.py` calcula grandezas determinísticas.
6. `heat_transfer_rendering.py` exibe item por item.
7. `exercise_logger.py` salva auditoria.

## Catálogo de Ferramentas Determinísticas

### Fase 1 — Fundamentos

#### Condução Plana 1D Estacionária

Entradas:

- `k`
- `A`
- `L`
- `T_1`
- `T_2`

Saídas:

- `q_dot`
- `q_flux`
- `R_cond`

Equações:

```latex
\dot q = \frac{kA(T_1-T_2)}{L}
```

```latex
R_{cond}=\frac{L}{kA}
```

#### Condução Radial em Cilindro

Entradas:

- `k`
- `L`
- `r_i`
- `r_o`
- `T_i`
- `T_o`

Saídas:

- `q_dot`
- `R_cil`

Equação:

```latex
R_{cil}=\frac{\ln(r_o/r_i)}{2\pi kL}
```

#### Condução Radial em Esfera

Entradas:

- `k`
- `r_i`
- `r_o`
- `T_i`
- `T_o`

Saídas:

- `q_dot`
- `R_esf`

Equação:

```latex
R_{esf}=\frac{1}{4\pi k}\left(\frac{1}{r_i}-\frac{1}{r_o}\right)
```

#### Rede de Resistências Térmicas

Entradas:

- resistências em série/paralelo;
- temperaturas de extremidade;
- convecção interna/externa quando aplicável.

Saídas:

- `R_total`
- `q_dot`
- temperaturas intermediárias.

Equações:

```latex
\dot q=\frac{\Delta T}{R_{total}}
```

```latex
R_{conv}=\frac{1}{hA}
```

#### Convecção

Entradas:

- `h`
- `A`
- `T_s`
- `T_inf`

Saídas:

- `q_dot`

Equação:

```latex
\dot q=hA(T_s-T_\infty)
```

#### Radiação Superfície-Vizinhança

Entradas:

- `epsilon`
- `A`
- `T_s`
- `T_sur`

Saídas:

- `q_dot_rad`

Equação:

```latex
\dot q_{rad}=\varepsilon\sigma A(T_s^4-T_{sur}^4)
```

#### Balanço de Energia

Entradas:

- `q_dot_in`
- `q_dot_out`
- `W_dot`
- energia acumulada quando transiente.

Saídas:

- grandeza faltante do balanço.

Equação base:

```latex
\dot E_{in}-\dot E_{out}+\dot E_{ger}=\frac{dE_{sist}}{dt}
```

### Fase 2 — Modelos Intermediários

#### Aletas

Casos iniciais:

- aleta reta de seção constante;
- ponta adiabática;
- ponta convectiva como evolução futura.

Grandezas:

- `m`
- `eta_f`
- `epsilon_f`
- `q_dot_f`

Equações típicas:

```latex
m=\sqrt{\frac{hP}{kA_c}}
```

```latex
\eta_f=\frac{\tanh(mL_c)}{mL_c}
```

#### Transiente por Capacitância Concentrada

Pré-condição:

```latex
Bi=\frac{hL_c}{k}<0,1
```

Equação:

```latex
\frac{T(t)-T_\infty}{T_i-T_\infty}=\exp\left(-\frac{hA}{\rho V c_p}t\right)
```

Se `Bi >= 0,1`, bloquear com explicação física e sugerir método transiente distribuído.

#### Trocadores de Calor por LMTD

Entradas:

- tipo de escoamento;
- temperaturas de entrada/saída conhecidas;
- `U`;
- `A`;
- vazões e `c_p` quando aplicável.

Equações:

```latex
\dot q=UA\Delta T_{lm}
```

```latex
\Delta T_{lm}=\frac{\Delta T_1-\Delta T_2}{\ln(\Delta T_1/\Delta T_2)}
```

#### Trocadores por Efetividade-NTU

Entradas:

- `C_min`
- `C_max`
- `UA`
- tipo de trocador.

Saídas:

- `epsilon`
- `q_dot`
- temperaturas de saída.

Equações:

```latex
NTU=\frac{UA}{C_{min}}
```

```latex
\dot q=\varepsilon C_{min}(T_{h,in}-T_{c,in})
```

### Fase 3 — Correlações e Propriedades

Adicionar:

- cálculo de `Re`, `Pr`, `Nu`, `Gr`, `Ra`;
- convecção interna forçada;
- convecção externa em placa/cilindro/esfera;
- convecção natural;
- tabela local de propriedades de ar, água e materiais comuns;
- interpolação simples de propriedades quando houver tabela versionada.

Regra: propriedades de materiais não devem ser inventadas. Se não houver dado no enunciado, na imagem ou em tabela local declarada, o app deve pedir o dado.

## Modelo Canônico de Fatos

### Temperaturas

- `T_1`
- `T_2`
- `T_s`
- `T_inf`
- `T_sur`
- `T_in`
- `T_out`
- `T_h_in`
- `T_h_out`
- `T_c_in`
- `T_c_out`

### Geometria

- `L`
- `A`
- `V`
- `r_i`
- `r_o`
- `D`
- `P`
- `A_c`
- `L_c`
- `thickness`

### Materiais

- `k`
- `rho`
- `c_p`
- `alpha`
- `epsilon`

### Convecção e Escoamento

- `h`
- `U`
- `Nu`
- `Re`
- `Pr`
- `Ra`
- `Gr`
- `V_flow`
- `m_dot`

### Calor e Resistência

- `q_dot`
- `q_flux`
- `R_th`
- `R_cond`
- `R_conv`
- `R_rad`
- `R_total`

### Tempo e Transiente

- `t`
- `tau`
- `Bi`
- `Fo`

## Normalização e Aliases

O normalizador deve reconhecer variações:

- `temperatura ambiente`, `T ambiente`, `T∞` → `T_inf`
- `temperatura da superfície`, `Ts`, `T parede` → `T_s`
- `condutividade`, `k do material` → `k`
- `coeficiente convectivo`, `h convectivo` → `h`
- `espessura`, `parede de`, `L` → `L`
- `área`, `superfície`, `A_s` → `A`
- `emissividade`, `ε` → `epsilon`
- `fluxo de calor` com unidade `W/m²` → `q_flux`
- `taxa de calor` com unidade `W` → `q_dot`

Unidades incompatíveis devem ser rejeitadas defensivamente. Exemplo: `k` não pode aceitar `m`, `h` não pode aceitar `W`, e temperatura não pode aceitar `MPa`.

## Planner OpenAI

O prompt da OpenAI deve instruir:

- Ler texto, imagem, diagramas, legendas, setas e dimensões.
- Separar dados visíveis na imagem, dados digitados pelo usuário e entrada oficial consolidada.
- Classificar o fenômeno antes de escolher ferramenta.
- Não marcar como faltante uma grandeza que é saída do problema.
- Não inventar propriedades de material.
- Sinalizar conflito entre imagem e texto; texto explícito do usuário tem prioridade.

Campos esperados no plano:

- `categoria`
- `fenomenos`
- `ferramentas_necessarias`
- `dados_conhecidos`
- `dados_faltantes`
- `fatos_canonicos`
- `geometria`
- `condicoes_contorno`
- `questoes`
- `diagramas`
- `validacoes`

## Renderização Didática

Cada item do enunciado deve aparecer como:

1. Interpretação física.
2. Dados usados.
3. Modelo físico.
4. Fórmula em LaTeX.
5. Substituição numérica.
6. Resultado com unidade.
7. Validação física.
8. Origem dos dados e propriedades.

Tabelas devem conter valores compactos. Fórmulas não devem ficar presas dentro de `st.dataframe`.

## UI Streamlit

Criar uma aba dedicada `Gabaritador Transferência de Calor`, separada da aba `Gabaritador Termodinâmica`.

A aba nova deve reaproveitar a experiência do Gabaritador atual:

- upload de imagem/PDF;
- campo de texto complementar;
- botão `Interpretar e planejar`;
- confirmação/edição de dados extraídos;
- botão `Resolver com ferramentas internas`;
- botão `Limpar exercício`;
- logs com caminhos visíveis.

Responsabilidades isoladas:

- `Gabaritador Termodinâmica`: usa prompts, fatos, ferramentas e renderizadores termodinâmicos existentes.
- `Gabaritador Transferência de Calor`: usa prompt, fatos, ferramentas e renderizadores próprios de transferência de calor.
- Componentes compartilhados podem existir para upload, limpeza, logs e cards, mas os executores e catálogos ficam separados.

Layout sugerido:

- coluna principal: resolução item por item;
- painel lateral/responsivo: símbolos e unidades;
- gráficos limitados em largura e altura;
- cards de validação física.

## Diagramas

Diagramas iniciais:

- perfil de temperatura em parede plana;
- rede de resistências térmicas;
- cilindro/esfera com raios anotados;
- curva transiente `T(t)`;
- esquema de trocador com correntes quente/fria.

Os gráficos devem usar unidades coerentes com a tabela final e anotar pontos relevantes.

## Logs

Reaproveitar o padrão atual:

- `input.md`: interpretação consolidada da imagem + texto.
- `plan.md`: fatos canônicos, ferramenta planejada, dados faltantes e questões.
- `output.md`: ferramenta executada, passos, resultados por item e validações.
- `error.md`: erro amigável, causa provável e dados faltantes reais.

## Roadmap Incremental

### Marco 1 — Documento e Skill

- Criar este documento.
- Criar `.agents/skills/especialista-transferencia-calor/SKILL.md`.

### Marco 2 — Núcleo Fase 1

- Implementar condução plana, cilíndrica e esférica.
- Implementar convecção simples.
- Implementar radiação superfície-vizinhança.
- Implementar redes de resistências.

### Marco 3 — Aba Dedicada no App

- Renomear a aba atual para `Gabaritador Termodinâmica`.
- Criar a aba `Gabaritador Transferência de Calor`.
- Criar planner/prompt específico para transferência de calor.
- Adicionar catálogo e executor.
- Renderizar item por item.
- Logar input, plano e output.

### Marco 4 — Modelos Intermediários

- Aletas.
- Capacitância concentrada.
- LMTD.
- Efetividade-NTU.

### Marco 5 — Correlações

- `Re`, `Pr`, `Nu`, `Ra`, `Gr`.
- Convecção interna/externa.
- Tabela local de propriedades.

## Testes e Critérios de Aceite

### Casos Numéricos

- Condução plana: `q_dot = kA(T1-T2)/L`.
- Parede composta: soma de resistências e temperaturas intermediárias.
- Cilindro: `R = ln(r_o/r_i)/(2πkL)`.
- Esfera: resistência radial correta.
- Convecção: `q_dot = hA(T_s-T_inf)`.
- Radiação: `q_dot = εσA(T_s^4-T_sur^4)`.
- Capacitância concentrada: resolver se `Bi < 0,1`; bloquear se `Bi >= 0,1`.
- LMTD: validar sinais e diferenças de temperatura.

### Casos de Interpretação

- Imagem com parede composta e dimensões.
- Enunciado com texto complementar corrigindo dado da imagem.
- Exercício pedindo grandeza que é saída, sem tratá-la como faltante.
- Exercício incompleto pedindo propriedade de material não informada.

### Validação Técnica

- Rodar `python -m py_compile` nos módulos novos.
- Verificar que toda questão planejada aparece na UI e no log.
- Confirmar que unidades globais afetam apenas a exibição.
- Confirmar que logs não misturam exercícios.

## Assumptions

- O primeiro entregável é somente documentação e skill local.
- Implementação em Python/Streamlit será incremental.
- O app atual de Termodinâmica será preservado e apenas terá a aba renomeada para `Gabaritador Termodinâmica`.
- A complexidade entre disciplinas será isolada por abas; não haverá roteamento automático entre matérias no MVP.
- A OpenAI não calcula valores de transferência de calor.
- Propriedades ausentes de materiais só poderão vir de enunciado, imagem, usuário ou tabela local versionada futura.

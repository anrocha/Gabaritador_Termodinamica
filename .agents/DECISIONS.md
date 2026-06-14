# Decisões Arquiteturais

## IA e Cálculo

- A OpenAI é usada para interpretar enunciados, imagens, diagramas e texto complementar.
- Os cálculos numéricos são feitos por CoolProp ou rotinas determinísticas locais.
- Propriedades calculáveis não entram em `dados_faltantes`; entram em propriedades ou fatos a calcular.

## Ferramentas

- Ferramentas principais resolvem famílias de exercícios: refrigeração, turbina, evaporador, reservatórios.
- Ferramentas auxiliares devem calcular estados, processos isoentrópicos/isoentálpicos e balanços.
- O executor deve validar a ferramenta escolhida pela IA e corrigir roteamentos fisicamente inválidos.

## Unidades

- Solvers operam com unidades internas explícitas e consistentes.
- Configurações globais de temperatura/pressão mudam só a apresentação.
- Entalpia, entropia, volume específico, potência e vazão devem manter padrão SI na tela do Gabaritador, salvo decisão futura.

## Logs

- `input.md` registra interpretação consolidada da imagem + texto.
- `plan.md` registra fatos, ferramenta planejada, estados e questões.
- `output.md` registra ferramenta executada, passos, resultados e bloqueios.
- Logs não substituem o plano atual da sessão.

# Plano de desenvolvimento mantido

Este documento é a referência de planejamento versionada. Os arquivos em
`misc/` são apontamentos locais e históricos; não devem ser tratados como
estado atual nem como fonte para material de pesquisa.

## Estado confirmado em 18 de setembro de 2026

- A fase de estabilização e a arquitetura de aleatoriedade Path B já estão no
  código: samplers usam `numpy.random.Generator(PCG64)` e `simulate(seed=...)`
  cria fluxos independentes por sampler.
- As simulações de dispositivo e de frota validam tempos sorteados positivos e
  finitos. A missão também exige duração positiva e finita, e `reps` exige um
  inteiro positivo, sem truncar frações.
- A fronteira temporal é `[0, T)`: falhas e conclusões de reparo agendadas
  exatamente em `T` são censuradas. Dispositivo e frota seguem a mesma regra,
  coberta por teste determinístico.
- O workflow preparado de integração contínua executará a suíte `pytest` em Python 3.9 e 3.13.

## Próximos incrementos técnicos

1. Consolidar a arquitetura de simulação e os resultados sem alterar o
   contrato de RNG nem a paridade `SimpleDevice`/`Fleet(n_devices=1, n_teams=1)`.
2. Construir a escada de validação analítica e intervalos de confiança de Monte
   Carlo antes de novos recursos de modelagem.
3. Adicionar empacotamento, verificações estáticas e documentação de API após a
   validação estatística básica.

Estas prioridades preservam a estratégia atual do projeto e não alteram
licença, escopo de pesquisa ou planos de publicação.

## Contratos que as próximas etapas devem preservar

- Disponibilidade: fração de tempo operacional no horizonte; na frota, uptime
  total dividido por N×T em cada replicação. Replicação, não dispositivo, é a
  unidade para futuros intervalos amostrais da frota.
- MTTF: tempo operacional acumulado / falhas. MTTR: tempo de reparo ativo /
  reparos concluídos; não inclui espera em fila. Os estimadores têm ressalvas
  de janela finita e retornam NaN quando o denominador é zero.
- `mean_wait_time` resume esperas de reparos que começaram; não inclui toda
  espera censurada na fila ao fim da missão. Não rotular como média irrestrita.
- RNG: SeedSequence distribui streams PCG64 por sampler; mesma seed inteira e
  mesmo ambiente reproduzem a execução. `np.random.seed` não controla esses
  streams. Reutilizar uma SeedSequence já consumida não equivale a recriá-la.
- Motores executam replicações em sequência; não há promessa de thread-safety
  para compartilhar uma instância/sampler mutável entre execuções concorrentes.
  Futura paralelização deverá preservar streams e testar independência.
- Intervalos de disponibilidade, falhas totais e utilização usam uma observação por replicação e a
  aproximação normal `média ± z·s/√R`; dispositivos da mesma frota não são
  observações independentes porque podem disputar equipes. Eles medem erro de
  Monte Carlo, não corrigem censura na janela finita nem erro de modelo. Com
  menos de duas replicações, os limites são `NaN`. Falhas são o total de toda
  a frota por replicação; utilização é `busy_team_hours/(K*T)` por
  replicação. A censura `[0,T)` também vale a esses dois resultados.
- Workflow de CI está preparado, sem publicação automática; até este registro,
  somente Python 3.9.6 foi executado localmente. Python 3.13/GitHub aguardam CI.

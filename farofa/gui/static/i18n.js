// One dictionary for the whole interface: each key holds [pt-BR, English].
// The language defaults to the browser's and can be switched in the top bar.
import { store } from "./core.js";

const D = {
  // shell
  "skip": ["Pular para o conteúdo", "Skip to content"],
  "brand.sub": ["simulação de sistemas reparáveis", "repairable systems simulation"],
  "views.aria": ["Áreas", "Views"],
  "views.sim": ["Simulação", "Simulation"],
  "views.est": ["Estimação", "Estimation"],
  "tabs.aria": ["Resultados", "Results"],
  "tabs.dash": ["Painel", "Dashboard"],
  "tabs.timeline": ["Linha do tempo", "Timeline"],
  "tabs.compare": ["Comparar cenários", "Compare scenarios"],
  "tabs.code": ["Python", "Python"],
  "cancel": ["Cancelar", "Cancel"],
  "yes": ["sim", "yes"],
  "no": ["não", "no"],
  "of": ["de", "of"],
  "sep": [";", ","],
  "sd": ["dp", "sd"],
  "ci95": ["IC 95%", "95% CI"],
  "ci.na": ["IC indisponível (menos de 2 replicações)", "CI unavailable (fewer than 2 replications)"],
  "export.svg": ["Baixar o gráfico em SVG (vetorial)", "Download the chart as SVG (vector)"],
  "export.png": ["Baixar o gráfico em PNG", "Download the chart as PNG"],

  // model panel
  "model.title": ["Modelo", "Model"],
  "model.save": ["Salvar", "Save"],
  "model.save.title": ["Salvar o cenário em um arquivo JSON", "Save the scenario as a JSON file"],
  "model.open": ["Abrir", "Open"],
  "model.open.title": ["Abrir um cenário salvo (JSON)", "Open a saved scenario (JSON)"],
  "model.loaded": ["Cenário carregado de {name}.", "Scenario loaded from {name}."],
  "model.load.bad": ["o arquivo não é um cenário do farofa", "the file is not a farofa scenario"],
  "model.load.fail": ["Não foi possível abrir o cenário: {msg}", "Could not open the scenario: {msg}"],
  "model.preset": ["Exemplo pronto", "Example"],
  "model.system": ["Sistema", "System"],
  "model.device": ["Um equipamento", "Single device"],
  "model.fleet": ["Frota com equipes", "Fleet with teams"],
  "model.n": ["Equipamentos N", "Devices N"],
  "model.k": ["Equipes de reparo K", "Repair teams K"],
  "model.failures": ["Tempo até a falha", "Time to failure"],
  "model.repairs": ["Tempo de reparo", "Repair time"],
  "model.dist": ["Distribuição", "Distribution"],
  "model.run": ["Execução", "Run"],
  "model.T": ["Tempo de missão T (h)", "Mission time T (h)"],
  "model.reps": ["Replicações", "Replications"],
  "model.seed": ["Semente", "Seed"],
  "model.seed.new": ["Sortear outra semente", "Draw another seed"],
  "model.trace": ["Replicações registradas", "Traced replications"],
  "model.trace.title": ["Quantas replicações guardam o registro de eventos para a linha do tempo", "How many replications keep their event log for the timeline"],
  "model.runBtn": ["Simular", "Simulate"],
  "model.running": ["simulando…", "simulating…"],
  "model.done": ["concluído em {s} s", "done in {s} s"],
  "model.cancelled": ["cancelado", "cancelled"],
  "model.invalid": ["Corrija os campos destacados.", "Fix the highlighted fields."],
  "model.mean": ["Média ≈ {v}.", "Mean ≈ {v}."],
  "model.mean.first": ["Média até a 1ª falha ≈ {v}.", "Mean time to the first failure ≈ {v}."],

  "preset.custom": ["— personalizado —", "— custom —"],
  "preset.single": ["Um equipamento, tempos exponenciais", "One device, exponential times"],
  "preset.fleet": ["Frota com fila (tempos exponenciais)", "Fleet with a queue (exponential times)"],
  "preset.grp": ["Desgaste com reparo imperfeito (GRP)", "Wear-out with imperfect repair (GRP)"],
  "preset.sizing": ["Quantas equipes? (20 equipamentos)", "How many teams? (20 devices)"],
  "preset.single.note": ["λ = 0,01 por h (MTTF 100 h) e μ = 0,1 por h (MTTR 10 h) em 1.000 h. A disponibilidade de longo prazo é μ/(λ + μ) = 0,9091; numa missão finita, começando novo, o equipamento se sai um pouco melhor. O painel confere ambos com a fórmula exata.",
    "λ = 0.01 per h (MTTF 100 h) and μ = 0.1 per h (MTTR 10 h) over 1,000 h. The long-run availability is μ/(λ + μ) = 0.9091; over a finite mission, starting new, the device does slightly better. The dashboard checks both against the exact formula."],
  "preset.fleet.note": ["Dez máquinas (MTTF 100 h cada) e duas equipes (MTTR 10 h): em média cerca de uma máquina está parada, mas as falhas se acumulam e forma-se fila. Com tempos exponenciais é o problema do reparo de máquinas, conferido com o resultado exato no painel.",
    "Ten machines (MTTF 100 h each) and two teams (MTTR 10 h): about one machine is down on average, but failures bunch up and a queue forms. With exponential times this is the machine-repair problem, checked against the exact result on the dashboard."],
  "preset.grp.note": ["Desgaste (Weibull b = 2,5, a = 400 h) com reparo imperfeito: cada reparo deixa 30% da idade do último intervalo (Kijima I, q = 0,3), a idade virtual cresce e as falhas ficam mais frequentes no fim da missão. Reparos gama com média de 12 h.",
    "Wear-out (Weibull b = 2.5, a = 400 h) with imperfect repair: each repair leaves 30% of the last interval's age (Kijima I, q = 0.3), so the virtual age grows and failures come faster late in the mission. Gamma repairs with a 12 h mean."],
  "preset.sizing.note": ["Vinte equipamentos (Weibull, vida média de 271 h) com reparos lognormais (média de 16 h). Uma equipe custa 40 por hora e um equipamento parado custa 120 por hora: em Comparar cenários, varie K para achar o número de equipes de menor custo.",
    "Twenty devices (Weibull, mean life 271 h) with lognormal repairs (mean 16 h). A team costs 40 per hour and a device down costs 120 per hour: in Compare scenarios, vary K to find the cheapest number of teams."],

  "dist.exponential": ["Exponencial", "Exponential"],
  "dist.weibull": ["Weibull (reparo perfeito)", "Weibull (perfect repair)"],
  "dist.weibull_min": ["Weibull, reparo mínimo", "Weibull, minimal repair"],
  "dist.weibull_grp": ["Weibull GRP, Kijima I", "Weibull GRP, Kijima I"],
  "dist.weibull_grp2": ["Weibull GRP, Kijima II", "Weibull GRP, Kijima II"],
  "dist.lognormal": ["Lognormal", "Lognormal"],
  "dist.normal": ["Normal (truncada em 0)", "Normal (truncated at 0)"],
  "dist.gamma": ["Gama", "Gamma"],
  "distnote.exponential": ["Sem memória: a idade não importa.", "Memoryless: age does not matter."],
  "distnote.weibull": ["Reparo perfeito: tão bom quanto novo.", "Perfect repair: as good as new."],
  "distnote.weibull_min": ["Reparo mínimo: tão ruim quanto antes (q = 1).", "Minimal repair: as bad as old (q = 1)."],
  "distnote.weibull_grp": ["Reparo imperfeito, Kijima I: v ← v + q·x (0 = novo, 1 = mínimo).", "Imperfect repair, Kijima I: v ← v + q·x (0 = new, 1 = minimal)."],
  "distnote.weibull_grp2": ["Reparo imperfeito, Kijima II: v ← q·(v + x) (0 = novo, 1 = mínimo).", "Imperfect repair, Kijima II: v ← q·(v + x) (0 = new, 1 = minimal)."],
  "distnote.lognormal": ["Comum para tempos de reparo.", "Common for repair times."],
  "distnote.normal": ["Sorteios negativos são descartados.", "Negative draws are rejected."],
  "distnote.gamma": ["Forma k e escala θ.", "Shape k and scale θ."],
  "param.rate": ["taxa λ (por h)", "rate λ (per h)"],
  "param.a": ["escala a (h)", "scale a (h)"],
  "param.b": ["forma b", "shape b"],
  "param.q": ["fator de reparo q", "repair factor q"],
  "param.lognormal.mu": ["μ (escala log)", "μ (log scale)"],
  "param.lognormal.sigma": ["σ (escala log)", "σ (log scale)"],
  "param.normal.mu": ["média μ (h)", "mean μ (h)"],
  "param.normal.sigma": ["desvio σ (h)", "std. dev. σ (h)"],
  "param.shape": ["forma k", "shape k"],
  "param.scale": ["escala θ (h)", "scale θ (h)"],
  "param.mu": ["μ", "μ"],
  "param.sigma": ["σ", "σ"],

  // GUI-level validation messages (engine messages are shown as they come)
  "err.missing": ["Informe um valor.", "Enter a value."],
  "err.number": ["Informe um número.", "Enter a number."],
  "err.seed_int": ["A semente deve ser um número inteiro (ou vazia, para sortear).", "The seed must be a whole number (or empty to draw one)."],
  "err.reps_max": ["No máximo 1.000.000 de replicações na interface.", "At most 1,000,000 replications in the GUI."],
  "err.trace_max": ["No máximo 50 replicações registradas na interface.", "At most 50 traced replications in the GUI."],
  "err.sweep_param": ["Este parâmetro não pode variar neste modelo.", "This parameter cannot vary in this model."],
  "err.sweep_values": ["Informe valores numéricos.", "Enter numeric values."],
  "err.sweep_max": ["Pontos demais.", "Too many points."],
  "err.est.empty": ["Nenhum tempo de falha informado.", "No failure times given."],
  "err.est.not_number": ["Valor não numérico: {detail}", "Not a number: {detail}"],
  "err.est.too_many": ["Tempos demais (máximo {detail}).", "Too many times (at most {detail})."],
  "err.est.intervals_positive": ["Os tempos entre falhas devem ser maiores que 0.", "Times between failures must be greater than 0."],
  "err.est.end_number": ["O fim da observação deve ser um número.", "The end of observation must be a number."],

  // run description
  "run.device": ["Um equipamento", "One device"],
  "run.fleet": ["Frota: N = {n}, K = {k}", "Fleet: N = {n}, K = {k}"],
  "run.reps": ["{n} replicações", "{n} replications"],
  "run.seed": ["semente {s}", "seed {s}"],
  "stale.run": ["O modelo mudou desde esta execução: clique em Simular para atualizar.", "The model changed since this run: click Simulate to update."],
  "stale.sweep": ["O modelo mudou desde esta comparação: rode-a de novo para atualizar.", "The model changed since this comparison: run it again to update."],

  // dashboard
  "dash.title": ["Resultados", "Results"],
  "dash.empty.title": ["Nenhuma simulação ainda", "No simulation yet"],
  "dash.empty.body": ["Escolha um exemplo ou monte o modelo à esquerda e clique em Simular.", "Pick an example or build the model on the left and click Simulate."],
  "dash.export": ["Exportar resultados (JSON)", "Export results (JSON)"],
  "dash.export.title": ["Resumo, intervalos, todas as replicações e o registro de eventos, no formato do farofa (to_dict)", "Summary, intervals, every replication and the event log, in farofa's format (to_dict)"],
  "dash.export.gone": ["Este resultado não está mais guardado no servidor: simule de novo para exportar.", "This result is no longer kept by the server: simulate again to export it."],
  "m.availability": ["Disponibilidade", "Availability"],
  "m.availability.title": ["Fração do tempo de missão em operação (na frota, equipamento-horas)", "Fraction of the mission spent operating (fleet: device-hours)"],
  "m.failures": ["Falhas por replicação", "Failures per replication"],
  "m.mttf": ["MTTF", "MTTF"],
  "m.mttf.sub": ["tempo em operação ÷ falhas", "operating time ÷ failures"],
  "m.mttr": ["MTTR", "MTTR"],
  "m.mttr.sub": ["tempo em reparo ÷ reparos concluídos", "repair time ÷ completed repairs"],
  "m.mttr.sub.fleet": ["reparo ativo ÷ reparos concluídos (sem a espera)", "active repair ÷ completed repairs (no waiting)"],
  "m.rate": ["Taxa de falhas", "Failure rate"],
  "m.rate.sub": ["falhas por hora de missão", "failures per mission hour"],
  "m.rate.sub.fleet": ["falhas da frota por hora de missão", "fleet failures per mission hour"],
  "m.utilization": ["Utilização das equipes", "Team utilization"],
  "m.wait": ["Espera por equipe", "Wait for a team"],
  "m.wait.sub": ["média por reparo iniciado", "mean per started repair"],
  "m.wait.title": ["Espera dos reparos que começaram na missão; o IC é o do método delta para a razão (espera total ÷ reparos), uma observação por replicação", "Wait of the repairs that started within the mission; the CI is the delta-method interval of the ratio (total wait ÷ repairs), one observation per replication"],
  "m.pwait": ["Reparos com espera", "Repairs that waited"],
  "m.pwait.sub": ["fração dos reparos iniciados que esperaram equipe", "share of started repairs that waited for a team"],
  "m.maxqueue": ["Fila máxima", "Max queue"],
  "m.maxqueue.sub": ["maior fila vista; média por replicação {v}", "largest queue seen; mean per replication {v}"],
  "hist.avail": ["Disponibilidade por replicação", "Availability per replication"],
  "hist.failures": ["Falhas por replicação", "Failures per replication"],
  "hist.util": ["Utilização das equipes por replicação", "Team utilization per replication"],
  "hist.wait": ["Espera média por replicação", "Mean wait per replication"],
  "hist.cap": ["{n} replicações · tracejado: média · faixa: IC 95% da média", "{n} replications · dashed: mean · band: 95% CI of the mean"],
  "hist.part": ["Histograma das primeiras {k} replicações; média e IC usam todas.", "Histogram of the first {k} replications; the mean and CI use all of them."],
  "hist.wait.cap": ["{n} replicações com algum reparo iniciado · tracejado: média geral (todos os reparos)", "{n} replications with a started repair · dashed: overall mean (all repairs)"],
  "chart.reps": ["{n} replicações", "{n} replications"],
  "chart.repsAxis": ["replicações", "replications"],
  "chart.mean": ["média", "mean"],
  "axis.avail": ["disponibilidade", "availability"],
  "axis.failures": ["falhas na missão", "failures in the mission"],
  "axis.util": ["utilização", "utilization"],
  "axis.wait": ["espera média (h)", "mean wait (h)"],
  "axis.time": ["tempo (h)", "time (h)"],
  "axis.optime": ["tempo de operação (h)", "operating time (h)"],
  "axis.device": ["equipamento", "device"],
  "unit.failures": ["falhas", "failures"],
  "dev.title": ["Disponibilidade por equipamento", "Availability per device"],
  "dev.cap": ["Diagnóstico: equipamentos da mesma frota disputam equipes e não são observações independentes; o IC usa a frota inteira.", "Diagnostic: devices of one fleet compete for teams and are not independent observations; the CI uses the whole fleet."],
  "dev.ref": ["frota", "fleet"],
  "dev.failures": ["falhas por replicação", "failures per replication"],
  "device.n": ["Equipamento {n}", "Device {n}"],
  "occ.title": ["Equipamentos parados ao longo da missão", "Devices down over the mission"],
  "occ.title.device": ["Probabilidade de estar em reparo ao longo da missão", "Probability of being in repair over the mission"],
  "occ.cap": ["Número médio de equipamentos em cada estado, por faixa de tempo, nas {k} replicações registradas (aumente “Replicações registradas” para suavizar).", "Mean number of devices in each state per time bin, over the {k} traced replications (raise “Traced replications” to smooth it)."],
  "occ.k": ["K = {k} equipes", "K = {k} teams"],
  "state.up": ["Operando", "Up"],
  "state.waiting": ["Esperando equipe", "Waiting for a team"],
  "state.repair": ["Em reparo", "In repair"],
  "state.failure": ["Falha", "Failure"],
  "exact.title": ["Conferência com o resultado exato (tempos exponenciais)", "Check against the exact result (exponential times)"],
  "exact.note.fleet": ["Fila de população finita: N = {N} equipamentos, K = {K} equipes, λ = {lam} e μ = {mu} por h. “Exato na missão” é a média esperada em [0, T] partindo com todos operando (cadeia de Markov, uniformização); “regime permanente” é o limite de longo prazo.",
    "Finite-source queue: N = {N} devices, K = {K} teams, λ = {lam} and μ = {mu} per h. “Exact, mission” is the expected time average over [0, T] starting with every device up (Markov chain, uniformization); “steady state” is the long-run limit."],
  "exact.note.device": ["Um equipamento, λ = {lam} e μ = {mu} por h: disponibilidade média exata em [0, T] e o limite de longo prazo μ/(λ + μ).", "One device, λ = {lam} and μ = {mu} per h: the exact mean availability over [0, T] and the long-run limit μ/(λ + μ)."],
  "exact.long": ["A missão é longa demais para o transiente exato; vale o regime permanente.", "The mission is too long for the exact transient; the steady state applies."],
  "exact.q": ["Grandeza", "Quantity"],
  "exact.sim": ["Simulação (IC 95%)", "Simulation (95% CI)"],
  "exact.mission": ["Exato na missão [0, T]", "Exact, mission [0, T]"],
  "exact.ss": ["Regime permanente", "Steady state"],
  "exact.inci": ["Exato dentro do IC?", "Exact inside the CI?"],

  // timeline
  "tl.title": ["Linha do tempo", "Timeline"],
  "tl.meta": ["{k} replicações registradas", "{k} traced replications"],
  "tl.repn": ["replicação {n}", "replication {n}"],
  "tl.rep": ["Replicação", "Replication"],
  "tl.of": ["de {k}", "of {k}"],
  "tl.prev": ["Replicação anterior", "Previous replication"],
  "tl.next": ["Próxima replicação", "Next replication"],
  "tl.zoomin": ["Ampliar", "Zoom in"],
  "tl.zoomout": ["Reduzir", "Zoom out"],
  "tl.all": ["Ver tudo", "Show all"],
  "tl.aria": ["Linha do tempo dos equipamentos na replicação registrada", "Timeline of the devices in the traced replication"],
  "tl.dev": ["Eq. {n}", "Dev. {n}"],
  "tl.device1": ["Equipamento", "Device"],
  "tl.queue": ["Fila (equipamentos esperando)", "Queue (devices waiting)"],
  "tl.busy": ["Equipes ocupadas", "Busy teams"],
  "tl.overview": ["visão geral", "overview"],
  "tl.duration": ["duração", "duration"],
  "tl.cut": ["cortado em T", "cut at T"],
  "tl.failuresDev": ["falhas até aqui: {n} de {all}", "failures so far: {n} of {all}"],
  "tl.help": ["Arraste sobre o gráfico para ampliar um trecho; na faixa “visão geral”, arraste a janela para deslocar ou clique para centralizar; duplo clique volta à missão inteira (Ctrl/⌘ + rolagem também amplia).",
    "Drag across the chart to zoom into a stretch; on the “overview” strip, drag the window to pan or click to centre it; double-click returns to the whole mission (Ctrl/⌘ + scroll also zooms)."],
  "tl.readout.fleet": ["Em t = <b>{t}</b>: {up} operando, {w} esperando, {r} em reparo ({r} de {k} equipes ocupadas).", "At t = <b>{t}</b>: {up} up, {w} waiting, {r} in repair ({r} of {k} teams busy)."],
  "tl.readout.up": ["Em t = <b>{t}</b>: o equipamento está operando.", "At t = <b>{t}</b>: the device is up."],
  "tl.readout.down": ["Em t = <b>{t}</b>: o equipamento está em reparo.", "At t = <b>{t}</b>: the device is in repair."],
  "tl.stats": ["Nesta replicação: {f} falhas · disponibilidade {a}", "This replication: {f} failures · availability {a}"],
  "tl.stats.queue": ["fila máxima {q}", "max queue {q}"],
  "tl.window": ["janela {a} a {b}", "window {a} to {b}"],
  "tl.empty.title": ["Nenhuma simulação ainda", "No simulation yet"],
  "tl.notrace.title": ["Nenhuma replicação registrada", "No traced replication"],
  "tl.notrace.body": ["Informe “Replicações registradas” maior que 0 e simule de novo.", "Set “Traced replications” above 0 and simulate again."],

  // comparison
  "cmp.heading": ["Comparar cenários", "Compare scenarios"],
  "cmp.intro": ["Varie um parâmetro do modelo atual e veja disponibilidade, espera e utilização das equipes em cada valor, com intervalos de confiança. Todos os pontos usam a mesma semente (números aleatórios comuns), o que torna as diferenças entre pontos vizinhos mais nítidas.",
    "Vary one parameter of the current model and see availability, waiting and team utilization at each value, with confidence intervals. Every point uses the same seed (common random numbers), which makes differences between neighbouring points sharper."],
  "cmp.param": ["Parâmetro que varia", "Parameter to vary"],
  "cmp.p.n_teams": ["Equipes K", "Teams K"],
  "cmp.p.n_devices": ["Equipamentos N", "Devices N"],
  "cmp.p.mission_time": ["Tempo de missão T (h)", "Mission time T (h)"],
  "cmp.p.failure": ["Falha", "Failure"],
  "cmp.p.repair": ["Reparo", "Repair"],
  "cmp.from": ["De", "From"],
  "cmp.to": ["Até", "To"],
  "cmp.step": ["Passo", "Step"],
  "cmp.reps": ["Replicações por ponto", "Replications per point"],
  "cmp.cteam": ["Custo por equipe-hora", "Cost per team-hour"],
  "cmp.cdown": ["Custo por equipamento-hora parado", "Cost per device-hour down"],
  "cmp.cost.hint": ["Opcional: custo por hora = K × custo da equipe + N × (1 − disponibilidade) × custo da parada.", "Optional: cost per hour = K × team cost + N × (1 − availability) × downtime cost."],
  "cmp.run": ["Rodar comparação", "Run comparison"],
  "cmp.preview": ["{n} pontos: {v} · {reps} replicações cada ({total} no total)", "{n} points: {v} · {reps} replications each ({total} in total)"],
  "cmp.err.numbers": ["Informe números em De, Até e Passo.", "Enter numbers in From, To and Step."],
  "cmp.err.step": ["O passo deve ser maior que 0.", "The step must be greater than 0."],
  "cmp.err.order": ["“Até” deve ser maior ou igual a “De”.", "“To” must not be below “From”."],
  "cmp.err.max": ["No máximo {max} pontos: aumente o passo.", "At most {max} points: increase the step."],
  "cmp.err.int": ["Este parâmetro só aceita números inteiros.", "This parameter takes whole numbers only."],
  "cmp.empty.title": ["Nenhuma comparação ainda", "No comparison yet"],
  "cmp.empty.body": ["Escolha o parâmetro e a faixa acima e clique em Rodar comparação.", "Choose the parameter and range above and click Run comparison."],
  "cmp.title": ["Variando {p}", "Varying {p}"],
  "cmp.base": ["cenário base:", "base scenario:"],
  "cmp.crn": ["mesma semente em todos os pontos", "same seed at every point"],
  "cmp.csv": ["Baixar a tabela em CSV", "Download the table as CSV"],
  "cmp.json": ["Baixar a comparação em JSON", "Download the comparison as JSON"],
  "cmp.best": ["Menor custo", "Lowest cost"],
  "cmp.best.sub": ["{c} por hora · disponibilidade {a}", "{c} per hour · availability {a}"],
  "cmp.current": ["Custo do valor atual", "Cost of the current value"],
  "cmp.current.sub": ["por hora, com o valor atual {v}", "per hour, at the current value {v}"],
  "cmp.now": ["atual", "current"],
  "cmp.c.avail": ["Disponibilidade", "Availability"],
  "cmp.c.wait": ["Espera média por equipe (h)", "Mean wait for a team (h)"],
  "cmp.c.util": ["Utilização das equipes", "Team utilization"],
  "cmp.c.failures": ["Falhas por replicação", "Failures per replication"],
  "cmp.c.cost": ["Custo total por hora", "Total cost per hour"],
  "cmp.costh": ["Custo/h", "Cost/h"],
  "cmp.ci.cap": ["Barras: IC 95% (uma observação por replicação) · tracejado: valor atual.", "Bars: 95% CI (one observation per replication) · dashed: current value."],
  "cmp.wait.cap": ["Reparos iniciados na missão; barras: IC 95% (método delta para a razão).", "Repairs started within the mission; bars: 95% CI (delta method for the ratio)."],
  "cmp.util.cap": ["Horas de equipe ocupada ÷ (K × T); barras: IC 95%.", "Busy team-hours ÷ (K × T); bars: 95% CI."],
  "cmp.cost.cap": ["K × {ct} + N × (1 − disponibilidade) × {cd}; anel: menor custo.", "K × {ct} + N × (1 − availability) × {cd}; ring: lowest cost."],
  "cmp.table.note": ["Fila máxima: a maior vista em todas as replicações (entre parênteses, a média das máximas por replicação). Espera: média dos reparos iniciados.", "Max queue: the largest over all replications (in brackets, the mean of the per-replication maxima). Wait: mean over started repairs."],

  // python
  "code.title": ["Reproduza em Python", "Reproduce it in Python"],
  "code.intro": ["O mesmo modelo como script do farofa: com a mesma semente, os números batem com os da interface (no mesmo ambiente).", "The same model as a farofa script: with the same seed, the numbers match the GUI's (in the same environment)."],
  "code.invalid": ["# Corrija o modelo à esquerda para obter o código.", "# Fix the model on the left to get the code."],
  "code.copy": ["Copiar", "Copy"],
  "code.copied": ["Copiado.", "Copied."],
  "code.copyfail": ["Não foi possível copiar: selecione o texto.", "Could not copy: select the text instead."],
  "code.download": ["Baixar .py", "Download .py"],
  "code.c.head": ["# farofa: simulação de falhas e reparos", "# farofa: failure and repair simulation"],
  "code.c.trace": ["# Linha do tempo da 1ª replicação registrada: (entity, state, start, end)", "# Timeline of the first traced replication: (entity, state, start, end)"],
  "code.c.export": ["# Resultados completos em JSON", "# Full results as JSON"],
  "code.c.sweep": ["# Quantas equipes? Mesma semente para todo K (números aleatórios comuns)", "# How many teams? Same seed for every K (common random numbers)"],
  "code.ci.avail": ["disponibilidade, IC 95%:", "availability, 95% CI:"],
  "code.ci.fail": ["falhas por replicação, IC 95%:", "failures per replication, 95% CI:"],
  "code.ci.util": ["utilização das equipes, IC 95%:", "team utilization, 95% CI:"],

  // estimation
  "est.title": ["Dados de falha", "Failure data"],
  "est.intro": ["Tempos acumulados de operação em que um sistema reparável falhou, observados desde novo (t = 0).", "Cumulative operating times at which one repairable system failed, observed from new (t = 0)."],
  "est.datasets": ["Registros publicados", "Published records"],
  "est.ds.halfbeak": ["motor diesel, 71 falhas, deterioração", "diesel engine, 71 failures, deteriorating"],
  "est.ds.grampus": ["motor diesel, 56 falhas em 16.000 h, sem tendência", "diesel engine, 56 failures in 16,000 h, no trend"],
  "est.ds.halfbeak.note": ["Motor de propulsão do submarino USS Halfbeak: 71 manutenções não programadas, registro truncado na última falha (25.518 h).", "Propulsion diesel of the USS Halfbeak: 71 unscheduled maintenance actions, failure-truncated at 25,518 h."],
  "est.ds.grampus.note": ["Motor de propulsão do submarino USS Grampus: 56 falhas nas primeiras 16.000 h. Há um empate (14.173 h duas vezes), que a verossimilhança do GRP não aceita.", "Propulsion diesel of the USS Grampus: 56 failures in the first 16,000 h. One tie (14,173 h twice), which the GRP likelihood cannot take."],
  "est.source": ["Fonte:", "Source:"],
  "est.times": ["Tempos de falha (h)", "Failure times (h)"],
  "est.placeholder": ["Um valor por linha ou separados por vírgula:\n1382, 2990, 4124, …\nCom ponto e vírgula, a vírgula vale como decimal.", "One value per line or comma-separated:\n1382, 2990, 4124, …\nWith semicolons, a comma is read as the decimal mark."],
  "est.file": ["Abrir arquivo CSV ou texto", "Open a CSV or text file"],
  "est.file.loaded": ["Arquivo {name} carregado.", "File {name} loaded."],
  "est.count": ["{n} valores", "{n} values"],
  "est.kind": ["Os valores são", "The values are"],
  "est.cumulative": ["tempos acumulados", "cumulative times"],
  "est.intervals": ["tempos entre falhas", "times between failures"],
  "est.end": ["Fim da observação T (h)", "End of observation T (h)"],
  "est.end.placeholder": ["vazio = última falha", "empty = last failure"],
  "est.end.hint": ["Vazio: o registro termina na última falha.", "Empty: the record ends at the last failure."],
  "est.run": ["Ajustar modelos", "Fit models"],
  "est.fitting": ["ajustando…", "fitting…"],
  "est.read": ["{n} tempos lidos.", "{n} times read."],
  "est.skipped": ["({n} cabeçalho ignorado)", "({n} header skipped)"],
  "est.heading": ["Ajuste do processo de falhas", "Failure-process fit"],
  "est.empty.title": ["Nenhum ajuste ainda", "No fit yet"],
  "est.empty.body": ["Escolha um registro publicado ou cole tempos de falha à esquerda e clique em Ajustar modelos.", "Pick a published record or paste failure times on the left and click Fit models."],
  "est.window.ft": ["{n} falhas · janela [0, {T}], truncada na última falha", "{n} failures · window [0, {T}], failure-truncated"],
  "est.window.tt": ["{n} falhas · janela [0, {T}], truncada no tempo", "{n} failures · window [0, {T}], time-truncated"],
  "est.c.n": ["Falhas", "Failures"],
  "est.c.n.sub": ["de {a} a {b}", "from {a} to {b}"],
  "est.c.laplace": ["Teste de Laplace", "Laplace test"],
  "est.lap.worse": ["tendência de deterioração (falhas cada vez mais frequentes)", "deteriorating trend (failures come faster)"],
  "est.lap.better": ["tendência de melhoria (falhas cada vez mais raras)", "improving trend (failures become rarer)"],
  "est.lap.none": ["sem evidência de tendência a 5%", "no evidence of a trend at 5%"],
  "est.c.best": ["Melhor modelo (AIC)", "Best model (AIC)"],
  "est.c.best.sub": ["seguinte: {m}, ΔAIC = {d}", "next: {m}, ΔAIC = {d}"],
  "est.c.q": ["q estimado, Kijima I", "Estimated q, Kijima I"],
  "est.c.q.sub": ["IC 95% (perfil): [{lo}; {hi}]", "95% CI (profile): [{lo}, {hi}]"],
  "est.m.power_law": ["Lei de potência (reparo mínimo, q = 1)", "Power law (minimal repair, q = 1)"],
  "est.m.grp1": ["Weibull GRP, Kijima I", "Weibull GRP, Kijima I"],
  "est.m.grp2": ["Weibull GRP, Kijima II", "Weibull GRP, Kijima II"],
  "est.m.renewal": ["Renovação Weibull (reparo perfeito, q = 0)", "Weibull renewal (perfect repair, q = 0)"],
  "est.short.power_law": ["Lei de potência", "Power law"],
  "est.short.grp1": ["Kijima I", "Kijima I"],
  "est.short.grp2": ["Kijima II", "Kijima II"],
  "est.short.renewal": ["Renovação", "Renewal"],
  "est.t.model": ["Modelo", "Model"],
  "est.t.a": ["escala a (h)", "scale a (h)"],
  "est.t.b": ["forma b", "shape b"],
  "est.t.ll": ["log-verossimilhança", "log-likelihood"],
  "est.t.k": ["parâmetros", "parameters"],
  "est.t.error": ["Não ajustado:", "Not fitted:"],
  "est.fixed": ["(fixo)", "(fixed)"],
  "est.best": ["melhor", "best"],
  "est.use": ["Usar na simulação", "Use in simulation"],
  "est.use.title": ["Leva este processo de falhas (e T = fim da observação) para o modelo de simulação", "Sends this failure process (and T = end of observation) to the simulation model"],
  "est.used": ["Falhas do modelo: {m}, T = {T}. Os tempos de reparo não entram nesta verossimilhança: defina-os separadamente.", "Model failures: {m}, T = {T}. Repair times do not enter this likelihood: set them separately."],
  "est.table.note": ["AIC = 2·parâmetros − 2·log-verossimilhança; menor é melhor, e diferenças abaixo de ~2 não separam os modelos. Na lei de potência, a = λ^(−1/β) e b = β.", "AIC = 2·parameters − 2·log-likelihood; lower is better, and differences below about 2 do not separate the models. For the power law, a = λ^(−1/β) and b = β."],
  "est.cum.title": ["Falhas acumuladas: observado × modelos ajustados", "Cumulative failures: observed vs fitted models"],
  "est.cum.mode": ["Curva dos modelos", "Model curves"],
  "est.cum.mean": ["Função média E[N(t)]", "Mean function E[N(t)]"],
  "est.cum.conditional": ["Condicional ao histórico", "Given the observed history"],
  "est.cum.cap.mean": ["Número esperado de falhas desde novo: forma fechada na lei de potência; nos demais, Monte Carlo com o próprio amostrador do farofa ({reps} replicações). No topo, cada traço é uma falha observada.",
    "Expected number of failures from new: closed form for the power law; for the others, Monte Carlo through farofa's own sampler ({reps} replications). On top, each tick is an observed failure."],
  "est.cum.cap.cond": ["Intensidade acumulada do modelo dada a sequência observada (o compensador): com o modelo certo, segue de perto a escada observada; a lei de potência coincide com a função média.",
    "The model's cumulative intensity given the observed sequence (the compensator): under the right model it tracks the observed staircase; for the power law it equals the mean function."],
  "est.cum.y": ["falhas acumuladas", "cumulative failures"],
  "est.observed": ["Observado", "Observed"],
  "est.events": ["falhas", "failures"],
  "est.prof.title": ["Verossimilhança perfilada do fator de reparo q", "Profile likelihood of the repair factor q"],
  "est.prof.x": ["q (0 = reparo perfeito, 1 = reparo mínimo)", "q (0 = perfect repair, 1 = minimal repair)"],
  "est.prof.y": ["log-verossimilhança relativa", "relative log-likelihood"],
  "est.prof.ci": ["limite do IC 95%", "95% CI limit"],
  "est.prof.cap": ["Para cada q fixo, forma e escala são reotimizadas. Os valores acima da linha tracejada (queda de 1,92) formam o IC 95% da razão de verossimilhanças: Kijima I {i1}, Kijima II {i2}.",
    "For each fixed q, shape and scale are re-optimized. Values above the dashed line (a drop of 1.92) form the 95% likelihood-ratio CI: Kijima I {i1}, Kijima II {i2}."],
  "est.gaps.title": ["Tempo entre falhas", "Time between failures"],
  "est.gaps.cap": ["Intervalos encurtando ao longo do registro indicam deterioração; alongando, melhoria.", "Intervals shrinking along the record suggest deterioration; growing, improvement."],
  "est.gaps.s": ["intervalo", "interval"],
  "est.gaps.x": ["número da falha", "failure number"],
  "est.gaps.y": ["horas desde a falha anterior", "hours since the previous failure"],
  "est.gaps.tip": ["Falha {i}", "Failure {i}"],
  "est.notes.title": ["Como ler este ajuste", "How to read this fit"],
  "est.notes": ["<p>Os dados são os tempos acumulados de operação de <b>um</b> sistema. O <b>teste de Laplace</b> pergunta se as falhas se concentram no fim (U &gt; 0, deterioração) ou no começo (U &lt; 0) da janela, contra um processo de Poisson homogêneo.</p><p>A <b>lei de potência</b> (Crow-AMSAA) supõe reparo mínimo: o sistema volta como estava. O <b>GRP de Weibull</b> estima quanto da idade cada reparo remove, via o fator q: no Kijima I o reparo atua só no último intervalo; no Kijima II, na idade acumulada. q = 0 é reparo perfeito (renovação) e q = 1 reproduz a lei de potência.</p><p>Os tempos de reparo não entram nestas verossimilhanças. Ao levar um ajuste para a simulação, defina a distribuição de reparo à parte.</p>",
    "<p>The data are the cumulative operating times of <b>one</b> system. The <b>Laplace test</b> asks whether failures concentrate at the end (U &gt; 0, deterioration) or the start (U &lt; 0) of the window, against a homogeneous Poisson process.</p><p>The <b>power law</b> (Crow-AMSAA) assumes minimal repair: the system comes back as it was. The <b>Weibull GRP</b> estimates how much age each repair removes, through the factor q: in Kijima I the repair acts on the last interval only; in Kijima II, on the accumulated age. q = 0 is perfect repair (renewal) and q = 1 reproduces the power law.</p><p>Repair times do not enter these likelihoods. When you send a fit to the simulation, set the repair distribution separately.</p>"],
};

let LANG = "pt";
export function lang() { return LANG; }
export function locale() { return LANG === "pt" ? "pt-BR" : "en-US"; }
export function has(key) { return Object.prototype.hasOwnProperty.call(D, key); }
export function keys() { return Object.keys(D); }

export function t(key, vars) {
  const entry = D[key];
  let s = entry ? entry[LANG === "pt" ? 0 : 1] : key;
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] === undefined ? m : String(vars[k])));
  return s;
}

export function setLang(l) {
  LANG = l === "en" ? "en" : "pt";
  store("farofa-lang", LANG);
  document.documentElement.lang = locale();
}

export function applyI18n(root = document) {
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const [attr, name] of [["i18nTitle", "title"], ["i18nPlaceholder", "placeholder"], ["i18nAriaLabel", "aria-label"]]) {
    for (const el of root.querySelectorAll(`[data-${attr.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase())}]`)) el.setAttribute(name, t(el.dataset[attr]));
  }
}

// ---------------------------------------------------------------- numbers --
const nf = {};
function formatter(opts) {
  const key = locale() + JSON.stringify(opts);
  return nf[key] || (nf[key] = new Intl.NumberFormat(locale(), opts));
}
const ok = (x) => typeof x === "number" && Number.isFinite(x);
export function fmt(x, d = 2) { return ok(x) ? formatter({ minimumFractionDigits: d, maximumFractionDigits: d }).format(x) : "—"; }
export function fmtInt(x) { return ok(x) ? formatter({ maximumFractionDigits: 0 }).format(x) : "—"; }
export function fmtSig(x, s = 4) {
  if (!ok(x)) return "—";
  s = Math.min(21, Math.max(1, Math.round(+s) || 4));
  if (x !== 0 && (Math.abs(x) >= 1e7 || Math.abs(x) < 1e-4)) return sci(x, s);
  return formatter({ maximumSignificantDigits: s }).format(x);
}
const SUP = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
function sci(x, s) {
  const [m, e] = x.toExponential(Math.max(0, s - 1)).split("e");
  const mant = LANG === "pt" ? m.replace(".", ",") : m;
  return `${mant} × 10${String(+e).replace(/./g, (c) => SUP[c] || c)}`;
}
export function fmtP(p) { return !ok(p) ? "—" : p < 1e-4 ? sci(p, 2) : fmt(p, p < 0.01 ? 4 : 3); }
export function fmtH(x) {
  if (!ok(x)) return "—";
  const a = Math.abs(x);
  const d = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : a >= 0.01 ? 3 : 4;
  return formatter({ maximumFractionDigits: d }).format(x) + " h";
}
/** Hours without the unit, with the same adaptive decimals as fmtH. */
export function fmtHn(x) { return fmtH(x).replace(/ h$/, ""); }
export function fmtPct(x, d = 1) { return ok(x) ? fmt(100 * x, d) + "%" : "—"; }
export function fmtCI(ci, d = 2, f) {
  if (!ci || !ok(ci[0]) || !ok(ci[1])) return "—";
  const g = f || ((v) => fmt(v, d));
  return `[${g(ci[0])}${t("sep")} ${g(ci[1])}]`;
}
/** Parse user text as a number, accepting a decimal comma ("0,5"). */
export function parseNum(s) {
  if (typeof s === "number") return s;
  if (s === null || s === undefined) return NaN;
  let str = String(s).trim().replace(/\s+/g, "");
  if (str === "") return NaN;
  if (str.includes(",") && !str.includes(".")) str = str.replace(",", ".");
  const v = Number(str);
  return Number.isFinite(v) ? v : NaN;
}

// initial language: saved choice, else the browser's
(() => {
  const saved = store("farofa-lang");
  const nav = (navigator.languages && navigator.languages[0]) || navigator.language || "pt";
  setLang(saved === "pt" || saved === "en" ? saved : nav.toLowerCase().startsWith("pt") ? "pt" : "en");
})();

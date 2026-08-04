# farofa

**F**ailure **A**nd **R**epair simulation **O**ptimization **F**r**A**mework

A Python framework for Monte Carlo simulation of repairable systems, with focus on reliability analysis. farofa enables modeling devices subject to failure and repair processes using common lifetime distributions, including imperfect repair models such as the Generalized Renewal Process (GRP).

> **Status:** Early development (pre-release). The API is unstable and subject to change.

## Features

- **Single-device failure-repair simulation** with configurable failure and repair time distributions
- **Fleet simulation** with `n` identical devices sharing `k` maintenance teams (FIFO queue)
- **Lifetime distributions:** Exponential, Weibull (perfect repair), Weibull with minimal repair, Weibull GRP (Kijima Type I and Type II), Lognormal, Normal, Gamma
- **Custom user-defined distributions** via callable factories
- **Monte Carlo replication** for statistical analysis (failures, availability, MTTF, MTTR, utilization, queue/wait metrics)
- **Reproducible by construction:** `simulate(seed=...)` gives bit-for-bit repeatable runs (same environment), with provably independent per-device PCG64 streams via `numpy.random.SeedSequence`
- **Vectorized random variate generation** (buffered batch draws through NumPy's PCG64 generator)

## Installation

```bash
git clone https://github.com/jmateusms/farofa.git
cd farofa
pip install -e .
```

## Quick start

### Single device

```python
import farofa

device = farofa.SimpleDevice()
device.set_failure_dist('exponential', 0.0001)  # rate = 0.0001 failures/hour
device.set_repair_dist('exponential', 0.01)      # rate = 0.01 repairs/hour
device.set_mission_time(8760)                     # 1 year in hours

result = device.simulate(reps=10000)
print(result)
```

### Fleet with shared maintenance teams

```python
import farofa

fleet = farofa.Fleet(n_devices=10, n_teams=2)
fleet.set_failure_dist('weibull_grp', 200.0, 1.8, 0.4)  # imperfect repair
fleet.set_repair_dist('lognormal', 2.0, 0.4)
fleet.set_mission_time(8760)

result = fleet.simulate(reps=200)
print(result)
```

### Reproducible runs

Pass `seed=` to `simulate()` to make a run bit-for-bit reproducible (in the
same environment). Each sampler — and each device in a fleet — draws from its
own independent PCG64 stream spawned from the seed, so a device's trajectory
does not depend on fleet size or event interleaving:

```python
r1 = device.simulate(reps=10000, seed=42)
r2 = device.simulate(reps=10000, seed=42)
# r1 and r2 are identical, sample by sample
```

## Available distributions

| Distribution | Function | Repair assumption | Parameters |
|---|---|---|---|
| Exponential | `exponential` | Memoryless (perfect repair) | `rate` |
| Weibull | `weibull` | Perfect repair (age reset to 0) | `a` (scale), `b` (shape) |
| Weibull (minimal repair) | `weibull_min` | Minimal repair (age preserved; stateful) | `a` (scale), `b` (shape) |
| Weibull GRP (Kijima I) | `weibull_grp` | Imperfect repair, `v_i = v_{i-1} + q·x_i` (stateful) | `a` (scale), `b` (shape), `q` (repair effectiveness, 0–1) |
| Weibull GRP (Kijima II) | `weibull_grp2` | Imperfect repair, `v_i = q·(v_{i-1} + x_i)` (stateful) | `a` (scale), `b` (shape), `q` (repair effectiveness, 0–1) |
| Lognormal | `lognormal` | — (typically used for repair times) | `mu`, `sigma` (log-scale) |
| Normal (truncated at 0) | `normal` | — (resampled until positive) | `mu`, `sigma` |
| Gamma | `gamma` | — | `shape`, `scale` |

## Roadmap

farofa is being developed incrementally. Below is the planned scope for each milestone.

### v0 — Single device simulation

Core simulation engine for a single repairable device.

- [x] Failure-repair simulation loop with exponential and Weibull distributions
- [x] Weibull GRP (Generalized Renewal Process) for imperfect repair modeling (Kijima Type I and Type II)
- [x] Reproducible, vectorized random variate generation (PCG64, seeded per-device streams)
- [x] Support for custom (user-defined) lifetime distributions
- [x] Lognormal, Normal, and Gamma distributions
- [x] Output metrics: availability, mean time to failure (MTTF), mean time to repair (MTTR), failure rate
- [x] Results object with summary statistics and raw simulation data
- [x] Input validation and meaningful error messages
- [x] Unit tests
- [ ] CI

### v1 — Queueing systems (current)

Multiple devices sharing repair resources (maintenance teams).

- [x] Queue with `n` identical devices and `k` repair servers (FIFO)
- [x] Metrics: queue length, waiting time, server utilization
- [ ] Additional queue disciplines (priority-based, custom)
- [ ] Support for custom queue models

### v2 — Heterogeneous systems

Different device types in the same system.

- [ ] Multiple device types with independent failure/repair behavior
- [ ] Priority classes for repair scheduling
- [ ] System-level metrics (e.g., system availability with redundancy)
- [ ] Expanded set of output metrics

### v3 — Optimization

Find optimal maintenance policies and system configurations.

- [ ] Optimization over maintenance parameters (e.g., preventive maintenance interval, number of repair teams)
- [ ] Built-in objective functions: cost, availability, profit
- [ ] Support for custom objective functions
- [ ] Integration with scipy.optimize or similar

### v4 — GUI

Graphical interface for building and running simulations without code.

### v5 — Parameter estimation

Estimate distribution parameters from observed failure/repair data.

- [ ] Maximum likelihood estimation for supported distributions
- [ ] Goodness-of-fit testing
- [ ] Integration with or reference to existing tools (e.g., `reliability` package)

## Background

farofa is inspired by research in reliability engineering, particularly repairable systems modeling with imperfect repair and queueing-based maintenance optimization. Key references:

- Moura, M. C. et al. (2017). Analysis of extended warranties for medical equipment: A Stackelberg game model using priority queues. *Reliability Engineering & System Safety*, 168, 338–354. [DOI](https://doi.org/10.1016/j.ress.2017.05.040)
- Santana, J. M. et al. (2018). Extended warranty of medical equipment subject to imperfect repairs. *Eksploatacja I Niezawodnosc*, 20(4), 567–578. [DOI](https://doi.org/10.17531/ein.2018.4.8)
- Yañez, M. et al. (2002). Generalized renewal process for analysis of repairable systems with limited failure experience. *Reliability Engineering and System Safety*, 77(2), 167–180. [DOI](https://doi.org/10.1016/S0951-8320(02)00044-3)
- Wang, Z. M. & Yang, J. G. (2012). Numerical method for Weibull generalized renewal process and its applications in reliability analysis of NC machine tools. *Computers and Industrial Engineering*. [DOI](https://doi.org/10.1016/j.cie.2012.06.019)
- Moura, M. C. et al. (2014). A competing risk model for dependent and imperfect condition-based preventive and corrective maintenances. *Proceedings of the Institution of Mechanical Engineers Part O*, 228(6), 590–605. [DOI](https://doi.org/10.1177/1748006X14540878)

## License

GNU General Public License v3 — see [LICENSE](LICENSE).

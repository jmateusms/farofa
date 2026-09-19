# AGENTS.md

## Project overview

farofa (Failure And Repair simulation Optimization Framework) is a Python library for Monte Carlo simulation of repairable systems. It models single devices and fleets of devices subject to failure and repair, using lifetime distributions including imperfect-repair models (Kijima Type I/II Generalized Renewal Process).

## Repository structure

- `farofa/` — main package
  - `device.py` — `SimpleDevice`: single-device failure-repair simulation
  - `fleet.py` — `Fleet`: heap-based discrete-event simulation of N identical devices sharing K maintenance teams (FIFO queue)
  - `distributions.py` — distribution factories: `exponential`, `weibull`, `weibull_min`, `weibull_grp` (Kijima I), `weibull_grp2` (Kijima II), `lognormal`, `normal`, `gamma`
  - `results.py` — `SimulationResult` / `FleetSimulationResult`: metrics (availability, MTTF/MTTR, utilization, queue/wait)
  - `utils.py` — small shared helpers
- `examples/` — runnable usage examples
- `tests/` — pytest suite
- `misc/` — planning docs (git-ignored): ROADMAP.md, CRITICAL_ANALYSIS.md, OPEN_DECISIONS.md, PAPER_PLAN.md — read ROADMAP.md before starting non-trivial work
- `paper/` — PSAM paper draft (git-ignored)

## Build and test

```bash
pip install -e ".[dev]"    # install in editable mode with dev dependencies
pytest                      # run tests
```

## Key conventions

- Distribution functions are factories returning sampler callables; stateful samplers (GRP virtual age) expose `reset()` and one instance is used per device so state never leaks across devices.
- MTTF/MTTR are renewal estimators (total uptime / number of failures), not naive means of completed intervals — the latter is length-biased (inspection paradox). Don't "simplify" it back.
- Failure/repair distributions must have positive support; engines validate every drawn time is positive and finite.
- **RNG model (roadmap Path B):** every sampler owns a `numpy.random.Generator(PCG64)`. `simulate(seed=...)` spawns independent child streams via `SeedSequence` (one per sampler; `spawn(2N)` for fleets, so device streams are a deterministic prefix — fleet size doesn't perturb existing devices). Stateless samplers refill from vectorized batch draws; GRP samplers buffer their uniforms. `np.random.seed()` has no effect — that's by design, use the `seed=` kwarg. Numba is gone (the old per-scalar `@njit` path was slower than NumPy); don't reintroduce it without benchmarking.
- Reproducibility is same-environment (numpy version + platform); a `SimpleDevice` and an N=1/K=1 `Fleet` under the same seed are exactly parity-tested.

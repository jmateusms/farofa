import numpy as np

from .distributions import DISTRIBUTIONS, Sampler
from .results import SimulationResult
from .utils import draw_positive, spawn_seed_sequence


class SimpleDevice:
    """
    A single repairable device with configurable failure and repair distributions.

    Usage:
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.001)
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(8760)
        result = device.simulate(reps=1000, seed=42)  # seed optional
        print(result)
    """

    def __init__(self):
        self.operational = True
        self.failure_dist = None
        self.repair_dist = None
        self.mission_time = None

    def set_failure_dist(self, dist, *args, **kwargs):
        """
        Set the failure time distribution.

        Parameters:
            dist: distribution name (str) or a callable *factory* that
                  returns a new sampler per call. Built-in names:
                  'exponential', 'weibull', 'weibull_min', 'weibull_grp',
                  'weibull_grp2', 'lognormal', 'normal', 'gamma'.
            *args, **kwargs: parameters passed to the distribution factory.
        """
        if isinstance(dist, Sampler):
            raise TypeError(
                'pass the distribution factory and its parameters, e.g. '
                "set_failure_dist('exponential', 0.01) or "
                'set_failure_dist(farofa.exponential, 0.01) — not an '
                'already-constructed sampler instance.'
            )
        if callable(dist):
            self.failure_dist = dist(*args, **kwargs)
        elif isinstance(dist, str):
            if dist not in DISTRIBUTIONS:
                raise ValueError(
                    f"Unknown distribution '{dist}'. "
                    f"Available: {', '.join(DISTRIBUTIONS.keys())}"
                )
            self.failure_dist = DISTRIBUTIONS[dist](*args, **kwargs)
        else:
            raise TypeError('dist must be a string name or a callable.')

    def set_repair_dist(self, dist, *args, **kwargs):
        """
        Set the repair time distribution.

        Parameters:
            dist: distribution name (str) or a callable *factory* that
                  returns a new sampler per call. Same options as
                  set_failure_dist.
            *args, **kwargs: parameters passed to the distribution factory.
        """
        if isinstance(dist, Sampler):
            raise TypeError(
                'pass the distribution factory and its parameters, e.g. '
                "set_repair_dist('exponential', 0.1) or "
                'set_repair_dist(farofa.exponential, 0.1) — not an '
                'already-constructed sampler instance.'
            )
        if callable(dist):
            self.repair_dist = dist(*args, **kwargs)
        elif isinstance(dist, str):
            if dist not in DISTRIBUTIONS:
                raise ValueError(
                    f"Unknown distribution '{dist}'. "
                    f"Available: {', '.join(DISTRIBUTIONS.keys())}"
                )
            self.repair_dist = DISTRIBUTIONS[dist](*args, **kwargs)
        else:
            raise TypeError('dist must be a string name or a callable.')

    def set_mission_time(self, mission_time):
        """Set the mission time (total simulation duration per replication)."""
        if not isinstance(mission_time, (int, float)):
            try:
                mission_time = float(mission_time)
            except (TypeError, ValueError) as e:
                raise TypeError('Mission time must be a number.') from e
        if mission_time <= 0:
            raise ValueError('Mission time must be greater than 0.')
        self.mission_time = float(mission_time)

    def generate_failure(self):
        return draw_positive(self.failure_dist, 'failure')

    def generate_repair(self):
        return draw_positive(self.repair_dist, 'repair')

    def simulate(self, reps=1, seed=None):
        """
        Run the failure-repair simulation.

        Parameters:
            reps: number of Monte Carlo replications.
            seed: optional int or numpy SeedSequence. When given, the run is
                bit-for-bit reproducible (same environment): the failure and
                repair samplers each get an independent PCG64 stream spawned
                from this seed. When None, fresh OS entropy is used.

        Returns:
            SimulationResult with detailed metrics.
        """
        if not isinstance(reps, int):
            try:
                reps = int(reps)
            except (TypeError, ValueError):
                raise ValueError('reps must be an integer or convertible to integer.')
        if reps <= 0:
            raise ValueError('reps must be greater than 0.')
        if self.failure_dist is None:
            raise ValueError('Failure distribution not set. Call set_failure_dist() first.')
        if self.repair_dist is None:
            raise ValueError('Repair distribution not set. Call set_repair_dist() first.')
        if self.mission_time is None:
            raise ValueError('Mission time not set. Call set_mission_time() first.')

        failure_ss, repair_ss = spawn_seed_sequence(seed, 2)
        if hasattr(self.failure_dist, 'set_rng'):
            self.failure_dist.set_rng(np.random.Generator(np.random.PCG64(failure_ss)))
        if hasattr(self.repair_dist, 'set_rng'):
            self.repair_dist.set_rng(np.random.Generator(np.random.PCG64(repair_ss)))

        T = self.mission_time
        failure_counts = []
        repair_counts = []
        all_uptimes = []
        all_downtimes = []
        total_uptime = []
        total_downtime = []

        for _ in range(reps):
            if hasattr(self.failure_dist, 'reset'):
                self.failure_dist.reset()
            if hasattr(self.repair_dist, 'reset'):
                self.repair_dist.reset()

            t = 0.0
            failures = 0
            repairs = 0
            rep_uptimes = []
            rep_downtimes = []
            rep_uptime = 0.0
            rep_downtime = 0.0
            operational = True

            while t < T:
                if operational:
                    ttf = self.generate_failure()
                    if t + ttf < T:
                        rep_uptimes.append(ttf)
                        rep_uptime += ttf
                        failures += 1
                        t += ttf
                        operational = False
                    else:
                        # Device survives until end of mission
                        rep_uptime += (T - t)
                        t = T
                else:
                    ttr = self.generate_repair()
                    if t + ttr < T:
                        rep_downtimes.append(ttr)
                        rep_downtime += ttr
                        repairs += 1
                        t += ttr
                        operational = True
                    else:
                        # Repair extends beyond mission time
                        rep_downtime += (T - t)
                        t = T

            failure_counts.append(failures)
            repair_counts.append(repairs)
            all_uptimes.append(np.array(rep_uptimes))
            all_downtimes.append(np.array(rep_downtimes))
            total_uptime.append(rep_uptime)
            total_downtime.append(rep_downtime)

        return SimulationResult(
            mission_time=T,
            failure_counts=failure_counts,
            repair_counts=repair_counts,
            uptimes=all_uptimes,
            downtimes=all_downtimes,
            total_uptime=total_uptime,
            total_downtime=total_downtime,
        )

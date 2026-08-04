import numpy as np
from .distributions import (
    exponential, weibull, weibull_min, weibull_grp, weibull_grp2,
    lognormal, normal, gamma,
)
from .results import SimulationResult

DISTRIBUTIONS = {
    'exponential': exponential,
    'weibull': weibull,
    'weibull_min': weibull_min,
    'weibull_grp': weibull_grp,
    'weibull_grp2': weibull_grp2,
    'lognormal': lognormal,
    'normal': normal,
    'gamma': gamma,
}


class SimpleDevice:
    """
    A single repairable device with configurable failure and repair distributions.

    Usage:
        device = SimpleDevice()
        device.set_failure_dist('exponential', 0.001)
        device.set_repair_dist('exponential', 0.1)
        device.set_mission_time(8760)
        result = device.simulate(reps=1000)
        print(result)
    """

    def __init__(self):
        self.operational = True

        self.failure_dist = None
        self.failure_args = ()
        self.failure_kwargs = {}

        self.repair_dist = None
        self.repair_args = ()
        self.repair_kwargs = {}

        self.mission_time = None

    def set_failure_dist(self, dist, *args, **kwargs):
        """
        Set the failure time distribution.

        Parameters:
            dist: distribution name (str) or a callable that returns a
                  random variate generator. Built-in names: 'exponential',
                  'weibull', 'weibull_min', 'weibull_grp', 'weibull_grp2',
                  'lognormal', 'normal', 'gamma'.
            *args, **kwargs: parameters passed to the distribution factory.
        """
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
        self.failure_args = args
        self.failure_kwargs = kwargs

    def set_repair_dist(self, dist, *args, **kwargs):
        """
        Set the repair time distribution.

        Parameters:
            dist: distribution name (str) or a callable that returns a
                  random variate generator. Same options as set_failure_dist.
            *args, **kwargs: parameters passed to the distribution factory.
        """
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
        self.repair_args = args
        self.repair_kwargs = kwargs

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
        return self.failure_dist()

    def generate_repair(self):
        return self.repair_dist()

    def simulate(self, reps=1):
        """
        Run the failure-repair simulation.

        Parameters:
            reps: number of Monte Carlo replications.

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

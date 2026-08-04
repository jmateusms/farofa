import heapq
from collections import deque

import numpy as np

from .distributions import (
    exponential, weibull, weibull_min, weibull_grp, weibull_grp2,
    lognormal, normal, gamma,
)
from .results import FleetSimulationResult
from .utils import draw_positive

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

_FAILURE = 0
_REPAIR_DONE = 1


class Fleet:
    """
    A homogeneous fleet of repairable devices sharing a pool of maintenance teams.

    All devices follow the same failure and repair distributions but maintain
    independent state (e.g., GRP virtual age). When a device fails and no team
    is available, it joins a FIFO queue; the first free team starts the repair.

    Usage:
        fleet = Fleet(n_devices=10, n_teams=2)
        fleet.set_failure_dist('weibull_grp', 100.0, 2.0, 0.5)
        fleet.set_repair_dist('exponential', 0.1)
        fleet.set_mission_time(8760)
        result = fleet.simulate(reps=100)
        print(result)
    """

    def __init__(self, n_devices=1, n_teams=1):
        if not isinstance(n_devices, int) or n_devices <= 0:
            raise ValueError('n_devices must be a positive integer.')
        if not isinstance(n_teams, int) or n_teams <= 0:
            raise ValueError('n_teams must be a positive integer.')

        self.n_devices = n_devices
        self.n_teams = n_teams

        self._failure_spec = None
        self._repair_spec = None
        self.mission_time = None

    def _resolve_spec(self, dist, args, kwargs):
        if callable(dist):
            factory = dist
        elif isinstance(dist, str):
            if dist not in DISTRIBUTIONS:
                raise ValueError(
                    f"Unknown distribution '{dist}'. "
                    f"Available: {', '.join(DISTRIBUTIONS.keys())}"
                )
            factory = DISTRIBUTIONS[dist]
        else:
            raise TypeError('dist must be a string name or a callable.')
        return (factory, args, kwargs)

    def set_failure_dist(self, dist, *args, **kwargs):
        """Set the failure time distribution shared by all devices."""
        self._failure_spec = self._resolve_spec(dist, args, kwargs)

    def set_repair_dist(self, dist, *args, **kwargs):
        """Set the repair time distribution shared by all devices."""
        self._repair_spec = self._resolve_spec(dist, args, kwargs)

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

    def _instantiate_samplers(self, spec, n):
        # Stateful samplers (have .reset) need one instance per device so that
        # virtual ages stay independent. Stateless samplers can be shared.
        factory, args, kwargs = spec
        first = factory(*args, **kwargs)
        if hasattr(first, 'reset'):
            return [first] + [factory(*args, **kwargs) for _ in range(n - 1)]
        return [first] * n

    def simulate(self, reps=1):
        """
        Run the fleet failure-repair simulation.

        Parameters:
            reps: number of Monte Carlo replications.

        Returns:
            FleetSimulationResult with per-device and fleet-level metrics.
        """
        if not isinstance(reps, int):
            try:
                reps = int(reps)
            except (TypeError, ValueError):
                raise ValueError('reps must be an integer or convertible to integer.')
        if reps <= 0:
            raise ValueError('reps must be greater than 0.')
        if self._failure_spec is None:
            raise ValueError('Failure distribution not set. Call set_failure_dist() first.')
        if self._repair_spec is None:
            raise ValueError('Repair distribution not set. Call set_repair_dist() first.')
        if self.mission_time is None:
            raise ValueError('Mission time not set. Call set_mission_time() first.')

        T = self.mission_time
        N = self.n_devices
        K = self.n_teams

        failure_samplers = self._instantiate_samplers(self._failure_spec, N)
        repair_samplers = self._instantiate_samplers(self._repair_spec, N)

        all_failure_counts = np.zeros((reps, N), dtype=np.int64)
        all_repair_counts = np.zeros((reps, N), dtype=np.int64)
        all_device_uptime = np.zeros((reps, N))
        all_device_downtime = np.zeros((reps, N))
        all_busy_team_hours = np.zeros(reps)
        all_max_queue = np.zeros(reps, dtype=np.int64)
        all_wait_times = []

        for r in range(reps):
            # Reset any stateful samplers between reps. The dedup avoids resetting
            # a shared stateless sampler N times (harmless, but wasteful).
            for s in {id(s): s for s in failure_samplers + repair_samplers}.values():
                if hasattr(s, 'reset'):
                    s.reset()

            device_failures = np.zeros(N, dtype=np.int64)
            device_repairs = np.zeros(N, dtype=np.int64)
            device_uptime = np.zeros(N)
            device_downtime = np.zeros(N)
            operational = np.ones(N, dtype=bool)
            state_since = np.zeros(N)
            team_busy = 0
            queue = deque()
            wait_times = []
            max_queue = 0

            heap = []
            counter = 0
            for d in range(N):
                ttf = draw_positive(failure_samplers[d], 'failure')
                heapq.heappush(heap, (ttf, counter, _FAILURE, d))
                counter += 1

            busy_team_hours = 0.0
            t_prev = 0.0

            while heap:
                t, _, kind, d = heapq.heappop(heap)
                if t >= T:
                    break

                busy_team_hours += team_busy * (t - t_prev)
                t_prev = t

                if kind == _FAILURE:
                    device_uptime[d] += t - state_since[d]
                    state_since[d] = t
                    operational[d] = False
                    device_failures[d] += 1

                    if team_busy < K:
                        team_busy += 1
                        ttr = draw_positive(repair_samplers[d], 'repair')
                        heapq.heappush(heap, (t + ttr, counter, _REPAIR_DONE, d))
                        counter += 1
                        wait_times.append(0.0)
                    else:
                        queue.append((d, t))
                        if len(queue) > max_queue:
                            max_queue = len(queue)

                else:  # _REPAIR_DONE
                    device_downtime[d] += t - state_since[d]
                    state_since[d] = t
                    operational[d] = True
                    device_repairs[d] += 1
                    team_busy -= 1

                    if queue:
                        d_next, failed_at = queue.popleft()
                        wait_times.append(t - failed_at)
                        team_busy += 1
                        ttr = draw_positive(repair_samplers[d_next], 'repair')
                        heapq.heappush(heap, (t + ttr, counter, _REPAIR_DONE, d_next))
                        counter += 1

                    ttf = draw_positive(failure_samplers[d], 'failure')
                    if t + ttf < T:
                        heapq.heappush(heap, (t + ttf, counter, _FAILURE, d))
                        counter += 1

            busy_team_hours += team_busy * (T - t_prev)
            for d in range(N):
                if operational[d]:
                    device_uptime[d] += T - state_since[d]
                else:
                    device_downtime[d] += T - state_since[d]

            all_failure_counts[r] = device_failures
            all_repair_counts[r] = device_repairs
            all_device_uptime[r] = device_uptime
            all_device_downtime[r] = device_downtime
            all_busy_team_hours[r] = busy_team_hours
            all_max_queue[r] = max_queue
            all_wait_times.append(np.array(wait_times))

        return FleetSimulationResult(
            mission_time=T,
            n_devices=N,
            n_teams=K,
            failure_counts=all_failure_counts,
            repair_counts=all_repair_counts,
            device_uptime=all_device_uptime,
            device_downtime=all_device_downtime,
            busy_team_hours=all_busy_team_hours,
            max_queue=all_max_queue,
            wait_times=all_wait_times,
        )

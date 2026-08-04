import numpy as np


class SimulationResult:
    """
    Stores and summarizes results from a failure-repair simulation.

    Attributes:
        mission_time: the mission time used in the simulation
        reps: number of replications
        failure_counts: array of failure counts per replication
        repair_counts: array of repair counts per replication
        uptimes: list of arrays, each containing uptimes (times to failure) per replication
        downtimes: list of arrays, each containing downtimes (times to repair) per replication
        total_uptime: array of total uptime per replication
        total_downtime: array of total downtime per replication
    """

    def __init__(self, mission_time, failure_counts, repair_counts,
                 uptimes, downtimes, total_uptime, total_downtime):
        self.mission_time = mission_time
        self.reps = len(failure_counts)
        self.failure_counts = np.array(failure_counts)
        self.repair_counts = np.array(repair_counts)
        self.uptimes = uptimes
        self.downtimes = downtimes
        self.total_uptime = np.array(total_uptime)
        self.total_downtime = np.array(total_downtime)

    @property
    def availability(self):
        """Mean availability across replications (fraction of time operational)."""
        return np.mean(self.total_uptime / self.mission_time)

    @property
    def availability_per_rep(self):
        """Availability for each replication."""
        return self.total_uptime / self.mission_time

    @property
    def mean_failures(self):
        """Mean number of failures across replications."""
        return np.mean(self.failure_counts)

    @property
    def std_failures(self):
        """Standard deviation of failure counts across replications."""
        return np.std(self.failure_counts, ddof=1)

    @property
    def mttf(self):
        """Mean time to failure (averaged across all replications)."""
        all_ttf = np.concatenate(self.uptimes) if self.uptimes else np.array([])
        if len(all_ttf) == 0:
            return np.inf
        return np.mean(all_ttf)

    @property
    def mttr(self):
        """Mean time to repair (averaged across all replications)."""
        all_ttr = np.concatenate(self.downtimes) if self.downtimes else np.array([])
        if len(all_ttr) == 0:
            return 0.0
        return np.mean(all_ttr)

    @property
    def failure_rate(self):
        """Mean failure rate (failures per unit time)."""
        return self.mean_failures / self.mission_time

    def summary(self):
        """Return a dictionary with all summary metrics."""
        return {
            'mission_time': self.mission_time,
            'replications': self.reps,
            'mean_failures': self.mean_failures,
            'std_failures': self.std_failures,
            'mean_repairs': np.mean(self.repair_counts),
            'mttf': self.mttf,
            'mttr': self.mttr,
            'availability': self.availability,
            'failure_rate': self.failure_rate,
        }

    def __repr__(self):
        s = self.summary()
        lines = [
            f"SimulationResult ({s['replications']} replications, T={s['mission_time']})",
            f"  Mean failures:  {s['mean_failures']:.4f} (std: {s['std_failures']:.4f})",
            f"  MTTF:           {s['mttf']:.4f}",
            f"  MTTR:           {s['mttr']:.4f}",
            f"  Availability:   {s['availability']:.6f}",
            f"  Failure rate:   {s['failure_rate']:.6f}",
        ]
        return '\n'.join(lines)


class FleetSimulationResult:
    """
    Stores and summarizes results from a fleet-level failure-repair simulation.

    Attributes:
        mission_time: mission time used in the simulation
        n_devices: number of devices in the fleet
        n_teams: number of maintenance teams
        reps: number of replications
        failure_counts: (reps, n_devices) array of failure counts per device per rep
        repair_counts: (reps, n_devices) array of completed repairs per device per rep
        device_uptime: (reps, n_devices) array of operational time per device per rep
        device_downtime: (reps, n_devices) array of down time (waiting + being repaired)
        busy_team_hours: (reps,) array of total team-busy time per rep
        max_queue: (reps,) array of the largest queue length observed per rep
        wait_times: list of length reps; each entry is an array of per-repair wait times
    """

    def __init__(self, mission_time, n_devices, n_teams,
                 failure_counts, repair_counts,
                 device_uptime, device_downtime,
                 busy_team_hours, max_queue, wait_times):
        self.mission_time = mission_time
        self.n_devices = n_devices
        self.n_teams = n_teams
        self.reps = len(failure_counts)
        self.failure_counts = np.asarray(failure_counts)
        self.repair_counts = np.asarray(repair_counts)
        self.device_uptime = np.asarray(device_uptime)
        self.device_downtime = np.asarray(device_downtime)
        self.busy_team_hours = np.asarray(busy_team_hours)
        self.max_queue = np.asarray(max_queue)
        self.wait_times = wait_times

    @property
    def fleet_availability(self):
        """Mean fraction of device-hours operational across the fleet."""
        return float(np.mean(self.device_uptime.sum(axis=1) / (self.n_devices * self.mission_time)))

    @property
    def availability_per_rep(self):
        """Fleet availability for each replication."""
        return self.device_uptime.sum(axis=1) / (self.n_devices * self.mission_time)

    @property
    def per_device_availability(self):
        """Mean availability per device, averaged across replications. Shape (n_devices,)."""
        return self.device_uptime.mean(axis=0) / self.mission_time

    @property
    def server_utilization(self):
        """Mean fraction of team-hours spent repairing (busy time / available team time)."""
        return float(np.mean(self.busy_team_hours / (self.n_teams * self.mission_time)))

    @property
    def mean_failures(self):
        """Mean total failures across the fleet per replication."""
        return float(self.failure_counts.sum(axis=1).mean())

    @property
    def mean_repairs(self):
        """Mean total completed repairs across the fleet per replication."""
        return float(self.repair_counts.sum(axis=1).mean())

    @property
    def mean_wait_time(self):
        """Mean wait time before repair starts, averaged over all repairs that started."""
        if not any(len(w) for w in self.wait_times):
            return 0.0
        all_waits = np.concatenate(self.wait_times)
        return float(all_waits.mean())

    @property
    def max_queue_observed(self):
        """Largest queue length seen across all replications."""
        return int(self.max_queue.max())

    def summary(self):
        """Return a dictionary with all summary metrics."""
        return {
            'mission_time': self.mission_time,
            'n_devices': self.n_devices,
            'n_teams': self.n_teams,
            'replications': self.reps,
            'mean_failures': self.mean_failures,
            'mean_repairs': self.mean_repairs,
            'fleet_availability': self.fleet_availability,
            'server_utilization': self.server_utilization,
            'mean_wait_time': self.mean_wait_time,
            'max_queue_observed': self.max_queue_observed,
        }

    def __repr__(self):
        s = self.summary()
        lines = [
            f"FleetSimulationResult (N={s['n_devices']}, K={s['n_teams']}, "
            f"{s['replications']} replications, T={s['mission_time']})",
            f"  Mean fleet failures:  {s['mean_failures']:.4f}",
            f"  Mean fleet repairs:   {s['mean_repairs']:.4f}",
            f"  Fleet availability:   {s['fleet_availability']:.6f}",
            f"  Server utilization:   {s['server_utilization']:.6f}",
            f"  Mean wait time:       {s['mean_wait_time']:.4f}",
            f"  Max queue observed:   {s['max_queue_observed']}",
        ]
        return '\n'.join(lines)

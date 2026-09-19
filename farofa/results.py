import json
from pathlib import Path
from statistics import NormalDist

import numpy as np


def mean_confidence_interval(values, confidence=0.95, *, lower=None, upper=None):
    """Normal-approximation confidence interval for a replication mean.

    ``values`` must contain one scalar outcome from each independent Monte
    Carlo replication.  It deliberately does not accept device-level values
    from a fleet: devices can share a repair queue and are therefore not
    independent observations.  With fewer than two replications the sampling
    variance is unavailable and both endpoints are ``nan``.

    The interval is ``mean ± z * s / sqrt(R)``, where ``s`` is the sample
    standard deviation (``ddof=1``).  It quantifies Monte Carlo sampling
    error only; it does not correct finite-horizon censoring or model error.
    Optional bounds clip endpoints for bounded estimands such as availability.
    """
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise TypeError('confidence must be a finite number between 0 and 1.')
    confidence = float(confidence)
    if not np.isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError('confidence must be a finite number between 0 and 1.')

    values = np.asarray(values, dtype=float)
    if values.ndim != 1:
        raise ValueError('values must be a one-dimensional array of replication outcomes.')
    if not np.all(np.isfinite(values)):
        raise ValueError('values must be finite.')

    def validate_bound(name, value):
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f'{name} must be a finite number or None.')
        value = float(value)
        if not np.isfinite(value):
            raise ValueError(f'{name} must be a finite number or None.')
        return value

    lower = validate_bound('lower', lower)
    upper = validate_bound('upper', upper)
    if lower is not None and upper is not None and lower > upper:
        raise ValueError('lower must not exceed upper.')
    if values.size < 2:
        return (np.nan, np.nan)

    mean = float(values.mean())
    # For a representable confidence just below 1, 0.5 + c/2 can round to
    # exactly 1. Clamp to the largest representable probability below it.
    probability = min(0.5 + confidence / 2.0, np.nextafter(1.0, 0.0))
    z = NormalDist().inv_cdf(probability)
    half_width = z * float(values.std(ddof=1)) / np.sqrt(values.size)
    lo, hi = mean - half_width, mean + half_width
    if lower is not None:
        lo = max(lower, lo)
    if upper is not None:
        hi = min(upper, hi)
    return (float(lo), float(hi))


def _json_safe(value):
    """Return JSON values, representing unavailable numeric estimates as null."""
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _export_json(payload, path):
    """Write a portable result payload and return the destination path."""
    destination = Path(path)
    destination.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return destination


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

    def availability_confidence_interval(self, confidence=0.95):
        """Confidence interval for finite-horizon availability across reps.

        The observation is each replication's ``uptime / mission_time``. The
        normal approximation describes Monte Carlo error, while failure or
        repair intervals crossing the mission boundary remain right-censored
        by the model's established ``[0, T)`` convention.
        """
        return mean_confidence_interval(
            self.availability_per_rep, confidence, lower=0.0, upper=1.0
        )

    @property
    def total_failures_per_rep(self):
        """Total failures in each replication (one device equals the total)."""
        return self.failure_counts.astype(float)

    def failure_count_confidence_interval(self, confidence=0.95):
        """Confidence interval for mean total failures per replication.

        The normal approximation describes Monte Carlo error of the finite
        mission count. It does not extrapolate failures censored at ``T``.
        """
        return mean_confidence_interval(
            self.total_failures_per_rep, confidence, lower=0.0
        )

    @property
    def mean_failures(self):
        """Mean number of failures across replications."""
        return np.mean(self.failure_counts)

    @property
    def std_failures(self):
        """Standard deviation of failure counts across replications (nan if reps < 2)."""
        if self.reps < 2:
            return np.nan
        return np.std(self.failure_counts, ddof=1)

    @property
    def mttf(self):
        """Mean time to failure: total operating time / total failures (renewal estimator).

        Completed intervals alone omit mission-end censoring and can underrepresent
        long intervals. This exposure/count ratio includes censored operating time,
        but is not generally unbiased in finite samples: a ratio of expectations
        is not the expectation of a ratio, even with exponential failures.

        For a regenerative renewal model with iid lifetimes and perfect repairs,
        the ratio converges to the lifetime mean over a sufficiently long horizon.
        Finite-window error depends on the failure law, horizon and number of
        replications. With imperfect repair or nonstationary hazards, interpret it
        as observed exposure per failure, not a distributional mean lifetime.

        Raw completed intervals remain available in `.uptimes`.
        Returns nan if no failures were observed.
        """
        total_failures = self.failure_counts.sum()
        if total_failures == 0:
            return np.nan
        return float(self.total_uptime.sum() / total_failures)

    @property
    def mttr(self):
        """Mean time to repair: total repair time / total completed repairs (renewal estimator).

        Same rationale and finite-window caveat as `mttf` (negligible in
        practice while MTTR << mission time). The numerator includes time
        spent in a repair still in progress at mission end. Raw completed
        repair durations remain available in `.downtimes`.

        Returns nan if no repairs were completed.
        """
        total_repairs = self.repair_counts.sum()
        if total_repairs == 0:
            return np.nan
        return float(self.total_downtime.sum() / total_repairs)

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

    def to_dict(self, confidence=0.95):
        """Return a JSON-serializable finite-horizon result export.

        Per-replication values are retained so a consumer can recompute the
        documented normal-approximation intervals. Unavailable estimates (for
        example an interval with fewer than two replications) are ``null`` in
        this export; the numerical API continues to return ``numpy.nan``.
        """
        return _json_safe({
            'schema_version': 1,
            'result_kind': 'simple_device',
            'summary': self.summary(),
            'confidence': confidence,
            'confidence_intervals': {
                'availability': list(self.availability_confidence_interval(confidence)),
                'failure_count': list(self.failure_count_confidence_interval(confidence)),
            },
            'replications': {
                'availability': self.availability_per_rep.tolist(),
                'failure_counts': self.failure_counts.tolist(),
                'repair_counts': self.repair_counts.tolist(),
                'total_uptime': self.total_uptime.tolist(),
                'total_downtime': self.total_downtime.tolist(),
            },
        })

    def export_json(self, path, confidence=0.95):
        """Write :meth:`to_dict` as UTF-8 JSON and return its ``Path``."""
        return _export_json(self.to_dict(confidence), path)

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

    def availability_confidence_interval(self, confidence=0.95):
        """Confidence interval for fleet availability across replications.

        One replication-wide device-hour fraction is one observation. Devices
        within a replication are correlated whenever they share maintenance
        teams, so treating them as independent would understate uncertainty.
        The interval quantifies Monte Carlo error only; events unfinished at
        the mission boundary are censored under the existing ``[0, T)`` rule.
        """
        return mean_confidence_interval(
            self.availability_per_rep, confidence, lower=0.0, upper=1.0
        )

    @property
    def total_failures_per_rep(self):
        """Total fleet failures in each replication, across all devices."""
        return self.failure_counts.sum(axis=1).astype(float)

    def failure_count_confidence_interval(self, confidence=0.95):
        """Confidence interval for mean total fleet failures per replication.

        One whole-fleet count is an observation; device counts in a shared
        queue are not independent. Counts at the finite mission boundary are
        subject to the established ``[0, T)`` censoring convention.
        """
        return mean_confidence_interval(
            self.total_failures_per_rep, confidence, lower=0.0
        )

    @property
    def per_device_availability(self):
        """Mean availability per device, averaged across replications. Shape (n_devices,)."""
        return self.device_uptime.mean(axis=0) / self.mission_time

    @property
    def server_utilization(self):
        """Mean fraction of team-hours spent repairing (busy time / available team time)."""
        return float(np.mean(self.busy_team_hours / (self.n_teams * self.mission_time)))

    @property
    def server_utilization_per_rep(self):
        """Busy team-hours divided by available team-hours in each replication."""
        return self.busy_team_hours / (self.n_teams * self.mission_time)

    def server_utilization_confidence_interval(self, confidence=0.95):
        """Confidence interval for mean finite-horizon team utilization.

        A replication-wide busy-hours fraction is the observation. Ongoing
        repairs contribute only their busy time up to mission end.
        """
        return mean_confidence_interval(
            self.server_utilization_per_rep, confidence, lower=0.0, upper=1.0
        )

    @property
    def mean_failures(self):
        """Mean total failures across the fleet per replication."""
        return float(self.failure_counts.sum(axis=1).mean())

    @property
    def mean_repairs(self):
        """Mean total completed repairs across the fleet per replication."""
        return float(self.repair_counts.sum(axis=1).mean())

    @property
    def mttf(self):
        """Mean time to failure: total device operating time / total failures.

        Renewal estimator over the whole fleet — see SimulationResult.mttf for
        why naive interval averaging is length-biased, and for the finite-window
        caveat with non-exponential lifetimes. Returns nan if no failures were
        observed.
        """
        total_failures = self.failure_counts.sum()
        if total_failures == 0:
            return np.nan
        return float(self.device_uptime.sum() / total_failures)

    @property
    def mttr(self):
        """Mean active repair time per completed repair.

        Uses total team-busy time (active repair only) over completed repairs.
        Note this excludes queue waiting time: a device's downtime is
        wait + repair, so mean downtime per failure typically exceeds mttr
        when repairs queue (end-of-mission censoring can perturb the exact
        comparison). Returns nan if no repairs were completed.
        """
        total_repairs = self.repair_counts.sum()
        if total_repairs == 0:
            return np.nan
        return float(self.busy_team_hours.sum() / total_repairs)

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
            'mttf': self.mttf,
            'mttr': self.mttr,
            'fleet_availability': self.fleet_availability,
            'server_utilization': self.server_utilization,
            'mean_wait_time': self.mean_wait_time,
            'max_queue_observed': self.max_queue_observed,
        }

    def to_dict(self, confidence=0.95):
        """Return a JSON-serializable finite-horizon fleet result export.

        Per-replication fleet metrics are the statistical observations. Device
        rows are also exported for diagnosis, but must not be treated as
        independent observations when teams are shared.
        """
        return _json_safe({
            'schema_version': 1,
            'result_kind': 'fleet',
            'summary': self.summary(),
            'confidence': confidence,
            'confidence_intervals': {
                'availability': list(self.availability_confidence_interval(confidence)),
                'failure_count': list(self.failure_count_confidence_interval(confidence)),
                'server_utilization': list(self.server_utilization_confidence_interval(confidence)),
            },
            'replications': {
                'availability': self.availability_per_rep.tolist(),
                'failure_counts': self.failure_counts.tolist(),
                'repair_counts': self.repair_counts.tolist(),
                'device_uptime': self.device_uptime.tolist(),
                'device_downtime': self.device_downtime.tolist(),
                'busy_team_hours': self.busy_team_hours.tolist(),
                'server_utilization': self.server_utilization_per_rep.tolist(),
                'max_queue': self.max_queue.tolist(),
                'wait_times': [wait.tolist() for wait in self.wait_times],
            },
        })

    def export_json(self, path, confidence=0.95):
        """Write :meth:`to_dict` as UTF-8 JSON and return its ``Path``."""
        return _export_json(self.to_dict(confidence), path)

    def __repr__(self):
        s = self.summary()
        lines = [
            f"FleetSimulationResult (N={s['n_devices']}, K={s['n_teams']}, "
            f"{s['replications']} replications, T={s['mission_time']})",
            f"  Mean fleet failures:  {s['mean_failures']:.4f}",
            f"  Mean fleet repairs:   {s['mean_repairs']:.4f}",
            f"  MTTF:                 {s['mttf']:.4f}",
            f"  MTTR (active):        {s['mttr']:.4f}",
            f"  Fleet availability:   {s['fleet_availability']:.6f}",
            f"  Server utilization:   {s['server_utilization']:.6f}",
            f"  Mean wait time:       {s['mean_wait_time']:.4f}",
            f"  Max queue observed:   {s['max_queue_observed']}",
        ]
        return '\n'.join(lines)

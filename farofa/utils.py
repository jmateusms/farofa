import math

import numpy as np


def spawn_seed_sequence(seed, n_children):
    """Derive ``n_children`` independent SeedSequences from ``seed`` without
    mutating a caller-supplied SeedSequence.

    ``SeedSequence.spawn`` advances the parent's internal child counter, so
    spawning directly from a user's object would make a second run with the
    same instance draw different children — silently breaking the
    reproducibility promise, and shifting streams for any other consumer of
    that object. We therefore spawn from a pristine clone: the children are
    always children 0..n-1 of the given sequence. (If you also spawn from the
    same SeedSequence yourself, avoid reusing its first ``n_children``
    children elsewhere.)
    """
    if isinstance(seed, np.random.SeedSequence):
        ss = np.random.SeedSequence(entropy=seed.entropy, spawn_key=seed.spawn_key,
                                    pool_size=seed.pool_size)
    else:
        ss = np.random.SeedSequence(seed)
    return ss.spawn(n_children)


def validate_mission_time(mission_time):
    """Return a finite, strictly positive mission duration as ``float``."""
    if isinstance(mission_time, (bool, np.bool_)):
        raise TypeError('Mission time must be a number.')
    try:
        mission_time = float(mission_time)
    except (TypeError, ValueError, OverflowError) as e:
        raise TypeError('Mission time must be a number.') from e
    if not math.isfinite(mission_time) or mission_time <= 0.0:
        raise ValueError('Mission time must be finite and greater than 0.')
    return mission_time


def validate_reps(reps):
    """Return a strictly positive whole number of Monte Carlo replications.

    Exact integral values such as ``2.0`` and ``"2"`` remain accepted for
    backwards compatibility. Fractional, non-finite, and boolean inputs are
    rejected instead of silently truncating a requested simulation.
    """
    if isinstance(reps, (bool, np.bool_)):
        raise ValueError('reps must be a positive integer.')
    if isinstance(reps, (int, np.integer)):
        value = int(reps)
    else:
        try:
            numeric = float(reps)
        except (TypeError, ValueError, OverflowError) as e:
            raise ValueError('reps must be a positive integer.') from e
        if not math.isfinite(numeric) or not numeric.is_integer():
            raise ValueError('reps must be a positive integer.')
        value = int(numeric)
    if value <= 0:
        raise ValueError('reps must be a positive integer.')
    return value


def validate_trace(trace):
    """Return how many leading replications to record in the event log.

    ``0`` (the default) records nothing. Values larger than ``reps`` simply
    record every replication. Same integer rules as :func:`validate_reps`.
    """
    if isinstance(trace, (bool, np.bool_)):
        raise ValueError('trace must be a non-negative integer.')
    if isinstance(trace, (int, np.integer)):
        value = int(trace)
    else:
        try:
            numeric = float(trace)
        except (TypeError, ValueError, OverflowError) as e:
            raise ValueError('trace must be a non-negative integer.') from e
        if not math.isfinite(numeric) or not numeric.is_integer():
            raise ValueError('trace must be a non-negative integer.')
        value = int(numeric)
    if value < 0:
        raise ValueError('trace must be a non-negative integer.')
    return value


def validate_progress(progress):
    """Return ``progress`` if it is ``None`` or callable; raise otherwise."""
    if progress is not None and not callable(progress):
        raise TypeError('progress must be a callable progress(done, reps) or None.')
    return progress


def draw_positive(sampler, role):
    """Draw one variate and enforce strictly positive, finite support.

    Failure/repair times <= 0 would stall or run simulated time backwards
    (silently corrupting every time-integral metric), so any distribution —
    including user-supplied callables — is validated at the engine boundary.
    """
    x = float(sampler())
    if not 0.0 < x < math.inf:  # also rejects nan
        raise ValueError(
            f'{role} distribution produced a non-positive or non-finite '
            f'time ({x!r}); failure/repair times must be strictly positive '
            f'and finite.'
        )
    return x

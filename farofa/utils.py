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

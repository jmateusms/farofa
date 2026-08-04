import math


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

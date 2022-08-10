import numpy as np
from numba import njit, float64
from .utils import safe_random

@njit(float64(float64))
def exponential(rate):
    '''
    Generates an exponentially distributed random time.

    Input:
        - rate: rate of failures/events per time unit ("lambda").

    Output:
        - x: time until the next event/failiure
    '''
    u = safe_random()
    
    x = -np.log(u) / rate
    
    return x

@njit(float64(float64, float64))
def weibull(a, b):
    '''
    Generates a Weibull distributed random time. Considers perfect repair
    (device age is not considered).
    This is equivalent to weibull_grp when q = 0.

    Inputs:
        - a: Weibull scale parameter
        - b: Weibull shape parameter

    Output:
        - x: time until the next event/failiure
    '''
    u = safe_random()

    x =  a * (-np.log(u)) ** (1 / b)

    return x

@njit(float64(float64, float64, float64))
def weibull_min(t, a, b):
    '''
    Generates a Weibull distributed random time. Considers minimal repair
    (device age is considered).
    This is equivalent to weibull_grp when q = 1.

    Inputs:
        - t: device age.
        - a: Weibull scale parameter
        - b: Weibull shape parameter

    Output:
        - x: time until the next event/failiure
    '''

    u = safe_random()

    x =  a * (((t / a) ** b) - np.log(u)) ** (1 / b) - t

    return x

@njit(float64(float64, float64, float64, float64))
def weibull_grp(t,a,b,q=None):
    '''
    Generate Weibull distributed time conditioned to virtual age (Kijima Type I GRP).
    
    Inputs:
        - t: If q is not given, t is the virtual age. If q is given, t is the real age.
            (virtual age = q*t)
        - a: Weibull scale parameter
        - b: Weibull shape parameter
        - q: GRP repair effectiveness

    Output:
        - x: time until the next event/failiure
    '''

    if q is not None:
        w = q * t
    else:
        w = t

    u = safe_random()

    return a * (((w / a) ** b) - np.log(u)) ** (1 / b) - w

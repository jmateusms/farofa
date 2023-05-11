from sys import float_info
from numpy.random import random
from numba import njit, float64

# parameters
fpmin = float_info.min
fpmax = float_info.max

# functions
@njit(float64())
def safe_random():
    u = random()
    while u < fpmin or u == 1:
        u = random()
    return u

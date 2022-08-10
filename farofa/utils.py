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

# classes
class use_numba: # WIP
    '''
    This class is a WIP, for now.
    Its idea is to allow the user to choose whether to use numba or not.
    '''
    def __init__(self, use_numba=True, fastmath=True, parallel=False):
        self.use_numba = use_numba
        self.fastmath = fastmath
        self.parallel = parallel
    
    def __call__(self, func, *args, **kwargs):
        if self.use_numba:
            @njit(fastmath=self.fastmath, parallel=self.parallel)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        else:
            return func

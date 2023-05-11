import numpy as np
from numba import njit, int64, float64

from .distributions import exponential, weibull, weibull_min, weibull_grp

class single_device: # improve name?
    '''
    Simulate a single device, using chosen failure and repair time generators.
    '''

    def __init__(self, fail_gen, repair_gen):
        if type(fail_gen) == str:
            if fail_gen.lower() in ['exp', 'exponential']:
                self.fail_gen = exponential
                self.fail_dist = 'exponential'
            elif fail_gen.lower() in ['weib', 'weibull']:
                self.fail_gen = weibull
                self.fail_dist = 'weibull'
            elif fail_gen.lower() in ['weib_min', 'weibull_min']:
                self.fail_gen = weibull_min
                self.fail_dist = 'weibull_min'
            elif fail_gen.lower() in ['weib_grp', 'weibull_grp']:
                self.fail_gen = weibull_grp
                self.fail_dist = 'weibull_grp'
            else:
                raise ValueError('Invalid failure generator.')
        else:
            raise ValueError('Invalid failure generator.')
        
        if type(repair_gen) == str:
            if repair_gen.lower() in ['exp', 'exponential']:
                self.repair_gen = exponential
                self.repair_dist = 'exponential'
            elif repair_gen.lower() in ['weib', 'weibull']:
                self.repair_gen = weibull
                self.repair_dist = 'weibull'
            elif repair_gen.lower() in ['weib_min', 'weibull_min']:
                self.repair_gen = weibull_min
                self.repair_dist = 'weibull_min'
            elif repair_gen.lower() in ['weib_grp', 'weibull_grp']:
                self.repair_gen = weibull_grp
                self.repair_dist = 'weibull_grp'
            else:
                raise ValueError('Invalid repair generator.')
        else:
            raise ValueError('Invalid repair generator.')
        
        print(f'Failure and repair time generators set as {self.fail_dist} and {self.repair_dist}.')
    
    def set_fail_parameters(self, *args, **kwargs):
        try:
            _ = self.fail_gen(*args, **kwargs)
            self.fail_args = args
            self.fail_kwargs = kwargs
            print('Failure parameters set.')
        except Exception as e:
            print(e)
            raise ValueError('Invalid failure parameters.')
    
    def set_repair_parameters(self, *args, **kwargs):
        try:
            _ = self.repair_gen(*args, **kwargs)
            self.repair_args = args
            self.repair_kwargs = kwargs
            print('Repair parameters set.')
        except Exception as e:
            print(e)
            raise ValueError('Invalid repair parameters.')
    
    def simulate(self, T, reps=1): # TODO: use a numba function for the whole loop
        '''
        Simulate single device for the specified mission time `T`.
        '''
        failures = np.zeros(reps)

        for i in range(reps):
            t = 0
            state = 1 # 1 = operational, 0 = failed
            
            while t < T or state == 0:
                if state == 1:
                    t += self.fail_gen(*self.fail_args, **self.fail_kwargs)
                    state = 0
                    failures[i] += 1
                else:
                    t += self.repair_gen(*self.repair_args, **self.repair_kwargs)
                    state = 1
        
        return failures
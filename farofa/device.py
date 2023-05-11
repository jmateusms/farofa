from .distributions import exponential, weibull, weibull_min, weibull_grp

distributions = {
    'exponential': exponential,
    'weibull': weibull,
    'weibull_min': weibull_min,
    'weibull_grp': weibull_grp
}

class simple_device:
    def __init__(self):
        self.operational = True
    
    def set_failure_dist(self, dist_name, *args, **kwargs):
        self.failure_dist = distributions[dist_name](*args, **kwargs)
        self.failure_args = args
        self.failure_kwargs = kwargs

        _ = self.failure_dist(*args, **kwargs)
    
    def set_repair_dist(self, dist_name, *args, **kwargs):
        self.repair_dist = distributions[dist_name](*args, **kwargs)
        self.repair_args = args
        self.repair_kwargs = kwargs

        _ = self.repair_dist(*args, **kwargs)
    
    def set_mission_time(self, mission_time):
        if not type(mission_time) == float:
            try:
                mission_time = float(mission_time)
            except Exception as e:
                print(e)
                raise TypeError('Mission time must be a number.')
        if mission_time < 1:
            raise ValueError('Mission time must be greater than 0.')
        self.mission_time = mission_time
    
    def generate_failure(self):
        return self.failure_dist(*self.failure_args, **self.failure_kwargs)
    
    def generate_repair(self):
        return self.repair_dist(*self.repair_args, **self.repair_kwargs)

    def failure(self):
        self.operational = False

    def repair(self):
        self.operational = True
    
    def simulate(self, reps=1):
        if not type(reps) == int:
            raise ValueError('Number of replications must be an integer.')
        if reps < 1:
            raise ValueError('Number of replications must be greater than 0.')
        if not hasattr(self, 'failure_dist'):
            raise ValueError('Failure distribution not set.')
        if not hasattr(self, 'repair_dist'):
            raise ValueError('Repair distribution not set.')
        if not hasattr(self, 'mission_time'):
            raise ValueError('Mission time not set.')

        failures_list = []

        for i in range(reps):
            t = 0
            T = self.mission_time
            failures = 0
            repairs = 0
            while t < T:
                if self.operational:
                    ttf = self.generate_failure()
                    if ttf < T:
                        failures += 1
                    t += ttf
                    self.failure()
                else:
                    ttr = self.generate_repair()
                    if ttr < T:
                        repairs += 1
                    t += ttr
                    self.repair()

            failures_list.append(failures)

        return failures_list

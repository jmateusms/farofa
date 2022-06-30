import farofa
import timeit

_ = farofa.weibull_grp(100, 100, 1.2, q=0.8) # "force" compilation by numba

t_numba = timeit.Timer(lambda: farofa.weibull_grp(100, 100, 1.2, q=0.8))

print('Avg. time:', t_numba.timeit(number=100))

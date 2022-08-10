import farofa
from time import time

model = farofa.single_device('weibull', 'exponential')
model.set_fail_parameters(100, 1.2)
model.set_repair_parameters(0.1)

start = time()
failures = model.simulate(1000, 10000)
end = time()

print(f'Time: {end - start:.5f}s.')

print(f'Avg. failures: {sum(failures)/len(failures):.2f}')

import farofa
from time import time

device = farofa.simple_device()

device.set_failure_dist('exponential', 0.0001)
device.set_repair_dist('exponential', 0.01)
device.set_mission_time(8760)

failures_list = []

start = time()
failures = device.simulate(reps=10000)
end = time()

print(f'Time: {end - start:.5f}s.')

print(f'Avg. failures: {sum(failures)/len(failures):.2f}')

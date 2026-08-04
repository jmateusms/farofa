import farofa
from time import time

# Create a device with exponential failure and repair times
device = farofa.SimpleDevice()
device.set_failure_dist('exponential', 0.0001)  # rate = 0.0001 failures/hour
device.set_repair_dist('exponential', 0.01)      # rate = 0.01 repairs/hour
device.set_mission_time(8760)                     # 1 year in hours

# Run simulation (seed makes the run bit-for-bit reproducible)
start = time()
result = device.simulate(reps=10000, seed=42)
elapsed = time() - start

print(f'Time: {elapsed:.3f}s')
print()
print(result)

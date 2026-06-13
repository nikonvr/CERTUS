import sys
import os
import time
import cProfile
import pstats
import io
import numpy as np

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from certus_physics import PGlobalOptimizer, epsilon_to_nk
from certus_optim import SplinePWLObjective # Assuming SplinePWLObjective is available

def dummy_objective(x):
    # Simulate a heavy math operation like in TMM
    res = 0.0
    for i in range(100):
        res += np.sum(np.sin(x * i))
    return float(res)

def run_benchmark():
    bounds = [(1.0, 5.0) for _ in range(10)]
    
    print("Initializing PGlobalOptimizer...")
    optimizer = PGlobalOptimizer(
        objective=dummy_objective,
        bounds=bounds,
        n_workers=4
    )
    
    print("Running optimization with cProfile...")
    pr = cProfile.Profile()
    pr.enable()
    
    # Run optimization
    optimizer.optimize(max_iter=50)
    
    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumtime')
    ps.print_stats(30)
    
    print("--- CUMULATIVE TIME ---")
    print(s.getvalue())

if __name__ == '__main__':
    run_benchmark()

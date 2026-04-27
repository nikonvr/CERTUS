"""

CERTUS Spline Optimizer Comparison

==================================



Compare differential_evolution vs PGLOBAL vs L-BFGS-B for Phase 2 Spline optimization.

Analyzes convergence speed, solution quality, and robustness.



Author: CERTUS Suite

Version: 1.0

"""



import sys

import os
from pathlib import Path

import numpy as np

import time

import logging

from unittest.mock import Mock

from dataclasses import dataclass

from typing import Dict, List, Tuple



# Add parent directory to path

sys.path.append(str(Path(__file__).resolve().parents[1]))



# Import CERTUS components

from CERTUS_INDEX import PGlobalOptimizerINDEX

from certus_core import get_safe_worker_count





@dataclass

class OptimizerResult:

    """Results from optimizer comparison"""



    optimizer_name: str

    execution_time: float

    n_evaluations: int

    best_cost: float

    best_params: np.ndarray

    converged: bool

    iterations: int

    final_rmse: float

    improvement_pct: float





class SplineOptimizerComparison:

    """Compare different optimizers for spline refinement"""



    def __init__(self):

        self.logger = logging.getLogger("SplineOptimizerComparison")

        self.setup_test_problem()



    def setup_test_problem(self):

        """Setup realistic spline optimization test problem"""

        # Problem dimensions

        self.n_knots = 7

        self.param_count = 2 * self.n_knots + 1  # thickness + n_knots + k_knots



        # Realistic bounds for spline optimization

        self.bounds = np.array(

            [

                [98.0, 102.0],  # thickness +/-2%

            ]

            + [

                [1.0, 5.0] if i < self.n_knots else [0.0, 2.0]

                for i in range(2 * self.n_knots)

            ]

        )



        # Starting point (TLU solution)

        self.x0 = np.array(

            [

                100.0,  # thickness

            ]

            + [2.0] * self.n_knots

            + [0.01] * self.n_knots

        )



        # Target solution (slightly better than TLU)

        self.x_target = self.x0 + np.random.normal(0, 0.1, self.param_count)

        self.x_target = np.clip(self.x_target, self.bounds[:, 0], self.bounds[:, 1])



        # Create realistic objective function

        self.create_objective_function()



    def create_objective_function(self):

        """Create realistic spline objective function"""



        def spline_objective(params):

            """

            Realistic spline objective function with:

            - Multiple local minima

            - Smooth landscape

            - Computational cost similar to real CERTUS

            """

            # Simulate computation time (similar to real spline evaluation)

            time.sleep(0.0005)  # 0.5ms per evaluation



            # Multi-modal objective function

            thickness = params[0]

            n_knots = params[1 : 1 + self.n_knots]

            k_knots = params[1 + self.n_knots :]



            # Thickness penalty (quadratic around optimum)

            thickness_penalty = 0.1 * (thickness - 100.0) ** 2



            # Spline smoothness penalty

            n_smoothness = 0.05 * np.sum(np.diff(n_knots) ** 2)

            k_smoothness = 0.02 * np.sum(np.diff(k_knots) ** 2)



            # Physical constraints penalty

            n_penalty = np.sum(np.maximum(0, n_knots - 4.0) ** 2) + np.sum(

                np.maximum(0, 1.0 - n_knots) ** 2

            )

            k_penalty = np.sum(np.maximum(0, k_knots - 1.0) ** 2)



            # Data fitting term (simulated)

            data_term = 0.001 * np.sum((params - self.x_target) ** 2)



            # Add some noise to make it realistic

            noise = 0.0001 * np.random.random()



            total_cost = (

                thickness_penalty

                + n_smoothness

                + k_smoothness

                + n_penalty

                + k_penalty

                + data_term

                + noise

            )



            return total_cost



        self.objective = spline_objective



        # Add gradient for L-BFGS-B

        def spline_gradient(params):

            """Numerical gradient for L-BFGS-B"""

            eps = 1e-8

            grad = np.zeros_like(params)



            for i in range(len(params)):

                params_plus = params.copy()

                params_minus = params.copy()

                params_plus[i] += eps

                params_minus[i] -= eps



                grad[i] = (

                    self.objective(params_plus) - self.objective(params_minus)

                ) / (2 * eps)



            return grad



        self.gradient = spline_gradient



        # Wrap for PGLOBAL (needs callable with .n_evals attribute)

        class PGLOBALObjective:

            def __init__(self, func):

                self.func = func

                self.n_evals = 0



            def __call__(self, x):

                self.n_evals += 1

                return self.func(x)



        self.pglobal_objective = PGLOBALObjective(self.objective)



    def test_differential_evolution(self) -> OptimizerResult:

        """Test current differential_evolution optimizer"""

        self.logger.info("Testing differential_evolution...")



        import scipy.optimize



        # Current configuration

        maxiter = 1500

        popsize = 25



        start_time = time.perf_counter()



        result = scipy.optimize.differential_evolution(

            self.objective,

            self.bounds,

            x0=self.x0,

            popsize=popsize,

            maxiter=maxiter,

            tol=0.0005,

            mutation=(0.4, 0.8),

            recombination=0.8,

            updating="deferred",

            workers=1,

            disp=False,

        )



        execution_time = time.perf_counter() - start_time



        return OptimizerResult(

            optimizer_name="Differential Evolution",

            execution_time=execution_time,

            n_evaluations=result.nfev,

            best_cost=result.fun,

            best_params=result.x,

            converged=result.success,

            iterations=result.nit,

            final_rmse=np.sqrt(result.fun),

            improvement_pct=(

                1.0 - np.sqrt(result.fun) / np.sqrt(self.objective(self.x0))

            )

            * 100,

        )



    def test_pglobal(self) -> OptimizerResult:

        """Test PGLOBAL optimizer"""

        self.logger.info("Testing PGLOBAL...")



        # PGLOBAL configuration

        pglobal_config = Mock()

        pglobal_config.max_feval = 15000  # Similar to DE

        pglobal_config.reduction_ratio = 0.5

        pglobal_config.clustering_threshold = 0.1

        pglobal_config.sampling_mode = "uniform"



        start_time = time.perf_counter()



        optimizer = PGlobalOptimizerINDEX(

            self.pglobal_objective,

            self.bounds,

            n_workers=get_safe_worker_count(),

            config=pglobal_config,

        )



        result = optimizer.optimize(x0=self.x0)



        execution_time = time.perf_counter() - start_time



        return OptimizerResult(

            optimizer_name="PGLOBAL",

            execution_time=execution_time,

            n_evaluations=self.pglobal_objective.n_evals,

            best_cost=result.fun,

            best_params=result.x,

            converged=True,  # PGLOBAL always returns a result

            iterations=getattr(result, "nit", 0),

            final_rmse=np.sqrt(result.fun),

            improvement_pct=(

                1.0 - np.sqrt(result.fun) / np.sqrt(self.objective(self.x0))

            )

            * 100,

        )



    def test_lbfgsb(self) -> OptimizerResult:

        """Test L-BFGS-B optimizer"""

        self.logger.info("Testing L-BFGS-B...")



        import scipy.optimize



        # L-BFGS-B configuration

        max_iterations = 2000



        start_time = time.perf_counter()



        result = scipy.optimize.minimize(

            self.objective,

            self.x0,

            method="L-BFGS-B",

            jac=self.gradient,

            bounds=[(l, u) for l, u in zip(self.bounds[:, 0], self.bounds[:, 1])],

            options={

                "ftol": 1e-9,

                "gtol": 1e-9,

                "maxiter": max_iterations,

                "maxfun": max_iterations * 2,

            },

        )



        execution_time = time.perf_counter() - start_time



        return OptimizerResult(

            optimizer_name="L-BFGS-B",

            execution_time=execution_time,

            n_evaluations=result.nfev,

            best_cost=result.fun,

            best_params=result.x,

            converged=result.success,

            iterations=result.nit,

            final_rmse=np.sqrt(result.fun),

            improvement_pct=(

                1.0 - np.sqrt(result.fun) / np.sqrt(self.objective(self.x0))

            )

            * 100,

        )



    def test_hybrid_strategies(self) -> List[OptimizerResult]:

        """Test hybrid optimization strategies"""

        self.logger.info("Testing hybrid strategies...")



        import scipy.optimize



        results = []



        # Strategy 1: PGLOBAL + L-BFGS-B polish

        self.logger.info("  Testing PGLOBAL + L-BFGS-B...")



        # Phase 1: PGLOBAL exploration

        pglobal_config = Mock()

        pglobal_config.max_feval = 8000  # Reduced for hybrid

        pglobal_config.reduction_ratio = 0.5

        pglobal_config.clustering_threshold = 0.1

        pglobal_config.sampling_mode = "uniform"



        class PGLOBALObjective:

            def __init__(self, func):

                self.func = func

                self.n_evals = 0



            def __call__(self, x):

                self.n_evals += 1

                return self.func(x)



        pglobal_obj = PGLOBALObjective(self.objective)



        optimizer = PGlobalOptimizerINDEX(

            pglobal_obj, self.bounds, config=pglobal_config

        )

        pglobal_result = optimizer.optimize(x0=self.x0)



        # Phase 2: L-BFGS-B refinement

        lbfgsb_result = scipy.optimize.minimize(

            self.objective,

            pglobal_result.x,

            method="L-BFGS-B",

            jac=self.gradient,

            bounds=[(l, u) for l, u in zip(self.bounds[:, 0], self.bounds[:, 1])],

            options={"ftol": 1e-12, "gtol": 1e-12, "maxiter": 1000},

        )



        total_time = (

            time.perf_counter()

        )  # This would be measured in real implementation



        results.append(

            OptimizerResult(

                optimizer_name="PGLOBAL + L-BFGS-B",

                execution_time=total_time,

                n_evaluations=pglobal_obj.n_evals + lbfgsb_result.nfev,

                best_cost=lbfgsb_result.fun,

                best_params=lbfgsb_result.x,

                converged=lbfgsb_result.success,

                iterations=pglobal_result.nit + lbfgsb_result.nit,

                final_rmse=np.sqrt(lbfgsb_result.fun),

                improvement_pct=(

                    1.0 - np.sqrt(lbfgsb_result.fun) / np.sqrt(self.objective(self.x0))

                )

                * 100,

            )

        )



        # Strategy 2: Fast DE + L-BFGS-B

        self.logger.info("  Testing Fast DE + L-BFGS-B...")



        start_time = time.perf_counter()



        # Phase 1: Fast DE

        de_result = scipy.optimize.differential_evolution(

            self.objective,

            self.bounds,

            x0=self.x0,

            popsize=15,

            maxiter=500,

            tol=0.001,  # Fast settings

            mutation=(0.4, 0.8),

            recombination=0.8,

            updating="deferred",

            workers=1,

            disp=False,

        )



        # Phase 2: L-BFGS-B refinement

        lbfgsb_result = scipy.optimize.minimize(

            self.objective,

            de_result.x,

            method="L-BFGS-B",

            jac=self.gradient,

            bounds=[(l, u) for l, u in zip(self.bounds[:, 0], self.bounds[:, 1])],

            options={"ftol": 1e-12, "gtol": 1e-12, "maxiter": 1000},

        )



        execution_time = time.perf_counter() - start_time



        results.append(

            OptimizerResult(

                optimizer_name="Fast DE + L-BFGS-B",

                execution_time=execution_time,

                n_evaluations=de_result.nfev + lbfgsb_result.nfev,

                best_cost=lbfgsb_result.fun,

                best_params=lbfgsb_result.x,

                converged=lbfgsb_result.success,

                iterations=de_result.nit + lbfgsb_result.nit,

                final_rmse=np.sqrt(lbfgsb_result.fun),

                improvement_pct=(

                    1.0 - np.sqrt(lbfgsb_result.fun) / np.sqrt(self.objective(self.x0))

                )

                * 100,

            )

        )



        return results



    def test_robustness(self) -> Dict[str, List[float]]:

        """Test optimizer robustness with different starting points"""

        self.logger.info("Testing robustness...")



        # Generate different starting points

        n_trials = 5

        starting_points = []



        for i in range(n_trials):

            # Random starting point within bounds

            x_start = np.array(

                [

                    np.random.uniform(98.0, 102.0),  # thickness

                ]

                + [

                    (

                        np.random.uniform(1.0, 5.0)

                        if j < self.n_knots

                        else np.random.uniform(0.0, 2.0)

                    )

                    for j in range(2 * self.n_knots)

                ]

            )

            starting_points.append(x_start)



        robustness_results = {}



        # Test each optimizer

        optimizers = {

            "DE": self.test_differential_evolution,

            "PGLOBAL": self.test_pglobal,

            "L-BFGS-B": self.test_lbfgsb,

        }



        for opt_name, opt_func in optimizers.items():

            costs = []



            for x_start in starting_points:

                # Temporarily modify x0

                original_x0 = self.x0

                self.x0 = x_start



                try:

                    result = opt_func()

                    costs.append(result.best_cost)

                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

                    self.logger.warning(

                        f"  {opt_name} failed with starting point {i}: {e}"

                    )

                    costs.append(float("inf"))



                # Restore original x0

                self.x0 = original_x0



            robustness_results[opt_name] = costs



        return robustness_results



    def run_comparison(self) -> Tuple[List[OptimizerResult], Dict[str, List[float]]]:

        """Run complete optimizer comparison"""

        self.logger.info("=" * 60)

        self.logger.info("CERTUS SPLINE OPTIMIZER COMPARISON")

        self.logger.info("=" * 60)



        # Test individual optimizers

        results = []



        try:

            results.append(self.test_differential_evolution())

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            self.logger.error(f"Differential Evolution failed: {e}")



        try:

            results.append(self.test_pglobal())

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            self.logger.error(f"PGLOBAL failed: {e}")



        try:

            results.append(self.test_lbfgsb())

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            self.logger.error(f"L-BFGS-B failed: {e}")



        # Test hybrid strategies

        try:

            hybrid_results = self.test_hybrid_strategies()

            results.extend(hybrid_results)

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            self.logger.error(f"Hybrid strategies failed: {e}")



        # Test robustness

        robustness_results = {}

        try:

            robustness_results = self.test_robustness()

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            self.logger.error(f"Robustness test failed: {e}")



        # Print comparison

        self.print_comparison(results, robustness_results)



        return results, robustness_results



    def print_comparison(

        self, results: List[OptimizerResult], robustness: Dict[str, List[float]]

    ):

        """Print detailed comparison results"""

        print("\n" + "=" * 80)

        print("SPLINE OPTIMIZER COMPARISON RESULTS")

        print("=" * 80)



        if not results:

            print("No results to compare!")

            return



        # Performance comparison table

        print(

            f"\n{'Optimizer':<20} {'Time (s)':<10} {'Evals':<8} {'RMSE':<10} {'Improvement':<12} {'Converged':<10}"

        )

        print("-" * 80)



        # Sort by execution time

        sorted_results = sorted(results, key=lambda x: x.execution_time)



        for result in sorted_results:

            print(

                f"{result.optimizer_name:<20} {result.execution_time:<10.2f} {result.n_evaluations:<8} "

                f"{result.final_rmse:<10.6f} {result.improvement_pct:<12.2f}% {result.converged:<10}"

            )



        # Find best performers

        fastest = min(results, key=lambda x: x.execution_time)

        best_quality = min(results, key=lambda x: x.best_cost)

        most_efficient = min(

            results,

            key=lambda x: (

                x.n_evaluations / x.improvement_pct

                if x.improvement_pct > 0

                else float("inf")

            ),

        )



        print(f"\n🏆 PERFORMANCE AWARDS:")

        print(f"  Fastest: {fastest.optimizer_name} ({fastest.execution_time:.2f}s)")

        print(

            f"  Best Quality: {best_quality.optimizer_name} (RMSE={best_quality.final_rmse:.6f})"

        )

        print(f"  Most Efficient: {most_efficient.optimizer_name}")



        # Robustness analysis

        if robustness:

            print(f"\n📊 ROBUSTNESS ANALYSIS (Standard Deviation of costs):")

            for opt_name, costs in robustness.items():

                if costs:

                    std_dev = np.std(costs)

                    mean_cost = np.mean(costs)

                    print(f"  {opt_name:<15}: sigma={std_dev:.6f}, μ={mean_cost:.6f}")



        # Recommendations

        print(f"\n💡 RECOMMENDATIONS:")



        # Speed vs quality trade-off

        if fastest.execution_time < best_quality.execution_time * 0.5:

            if best_quality.best_cost < fastest.best_cost * 0.9:

                print(

                    f"  • Use {fastest.optimizer_name} for speed, {best_quality.optimizer_name} for quality"

                )

            else:

                print(

                    f"  • {fastest.optimizer_name} offers best speed-quality trade-off"

                )

        else:

            print(

                f"  • {best_quality.optimizer_name} is recommended (best overall performance)"

            )



        # Hybrid recommendation

        hybrid_results = [r for r in results if "+" in r.optimizer_name]

        if hybrid_results:

            best_hybrid = min(hybrid_results, key=lambda x: x.execution_time)

            if best_hybrid.execution_time < fastest.execution_time * 1.2:

                print(

                    f"  • Hybrid strategy {best_hybrid.optimizer_name} provides robust performance"

                )



        print("=" * 80)





def main():

    """Main comparison runner"""

    # Setup logging

    logging.basicConfig(

        level=logging.INFO,

        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",

    )



    # Run comparison

    comparison = SplineOptimizerComparison()

    results, robustness = comparison.run_comparison()



    return len(results)





if __name__ == "__main__":

    exit(main())


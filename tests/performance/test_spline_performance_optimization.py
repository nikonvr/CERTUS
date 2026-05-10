"""


CERTUS Spline Phase Performance Optimization Analysis


======================================================





Analyzes potential performance improvements for Phase 2 Spline optimization.


Identifies bottlenecks and proposes optimizations with validation.





Author: CERTUS Suite


Version: 1.0


"""





import sys


import os
from pathlib import Path


import numpy as np


import time


import logging





# Add parent directory to path


sys.path.append(str(Path(__file__).resolve().parents[1]))








class SplinePerformanceAnalyzer:


    """Analyzes and tests performance optimizations for spline phase"""





    def __init__(self):


        self.logger = logging.getLogger("SplinePerformanceAnalyzer")


        self.setup_test_data()





    def setup_test_data(self):


        """Setup realistic test data for performance testing"""


        # Realistic problem size


        self.n_knots = 7


        self.param_count = 2 * self.n_knots + 1  # thickness + n_knots + k_knots





        # Test bounds


        self.bounds = np.array(


            [


                [98.0, 102.0],  # thickness +/-2%


            ]


            + [


                [1.0, 5.0] if i < self.n_knots else [0.0, 2.0]


                for i in range(2 * self.n_knots)


            ]


        )





        # Test parameters


        self.x0 = np.array(


            [


                100.0,  # thickness


            ]


            + [2.0] * self.n_knots


            + [0.01] * self.n_knots


        )  # n_knots, k_knots





        # Mock objective function (realistic complexity)


        def mock_objective(x):


            # Simulate realistic computation time


            time.sleep(0.001)  # 1ms per evaluation


            return np.sum((x - self.x0) ** 2) + 0.001 * np.random.random()





        self.mock_objective = mock_objective





    def test_current_performance(self):


        """Test current differential_evolution performance"""


        self.logger.info("Testing current differential_evolution performance...")





        import scipy.optimize





        # Current configuration


        maxiter = 1500


        popsize = 25





        start_time = time.perf_counter()





        result = scipy.optimize.differential_evolution(


            self.mock_objective,


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





        self.logger.info(


            f"Current DE: {execution_time:.2f}s, {result.nfev} evaluations"


        )


        self.logger.info(f"Best cost: {result.fun:.6f}")





        return {


            "execution_time": execution_time,


            "n_evaluations": result.nfev,


            "best_cost": result.fun,


            "converged": result.success,


        }





    def test_parallel_differential_evolution(self):


        """Test parallel differential_evolution optimization"""


        self.logger.info("Testing parallel differential_evolution...")





        import scipy.optimize


        from certus_core import get_safe_worker_count





        # Get optimal worker count


        n_workers = get_safe_worker_count()


        self.logger.info(f"Using {n_workers} workers for parallel DE")





        maxiter = 1500


        popsize = 25





        start_time = time.perf_counter()





        result = scipy.optimize.differential_evolution(


            self.mock_objective,


            self.bounds,


            x0=self.x0,


            popsize=popsize,


            maxiter=maxiter,


            tol=0.0005,


            mutation=(0.4, 0.8),


            recombination=0.8,


            updating="deferred",


            workers=n_workers,  # Enable parallelism


            disp=False,


        )





        execution_time = time.perf_counter() - start_time





        self.logger.info(


            f"Parallel DE: {execution_time:.2f}s, {result.nfev} evaluations"


        )


        self.logger.info(f"Best cost: {result.fun:.6f}")





        return {


            "execution_time": execution_time,


            "n_evaluations": result.nfev,


            "best_cost": result.fun,


            "converged": result.success,


            "n_workers": n_workers,


        }





    def test_adaptive_parameters(self):


        """Test adaptive parameter tuning"""


        self.logger.info("Testing adaptive parameters...")





        import scipy.optimize





        # Adaptive configurations


        configs = [


            {"maxiter": 500, "popsize": 15, "tol": 0.001, "name": "Fast"},


            {"maxiter": 800, "popsize": 20, "tol": 0.0008, "name": "Balanced"},


            {"maxiter": 1200, "popsize": 30, "tol": 0.0003, "name": "Precise"},


        ]





        results = []





        for config in configs:


            start_time = time.perf_counter()





            result = scipy.optimize.differential_evolution(


                self.mock_objective,


                self.bounds,


                x0=self.x0,


                popsize=config["popsize"],


                maxiter=config["maxiter"],


                tol=config["tol"],


                mutation=(0.4, 0.8),


                recombination=0.8,


                updating="deferred",


                workers=1,


                disp=False,


            )





            execution_time = time.perf_counter() - start_time





            result_data = {


                "name": config["name"],


                "execution_time": execution_time,


                "n_evaluations": result.nfev,


                "best_cost": result.fun,


                "converged": result.success,


                "config": config,


            }





            results.append(result_data)





            self.logger.info(


                f"{config['name']}: {execution_time:.2f}s, {result.nfev} evals, cost={result.fun:.6f}"


            )





        return results





    def test_hybrid_optimization(self):


        """Test hybrid optimization (DE + local refinement)"""


        self.logger.info("Testing hybrid optimization...")





        import scipy.optimize





        # Phase 1: Fast DE exploration


        start_time = time.perf_counter()





        result_de = scipy.optimize.differential_evolution(


            self.mock_objective,


            self.bounds,


            x0=self.x0,


            popsize=15,


            maxiter=300,


            tol=0.002,  # Fast settings


            mutation=(0.4, 0.8),


            recombination=0.8,


            updating="deferred",


            workers=1,


            disp=False,


        )





        de_time = time.perf_counter() - start_time





        # Phase 2: Local refinement


        def gradient_objective(x):


            # Simple gradient approximation


            eps = 1e-8


            grad = np.zeros_like(x)


            for i in range(len(x)):


                x_plus = x.copy()


                x_plus[i] += eps


                x_minus = x.copy()


                x_minus[i] -= eps


                grad[i] = (


                    self.mock_objective(x_plus) - self.mock_objective(x_minus)


                ) / (2 * eps)


            return self.mock_objective(x), grad





        start_time = time.perf_counter()





        result_local = scipy.optimize.minimize(


            gradient_objective,


            result_de.x,


            method="L-BFGS-B",


            bounds=self.bounds,


            options={"ftol": 1e-9, "gtol": 1e-9, "maxiter": 200},


        )





        local_time = time.perf_counter() - start_time


        total_time = de_time + local_time





        self.logger.info(


            f"Hybrid: DE {de_time:.2f}s + Local {local_time:.2f}s = {total_time:.2f}s"


        )


        self.logger.info(f"Final cost: {result_local.fun:.6f}")





        return {


            "execution_time": total_time,


            "de_time": de_time,


            "local_time": local_time,


            "n_evaluations": result_de.nfev + getattr(result_local, "nfev", 0),


            "best_cost": result_local.fun,


            "converged": result_local.success,


        }





    def test_early_stopping(self):


        """Test early stopping strategies"""


        self.logger.info("Testing early stopping...")





        import scipy.optimize





        # Early stopping callback


        class EarlyStopCallback:


            def __init__(self, patience=50, tol=1e-6):


                self.patience = patience


                self.tol = tol


                self.best_cost = float("inf")


                self.no_improvement_count = 0


                self.stop_requested = False





            def __call__(self, xk, _convergence):


                current_cost = self.mock_objective(xk)





                if current_cost < self.best_cost - self.tol:


                    self.best_cost = current_cost


                    self.no_improvement_count = 0


                else:


                    self.no_improvement_count += 1





                if self.no_improvement_count >= self.patience:


                    self.stop_requested = True


                    return True  # Stop optimization





                return False





        callback = EarlyStopCallback(patience=30, tol=1e-6)





        start_time = time.perf_counter()





        result = scipy.optimize.differential_evolution(


            self.mock_objective,


            self.bounds,


            x0=self.x0,


            popsize=25,


            maxiter=1500,


            tol=0.0005,


            mutation=(0.4, 0.8),


            recombination=0.8,


            updating="deferred",


            workers=1,


            callback=callback,


            disp=False,


        )





        execution_time = time.perf_counter() - start_time





        self.logger.info(


            f"Early stopping: {execution_time:.2f}s, {result.nfev} evaluations"


        )


        self.logger.info(


            f"Best cost: {result.fun:.6f}, Stopped early: {callback.stop_requested}"


        )





        return {


            "execution_time": execution_time,


            "n_evaluations": result.nfev,


            "best_cost": result.fun,


            "stopped_early": callback.stop_requested,


        }





    def analyze_memory_usage(self):


        """Analyze memory usage patterns"""


        self.logger.info("Analyzing memory usage...")





        try:


            import psutil


            import gc





            process = psutil.Process()





            # Baseline memory


            gc.collect()


            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB





            # Run optimization


            self.test_current_performance()





            # Peak memory


            peak_memory = process.memory_info().rss / 1024 / 1024  # MB





            # Cleanup


            gc.collect()


            final_memory = process.memory_info().rss / 1024 / 1024  # MB





            memory_usage = {


                "baseline_mb": baseline_memory,


                "peak_mb": peak_memory,


                "final_mb": final_memory,


                "increase_mb": peak_memory - baseline_memory,


                "leak_mb": final_memory - baseline_memory,


            }





            self.logger.info(


                f"Memory: Baseline {baseline_memory:.1f}MB, Peak {peak_memory:.1f}MB, Increase {memory_usage['increase_mb']:.1f}MB"


            )





            return memory_usage





        except ImportError:


            self.logger.warning("psutil not available for memory analysis")


            return None





    def generate_performance_report(self):


        """Generate comprehensive performance report"""


        self.logger.info("=" * 60)


        self.logger.info("CERTUS SPLINE PERFORMANCE ANALYSIS")


        self.logger.info("=" * 60)





        results = {}





        # Test current performance


        results["current"] = self.test_current_performance()





        # Test parallel optimization


        results["parallel"] = self.test_parallel_differential_evolution()





        # Test adaptive parameters


        results["adaptive"] = self.test_adaptive_parameters()





        # Test hybrid optimization


        results["hybrid"] = self.test_hybrid_optimization()





        # Test early stopping


        results["early_stopping"] = self.test_early_stopping()





        # Memory analysis


        results["memory"] = self.analyze_memory_usage()





        # Generate recommendations


        recommendations = self.generate_recommendations(results)





        # Print summary


        self.print_performance_summary(results, recommendations)





        return results, recommendations





    def generate_recommendations(self, results):


        """Generate performance optimization recommendations"""


        recommendations = []





        current_time = results["current"]["execution_time"]





        # Parallel optimization


        if "parallel" in results:


            speedup = current_time / results["parallel"]["execution_time"]


            if speedup > 1.2:  # 20% improvement threshold


                recommendations.append(


                    {


                        "priority": "HIGH",


                        "action": "Enable parallel differential_evolution",


                        "expected_speedup": f"{speedup:.2f}x",


                        "implementation": "Change workers=1 to workers=get_safe_worker_count()",


                        "risk": "LOW",


                    }


                )





        # Adaptive parameters


        if "adaptive" in results:


            best_adaptive = min(results["adaptive"], key=lambda x: x["execution_time"])


            adaptive_speedup = current_time / best_adaptive["execution_time"]


            if adaptive_speedup > 1.15:


                recommendations.append(


                    {


                        "priority": "MEDIUM",


                        "action": f"Use {best_adaptive['name']} parameter set",


                        "expected_speedup": f"{adaptive_speedup:.2f}x",


                        "implementation": f"maxiter={best_adaptive['config']['maxiter']}, popsize={best_adaptive['config']['popsize']}",


                        "risk": "LOW",


                    }


                )





        # Hybrid optimization


        if "hybrid" in results:


            hybrid_speedup = current_time / results["hybrid"]["execution_time"]


            if hybrid_speedup > 1.1:


                recommendations.append(


                    {


                        "priority": "MEDIUM",


                        "action": "Implement hybrid DE + local refinement",


                        "expected_speedup": f"{hybrid_speedup:.2f}x",


                        "implementation": "Fast DE (300 iter) + L-BFGS-B refinement",


                        "risk": "MEDIUM",


                    }


                )





        # Early stopping


        if "early_stopping" in results and results["early_stopping"]["stopped_early"]:


            early_speedup = current_time / results["early_stopping"]["execution_time"]


            if early_speedup > 1.1:


                recommendations.append(


                    {


                        "priority": "LOW",


                        "action": "Implement early stopping",


                        "expected_speedup": f"{early_speedup:.2f}x",


                        "implementation": "Add patience-based early stopping callback",


                        "risk": "LOW",


                    }


                )





        return recommendations





    def print_performance_summary(self, results, recommendations):


        """Print comprehensive performance summary"""


        print("\n" + "=" * 60)


        print("PERFORMANCE ANALYSIS SUMMARY")


        print("=" * 60)





        # Current performance baseline


        current = results["current"]


        print(


            f"Current Performance: {current['execution_time']:.2f}s, {current['n_evaluations']} evals"


        )





        # Comparison table


        print(f"\n{'Method':<20} {'Time (s)':<10} {'Speedup':<10} {'Evals':<10}")


        print("-" * 50)





        for method, result in results.items():


            if method == "current" or method == "memory" or method == "adaptive":


                continue





            speedup = current["execution_time"] / result["execution_time"]


            print(


                f"{method:<20} {result['execution_time']:<10.2f} {speedup:<10.2f} {result.get('n_evaluations', 'N/A'):<10}"


            )





        # Adaptive configs


        if "adaptive" in results:


            print(f"\nAdaptive Configurations:")


            for config in results["adaptive"]:


                speedup = current["execution_time"] / config["execution_time"]


                print(


                    f"  {config['name']:<15} {config['execution_time']:<8.2f}s {speedup:<8.2f}x"


                )





        # Memory usage


        if "memory" in results and results["memory"]:


            mem = results["memory"]


            print(


                f"\nMemory Usage: {mem['baseline_mb']:.1f}MB -> {mem['peak_mb']:.1f}MB (+{mem['increase_mb']:.1f}MB)"


            )





        # Recommendations


        if recommendations:


            print(f"\nOPTIMIZATION RECOMMENDATIONS:")


            for i, rec in enumerate(recommendations, 1):


                print(f"  {i}. [{rec['priority']}] {rec['action']}")


                print(f"     Speedup: {rec['expected_speedup']}, Risk: {rec['risk']}")


                print(f"     Implementation: {rec['implementation']}")


        else:


            print(f"\nNo significant optimizations identified.")





        print("=" * 60)








def main():


    """Main performance analysis runner"""


    # Setup logging


    logging.basicConfig(


        level=logging.INFO,


        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",


    )





    # Run performance analysis


    analyzer = SplinePerformanceAnalyzer()


    results, recommendations = analyzer.generate_performance_report()





    # Return recommendations count


    return len(recommendations)








if __name__ == "__main__":


    exit(main())



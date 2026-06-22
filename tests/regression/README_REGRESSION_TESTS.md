# CERTUS Regression Tests

This folder contains the convergence and non-regression test suite of the CERTUS application.

## Principe du "Golden Master"
During development, mathematical optimizations or algorithmic refactoring, small errors can degrade accuracy or the algorithm's ability to converge to an optimal solution (RMSE).

To prevent this, we extracted the best RMSE error obtained on a series of robust examples (Golden Masters) stored in the file `baseline_rmse.json`.

## Absolute Development Rule
**ANY source code modification (UI, refactoring, Numba JIT, workers, business logic) MUST be validated by a pass of this test suite.**

The tests verify that the code can still run the full pipelines "headless" (without interface) and that the obtained RMSE does not deviate by more than 1% from the absolute reference.

## Comment Lancer ?
Double-cliquez simplement sur `RUN_CONVERGENCE_TESTS.bat` à la racine du projet, ou exécutez la commande :

```bash
python tests/regression/test_convergence.py
```

If the test fails, the changes introduced an algorithmic regression and must be corrected before integration.

## Baseline Update
If a new algorithm proves to be mathematically and fundamentally better (structurally and intentionally improved RMSE), the baseline can be updated via the collection script.

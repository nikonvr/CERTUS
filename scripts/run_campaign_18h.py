import os
import sys
import json
import subprocess
import time
import hashlib
from pathlib import Path

# Grid definition
TOLS = [1e-12, 1e-8, 1e-5]
ALPHAS = [0.02, 0.1, 0.2]
N_SAMPLES = [500, 2000, 5000]
LOCAL_BUDGETS = [2000, 5000, 10000]

CAMPAIGN_DIR = Path("D:/1406/1406/campaign_18h")
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_FILE = CAMPAIGN_DIR / "campaign_results.jsonl"

def get_hash(config):
    s = json.dumps(config, sort_keys=True)
    return hashlib.md5(s.encode('utf-8')).hexdigest()[:8]

def load_completed():
    completed = set()
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        completed.add(data["hash"])
                    except Exception:
                        pass
    return completed

def main():
    completed = load_completed()
    print(f"Loaded {len(completed)} completed configurations.")

    combinations = []
    for tol in TOLS:
        for alpha in ALPHAS:
            for n_samp in N_SAMPLES:
                for l_bud in LOCAL_BUDGETS:
                    combinations.append({
                        "tol": tol,
                        "alpha": alpha,
                        "n_samples": n_samp,
                        "local_budget": l_bud,
                    })

    print(f"Total configurations: {len(combinations)}")
    
    for idx, config in enumerate(combinations):
        chash = get_hash(config)
        if chash in completed:
            print(f"[{idx+1}/{len(combinations)}] Skipping {chash} (already done)")
            continue

        print(f"\n[{idx+1}/{len(combinations)}] Running {chash} ...")
        print(f"Params: {config}")

        out_file = CAMPAIGN_DIR / f"result_{chash}.json"
        
        # Prepare environment
        env = os.environ.copy()
        env["PYTHONPATH"] = "D:/1406/1406"
        env["CERTUS_LBFGSB_TOL"] = str(config["tol"])
        
        pglobal_params = {
            "alpha": config["alpha"],
            "n_samples": config["n_samples"],
            "local_budget": config["local_budget"]
        }
        env["CERTUS_PGLOBAL_PARAMS"] = json.dumps(pglobal_params)

        start_time = time.time()
        try:
            # 16 minutes hard timeout (15m in the script + 1m margin)
            proc = subprocess.run(
                [sys.executable, "tests/headless/test_design_campaign.py", str(out_file)],
                env=env,
                cwd="D:/1406/1406",
                timeout=960,
                capture_output=True,
                text=True
            )
            
            elapsed = time.time() - start_time
            print(f"Completed in {elapsed:.1f}s. Exit code: {proc.returncode}")
            
            # Read output
            best_rmse = None
            layers = 0
            if out_file.exists():
                with open(out_file, "r") as f:
                    try:
                        res = json.loads(f.read())
                        best_rmse = res.get("best_rmse")
                        layers = res.get("layers", 0)
                    except Exception:
                        pass
                        
            if best_rmse is None:
                print("WARNING: Script finished but no valid output file found. Check logs.")
                # Save stdout for debugging
                with open(CAMPAIGN_DIR / f"log_{chash}.txt", "w") as f:
                    f.write(proc.stdout)
                    f.write("\n\n--- STDERR ---\n\n")
                    f.write(proc.stderr)
            
            # Save to jsonl
            res_line = {
                "hash": chash,
                "params": config,
                "elapsed_s": elapsed,
                "best_rmse": best_rmse,
                "layers": layers,
                "exit_code": proc.returncode
            }
            
            with open(RESULTS_FILE, "a") as f:
                f.write(json.dumps(res_line) + "\n")
                
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT EXPIRED (>16m) for {chash}")
            res_line = {
                "hash": chash,
                "params": config,
                "elapsed_s": 960,
                "best_rmse": None,
                "layers": 0,
                "exit_code": "TIMEOUT"
            }
            with open(RESULTS_FILE, "a") as f:
                f.write(json.dumps(res_line) + "\n")
        except Exception as e:
            print(f"UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    main()

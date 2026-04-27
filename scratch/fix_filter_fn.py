
import ast

def fix_filter_fn():
    with open('CERTUS_STRAT.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Locate the function
    start_idx = -1
    for i, line in enumerate(lines):
        if 'def _filter_valid_strategies' in line:
            start_idx = i
            break
            
    if start_idx == -1:
        print("Function not found")
        return

    # Find the end of the function (where run_final_simulation_block starts)
    end_idx = -1
    for i in range(start_idx, len(lines)):
        if 'def _prepare_robustness_physics_context' in lines[i]:
            end_idx = i
            break
            
    if end_idx == -1:
        print("End of function not found")
        return

    new_fn = [
        "def _filter_valid_strategies(\n",
        "    all_strategies_in: list[dict[str, Any]], num_layers: int, logger: logging.Logger\n",
        ") -> list[dict[str, Any]]:\n",
        '    """Filter strategies passing the block contract validation."""\n',
        "    valid_strategies = []\n",
        "    for strat in all_strategies_in:\n",
        "        try:\n",
        '            expected_blocks = int(strat.get("n_blocks", len(strat.get("blocks", []))))\n',
        "        except (TypeError, ValueError):\n",
        '            expected_blocks = len(strat.get("blocks", []))\n',
        "\n",
        "        ok, reason = _validate_strategy_blocks_contract(\n",
        "            strat, num_layers, expected_n_blocks=expected_blocks\n",
        "        )\n",
        "        if ok:\n",
        "            valid_strategies.append(strat)\n",
        "        else:\n",
        "            logger.warning(\n",
        "                f'[ROBUSTNESS] Dropped invalid strategy {strat.get(\"strategy_id\", \"?\")}: {reason}'\n",
        "            )\n",
        "    return valid_strategies\n",
        "\n",
        "\n"
    ]
    
    lines[start_idx:end_idx] = new_fn
    
    with open('CERTUS_STRAT.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

if __name__ == "__main__":
    fix_filter_fn()

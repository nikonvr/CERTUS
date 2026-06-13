import re

filepath = r'certus\ui\certus_strat_ui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add the methods to CertusStratApp (we can put them just before _generate_strat_report_from_state, or just at the end of the class. Let's find _generate_strat_report_from_state and insert before it).
method_definitions = """
    def _resolve_manifest_seed(self, seed_container: Any) -> int | None:
        if not isinstance(seed_container, dict):
            return None
        for _k in (
            "seed",
            "random_seed",
            "robustness_seed",
            "phase_a_seed",
            "ensemble_seed",
        ):
            _v = seed_container.get(_k)
            if _v is None:
                continue
            try:
                return int(_v)
            except (TypeError, ValueError):
                continue
        return None

    def _manifest_source_paths(self) -> list[str]:
        paths: list[str] = []
        cfg_path = str(getattr(self, "_last_config_file", "") or "").strip()
        if cfg_path:
            paths.append(cfg_path)
        try:
            db_path = str(_resolve_strat_indices_db_path() or "").strip()
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            db_path = ""
        if db_path:
            paths.append(db_path)
        return list(dict.fromkeys(paths))

    def _generate_strat_report_from_state"""

content = content.replace("    def _generate_strat_report_from_state", method_definitions)

# 2. Remove the inline defs
pattern_inline = r'^[ \t]+def _resolve_manifest_seed\(seed_container: Any\) -> int \| None:\n(?:[ \t]+.*?\n)*?^[ \t]+def _manifest_source_paths\(\) -> list\[str\]:\n(?:[ \t]+.*?\n)*?(?=[ \t]+manifest_payload_source|self\.manifest_payload_source)'
# The first usage is followed by `manifest_payload_source: dict[str, Any] = self.opti_results or {}`
# The second usage is followed by `manifest_payload_source = self.cache.get("strat_opti_results", {})`
# Let's write a generic regex that removes the two definitions.

# Instead of regex, let's just match the exact blocks since we can.
def_block = """            def _resolve_manifest_seed(seed_container: Any) -> int | None:
                if not isinstance(seed_container, dict):
                    return None
                for _k in (
                    "seed",
                    "random_seed",
                    "robustness_seed",
                    "phase_a_seed",
                    "ensemble_seed",
                ):
                    _v = seed_container.get(_k)
                    if _v is None:
                        continue
                    try:
                        return int(_v)
                    except (TypeError, ValueError):
                        continue
                return None

            def _manifest_source_paths() -> list[str]:
                paths: list[str] = []
                cfg_path = str(getattr(self, "_last_config_file", "") or "").strip()
                if cfg_path:
                    paths.append(cfg_path)
                try:
                    db_path = str(_resolve_strat_indices_db_path() or "").strip()
                except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
                    db_path = ""
                if db_path:
                    paths.append(db_path)
                # Keep stable order while removing duplicates.
                return list(dict.fromkeys(paths))

"""

content = content.replace(def_block, "")

# 3. Replace the calls
content = content.replace("_manifest_source_paths()", "self._manifest_source_paths()")
content = content.replace("_resolve_manifest_seed(params_for_manifest)", "self._resolve_manifest_seed(params_for_manifest)")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched certus_strat_ui.py")

"""CERTUS STRAT ROBUSTNESS - the two small wrappers that the robustness code reads clues through (moved out of certus_strat_robustness.py, S5.2)."""

from typing import Any


class _IdxWrapper:
    """Dict-like wrapper supporting both ``dict.get`` and ``list[idx]`` access."""

    __slots__ = ("_is_dict", "obj")

    def __init__(self, obj: Any) -> None:
        self.obj = obj
        self._is_dict = hasattr(obj, "get")

    def __getitem__(self, k: Any) -> Any:
        return self.obj.get(k) if self._is_dict else self.obj[k]

    def __contains__(self, k: Any) -> bool:
        if hasattr(self.obj, "__contains__"):
            return k in self.obj
        if self._is_dict:
            return self.obj.get(k) is not None
        return False


class _SafeLocalClues(dict):
    """Fallback cache dictionary for clues, optimized for Top 1%."""

    __slots__ = ("_original",)

    def __init__(self, original: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._original = _IdxWrapper(original)

    def get(self, wl: float, default: Any = None) -> Any:
        wl_f = float(wl)
        if super().__contains__(wl_f):
            return super().__getitem__(wl_f)
        try:
            res = self._original[wl_f]
            self[wl_f] = res
            return res
        except Exception:
            return default

    def __getitem__(self, wl: float) -> Any:
        res = self.get(wl)
        if res is None:
            raise KeyError(wl)
        return res

    def __contains__(self, wl: Any) -> bool:  # `Any`: the supertype takes `object`
        wl_f = float(wl)
        if super().__contains__(wl_f):
            return True
        return wl_f in self._original

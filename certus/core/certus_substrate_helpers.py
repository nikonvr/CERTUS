"""Shared helpers for CERTUS substrate index extraction and selection."""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd




def norm_header(raw) -> str:
    s = str(raw).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = s.replace("œ", "oe").replace("æ", "ae")
    s = re.sub(r"[_\-\./\\+|,:;]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def expand_substrate_abbrevs(s: str) -> str:
    repl: tuple[tuple[str, str], ...] = (
        (r"\bsubstrate\b", "substrate"),
        (r"\bsubstrat\b", "substrate"),
        (r"\bsubstn\b", "substrate nu"),
        (r"\bsbstn\b", "substrate nu"),
        (r"\bsubstnu\b", "substrate nu"),
        (r"\bsbstnu\b", "substrate nu"),
        (r"\bsnu\b", "substrate nu"),
        (r"\bsubst\b", "substrate"),
        (r"\bsbst\b", "substrate"),
        (r"\bsubstr\b", "substrate"),
        (r"\bsubs\b", "substrate"),
        (r"\bsub\b", "sub"),
        (r"\buncoated\b", "uncoated"),
        (r"\buncoat\b", "uncoated"),
        (r"\bnocoat\b", "no coating"),
        (r"\bno\s*coat\b", "no coating"),
        (r"\bwo\s*coat\b", "no coating"),
        (r"\bw/o\s*coat\b", "no coating"),
        (r"\btemoin\b", "witness"),
        (r"\bwitness\b", "witness"),
        (r"\bblk\b", "blank"),
        (r"\bref\b", "ref"),
    )
    out = s
    for pat, to in repl:
        out = re.sub(pat, to, out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip()


def unglue_substrate_nu(s: str) -> str:
    out = s
    out = re.sub(r"(substrate|sub|sbst|subst|substr|bare|blank|uncoated)(nu|nus|nue)\b", r"\1 \2", out, flags=re.IGNORECASE)
    out = re.sub(r"\b(bare|blank|ref|raw|empty|void)(sub|substrate|substrate)\b", r"\1 \2", out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip()


_RE_SUBSTRATE_INDEX_EXCLUDE = re.compile(
    r"\b(" r"filt|flt|filter|" r"multilayer|ml|hl|hlstack|stack|stk|layering|pile|" r"tgt|target|obj|objective|" r"design|dsg|qwot|qw\b|" r"theor|theoretical|theo\b|optimis|opti\b|reconst|simu|simulation|" r"sample|spc\b|specimen|lot\b|batch|" r"final|mes\s*filt" r")\b",
    re.IGNORECASE,
)

_RE_SUBSTRATE_INDEX_INCLUDE = re.compile(
    r"(" r"\brnu(?:\b|[\s\-_]*\d+[fsp]?|\d+[fsp]?)|" r"\btnu(?:\b|[\s\-_]*\d+[fsp]?|\d+[fsp]?)|" r"substrate\s+nu\b|nu\s+substrate\b|nu\s+sub\b|" r"substrate\s+bare|sub\s+bare|sub\s+only|substrate\s+only|only\s+substrate|only\s+sub\b|" r"\bsub\s+nu\b|\bsub\s+nus\b|" r"substratnu\b|subnu\b|sbstnu\b|substnu\b|" r"\bbare\s+sub(strate)?\b|\bbaresub\b|" r"\b(blank|empty|void)\s+sub(strate)?\b|\bsub(strate)?\s+blank\b|" r"\buncoated\b|\bno\s*coating\b|" r"\bpolished\s+substrate\b|" r"without\s*(layer|deposit|coat|coating|stack|layering)|" r"without[\s\-_/]*dep\b|" r"\b(ref|raw|empty|void)\s+sub(strate|strat)?\b|\bsub(strate)?\s+ref\b|" r"\b(witness|blank|empty|unstacked)\b|" r"\b(sapphire|saphir|al2o3)\b|" r"\bsnu\b|\bsbn\b|\bbsub\b|" r"(?:^|[^a-z0-9])nu(?:s|es|e)?(?:[^a-z0-9]|$)" r")",
    re.IGNORECASE,
)


def is_bare_substrate_column(name) -> bool:
    s0 = norm_header(name)
    if not s0:
        return False
    s1 = unglue_substrate_nu(s0)
    s2 = expand_substrate_abbrevs(s1)
    s3 = unglue_substrate_nu(s2)
    if _RE_SUBSTRATE_INDEX_EXCLUDE.search(s3):
        return False
    return bool(_RE_SUBSTRATE_INDEX_INCLUDE.search(s3))


def filter_bare_substrate_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    if df is None or df.empty or len(df.columns) < 2:
        return df, [], []

    col_names = list(df.columns)
    wl = col_names[0]
    for c in col_names:
        s = norm_header(c)
        if not re.search(r"\b(wavelength|lambda|wl)\b", s):
            continue
        vals = pd.to_numeric(df[c], errors="coerce")
        if int(np.count_nonzero(np.isfinite(vals.values))) >= 3:
            wl = c
            break

    kept_cols: list = [wl]
    kept_spec: list[str] = []
    dropped: list[str] = []
    for col in col_names:
        if col == wl:
            continue
        if is_bare_substrate_column(col):
            kept_cols.append(col)
            kept_spec.append(str(col))
        else:
            dropped.append(str(col))
    return df[kept_cols].copy(), kept_spec, dropped

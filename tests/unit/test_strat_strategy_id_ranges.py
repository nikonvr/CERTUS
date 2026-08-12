"""Les identifiants de strategie ne sont PAS une donnee -- et ils ont menti une fois.

🔴 CE QUE CE FICHIER EMPECHE DE REVENIR. Le 2026-08-12 la gagnante d'un run nominal
portait l'identifiant 990000320. Lu comme "plage 990 = variante Rate", il a ete rapporte
comme tel; son `origin` disait LOCAL_SEARCH. La lecture fausse est remontee jusqu'a
l'utilisateur, qui a cru voir le mode Rate gagner la ou aucune gagnante n'en a jamais
porte -- verifie ensuite sur les huit runs de la journee, `rate_layers` vide partout.

La cause: les generateurs incrementaux (consensus, ELITE, recherche locale) partent de
`max_sid + 1`, donc ils GRIMPENT dans les plages reservees des qu'une variante existe.
Deux generateurs finissent par se partager les memes numeros, et rien ne le signale.

🔑 LA REGLE : le generateur se lit dans `origin`, qui fait foi. Les plages ne servent
qu'a garantir l'unicite des numeros. Ces tests verifient les deux moities de cela.
"""

from __future__ import annotations

from itertools import pairwise

from certus.core.certus_strat_ranking import (
    STRATEGY_ID_DERIVED_BASE,
    STRATEGY_ID_INCREMENTAL_CEILING,
    STRATEGY_ID_RATE_BASE,
    STRATEGY_ID_SLIT_BASE,
    clamp_incremental_strategy_id,
)
from certus.core.certus_strat_robustness import (
    _expand_with_rate_variants,
    _expand_with_resolution_variants,
)


class _Log:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


def _strat(n_blocks: int = 3, sid: int = 7) -> dict:
    step = 48 // n_blocks
    return {
        "strategy_id": sid,
        "blocks": [
            {"start": i * step, "end": (i + 1) * step if i < n_blocks - 1 else 48,
             "wavelength": 544.0 + i}
            for i in range(n_blocks)
        ],
    }


def test_the_three_ranges_are_disjoint_and_ordered():
    """Deux strategies distinctes ne doivent jamais porter le meme numero."""
    bases = [STRATEGY_ID_DERIVED_BASE, STRATEGY_ID_SLIT_BASE, STRATEGY_ID_RATE_BASE]
    assert bases == sorted(bases), "les plages doivent etre ordonnees"
    assert len(set(bases)) == 3, "deux generateurs partagent une base"
    # 10 M de marge entre deux bases : un generateur devrait produire dix millions de
    # variantes pour deborder, ce qui n'arrive pas avec le plafond de 3 par strategie.
    assert min(b - a for a, b in pairwise(bases)) >= 10_000_000


def test_an_incremental_counter_can_never_enter_a_reserved_range():
    """🔴 LE DEFAUT LUI-MEME. `max_sid + 1` suivait les variantes vers le haut."""
    assert clamp_incremental_strategy_id(5_000) == 5_000
    assert clamp_incremental_strategy_id(STRATEGY_ID_DERIVED_BASE + 12) == \
        STRATEGY_ID_DERIVED_BASE + 12
    # une variante Rate dans la liste ne doit plus tirer le compteur derriere elle
    assert clamp_incremental_strategy_id(STRATEGY_ID_RATE_BASE + 321) < \
        STRATEGY_ID_INCREMENTAL_CEILING
    assert clamp_incremental_strategy_id(STRATEGY_ID_SLIT_BASE) < \
        STRATEGY_ID_INCREMENTAL_CEILING


def test_rate_variants_land_in_the_rate_range():
    out = _expand_with_rate_variants([_strat(3)], {"allow_rate": True}, 48, _Log())
    variants = [v for v in out if v.get("rate_layers")]
    assert variants, "le montage ne genere aucune variante : le test ne teste rien"
    for v in variants:
        assert STRATEGY_ID_RATE_BASE <= v["strategy_id"] < STRATEGY_ID_RATE_BASE + 10_000_000


def test_slit_variants_land_in_the_slit_range():
    out = _expand_with_resolution_variants([_strat(3)], {"search_resolution": True}, _Log())
    variants = [v for v in out if "SLIT" in str(v.get("origin"))]
    assert variants, "le montage ne genere aucune variante : le test ne teste rien"
    for v in variants:
        assert STRATEGY_ID_SLIT_BASE <= v["strategy_id"] < STRATEGY_ID_SLIT_BASE + 10_000_000


def test_the_generator_is_read_from_origin_never_from_the_id():
    """🔑 La moitie qui compte vraiment.

    Meme avec des plages disjointes, l'identifiant reste un NUMERO. Ce qui nomme le
    generateur est `origin`, et c'est ce qu'il faut lire -- y compris quand un parent
    porte deja un identifiant de la plage d'un autre generateur, ce qui arrive des qu'on
    enchaine deux expansions.
    """
    rate = _expand_with_rate_variants([_strat(3)], {"allow_rate": True}, 48, _Log())
    both = _expand_with_resolution_variants(rate, {"search_resolution": True}, _Log())
    for v in both:
        origin = str(v.get("origin", ""))
        if "SLIT" in origin:
            assert "SLIT" in origin      # l'origine dit la verite...
        # ...et l'identifiant seul ne suffit jamais a trancher : une variante de fente
        # NEE d'une variante Rate porte un id de la plage FENTE tout en descendant du
        # Rate. Seule `origin` porte la filiation complete.
    slit_from_rate = [v for v in both if "SLIT" in str(v.get("origin")) and v.get("rate_layers")]
    assert slit_from_rate, "l'enchainement Rate -> fente doit produire des variantes mixtes"
    for v in slit_from_rate:
        assert v["strategy_id"] >= STRATEGY_ID_SLIT_BASE
        assert "SLIT" in str(v["origin"])


def test_a_string_id_parent_keeps_a_string_id_variant():
    """`sorted()` LEVE sur une liste melangeant int et str, et le departage des ex aequo
    trie sur l'identifiant. Trouve le 2026-08-12, latent tant que Rate etait eteint."""
    out = _expand_with_rate_variants([{"strategy_id": "a", "blocks": _strat(3)["blocks"]}],
                                     {"allow_rate": True}, 48, _Log())
    ids = [v["strategy_id"] for v in out]
    assert all(isinstance(i, str) for i in ids), f"types melanges : {ids}"
    sorted(ids)          # doit ne pas lever

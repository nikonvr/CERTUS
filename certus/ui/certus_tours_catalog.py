"""CERTUS onboarding tour definitions (P2.2).

Centralises the :class:`certus_onboarding.TourStep` sequences per app so
each monolith can trigger its tour with a single call::

    from certus.ui.certus_tours_catalog import run_app_onboarding
    run_app_onboarding(self)  # uses self.APP_NAME

The catalog is intentionally generic: each step points at an **attribute
name** on the app instance (``target_attr``), and missing attributes are
silently skipped by ``certus_onboarding.filter_resolvable_steps``. This
keeps the catalog decoupled from monolith internals.

Mapping of app names
--------------------

- ``CERTUS-DESIGN`` / ``CertusDesignApp``
- ``CERTUS-INDEX`` / ``CertusIndexApp``
- ``CERTUS-STRAT`` / ``CertusStratApp``
- ``CERTUS-INDEX-SPLINE`` / ``CertusIndexSplineApp``
- ``CERTUS-METAL-SINGLE`` / ``CertusMetalSingleApp``
- ``CERTUS-METAL-BILAYER`` / ``CertusMetalBilayerApp``
- ``CERTUS-RE`` / ``CertusREApp``

Any unknown app name yields a minimal "welcome" tour so new apps still
get a default experience.
"""

from __future__ import annotations

from typing import Callable, Iterable


def _steps_design() -> list:
    from certus.ui.certus_onboarding import TourStep

    return [
        TourStep(
            title="Welcome to CERTUS-DESIGN",
            body=(
                "Design multi-layer optical filters and let the solver optimise them. "
                "Press F1 at any time to see every keyboard shortcut."
            ),
            icon_name="layers",
        ),
        TourStep(
            title="Stack editor",
            body="Add layers to the front stack, set their QWOT thickness and mark them as variable.",
            target_attr="front_table",
            icon_name="layers",
        ),
        TourStep(
            title="Spectral targets",
            body="Define the wavelength windows and transmittance targets the solver must match.",
            target_attr="target_table",
            icon_name="target",
        ),
        TourStep(
            title="Reference wavelength",
            body="Pick l0, the QWOT reference. Most designs work well around 550 nm.",
            target_attr="l0_spin",
            icon_name="sliders",
        ),
        TourStep(
            title="Optimize",
            body="Launch the solver via the command palette (Ctrl+K) or the Run menu.",
            icon_name="play",
        ),
    ]


def _steps_index() -> list:
    from certus.ui.certus_onboarding import TourStep

    return [
        TourStep(
            title="Welcome to CERTUS-INDEX",
            body="Characterise the n(λ), k(λ), d and d_variance of a dielectric thin film from a spectrum.",
            icon_name="activity",
        ),
        TourStep(
            title="Load a spectrum",
            body="Use File → Load spectrum (or drop a sample from the palette) to bring in R/T data.",
            icon_name="upload",
        ),
        TourStep(
            title="Substrate",
            body="Import a substrate n,k table (demo samples are shipped in samples/substrate/).",
            icon_name="layers",
        ),
        TourStep(
            title="Run the fit",
            body="The solver combines n/k splines + thickness to match the measured spectrum.",
            icon_name="play",
        ),
        TourStep(
            title="Need help?",
            body="Press F1 for shortcuts, Ctrl+K for the command palette, or Help → Open documentation.",
            icon_name="book-open",
        ),
    ]


def _steps_strat() -> list:
    from certus.ui.certus_onboarding import TourStep

    return [
        TourStep(
            title="Welcome to CERTUS-STRAT",
            body="Stratified fits across strategies - choose the approach that best fits your data.",
            icon_name="layers",
        ),
        TourStep(
            title="Measurements",
            body="Load your measurement file (Excel or CSV) - samples are available in samples/spectrum/.",
            target_attr="measurement_table",
            icon_name="line-chart",
        ),
        TourStep(
            title="Strategy picker",
            body="Pick a strategy or a combination. Each strategy explores a different optimisation path.",
            icon_name="sliders",
        ),
        TourStep(
            title="Run & compare",
            body="Start the comparison, then export the best result via the command palette.",
            icon_name="play",
        ),
    ]


def _steps_index_spline() -> list:
    from certus.ui.certus_onboarding import TourStep

    return [
        TourStep(
            title="Welcome to CERTUS-INDEX+",
            body=(
                "The spline-based thickness and index recovery tool. Use Smart Init on a new "
                "dataset to seed the solver reliably."
            ),
            icon_name="sparkles",
        ),
        TourStep(
            title="Smart Init",
            body="Opens a guided dialog that analyses the data and proposes a starting configuration.",
            icon_name="sparkles",
        ),
        TourStep(
            title="Optimization",
            body="Once initialised, launch the main pipeline with Ctrl+R or via Run → Optimize.",
            icon_name="play",
        ),
        TourStep(
            title="Corridor view",
            body="Explore the d-profile corridor: RMSE vs d, mesh polish, corridor refits.",
            icon_name="activity",
        ),
        TourStep(
            title="Cheatsheet",
            body="Press F1 any time to see every shortcut - the tool exposes many power features.",
            icon_name="keyboard",
        ),
    ]


def _steps_metal() -> list:
    from certus.ui.certus_onboarding import TourStep

    return [
        TourStep(
            title="Welcome to CERTUS-METAL",
            body="Metal-layer characterisation (single or bilayer) from spectro-photometric data.",
            icon_name="layers",
        ),
        TourStep(
            title="Load spectrum",
            body="Load your transmittance / reflectance data - the solver computes n, k and thickness.",
            icon_name="upload",
        ),
        TourStep(
            title="Beam analysis",
            body="Start the analysis and follow the progress in the tracker panel or the log.",
            icon_name="play",
        ),
    ]


def _steps_re() -> list:
    from certus.ui.certus_onboarding import TourStep

    return [
        TourStep(
            title="Welcome to CERTUS-RE",
            body="Reverse-engineer an existing coating from R and T measurements.",
            icon_name="activity",
        ),
        TourStep(
            title="Measurement loader",
            body="Import your Excel measurement file, or switch to the sample demos to explore.",
            icon_name="upload",
        ),
        TourStep(
            title="Targets",
            body="Add / edit spectral targets before running the fit.",
            target_attr="target_table",
            icon_name="target",
        ),
        TourStep(
            title="Run the reverse fit",
            body="Launch the fit from Ctrl+K or the toolbar. Monitor progress in the log panel.",
            icon_name="play",
        ),
    ]


def _default_steps() -> list:
    from certus.ui.certus_onboarding import TourStep

    return [
        TourStep(
            title="Welcome",
            body=(
                "Every CERTUS app has a command palette (Ctrl+K), a shortcuts cheatsheet (F1) "
                "and a recent-files MRU via File → Open recent."
            ),
            icon_name="command",
        ),
    ]


_TOURS_BY_APP_NAME: dict[str, Callable] = {
    "CERTUS-DESIGN": _steps_design,
    "CERTUS-INDEX": _steps_index,
    "CERTUS-STRAT": _steps_strat,
    "CERTUS-INDEX-SPLINE": _steps_index_spline,
    "CERTUS-METAL-SINGLE": _steps_metal,
    "CERTUS-METAL-BILAYER": _steps_metal,
    "CERTUS_RE": _steps_re,
    "CERTUS-RE": _steps_re,
}


def steps_for_app(app_name: str) -> list:
    """Return the :class:`TourStep` list registered for ``app_name``.

    Falls back to a minimal default tour on unknown app names so new
    monoliths still benefit from onboarding without a code change here.
    """
    factory = _TOURS_BY_APP_NAME.get(str(app_name))
    if factory is None:
        return _default_steps()
    try:
        return list(factory())
    except (TypeError, ValueError, AttributeError):  # pragma: no cover - defensive
        return _default_steps()


def registered_app_names() -> Iterable[str]:
    """Return the set of app names with an explicit tour definition."""
    return tuple(_TOURS_BY_APP_NAME.keys())


def run_app_onboarding(app, *, force: bool = False) -> str:
    """Run the onboarding tour tied to ``app.APP_NAME``.

    This is a thin convenience wrapper around
    :func:`certus_onboarding.run_onboarding` that supplies the right
    step list for the app automatically.
    """
    try:
        from certus.ui.certus_onboarding import run_onboarding
    except ImportError:
        return "empty"

    app_name = getattr(app, "APP_NAME", "CERTUS")
    steps = steps_for_app(app_name)
    return run_onboarding(app, app_name, steps, force=force)


__all__ = [
    "steps_for_app",
    "registered_app_names",
    "run_app_onboarding",
]

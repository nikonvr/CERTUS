"""CERTUS-INDEX-SPLINE - the lazy stand-in for the window class: a mixin that must call a method of `CertusIndexSplineApp` outside an instance reads it here, and the module of the window is imported at that call only (class and instance moved, text unchanged, out of certus_index_spline_common.py, which goes on exposing them). A leaf: it imports nothing at module level."""

from __future__ import annotations


class _LazyCertusIndexSplineApp:
    def __getattr__(self, name):
        from certus.ui.certus_index_spline_ui import CertusIndexSplineApp
        return getattr(CertusIndexSplineApp, name)

CertusIndexSplineApp = _LazyCertusIndexSplineApp()

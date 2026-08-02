"""L'objectif et le gradient de DESIGN doivent survivre au pool de PGLOBAL.

``PGlobalOptimizer`` evalue son lot via ``pool.map(self.objective, X)`` puis
lance une recherche locale L-BFGS-B par thread : l'objectif ET le gradient sont
donc appeles simultanement par une dizaine de threads.

Tant que toutes les couches sont variables, chaque appel travaille sur son propre
tableau et tout va bien. Des qu'une epaisseur est figee — cas courant — le
chemin passe par un tampon reconstruit a chaque appel :

    ep_buffer[:] = app._ep0
    ep_buffer[app._var_idx] = x

Si ce tampon est partage entre threads, deux appels s'ecrasent mutuellement entre
l'ecriture et la lecture, et le cout est calcule sur un MELANGE de deux
empilements. Rien ne leve, rien ne previent : l'optimiseur recoit simplement des
valeurs fausses.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

import certus.core.certus_design_core as dc

N_LAYERS = 40
N_THREADS = 12
N_ITER = 3000


class _FakeApp:
    """Juste ce que les deux fonctions lisent, rien de plus."""

    def __init__(self) -> None:
        self._ep0 = np.full(N_LAYERS, 7.0, dtype=np.float64)
        # Une couche sur deux FIGEE : c'est ce qui met all_variable a False.
        self._var_idx = np.arange(0, N_LAYERS, 2)
        self._all_variable = False
        self._ep_buffer = np.array(self._ep0, copy=True)
        self._oblique_mode = False
        self._has_back_calc = False
        for attr in (
            "_n_layers_T",
            "_n_sub",
            "_wls",
            "_tgt_vals",
            "_tgt_weights",
            "_n_back_T",
            "_d_back",
        ):
            setattr(self, attr, None)


_WEIGHTS = np.arange(1, N_LAYERS + 1, dtype=np.float64)


def _signature(ep: np.ndarray) -> float:
    """Rend une valeur qui depend de TOUT le vecteur d'epaisseurs.

    Une somme ponderee : si un autre thread a ecrase ne serait-ce qu'une case du
    tampon, le resultat differe.
    """
    return float(np.dot(ep, _WEIGHTS))


@pytest.fixture
def app(monkeypatch) -> _FakeApp:
    # On substitue au noyau compile une fonction qui renvoie la signature exacte
    # du tampon recu : le test porte sur le tampon, pas sur la physique.
    monkeypatch.setattr(dc, "cost_numba_fast", lambda ep, *a, **k: _signature(ep))
    return _FakeApp()


def test_objectif_concurrent_ne_melange_pas_les_empilements(app: _FakeApp) -> None:
    """Douze threads, epaisseurs distinctes : aucune evaluation ne doit etre fausse.

    Sur la version a tampon partage, ce test releve quelques centaines
    d'evaluations fausses sur 36 000 (mesure : 278 sur 48 000). Le taux est
    faible mais l'effet ne l'est pas : dans un optimiseur global, une valeur
    fausse cree un minimum fantome ou fait rejeter un bon candidat.
    """
    wrong = []

    def attendu(x: np.ndarray) -> float:
        ep = app._ep0.copy()
        ep[app._var_idx] = x
        return _signature(ep)

    def work(seed: int) -> None:
        rng = np.random.default_rng(seed)
        local_wrong = 0
        for _ in range(N_ITER):
            x = rng.uniform(20.0, 200.0, len(app._var_idx))
            if dc._design_objective_wrapper_common(app, x) != attendu(x):
                local_wrong += 1
        if local_wrong:
            wrong.append(local_wrong)

    threads = [threading.Thread(target=work, args=(s,)) for s in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not wrong, f"{sum(wrong)} evaluations fausses sur {N_THREADS * N_ITER}"


def test_le_tampon_est_propre_a_chaque_thread(app: _FakeApp) -> None:
    """Deux threads ne doivent jamais recevoir le MEME objet tampon.

    Verification directe du mecanisme, sans dependre d'un enchainement
    malheureux : c'est le partage lui-meme qui est interdit, pas seulement ses
    consequences observees.
    """
    # On garde une REFERENCE sur chaque tampon, et pas seulement son id().
    # Un thread termine libere son tableau, et CPython reattribue aussitot la
    # meme adresse au suivant : comparer des id() d'objets morts ferait croire a
    # un partage la ou il n'y en a pas.
    seen: list[np.ndarray] = []
    lock = threading.Lock()
    barrier = threading.Barrier(N_THREADS)

    def grab() -> None:
        buf = dc._get_ep_buffer(app)
        with lock:
            seen.append(buf)
        barrier.wait()  # tous vivants en meme temps

    threads = [threading.Thread(target=grab) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len({id(b) for b in seen}) == N_THREADS

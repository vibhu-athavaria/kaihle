"""Eval core shared by the offline harness (``backend/evals``) and in-product sampling (T18).

Everything here MUST stay importable without DeepEval: it lives in the ``eval`` dependency group,
which is not installed in the production image. DeepEval-dependent classes stay in ``backend/evals``.
"""

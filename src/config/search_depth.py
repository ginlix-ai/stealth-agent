from __future__ import annotations

from typing import Any, Dict, Literal, TypedDict

SearchDepthMode = Literal["low", "intermediate", "heavy"]


class SearchDepthConfig(TypedDict):
    max_iterations: int
    coverage_threshold: float
    max_search_results: int
    concurrent_workers: int


SEARCH_DEPTH_MODES: Dict[SearchDepthMode, SearchDepthConfig] = {
    "low": {
        "max_iterations": 2,
        "coverage_threshold": 0.6,
        "max_search_results": 3,
        "concurrent_workers": 2,
    },
    "intermediate": {
        "max_iterations": 3,
        "coverage_threshold": 0.8,
        "max_search_results": 3,
        "concurrent_workers": 5,
    },
    "heavy": {
        "max_iterations": 3,
        "coverage_threshold": 0.9,
        "max_search_results": 3,
        "concurrent_workers": 8,
    },
}


def get_search_depth_config(mode: SearchDepthMode) -> SearchDepthConfig:
    """Return the config for the given search depth mode.

    Defaults to "intermediate" if an unknown mode is provided.
    """
    return SEARCH_DEPTH_MODES.get(
        mode, SEARCH_DEPTH_MODES["intermediate"])  # type: ignore


def apply_search_depth_to_iterative_params(mode: SearchDepthMode,
                                           params: Any) -> Any:
    """Apply the search depth config to an IterativeParams-like object if available.

    This function is resilient: it will set attributes only if they exist, so
    callers can pass either an IterativeParams instance or a simple object/dict-like
    with the expected attributes.
    """
    cfg = get_search_depth_config(mode)

    # Support dataclass-like objects and simple objects with attributes
    if hasattr(params, "max_iterations"):
        setattr(params, "max_iterations", int(cfg["max_iterations"]))
    if hasattr(params, "coverage_threshold"):
        setattr(params, "coverage_threshold", float(cfg["coverage_threshold"]))
    if hasattr(params, "max_search_results"):
        setattr(params, "max_search_results", int(cfg["max_search_results"]))
    if hasattr(params, "concurrent_workers"):
        setattr(params, "concurrent_workers", int(cfg["concurrent_workers"]))

    return params

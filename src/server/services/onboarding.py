"""
Onboarding completion service.

Checks if user has completed onboarding requirements and auto-sets onboarding_completed.
Requirements: at least one stock (watchlist or portfolio) + risk preference.
"""

import logging

from src.server.database import user as user_db
from src.server.database import watchlist as watchlist_db
from src.server.database import portfolio as portfolio_db

logger = logging.getLogger(__name__)


def _has_risk_preference(prefs: dict | None) -> bool:
    """Check if user has any risk preference set (flexible field names)."""
    if not prefs:
        return False
    risk = prefs.get("risk_preference") or {}
    if not isinstance(risk, dict):
        return False
    # Accept risk_tolerance, tolerance, or any non-empty value
    for key in ("risk_tolerance", "tolerance"):
        val = risk.get(key)
        if val and isinstance(val, str) and val.strip():
            return True
    # Fallback: any truthy value in risk_preference
    for v in risk.values():
        if v and isinstance(v, str) and v.strip():
            return True
    return False


async def maybe_complete_onboarding(user_id: str) -> bool:
    """
    If onboarding requirements are met, set onboarding_completed=True.

    Requirements:
    - At least one stock (watchlist item OR portfolio holding)
    - Risk preference set (risk_tolerance or tolerance field)

    Returns:
        True if onboarding was completed, False otherwise.
    """
    try:
        user = await user_db.get_user(user_id)
        if not user:
            return False
        if user.get("onboarding_completed"):
            return False

        prefs = await user_db.get_user_preferences(user_id)
        if not _has_risk_preference(prefs):
            return False

        # Check watchlist items across all watchlists
        watchlists = await watchlist_db.get_user_watchlists(user_id)
        total_items = 0
        for wl in watchlists or []:
            items = await watchlist_db.get_watchlist_items(wl["watchlist_id"], user_id)
            total_items += len(items or [])
        has_watchlist_stock = total_items > 0

        holdings = await portfolio_db.get_user_portfolio(user_id)
        has_portfolio_stock = len(holdings or []) > 0

        if has_watchlist_stock or has_portfolio_stock:
            await user_db.update_user(user_id=user_id, onboarding_completed=True)
            logger.info(f"[onboarding] Auto-completed onboarding for user {user_id}")
            return True
    except Exception as e:
        logger.warning(f"[onboarding] Failed to check/complete onboarding: {e}")
    return False

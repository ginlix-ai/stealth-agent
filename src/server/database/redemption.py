"""
Database functions for code redemption.

Provides a single atomic function that validates and redeems a code
in one database transaction.
"""

import logging
from typing import Any, Dict

from psycopg.rows import dict_row

from src.server.database.conversation import get_db_connection
from src.server.services.membership_service import MembershipService

logger = logging.getLogger(__name__)


async def redeem_code(user_id: str, code: str) -> Dict[str, Any]:
    """
    Validate and redeem a code in a single transaction.

    Checks:
    1. Code exists and is_active
    2. Code not expired
    3. Code not exhausted (current_redemptions < max_redemptions, or max=-1)
    4. User hasn't already redeemed this code
    5. Code tier is >= user's current tier (no downgrade)

    On success: updates users.membership_id, increments current_redemptions,
    inserts redemption_histories row (with plan names for audit).

    Args:
        user_id: The user redeeming the code
        code: The redemption code (case-insensitive, will be uppercased)

    Returns:
        {"previous_plan": "free", "new_plan": "pro", "code": "PROMO123"}

    Raises:
        ValueError: With specific message on any validation failure
    """
    code = code.strip().upper()

    svc = MembershipService.get_instance()
    await svc.ensure_loaded()

    async with get_db_connection() as conn:
        # Run everything in a single transaction
        async with conn.transaction():
            async with conn.cursor(row_factory=dict_row) as cur:
                # 1. Look up the code
                await cur.execute(
                    "SELECT * FROM redemption_codes WHERE code = %s FOR UPDATE",
                    (code,),
                )
                code_row = await cur.fetchone()

                if not code_row:
                    raise ValueError("Invalid code")

                if not code_row['is_active']:
                    raise ValueError("Code is no longer active")

                # 2. Check expiry
                if code_row['expires_at'] is not None:
                    from datetime import datetime, timezone as tz
                    now = datetime.now(tz.utc)
                    if now > code_row['expires_at']:
                        raise ValueError("Code has expired")

                # 3. Check exhaustion
                if code_row['max_redemptions'] != -1:
                    if code_row['current_redemptions'] >= code_row['max_redemptions']:
                        raise ValueError("Code has been fully redeemed")

                # 4. Check double-redeem
                await cur.execute(
                    "SELECT redemption_id FROM redemption_histories WHERE code = %s AND user_id = %s",
                    (code, user_id),
                )
                if await cur.fetchone():
                    raise ValueError("You have already redeemed this code")

                # 5. Get user's current membership_id
                await cur.execute(
                    "SELECT membership_id FROM users WHERE user_id = %s FOR UPDATE",
                    (user_id,),
                )
                user_row = await cur.fetchone()
                if not user_row:
                    raise ValueError("User not found")

                current_membership_id = user_row['membership_id']
                target_membership_id = code_row['membership_id']

                # Resolve to MembershipInfo for rank comparison and name display
                current_plan = svc.get_membership(current_membership_id)
                target_plan = svc.get_membership(target_membership_id)

                # No downgrade check
                if target_plan.rank <= current_plan.rank:
                    if target_membership_id == current_membership_id:
                        raise ValueError(f"You are already on the {current_plan.display_name} plan")
                    raise ValueError(f"Cannot downgrade from {current_plan.display_name} to {target_plan.display_name}")

                # All checks passed — apply the upgrade
                await cur.execute(
                    "UPDATE users SET membership_id = %s, updated_at = NOW() WHERE user_id = %s",
                    (target_membership_id, user_id),
                )

                await cur.execute(
                    "UPDATE redemption_codes SET current_redemptions = current_redemptions + 1 WHERE code = %s",
                    (code,),
                )

                # Audit trail uses plan names (strings) for readability
                await cur.execute("""
                    INSERT INTO redemption_histories (code, user_id, previous_plan, new_plan)
                    VALUES (%s, %s, %s, %s)
                """, (code, user_id, current_plan.name, target_plan.name))

                logger.info(
                    f"[redemption] User {user_id} redeemed code {code}: "
                    f"{current_plan.name} -> {target_plan.name}"
                )

                return {
                    'previous_plan': current_plan.name,
                    'new_plan': target_plan.name,
                    'code': code,
                }

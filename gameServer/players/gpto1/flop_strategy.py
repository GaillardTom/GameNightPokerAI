def get_card_action(
        player_name,
        best_hand,
        highest_hand,
        min_amount,
        max_amount,
        street,
        pot,
        side_pots,
        action_histories,
        logger,
):
    """
    Enhanced decision-making mimicking a poker master’s style.

    Parameters:
      player_name (str): Name of your player.
      best_hand (int): Numeric ranking (1-9) of your best hand (9 is best).
      highest_hand (int): Numeric ranking of the highest board possibility.
      min_amount (float): Amount to call.
      max_amount (float): Maximum raise allowed.
      street (str): "preflop", "flop", "turn", or "river".
      pot (float): Main pot size.
      side_pots (list): List of side-pot dictionaries.
      action_histories (dict): History of actions by street.
      logger: Logger with methods info(), warning(), error().

    Returns:
      Tuple[str, float]: ("call", amount), ("raise", amount), or ("fold", 0).
    """

    # ----------------------------------------------------------------
    # --- AGGRESSION CONSTANTS & MASTER ADJUSTMENT FACTORS -------------
    # ----------------------------------------------------------------
    # Base raise percentages (relative to max_amount).
    AGGRESSION = 1.0  # Global multiplier (e.g., >1.0 for extra aggressive)
    SMALL_RAISE = 0.05  # 5%
    MODERATE_RAISE = 0.10  # 10%
    STRONG_RAISE = 0.20  # 20%
    VERY_STRONG_RAISE = 0.35  # 35%
    ALL_IN_RAISE = 0.50  # 50%

    # If the bet to call is less than 10% of the pot, we consider it a “cheap call.”
    LOW_BET_THRESHOLD = 0.10

    # ----------------------------------------------------------------
    # --- INITIAL LOGGING & SETUP ------------------------------------
    # ----------------------------------------------------------------
    logger.info(f"Street: {street}")
    logger.info(f"Best hand: {best_hand} | Highest board hand: {highest_hand}")
    logger.info(f"Pot: {pot} | Side pots: {side_pots}")
    logger.info(f"Min: {min_amount} | Max: {max_amount}")

    # If min_amount or max_amount are not positive, mark opponent as “dry” and set defaults.
    OPP_DRY = False
    if min_amount <= 0:
        OPP_DRY = True
        min_amount = 500
    if max_amount <= 0:
        OPP_DRY = True
        max_amount = 501

    # ----------------------------------------------------------------
    # --- HELPER FUNCTIONS -------------------------------------------
    # ----------------------------------------------------------------
    def compute_pot_odds():
        """Returns the fraction of the pot that min_amount represents."""
        return min_amount / (pot + min_amount) if (pot + min_amount) > 0 else 1.0

    def master_raise_factor(base_factor):
        """
        Adjusts a base raise factor based on pot odds.
        – If min_amount is cheap relative to the pot (low odds), be bolder.
        – If min_amount is expensive (high odds), be cautious.
        """
        odds = compute_pot_odds()
        if odds < 0.15:
            adjusted = base_factor * 1.2
        elif odds > 0.30:
            adjusted = base_factor * 0.8
        else:
            adjusted = base_factor
        logger.info(
            f"Master adjustment: base {base_factor:.2f} -> adjusted {adjusted:.2f} (pot odds: {odds:.2f})"
        )
        return adjusted

    def raise_player(amount_percent):
        """
        Computes a raise scaled by AGGRESSION and any master adjustment.
        Returns a tuple (action, amount).
        """
        # Apply master adjustment to the base raise percent.
        adjusted_percent = master_raise_factor(amount_percent)
        desired_raise = max_amount * adjusted_percent * AGGRESSION
        if OPP_DRY:
            logger.info("Opponent appears tight; opting to call instead of raise.")
            return "call", min_amount
        # Ensure raise is within allowed limits.
        desired_raise = max(min_amount, min(desired_raise, max_amount))
        if desired_raise > min_amount:
            logger.info(f"Raising with amount: {desired_raise:.2f}")
            return "raise", desired_raise
        return "call", min_amount

    def get_last_action():
        """Returns the last action from any street (if available)."""
        for actions in action_histories.values():
            if actions:
                return actions[-1]
        return None

    def checkRaisePreflop(histories):
        """True if any raise was made during preflop."""
        for action in histories.get("preflop", []):
            if action.get("action") == "RAISE":
                return True
        return False

    def sum_raises(histories, player_name):
        """Sums the total amount this player has raised."""
        total = 0
        for actions in histories.values():
            for action in actions:
                if action.get("action") == "RAISE" and action.get("name") == player_name:
                    total += action.get("paid", 0)
        return total

    def is_opponent_aggressive():
        """Returns True if opponents have raised at least twice."""
        count = 0
        for actions in action_histories.values():
            for action in actions:
                if action.get("action") == "RAISE" and action.get("name") != player_name:
                    count += 1
        return count >= 2

    current_raise = sum_raises(action_histories, player_name)
    opponent_aggressive = is_opponent_aggressive()
    logger.info(f"Opponent is {'aggressive' if opponent_aggressive else 'passive'}")
    logger.info(f"Last action: {get_last_action()}")
    logger.info(f"Computed pot odds: {compute_pot_odds():.2f}")

    # ----------------------------------------------------------------
    # --- STRATEGY LOGIC BY STREET (POKER MASTER STYLE) -------------
    # ----------------------------------------------------------------
    if street == "flop":
        logger.info("Flop decision: channeling master intuition...")
        # Premium holdings: premium hands or strong draws.
        if best_hand >= 7 and best_hand >= highest_hand:
            # With a premium hand, be bold.
            factor = ALL_IN_RAISE if not opponent_aggressive else VERY_STRONG_RAISE
            logger.info("René would say: 'Confidence is key! I must seize the moment.'")
            return raise_player(factor)
        # Moderately strong hands (good pair or drawing potential).
        elif best_hand >= 4:
            if min_amount < pot * LOW_BET_THRESHOLD:
                logger.info("Moderate strength with cheap call; let's put some pressure.")
                return raise_player(MODERATE_RAISE)
            else:
                logger.info("Bet is steep relative to the pot; I'll call and keep options open.")
                return "call", min_amount
        # Weak holdings: a mere pair or below.
        elif best_hand >= 2:
            if checkRaisePreflop(action_histories):
                logger.info("Not great, but we've shown preflop strength. I call this one.")
                return "call", min_amount
            else:
                logger.info("Without prior aggression, this hand won't fly. Folding.")
                return "fold", 0
        else:
            logger.info("This flop doesn't inspire confidence – folding.")
            return "fold", 0

    elif street == "turn":
        logger.info("Turn decision: reading the table like a master strategist...")
        if best_hand >= 7 and best_hand >= highest_hand:
            factor = VERY_STRONG_RAISE if not opponent_aggressive else STRONG_RAISE
            logger.info("Turn: Holding a monster hand – time to build the pot!")
            return raise_player(factor)
        elif best_hand >= 4:
            if min_amount < pot * LOW_BET_THRESHOLD:
                logger.info("Turn: A solid hand with enticing pot odds – I'll raise.")
                return raise_player(MODERATE_RAISE)
            else:
                logger.info("Turn: Facing a heavy bet; I'll call and re-evaluate on the river.")
                return "call", min_amount
        elif best_hand >= 2:
            logger.info("Turn: Just a pair; I call to see if I can improve on the river.")
            return "call", min_amount
        else:
            logger.info("Turn: Not strong enough to continue – folding.")
            return "fold", 0

    elif street == "river":
        logger.info("River decision: the final act. Time for a masterstroke!")
        if best_hand >= 7 and best_hand >= highest_hand:
            # On river, if our hand is dominant and opponents are passive, we can go big.
            factor = ALL_IN_RAISE if not opponent_aggressive else VERY_STRONG_RAISE
            logger.info("River: This is a monster hand – I'm going all in on intuition!")
            return raise_player(factor)
        elif best_hand >= 4:
            if min_amount < pot * LOW_BET_THRESHOLD:
                logger.info("River: Strong hand with favorable odds – I'll raise to extract value.")
                return raise_player(STRONG_RAISE)
            else:
                logger.info("River: Good enough to call but not to risk too much – calling.")
                return "call", min_amount
        elif best_hand >= 2:
            logger.info("River: Only a pair, but I'll call if the price is right.")
            return "call", min_amount
        else:
            logger.info("River: My hand doesn't merit further investment – folding.")
            return "fold", 0

    # Default action if no street-specific logic applies.
    logger.info("Default decision: erring on the side of caution.")
    if min_amount <= 500:
        logger.info("Default: low bet – calling.")
        return "call", min_amount
    else:
        logger.info("Default: bet too steep – folding.")
        return "fold", 0

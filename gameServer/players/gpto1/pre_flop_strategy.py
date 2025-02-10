from random import randint

def get_pre_flop_action(
    player_name,
    hole_cards,
    min_amount,
    max_amount,
    street,
    pot,
    side_pots,
    action_histories,  # can be None
    logger,
):
    """
    Determines the appropriate pre-flop action (call, raise, or fold) based on the hole cards
    and the betting amounts.

    Parameters:
    - player_name (str): The name of your player
    - hole_cards (list of str): The list of hole cards (e.g., ['DQ', 'S6']).
    - min_amount (float): The minimum amount to be matched or raised.
    - max_amount (float): The maximum allowable amount for a bet or raise.
    - street (str): The current betting round, e.g., "preflop".
    - pot (float): The size of the main pot
    - side_pots (list): If playing against more than one player this is a side pot.
    - action_histories (dict or None): A dict containing actions so far, or None.
    - logger (DcmLoggerWrapper): A logger which will add messages to match report.

    Returns:
    Tuple[str, float]:
        A tuple representing the recommended action and the corresponding amount.
        - If the action is "call," the amount is the minimum amount to be matched.
        - If the action is "raise," the amount is the recommended raise amount.
        - If the action is "fold," the amount is always 0.
    """

    ################################################
    # 1) Handle potential None for action_histories
    ################################################
    if not action_histories or not isinstance(action_histories, dict):
        # If action_histories is None or not a dict, default to empty
        preflop_actions = []
    else:
        preflop_actions = action_histories.get("preflop", [])

    # Safely get the last action from preflop
    if preflop_actions:
        last_action_dict = preflop_actions[-1]
        last_action = last_action_dict.get("action", "SMALLBLIND")
    else:
        last_action = "SMALLBLIND"

    ################################################
    # 2) Setup rank map and helper functions
    ################################################
    rank_map = {
        'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
        '9': 9,  '8': 8,  '7': 7,  '6': 6,  '5': 5,
        '4': 4,  '3': 3,  '2': 2
    }

    def get_card_value(card):
        """Extract the rank from a card string, handling e.g. 'S10' vs 'DQ'."""
        rank_str = card[1:] if len(card) == 3 else card[1]
        return rank_map.get(rank_str, 2)

    values = [get_card_value(c) for c in hole_cards]

    def is_pair():
        return values[0] == values[1]

    def is_suited():
        return hole_cards[0][0] == hole_cards[1][0]

    def is_connected(gap=1):
        return abs(values[0] - values[1]) <= gap

    def any_above(x):
        return any(v > x for v in values)

    def all_above(x):
        return all(v > x for v in values)

    def any_broadway():
        # broadway card => rank >= 10
        return any_above(9)

    # Ensure min_amount and max_amount have sane defaults
    if min_amount <= 0:
        min_amount = 1
    if max_amount <= 0:
        max_amount = 50

    ################################################
    # 3) Log details for debugging
    ################################################
    logger.info(
        f"[Preflop] {player_name} hole_cards={hole_cards}, "
        f"min_amount={min_amount}, max_amount={max_amount}, pot={pot}, "
        f"last_action={last_action}"
    )
    print(
        f"DEBUG => Player={player_name}, HoleCards={hole_cards}, "
        f"min={min_amount}, max={max_amount}, pot={pot}, last_action={last_action}"
    )

    ################################################
    # 4) Evaluate a "score" or "category" for the hand
    ################################################
    def evaluate_preflop_strength(vals, suited):
        v1, v2 = sorted(vals, reverse=True)
        # Pair
        if v1 == v2:
            if v1 >= 13:    # KK+
                return 10
            elif v1 == 12: # QQ
                return 9
            elif v1 == 11: # JJ
                return 8
            elif v1 == 10: # TT
                return 7
            else:
                return 6
        else:
            # Not a pair
            # AK, AQ, AJ, etc.
            if v1 == 14 and v2 >= 13:  # AK
                return 9 if suited else 8
            elif v1 == 14 and v2 >= 12: # AQ
                return 8 if suited else 7
            elif v1 == 14 and v2 >= 10: # AJ, AT
                return 7 if suited else 6
            elif v1 == 13 and v2 == 12: # KQ
                return 7 if suited else 6
            elif v1 == 14 and v2 < 10:
                return 5 if suited else 4
            elif v1 == 13 and v2 == 11: # KJ
                return 6 if suited else 5
            else:
                # Possibly connectors
                if suited and is_connected(gap=1) and v1 >= 10:
                    return 5
                if is_connected(gap=1) and v1 >= 10:
                    return 4
                if all_above(9):
                    return 5
                if any_broadway():
                    return 3
                if suited and is_connected(gap=4):
                    return 3
                return 2

    hand_score = evaluate_preflop_strength(values, is_suited())

    ################################################
    # 5) Make decision based on hand score & bet size
    ################################################
    bet_ratio = min_amount / float(max_amount) if max_amount else 0
    pot_ratio = min_amount / float(pot) if pot else 0

    logger.info(
        f"[Preflop] hand_score={hand_score}, bet_ratio={bet_ratio:.2f}, "
        f"pot_ratio={pot_ratio:.2f}"
    )

    if hand_score >= 9:  # Monster
        if bet_ratio < 0.3:
            raise_amount = max_amount * 0.2
            logger.info("Monster hand (score >= 9) => raising.")
            return "raise", raise_amount
        else:
            logger.info("Monster hand, but bet is huge => calling.")
            return "call", min_amount

    elif hand_score >= 7:  # Strong
        if bet_ratio < 0.2:
            raise_amount = max_amount * 0.15
            logger.info("Strong hand => moderate raise.")
            return "raise", raise_amount
        elif bet_ratio < 0.5:
            logger.info("Strong hand => biggish bet => call.")
            return "call", min_amount
        else:
            # Occasional call if the bet is huge
            if randint(0, 2) == 0:
                logger.info("Strong hand => occasionally calling large bet.")
                return "call", min_amount
            else:
                logger.info("Strong hand => but bet too big => folding sometimes.")
                return "fold", 0

    elif hand_score >= 5:  # Medium
        if bet_ratio < 0.1:
            logger.info("Medium hand => cheap to call => calling.")
            return "call", min_amount
        elif bet_ratio < 0.25:
            if randint(0, 3) == 0:
                raise_amt = max_amount * 0.1
                logger.info("Medium hand => occasionally re-raise.")
                return "raise", raise_amt
            else:
                logger.info("Medium hand => usually just call.")
                return "call", min_amount
        else:
            logger.info("Medium hand => bet too large => fold.")
            return "fold", 0

    elif hand_score >= 3:  # Weak-ish
        if bet_ratio < 0.05:
            logger.info("Weak-ish hand => but it's very cheap => call.")
            return "call", min_amount
        else:
            logger.info("Weak-ish hand => not cheap => fold.")
            return "fold", 0

    else:  # Trash
        if bet_ratio < 0.02:
            logger.info("Trash hand => minimal bet => call anyway.")
            return "call", min_amount
        else:
            logger.info("Trash hand => folding.")
            return "fold", 0

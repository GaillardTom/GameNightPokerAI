def get_card_action(player_name, best_hand, highest_hand, min_amount, max_amount, street, pot, side_pots, action_histories, logger):
    """
    Optimized post-flop strategy considering hand strength, board texture, and opponent tendencies.
    """
    OPP_DRY = False


    if min_amount <= 0:
        OPP_DRY = True
        min_amount = 500
    if max_amount <= 0: 
        OPP_DRY = True
        max_amount = 501
    
    # Function to determine the action to raise the player
    # Take in the amount_percent between 0 and 1 and return the action and the amount
    def raise_player(amount_percent):
        desired_raise = max_amount * amount_percent
        if OPP_DRY:
            return "call", min_amount
        if desired_raise > max_amount:
            return "raise", max_amount
        if desired_raise > min_amount and desired_raise < max_amount:
            return "raise", desired_raise
        else:
            return "call", min_amount

    # last_action = action_histories.get(street, [{}])[-1].get("action", "")
    is_top_pair = best_hand == 2 and highest_hand == 2
    is_three_of_a_kind = best_hand == 3
    is_flush_or_straight = best_hand >= 5
    opponent_aggressive = sum(1 for action in action_histories.get(
        street, []) if action.get('action') == 'RAISE') >= 2

    if is_flush_or_straight:
        return "raise", raise_player(0.5)
    elif is_three_of_a_kind:
        return "raise", raise_player(0.3)
    elif is_top_pair:
        return "call", min_amount
    elif best_hand >= 2 and not opponent_aggressive:
        return "call", min_amount
    else:
        return "fold", 0

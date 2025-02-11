def get_pre_flop_action(
    player_name,
    hole_cards,
    min_amount,
    max_amount,
    street,
    pot,
    side_pots,
    action_histories,
    logger,
):
    card_rank_map = {'A': 14, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                     '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13}

    # Get numerical values of both cards
    values = []
    for card in hole_cards:
        if len(card) == 3: 
            values.append(card_rank_map[card[1:]])
        else: 
            values.append(card_rank_map[card[1]])

    OPP_DRY = False

    if min_amount < 0 or max_amount <= 0:
        OPP_DRY = True
        min_amount = 500
        max_amount = 501

    # Log the most information possible to help debugging
    logger.info(f"Player {player_name} has hole cards {hole_cards}")
    logger.info(f"Min amount: {min_amount}")
    logger.info(f"Actions history: {action_histories}")
    logger.info(f"Pot: {pot}")
    logger.info(f"Max amount: {max_amount}")

    # Function to determine the action to raise the player
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

    # Helper functions
    def is_color_same():
        return hole_cards[0][0] == hole_cards[1][0]

    def is_pair():
        return values[0] == values[1]

    def all_values_above(lowest_card):
        return all(value > lowest_card for value in values)

    def any_value_above(lowest_card):
        return any(value > lowest_card for value in values)

    def all_values_below(highest_card):
        return all(value < highest_card for value in values)

    def check_potential_straight():
        return abs(values[0] - values[1]) <= 1

    # Improved strategy
    if is_pair() and all_values_above(10):
        logger.info("Raise as both cards are high and we have a pair")
        return raise_player(0.2)
    elif is_pair():
        logger.info("Raise as we have a pair")
        return raise_player(0.1)
    elif all_values_above(10) and is_color_same():
        logger.info("Raise as both cards are high and suited")
        return raise_player(0.15)
    elif all_values_above(10):
        logger.info("Raise as both cards are high")
        return raise_player(0.1)
    elif any_value_above(11):
        logger.info(f"Call as we have a high card {values[0], values[1]}")
        return "call", min_amount
    elif check_potential_straight() and is_color_same():
        logger.info("Call as we have connected suited cards")
        return "call", min_amount
    elif check_potential_straight():
        if min_amount < max_amount * 0.1:
            logger.info("Call as we have connected cards")
            return "call", min_amount
        else:
            logger.info("Fold as the raise is too much")
            return "fold", 0
    elif all_values_below(5):
        if min_amount < max_amount * 0.05:
            logger.info("Call as both cards are low but the raise is small")
            return "call", min_amount
        else:
            logger.info("Fold as both cards are low and the raise is high")
            return "fold", 0
    else:
        if min_amount < max_amount * 0.05:
            logger.info("Call as we have nothing but the raise is small")
            return "call", min_amount 
        else:
            return "fold", 0
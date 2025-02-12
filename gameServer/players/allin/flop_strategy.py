from random import randint, random

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
    return "raise", max_amount
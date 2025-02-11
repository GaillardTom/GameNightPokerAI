from random import randint, random

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
   return "raise", max_amount
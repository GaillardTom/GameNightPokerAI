import logging
from flop_strategy import get_card_action
best_hand = 0
highest_hand = 4
card_action = get_card_action(
    player_name= "Player",
    best_hand = best_hand,
    highest_hand = highest_hand,
    min_amount = 10,
    max_amount = 100,
    street = "flop",
    pot = 100,
    side_pots = [],
    action_histories = [],
    logger = logging,
)

print(card_action)
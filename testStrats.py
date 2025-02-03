from testModel import get_model_output
from flop_strategy import get_card_action
import logging
hole_card = ["CK", "C6"]
community_card = ["C7", "C8", "C9"]

best_hand, highest_hand = get_model_output(hole_card + community_card, "team_name")
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
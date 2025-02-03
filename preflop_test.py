import logging
#import the get_pre_flop_action function from the preflop_strategy module
from pre_flop_strategy import get_pre_flop_action
# Example usage with a starting hand (e.g., K6 suited)
hole_cards = ["CA", "C6"]
pre_flop_action = get_pre_flop_action(
    player_name = "Player",
    hole_cards = hole_cards,
    min_amount = 10,
    max_amount = 1000,
    street = "preflop",
    pot = 50,
    side_pots = [],
    action_histories = [],
    logger=logging,
)
print(pre_flop_action)

hole_cards = ["S2", "C4"]
pre_flop_action = get_pre_flop_action(
    player_name = "Player",
    hole_cards = hole_cards,
    min_amount = 10,
    max_amount = 1000,
    street = "preflop",
    pot = 50,
    side_pots = [],
    action_histories = [],
    logger=logging,
)
print(pre_flop_action)

hole_cards = ["SA", "C4"]
pre_flop_action = get_pre_flop_action(
    player_name = "Player",
    hole_cards = hole_cards,
    min_amount = 10,
    max_amount = 1000,
    street = "preflop",
    pot = 50,
    side_pots = [],
    action_histories = [],
    logger=logging,
)
print(pre_flop_action)

hole_cards = ["SK", "SQ"]
pre_flop_action = get_pre_flop_action(
    player_name = "Player",
    hole_cards = hole_cards,
    min_amount = 10,
    max_amount = 1000,
    street = "preflop",
    pot = 50,
    side_pots = [],
    action_histories = [],
    logger=logging,
)
print(pre_flop_action)

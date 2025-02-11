
from random import randint

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
    """
    Determines the appropriate pre-flop action (call, raise, or fold) based on the hole cards
    and the betting amounts.

    Parameters:
    - player_name (str): The name of your player - useful when looking at side pots / action histories
    - hole_cards (list of str): The list of hole cards (e.g., ['DQ', 'S6']).
    - min_amount (float): The minimum amount to be matched or raised.
    - max_amount (float): The maximum allowable amount for a bet or raise.
    - street (str): preflop
    - pot (float): The size of the main pot
    - side_pots (list): If playing against more than one player this is a side pot.
        [{'amount': 45, 'eligibles': ['Player 1']}]
    - action_histories (dict):  A dict where the key is street of the game played so far. The value is a list of actions
        that happened with the latest action being the last one in the list.
        { "preflop": [
            { "action": "SMALLBLIND", "amount": 10, "add_amount": 10, "uuid": "1", "name": "Random Player" },
            { "action": "BIGBLIND", "amount": 20, "add_amount": 10, "uuid": "2", "name": "AI Player" },
            { "action": "CALL", "amount": 20, "paid": 20, "uuid": "0", "name": "Call Everything Player" },
            { "action": "FOLD", "uuid": "1", "name": "Random Player" },
            { "action": "CALL", "amount": 20, "paid": 0, "uuid": "2", "name": "AI Player" }
        ]}
    - logger (DcmLoggerWrapper): A logger which will add messages to match report.
        Methods avialble are:
        * error(str)
        * warning(str)
        * info(str)

    Returns:
    Tuple[str, float]: A tuple representing the recommended action and the corresponding amount.
                      - If the action is "call," the amount is the minimum amount to be matched.
                      - If the action is "raise," the amount is the recommended raise amount.
                      - If the action is "fold," the amount is always 0.

    Raises:
    None
    """

    card_rank_map = {'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                     '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13}

    # Get numerical values of both cards
    values = []
    for card in hole_cards:
        if len(card) == 3: 
            values.append([card_rank_map[card[1:]]])
        else: 
            values.append(card_rank_map[card[1]])

    # Log the most informations possible to help debugging
    logger.info(f"Player {player_name} has hole cards {hole_cards}")
    logger.info(f"Min amount: {min_amount}")
    logger.info(f"actions history {action_histories}")
    logger.info(f"Pot: {pot}")
    logger.info(f"max amounts: {max_amount}")
    #also print them to the console for testing
    print(f"Player {player_name} has hole cards {hole_cards}")
    print(f"Min amount: {min_amount}")
    print(f"actions history {action_histories}")
    print(f"Pot: {pot}")
    print(f"max amounts: {max_amount}")
    
     # Function to get the latest action
    def get_last_action(): 
        #Fix to check if the action_histories is empty
        if(not action_histories):
            return 'SMALLBLIND'
        for key, value in action_histories.items():
            if value != []:
                return value[-1]['action']
        return 'SMALLBLIND'

    #Fix for OPP_DRY happens when the min_amount or max_amount are -1
    if min_amount <= 0:
        OPP_DRY = True
        min_amount = 500
    if max_amount <= 0: 
        OPP_DRY = True
        max_amount = 501
    
    last_action = get_last_action()
    print(last_action)
    #Small fix for Ace so that it is considered as 14 instead of 1 (to better count the high cards)
    if values[0] == 1: 
        values[0] = 14
    elif values[1] == 1: 
        values[1] = 14
    #We are the big blind 

    if min_amount <= 0: 
        min_amount = 1
    elif max_amount <= 0: 
        max_amount = 10
    

    #Helper function
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
    def isColorSame():
        if hole_cards[0][0] == hole_cards[1][0]:
            return True
        return False
    def isPair():
        return values[0] == values[1]    
    #Check if all cards are above a certain value
    def allValuesAbove(lowest_card):
        return all(value > lowest_card for value in values)
    #check if any cards is above a certain value
    def anyValueAbove(lowest_card):
        return any(value > lowest_card for value in values)
    #check if all cards are below a certain value
    def allValuesBelow(highest_card):
        return all(value < highest_card for value in values) 
    #check if the cards are connected (potential straight)
    def checkPotentialStraight():
        return abs(values[0] - values[1]) <= 1
    if last_action == 'SMALLBLIND':
    #if True:
        if (isPair() or allValuesAbove(10)) and isColorSame():
            logger.info("Raise as both cards are high and we have a pair and same color")
            return "raise", max_amount * 0.1
        elif isPair() and allValuesAbove(10):
            logger.info("Raise as both cards are high and we have a pair")
            return "raise", max_amount * 0.08
         # Check for pairs
        elif isPair():
            logger.info("Raise as we have a pair")
            return "raise", max_amount * 0.015
        elif allValuesAbove(10):
            logger.info("Raise as both cards are high")
            return "raise", max_amount * 0.015
        elif any(value >= 11 for value in values):
            logger.info(f"Call as we have a high card {values[0], values[1]}")
            return "call", min_amount
        elif checkPotentialStraight():
            if min_amount < max_amount * 0.05:
                logger.info("Call as we have connected cards")
                return "call", min_amount
            else:
                logger.info("Fold as the raise is too much")
                return "fold", 0
        elif allValuesBelow(5):
            if min_amount < max_amount * 0.02:
                logger.info("Call as both cards are less than 5 but the raise is small")
                return "call", min_amount
            else:
                logger.info("Both hole cards are less than 5 and the raise is high so fold")
                return "fold", 0
        else:
            if min_amount < max_amount * 0.05:
                logger.info("Call as we have nothing but the raise is small")
                return "call", min_amount 
            else:
                return "fold", 0
    elif last_action == "BIGBLIND":
    # elif False:
        if isPair() and allValuesAbove(10):
            logger.info("Raise as both cards are high and we have a pair")
            return "raise", max_amount * 0.1
        elif anyValueAbove(10):
            if min_amount < max_amount * 0.2:
                logger.info("Call as we have a high card")
                return "call", min_amount
            else: 
                if 1 == randint(0, 3):
                    logger.info(f"Call as we have a high card {values[0], values[1]} and god is on our side")
                    return "call", min_amount
                else:
                    logger.info("Fold as the raise is too high")
                    return "fold", 0
        # Check for pairs
        elif isPair():
            logger.info("Raise as we have a pair")
            return "raise", max_amount * 0.01
        # Check if both cards are less than 5
        
        # Check for connected cards (potential straight)
        elif checkPotentialStraight():
            if min_amount < max_amount * 0.05 and pot < 2000:
                logger.info("Call as we have connected cards")
                return "call", min_amount
            else:
                logger.info("Fold as the raise is too much")
                return "fold", 0
       
        elif isColorSame() and any(value >= 8  for value in values):
            if min_amount < max_amount * 0.05:
                logger.info("Call as we have same color")
                return "call", min_amount
            else:
                logger.info("Fold as the raise is too much")
                return "fold", 0
        elif isColorSame(): 
            if min_amount < max_amount * 0.02:
                logger.info("Call as we have same color")
                return "call", min_amount
            else:
                logger.info("Fold as the raise is too much")
                return "fold", 0
        elif allValuesAbove(10):
            if min_amount < max_amount * 0.05:
                logger.info("Call as both cards are high")
                return "call", min_amount
            else:
                logger.info("Fold as the raise is too much")
                return "fold", 0
        else:
            logger.info("Fold as we got nothing good and we are the small blind")
            return "fold", 0
    elif last_action == "CALL":
        if isPair(): 
            logger.info("Raise a bit as we have a pair")
            return "raise", max_amount * 0.02
        elif allValuesAbove(9):
            logger.info("raise as both cards are high")
            return "raise", max_amount * 0.034
        elif isColorSame() and anyValueAbove(8):
            return "call", min_amount
        elif anyValueAbove(10):
            if min_amount < 5000:
                logger.info("call as we have a high card")
                return "call", min_amount
            else: 
                logger.info("Got high card but Fold as the raise is too high")
                return "fold", 0
        elif abs(values[0] - values[1]) <= 2:
            return "call", min_amount 
        else:
            if min_amount < 1000:
                logger.info("Call as we have nothing but the raise is small")
                return "call", min_amount
            else: 
                logger.info("Fold as the raise is too high")
                return "fold", 0
    else:
        if isPair() and values[0] == 14:
            if max_amount * 0.2 >= min_amount:
                logger.info("Raise as both cards are high and we have a pair of Aces")
                return "raise", max_amount * 0.2
            else: 
                logger.info("Calling the preflop as we have a pair of Aces")
                return "call", min_amount
        if isPair() and allValuesAbove(10):
            if max_amount * 0.1 >= min_amount:
                logger.info("Call as both cards are high and we have a pair")
                return "raise", max_amount * 0.1
            else: 
                logger.info("Calling the preflop")
                return "call", min_amount
        elif allValuesAbove(9) and isColorSame():
            if max_amount * 0.1 >= min_amount:
                logger.info("Call as both cards are high and we have a pair")
                return "raise", max_amount * 0.1
            else: 
                logger.info("Calling the preflop")
                return "call", min_amount
        elif isPair(): 
            if min_amount <= 50000:
                logger.info("Call as we have a pair and raise is less than 40% of the max amount")
                return "call", min_amount
            else: 
                logger.info("Fold as the raise is higher than 40% of the max amount")
                return "fold", 0
        elif isColorSame() and anyValueAbove(9):
            if min_amount < 40000:
                logger.info("Call as we have same color")
                return "call", min_amount
            else: 
                logger.info("Fold as the raise is too much")
                return "fold", 0
        elif allValuesAbove(10):
            if(min_amount < max_amount * 0.6):
                logger.info("Call as both cards are high")
                return "call", min_amount
            else: 
                logger.info("Fold as the raise is too much but cards are high")
                return "fold", 0
        elif anyValueAbove(10):
            if(min_amount <= 5000 and pot < 4000):
                logger.info("Call as we have a high card")
                return "call", min_amount
            else: 
                logger.info("Fold as the raise is too much")
                return "fold", 0
        elif abs(values[0] - values[1]) <= 2:
            if(min_amount < max_amount * 0.2 and pot <= 5000):
                logger.info("Call as we have connected cards")
                return "call", min_amount
            else:
                logger.info("Fold as the raise is too much")
                return "fold", 0
        else: 
            logger.info("Fold as we got nothing good")
            return "fold", 0




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
    Determines the appropriate post-flop action (call, raise, or fold) based on the hole cards
    and the betting amounts.

    Parameters:
    - player_name (str): The name of your player - useful when looking at side pots / action histories
    - best_hand (int): The numerical category of the player's best possible hand (1-9, with 9 being the best).
    - highest_hand (int): The numerical category of the highest possible hand on the table.
    - min_amount (float): The minimum amount to be matched or raised.
    - max_amount (float): The maximum allowable amount for a bet or raise.
    - street (str): preflop | flop | turn | river
    - pot (float): The size of the main pot
    - side_pots (list): If playing against more than one player this is a side pot.
        [{'amount': 45, 'eligibles': ['Player 1']}]
    - action_histories (dict):  A dict where the key is street of the game played so far. The value is a list of actions
        that happened with the latest action being the last one in the list.
        {
        "preflop": [
            { "action": "SMALLBLIND", "amount": 10, "add_amount": 10, "uuid": "1", "name": "Random Player" },
            { "action": "BIGBLIND", "amount": 20, "add_amount": 10, "uuid": "2", "name": "AI Player" },
            { "action": "CALL", "amount": 20, "paid": 20, "uuid": "0", "name": "Call Everything Player" },
            { "action": "FOLD", "uuid": "1", "name": "Random Player" },
            { "action": "CALL", "amount": 20, "paid": 0, "uuid": "2", "name": "AI Player" }
        ],
        "flop": [
            { "action": "CALL", "amount": 0, "paid": 0, "uuid": "2", "name": "AI Player" },
            { "action": "CALL", "amount": 0, "paid": 0, "uuid": "0", "name": "Call Everything Player" }
            { "action": "RAISE", "amount": 15000, "paid": 15000, "uuid": "0", "name": "Call Everything Player" }
        ],
        "turn": [
            { "action": "CALL", "amount": 0, "paid": 0, "uuid": "2", "name": "AI Player" },
            { "action": "CALL", "amount": 0, "paid": 0, "uuid": "0", "name": "Call Everything Player" }
        ],
        "river": []
        }
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

    # Log the current state
    logger.info(f"Current street: {street}")
    logger.info(f"Best hand: {best_hand}, Highest hand: {highest_hand}")
    logger.info(f"Pot size: {pot}, Side pots: {side_pots}")
    logger.info(f"Action histories: {action_histories}")
    logger.info(f"Minimum amount: {min_amount}, Maximum amount: {max_amount}")

    OPP_DRY = False
    def checkRaisePreflop(action_histories):
        #Check to see if we have raised during the preflop phase
        #If we have then we should call
        #If we have not then we should fold
        
        for action in action_histories.get("preflop", []):
            print(f"Single Action in preflop: {action}")
            if action != []:
                if action.get("action") == "RAISE":
                    return True
        return False
    #Function to that sums the raises we've made
    # def sum_raises(action_histories):
    #     c = 0 
    #     print(action_histories)
    #     for key, value in action_histories.items():
    #         for actions in action_histories[key]:
    #             for action in actions:
    #                 if action != []:
    #                     if action[0] == "RAISE" and action[-1] == player_name:
    #                         c += action["paid"]
    #     return c                
    def sum_raises(action_histories, player_name):
        total_raises = 0  # Initialize the counter for raises
        
        # Loop through each phase in the action_histories
        for key, actions in action_histories.items():
            for action in actions:
                # Check if the action is a "RAISE" and if the player's name matches
                if action.get('action') == 'RAISE' and action.get('name') == player_name:
                    # Add the "paid" value to the total raise amount
                    total_raises += action.get('paid', 0)
        
        return total_raises

    
    # Determine opponent's aggressiveness
    def is_opponent_aggressive():
        # #make the sum of all the actions that are aggressive and that is not me 
        # c = 0 
        # for key, value in action_histories.items():
        #     for actions in action_histories[key]:
        #         for action in actions:
        #             if action != []:
        #                 if action[0] == "RAISE" and action[-1] != player_name:
        #                     c += 1
        # return c >= 2  

        aggressive_count = 0 
        
        # Loop through all the phases in the action_histories
        for key, actions in action_histories.items():
            for action in actions:
                # Check if the action is a "RAISE" and not by the player_name
                if action.get('action') == 'RAISE' and action.get('name') != player_name:
                    aggressive_count += 1
        
        # Return True if there are 2 or more raises by opponents
        return aggressive_count >= 2

    current_raise = sum_raises(action_histories, player_name)
    opponent_aggressive = is_opponent_aggressive()
    logger.info(f"Opponent is {'aggressive' if opponent_aggressive else 'passive'}")

    if min_amount <= 0:
        OPP_DRY = True
        min_amount = 500
    if max_amount <= 0: 
        OPP_DRY = True
        max_amount = 501
    # Determine strategy based on the stage of the game and opponent's aggressiveness
    if street == "flop":
        logger.info("Flop strategy")
        #If we have the biggest hand then we should raise on the flop
        if best_hand >= highest_hand and best_hand >= 2: 
            if not OPP_DRY and max_amount * 0.2 < max_amount:
                logger.info(f"Hand strength {best_hand} is one of the best - raising")
                return "raise", max_amount * 0.2
            else:
                return "call", min_amount
        elif best_hand >= highest_hand and best_hand < 2:
            if checkRaisePreflop(action_histories) and min_amount <= 5000:
                logger.info(f"Hand strength {best_hand} is a pair but we raised preflop so let's keep it - raising")
                return "raising", 2000
            if min_amount < 10000: 
                return "call", min_amount
            else: 
                return "fold", 0
        if best_hand >= 7:
            if not OPP_DRY and min_amount + max_amount * best_hand / (8.0 if opponent_aggressive else 2.5) >= min_amount:
                logger.info(f"Hand strength {best_hand} is very strong - raising")
                return "raise", min_amount + max_amount * best_hand / (8.0 if opponent_aggressive else 2.5)
            else: 
                return "call", min_amount
        elif 2 <= best_hand < 7:
            if best_hand == 2: 
                if min_amount < max_amount * 0.2 or min_amount <= 500:
                    if opponent_aggressive:
                        logger.info(f"Hand strength {best_hand} is a pair and opp aggressive - calling")
                        return "call", min_amount
                    else: 
                        if not OPP_DRY:
                            logger.info(f"Hand strength {best_hand} is a pair and opp passive - raising")
                            return "raise", 500
                        else:
                            return "call", min_amount
                else:
                    logger.info(f"Hand strength {best_hand} is moderate but amount too much - folding")
                    return "fold", 0
            elif best_hand == 3:
                if OPP_DRY: 
                    return "call", min_amount
                logger.info("Hand strength is a three of a kind - raising")
                return "raise", max_amount * 0.02 if opponent_aggressive else max_amount * 0.03
            else: 
                if OPP_DRY:
                    return "call", min_amount
                logger.info(f"Hand strength {best_hand} is strong - raising")
                return "raise", (max_amount * 0.5)
        elif 1 <= best_hand < 2:
            if min_amount < max_amount * 0.09 and min_amount <= 500:
                logger.info(f"Hand strength {best_hand} is weak   - calling")
                return "call", min_amount
            elif checkRaisePreflop(action_histories) and min_amount <= 1500:
                if OPP_DRY:
                    return "call", min_amount
                logger.info(f"Hand strength {best_hand} is weak but we raised let's juke this kid - raising")
                return "raise", 1000
            elif checkRaisePreflop(action_histories) and min_amount <= 9000:
                logger.info(f"Hand strength {best_hand} is weak but buyin too high but raised too much during preflop - calling")
                return "call", min_amount
            else: 
                logger.info(f"Hand strength {best_hand} is moderate and raise too high - folding")
                return "fold", 0
        else:
            #Check to see if we have raised during the preflop phase
            #If we have then we should call
            #If we have not then we should fold
            if checkRaisePreflop(action_histories):
                if min_amount < max_amount * 0.05 or min_amount <= 1500:
                    logger.info(f"Hand strength {best_hand} is weak but we raised so calling")
                    return "call", min_amount
                else: 
                    logger.info(f"Hand strength {best_hand} is weak and raise too high - folding")
                    return "fold", 0
            else:
                if min_amount < max_amount * 0.01 and min_amount <= 500:
                    #No high raise during the preflop phase so call 
                    logger.info(f"Hand strength {best_hand} is weak - calling")
                    return "call", min_amount
                else:
                    logger.info(f"Hand strength {best_hand} is weak - folding")
                    return "fold", 0

    elif street == "turn":
        logger.info("Turn strategy")
        if best_hand >= highest_hand and best_hand >= 2:
            if not OPP_DRY and min_amount < 40000 and max_amount * (0.06 if opponent_aggressive else 0.09) > min_amount:
                logger.info("Hand strength is one of the best but raise too high - calling")
                return "raise", max_amount * (0.3 if opponent_aggressive else 0.2)
            else:
                if not OPP_DRY and max_amount * (0.03 if opponent_aggressive else 0.06) > min_amount:
                    logger.info("Hand strength is one of the best raising a bit")
                    return "raise", max_amount * (0.2 if opponent_aggressive else 0.3)
                else: 
                    return "call", min_amount
        elif best_hand >= highest_hand and best_hand == 1:
            if min_amount < 5000:
                logger.info("Hand strength is a pair - calling to see the river")
                return "call", min_amount
            else:
                logger.info("Hand strength is a pair but buyin too high - folding")
                return "fold", 0
        elif best_hand >= highest_hand and best_hand == 0:
            if min_amount <= 1000:
                logger.info("Hand strength is weak - calling to see the river")
                return "call", min_amount
            else:
                logger.info("Hand strength is weak but buyin too high - folding")
                return "fold", 0
        elif best_hand >= 7:
            if min_amount < max_amount * 0.15:
                if max_amount * (0.15 if opponent_aggressive else 0.3) < min_amount:
                    logger.info(f"Hand strength {best_hand} is very strong - calling")
                    return "call", min_amount
                else:
                    if not OPP_DRY:
                        logger.info(f"Hand strength {best_hand} is very strong - raising")
                        return "raise", max_amount * (0.15 if opponent_aggressive else 0.3)
                    else: 
                        return "call", min_amount
            else: 
                logger.info(f"Hand strength {best_hand} is very strong but raise too high - calling")
                return "call", min_amount
        elif 4 <= best_hand < 7:
            if min_amount < max_amount * 0.3 or min_amount <= 8000:
                if not OPP_DRY and min_amount + max_amount * best_hand / (10.0 if opponent_aggressive else 8.0) >= min_amount:
                    logger.info(f"Hand strength {best_hand} is strong - raising")
                    return "raise", min_amount + max_amount * best_hand / (10.0 if opponent_aggressive else 8.0)
                else:
                    return "call", min_amount
            else:
                logger.info(f"Hand strength {best_hand} is strong but raise too high - folding")
                return "fold", 0
        elif 2 <= best_hand < 4:
            if not opponent_aggressive:
                if min_amount >= 10000: 
                    logger.info(f"Hand strength {best_hand} is moderate, opp passive - calling")
                    return "call", min_amount
                else:
                    if OPP_DRY or min_amount > min_amount + (max_amount * 0.03):
                        return "call", min_amount
                    logger.info(f"Hand strength {best_hand} is moderate, opp passive - raising")
                    return "raise", max_amount * 0.08
            elif opponent_aggressive and min_amount < 10000: 
                logger.info(f"Hand strength {best_hand} is moderate, opp aggressive but raise low - calling")
                return "call", min_amount
            elif current_raise >= 30000 or pot["amount"] >= 30000: 
                logger.info(f"Hand strength {best_hand} is moderate but we raised more than 30k - calling")
                return "call", min_amount
            else:
                logger.info(f"Hand strength {best_hand} is moderate - folding")
                return "fold", 0
        elif best_hand == 1:
            if min_amount <= 1000:
                logger.info(f"Hand strength {best_hand} is weak - calling")
                return "call", min_amount
            else:
                logger.info(f"Hand strength {best_hand} is too weak, buyin too high - folding")
                return "fold", 0
        else:
            if min_amount < max_amount * 0.01 and min_amount <= 500:
                logger.info(f"Hand strength {best_hand} is weak - calling")
                return "call", min_amount
            else:
                logger.info(f"Hand strength {best_hand} is weak - folding")
                return "fold", 0

    elif street == "river":
        logger.info("River strategy")
        if best_hand >= highest_hand and best_hand > 2:
            if not opponent_aggressive:
                if (max_amount - min_amount) * 0.5 + min_amount >= min_amount and not OPP_DRY:
                    logger.info("Hand strength is one of the best - all in baby")
                    return "raise", ((max_amount - min_amount)* 0.5) + min_amount
                else :
                    logger.info("Hand strength is one of the best but not enough funds - calling")
                    return "call", min_amount
            else: 
                logger.info("Hand strength is one of the best but opponent is aggressive - calling")
                return "call", min_amount
        elif best_hand >= highest_hand and best_hand <= 2:
            if min_amount<50000:
                logger.info("Hand strength is a pair - calling")
                return "call", min_amount
            else: 
                if opponent_aggressive:
                    return "fold", 0
                else: 
                    if min_amount < 50000:
                        logger.info("Hand strength is a pair - calling")
                        return "call", min_amount
                    else: 
                        logger.info(f"Hand strength is {best_hand} but buyin too high - folding")
                        return "fold", 0
        elif best_hand >= highest_hand - 1 and best_hand > 1: 
            if min_amount < 50000:
                if opponent_aggressive:
                    logger.info("Hand strength is strong but opp aggressive - calling")
                    return "call", min_amount
                else: 
                    if min_amount <= max_amount * 0.1 if max_amount * 0.1 > min_amount else min_amount and not OPP_DRY:
                        logger.info("Hand strength is strong and opp passive - raising")
                        return "raise", max_amount * 0.1 if max_amount * 0.1 > min_amount else min_amount
                    else: 
                        logger.info("Hand strength is strong but raise too high - calling")
                        return "call", min_amount
            else: 
                logger.info("Hand strength is strong but buyin too high - folding")
                return "fold", 0
        elif best_hand >= 7:
            if min_amount <=  max_amount * (0.85 if opponent_aggressive else 0.9) and not OPP_DRY:
                logger.info(f"Hand strength {best_hand} is very strong - raising")
                return "raise", max_amount * (0.85 if opponent_aggressive else 0.9)
            else: 
                return "call", min_amount
        elif 4 <= best_hand < 7:
            if min_amount <= max_amount * 0.15 if max_amount * 0.15 > min_amount else min_amount and not OPP_DRY:
                logger.info(f"Hand strength {best_hand} is strong - raising")
                return "raise", max_amount * 0.15 if max_amount * 0.15 > min_amount else min_amount
            else: 
                logger.info(f"Hand strength {best_hand} is strong but raise too high - calling")
                return "call", min_amount
        elif best_hand == 2 and highest_hand == 2:
            if not OPP_DRY: 
                logger.info(f"Hand strength {best_hand} is a pair and the highest hand - raising")
                return "raise", max_amount if max_amount > min_amount else min_amount * 1.2
            else: 
                return "call", min_amount
        elif best_hand == 3 and highest_hand >= 5: 
            if not opponent_aggressive:
                if not OPP_DRY: 
                    logger.info(f"Hand strength {best_hand} is a three of a kind - raising")
                    return "raise", max_amount * 0.5 if max_amount * 0.5 > min_amount else min_amount * 1.2
                else: 
                    return "call", min_amount
            else: 
                logger.info(f"Hand strength {best_hand} is a three of a kind - calling")
                if min_amount < 50000:
                    logger.info(f"Hand strength {best_hand} is a three of a kind - calling")
                    return "call", min_amount
                else:
                    return "fold", 0
        elif 2 <= best_hand < 4:
            if best_hand >= 2 and highest_hand >= 5:
                if min_amount <= 15000:
                    if opponent_aggressive:
                        if min_amount >= 500:
                            logger.info(f"Hand strength {best_hand} is too moderate and opponent is agressive - folding")
                            return "fold", 0
                        else: 
                            logger.info(f"Hand strength {best_hand} is too moderate and opponent is agressive but buyin free - calling")
                            return "call", min_amount
                    else: 
                        logger.info(f"Hand strength {best_hand} is moderate and opp is passive - calling")
                        return "call", min_amount
                else:
                    if opponent_aggressive:
                        logger.info(f"Hand strength {best_hand} is moderate - folding")
                        return "fold", 0
                    else: 
                        if current_raise > 20000 or pot["amount"] > 20000 and min_amount < max_amount * 0.18:
                            logger.info(f"Hand strength {best_hand} is moderate - calling")
                            return "call", min_amount
                        else: 
                            if opponent_aggressive and min_amount < 30000:
                                logger.info(f"Hand strength {best_hand} is moderate but opp aggressive - folding")
                                return "fold", 0
                            else: 
                                logger.info(f"Hand strength {best_hand} is moderate but opp passive - calling")
                                return "call", min_amount
            #else if we have a pair and the highest hand is a pair then we should raise
            elif best_hand == 2 and highest_hand == 2:
                if opponent_aggressive:
                    logger.info(f"Hand strength {best_hand} is a pair and the highest hand - calling")
                    return "call", min_amount
                else: 
                    if min_amount <= max_amount * 0.08:
                        if not OPP_DRY:
                            logger.info(f"Hand strength {best_hand} is a pair and the highest hand - raising")
                            return "raise", max_amount if max_amount > min_amount else min_amount * 1.2
                        else: 
                            return "call", min_amount
                    else: 
                        logger.info(f"Hand strength {best_hand} is a pair and the highest hand - calling")
                        return "call", min_amount
            elif best_hand == 3 and highest_hand >= 5: 
                if not opponent_aggressive:
                    logger.info(f"Hand strength {best_hand} is a three of a kind - raising")
                    if not OPP_DRY:
                        return "raise", max_amount * 0.5 if max_amount * 0.5 > min_amount else min_amount * 1.2
                    else: 
                        return "call", min_amount
                else: 
                    logger.info(f"Hand strength {best_hand} is a three of a kind - calling")
                    if min_amount < 20000:
                        logger.info(f"Hand strength {best_hand} is a three of a kind - calling")
                        return "call", min_amount
                    else:
                        return "fold", 0
            elif min_amount < max_amount * 0.08 or min_amount <= 500:
                logger.info(f"Hand strength {best_hand} is moderate - calling")
                return "call", min_amount
            else: 
                return "fold", 0
        elif best_hand == 1:
            if min_amount <= 1000:
                if opponent_aggressive:
                    logger.info(f"Hand strength {best_hand} is weak - calling")
                    return "call", min_amount
                else: 
                    logger.info(f"Hand strength {best_hand} is weak - calling")
                    return "call", min_amount
            else:
                logger.info(f"Hand strength {best_hand} is weak - folding")
                return "fold", 0
        else:
            if min_amount <= 800:
                logger.info(f"Min buyin: {min_amount} Hand strength {best_hand} is weak but raise low - calling")
                return "call", min_amount
            else: 
                logger.info(f"Min buyin: {min_amount} Hand strength {best_hand} is weak - folding")
                return "fold", 0

    # Default action if no specific strategy is applied
    if min_amount <= 500:
        logger.info("Default action - calling")
        return "call", min_amount
    else: 
        logger.info("Default action - folding")
        return "fold", 0
  
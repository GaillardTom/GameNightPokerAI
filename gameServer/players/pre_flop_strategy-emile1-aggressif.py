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
    Détermine l'action préflop (call, raise, ou fold) en fonction des cartes fermées et des montants à miser.
    
    Stratégie agressive et dynamique :
      - Classification améliorée des mains (strong, playable, marginal, junk).
      - Ajustement de la taille des raises en fonction de l’agressivité adverse.
      - Favorise le re-raise plutôt que le limp-call afin de conserver l’initiative.
    
    Retourne:
      Tuple[str, float]: (action, montant)
    """

    # Dictionnaire pour la valeur des cartes
    card_rank_map = {
        'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
        '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13
    }

    # Extraction des valeurs numériques pour chaque carte
    values = []
    for card in hole_cards:
        if len(card) == 3:
            values.append(card_rank_map[card[1:]])
        else:
            values.append(card_rank_map[card[1]])
    
    # Journalisation pour debug
    logger.info(f"Player {player_name} has hole cards {hole_cards}")
    logger.info(f"Min amount: {min_amount}, Max amount: {max_amount}, Pot: {pot}")
    logger.info(f"Actions history: {action_histories}")
    print(f"Player {player_name} has hole cards {hole_cards}")
    print(f"Min amount: {min_amount}, Max amount: {max_amount}, Pot: {pot}")
    print(f"Actions history: {action_histories}")
    
    # Récupération de la dernière action préflop
    if action_histories.get('preflop') and action_histories['preflop'][-1]:
        last_action = action_histories['preflop'][-1]['action']
    else:
        last_action = 'SMALLBLIND'
    print(f"Last action: {last_action}")

    # Ajustement de la valeur de l'As pour qu'il compte comme 14
    for i in range(len(values)):
        if values[i] == 1:
            values[i] = 14

    # Correction si montants négatifs ou nuls
    if min_amount <= 0:
        min_amount = 1
    if max_amount <= 0:
        max_amount = 10

    # Calcul de l'agressivité adverse (ratio de raises dans l'historique préflop)
    def compute_opp_aggression_ratio():
        preflop = action_histories.get("preflop", [])
        if not preflop:
            return 0
        total = len(preflop)
        raises = sum(1 for act in preflop if act.get("action", "").lower() in ["raise", "re-raise", "bet"])
        return raises / total
    opp_agg = compute_opp_aggression_ratio()
    logger.info(f"Opponent aggression ratio: {opp_agg:.2f}")

    # Fonctions d'aide pour l'évaluation
    def isColorSame():
        return hole_cards[0][0] == hole_cards[1][0]

    def isPair():
        return values[0] == values[1]

    def allValuesAbove(lowest_card):
        return all(value > lowest_card for value in values)

    def anyValueAbove(lowest_card):
        return any(value > lowest_card for value in values)

    def checkPotentialStraight():
        return abs(values[0] - values[1]) <= 1

    def hasAceWithWeakKicker():
        return (14 in values) and (min(values) < 9)

    # Amélioration de la classification des mains
    def classify_hand():
        if isPair():
            if values[0] >= 10:
                return "strong"
            elif values[0] >= 7:
                return "playable"
            else:
                return "junk"
        else:
            suited = isColorSame()
            diff = abs(values[0] - values[1])
            # Suited connectors ou mains assorties élevées sont jouables
            if suited and diff <= 1 and max(values) >= 8:
                return "playable"
            if not suited and max(values) >= 11 and min(values) >= 7:
                return "playable"
            if suited:
                return "marginal"
            return "junk"
    hand_class = classify_hand()
    logger.info(f"Classified hand: {hand_class} with values {values}")

    # Facteur dynamique basé sur l'agressivité adverse
    # Si l'adversaire est passif (opp_agg < 0.3), on renforce nos raises (+20%)
    # Sinon, on garde les multiplicateurs de base
    def adjust_multiplier(base):
        return base * (1.2 if opp_agg < 0.3 else 1.0)

    # Détermination de l'action selon la position (basée sur last_action) et la classification
    if last_action == 'SMALLBLIND':
        if hand_class == "strong":
            multiplier = adjust_multiplier(0.20)
            logger.info("Small Blind – Strong hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "playable":
            multiplier = adjust_multiplier(0.12)
            logger.info("Small Blind – Playable hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                multiplier = adjust_multiplier(0.08)
                logger.info("Small Blind – Marginal hand: forced re-raise pour voir un flop bon marché")
                return "raise", max_amount * multiplier
            else:
                logger.info("Small Blind – Marginal hand face à grosse mise: fold")
                return "fold", 0
        else:  # junk
            logger.info("Small Blind – Junk hand: fold")
            return "fold", 0

    elif last_action == "BIGBLIND":
        if hand_class == "strong":
            multiplier = adjust_multiplier(0.20)
            logger.info("Big Blind – Strong hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "playable":
            multiplier = adjust_multiplier(0.12)
            logger.info("Big Blind – Playable hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                multiplier = adjust_multiplier(0.08)
                logger.info("Big Blind – Marginal hand: raise agressif")
                return "raise", max_amount * multiplier
            else:
                logger.info("Big Blind – Marginal hand: call pour voir le flop")
                return "call", min_amount
        else:
            logger.info("Big Blind – Junk hand: fold")
            return "fold", 0

    elif last_action == "CALL":
        if hand_class == "strong":
            multiplier = adjust_multiplier(0.20)
            logger.info("Call – Strong hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "playable":
            multiplier = adjust_multiplier(0.15)
            logger.info("Call – Playable hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                multiplier = adjust_multiplier(0.08)
                logger.info("Call – Marginal hand: raise agressif")
                return "raise", max_amount * multiplier
            else:
                logger.info("Call – Marginal hand: call pour éviter un fold prématuré")
                return "call", min_amount
        else:
            logger.info("Call – Junk hand: fold")
            return "fold", 0

    else:
        # Branche par défaut
        if hand_class == "strong":
            multiplier = adjust_multiplier(0.20)
            logger.info("Default – Strong hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "playable":
            multiplier = adjust_multiplier(0.15)
            logger.info("Default – Playable hand: raise agressif")
            return "raise", max_amount * multiplier
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                multiplier = adjust_multiplier(0.08)
                logger.info("Default – Marginal hand: raise agressif")
                return "raise", max_amount * multiplier
            else:
                logger.info("Default – Marginal hand: call pour voir le flop")
                return "call", min_amount
        else:
            logger.info("Default – Junk hand: fold")
            return "fold", 0

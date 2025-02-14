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
    
    Version agressive : on force le re‑raise à tout prix, même avec des mains marginales,
    afin de récupérer l’initiative et d’empêcher l’adversaire de dicter la taille du pot.
    
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
    
    # Loggage et affichage pour debug
    logger.info(f"Player {player_name} has hole cards {hole_cards}")
    logger.info(f"Min amount: {min_amount}")
    logger.info(f"Actions history: {action_histories}")
    logger.info(f"Pot: {pot}")
    logger.info(f"Max amount: {max_amount}")
    print(f"Player {player_name} has hole cards {hole_cards}")
    print(f"Min amount: {min_amount}")
    print(f"Actions history: {action_histories}")
    print(f"Pot: {pot}")
    print(f"Max amount: {max_amount}")
    
    # Récupérer la dernière action de la street préflop
    if action_histories['preflop'] and action_histories['preflop'][-1]:
        last_action = action_histories['preflop'][-1]['action']
    else:
        last_action = 'SMALLBLIND'
    print(f"Last action: {last_action}")

    # L'As compte désormais comme 14 pour mieux évaluer les cartes hautes
    if values[0] == 1:
        values[0] = 14
    if values[1] == 1:
        values[1] = 14

    # Correction si les montants sont négatifs ou nuls
    if min_amount <= 0:
        min_amount = 1
    if max_amount <= 0:
        max_amount = 10

    # Fonctions d'aide
    def isColorSame():
        return hole_cards[0][0] == hole_cards[1][0]

    def isPair():
        return values[0] == values[1]

    def allValuesAbove(lowest_card):
        return all(value > lowest_card for value in values)

    def anyValueAbove(lowest_card):
        return any(value > lowest_card for value in values)

    def allValuesBelow(highest_card):
        return all(value < highest_card for value in values)

    def checkPotentialStraight():
        return abs(values[0] - values[1]) <= 1

    # Repérer un As avec un kicker faible (main spéculative)
    def hasAceWithWeakKicker():
        return (14 in values) and (min(values) < 9)

    # --- Décision selon la dernière action ---
    if last_action == 'SMALLBLIND':
        # STRATÉGIE AGRESSIVE EN SMALL BLIND
        if isPair() and allValuesAbove(10) and isColorSame():
            logger.info("Small Blind – Strong pair hautes et assorties : re-raise très agressif")
            return "raise", max_amount * 0.15  # 15% du max_amount
        elif isPair():
            logger.info("Small Blind – Pair : re-raise agressif")
            return "raise", max_amount * 0.07  # 7%
        elif allValuesAbove(10):
            logger.info("Small Blind – Deux cartes hautes : re-raise agressif")
            return "raise", max_amount * 0.07
        elif hasAceWithWeakKicker():
            logger.info("Small Blind – As avec kicker faible : re-raise agressif")
            return "raise", max_amount * 0.07
        elif any(value >= 11 for value in values):
            # Au lieu de caller, on re-raise pour ne pas perdre l'initiative
            if min_amount < max_amount * 0.05:
                logger.info("Small Blind – Carte haute marginale : re-raise agressif")
                return "raise", max_amount * 0.05
            else:
                logger.info("Small Blind – Carte haute mais mise trop importante, fold")
                return "fold", 0
        elif checkPotentialStraight():
            # Mains connectées : on force un petit re-raise
            if min_amount < max_amount * 0.05:
                logger.info("Small Blind – Cartes connectées : re-raise agressif")
                return "raise", max_amount * 0.03
            else:
                logger.info("Small Blind – Cartes connectées mais mise trop élevée, fold")
                return "fold", 0
        else:
            # Mains marginales : on privilégie le re-raise plutôt que le call
            if min_amount < max_amount * 0.05:
                logger.info("Small Blind – Main marginale : re-raise faible pour rester agressif")
                return "raise", max_amount * 0.03
            else:
                logger.info("Small Blind – Main marginale face à une grosse mise : fold")
                return "fold", 0

    elif last_action == "BIGBLIND":
        # STRATÉGIE AGRESSIVE EN BIG BLIND
        if isPair() and allValuesAbove(10):
            logger.info("Big Blind – Strong pair hautes : re-raise très agressif")
            return "raise", max_amount * 0.15
        elif anyValueAbove(10):
            if min_amount < max_amount * 0.1:
                logger.info("Big Blind – Carte haute : re-raise agressif")
                return "raise", max_amount * 0.06
            elif min_amount < max_amount * 0.2:
                logger.info("Big Blind – Carte haute : call (tendance à re-raise)")
                return "call", min_amount
            else:
                logger.info("Big Blind – Carte haute mais mise trop élevée, fold")
                return "fold", 0
        elif isPair():
            logger.info("Big Blind – Pair : re-raise agressif")
            return "raise", max_amount * 0.06
        elif checkPotentialStraight():
            if min_amount < max_amount * 0.05 and pot < 2000:
                logger.info("Big Blind – Cartes connectées : re-raise agressif")
                return "raise", max_amount * 0.04
            else:
                logger.info("Big Blind – Cartes connectées mais mise trop élevée, fold")
                return "fold", 0
        elif isColorSame() and any(value >= 8 for value in values):
            if min_amount < max_amount * 0.05:
                logger.info("Big Blind – Main assortie modérée : re-raise agressif")
                return "raise", max_amount * 0.04
            else:
                logger.info("Big Blind – Main assortie mais mise trop élevée, fold")
                return "fold", 0
        elif isColorSame():
            if min_amount < max_amount * 0.02:
                logger.info("Big Blind – Main assortie faible : call")
                return "call", min_amount
            else:
                logger.info("Big Blind – Main assortie faible avec grosse mise, fold")
                return "fold", 0
        elif allValuesAbove(10):
       

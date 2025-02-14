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
    
    Cette version a été modifiée pour éviter une approche trop passive (limp ou call) notamment depuis la small blind.
    En effet, plutôt que de se contenter d’appeler avec des mains marginales ou spéculatives,
    on opte parfois pour un léger re-raise afin de récupérer l’initiative et de ne pas laisser l’adversaire
    dicter la taille du pot.

    Paramètres identiques à la version d’origine.
    
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

    # Ajustement de la valeur de l'As pour qu'il compte comme 14 (pour mieux évaluer les cartes hautes)
    if values[0] == 1:
        values[0] = 14
    if values[1] == 1:
        values[1] = 14

    # Correction des montants si négatifs ou nuls
    if min_amount <= 0:
        min_amount = 1
    if max_amount <= 0:
        max_amount = 10

    # Fonctions d'aide pour simplifier les conditions
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

    # Nouvelle fonction pour repérer un As avec un kicker faible (main spéculative à améliorer)
    def hasAceWithWeakKicker():
        return (14 in values) and (min(values) < 9)

    # --- Branche selon la dernière action ---
    if last_action == 'SMALLBLIND':
        # AJUSTEMENT : Jouer de manière plus agressive depuis la small blind
        if isPair() and allValuesAbove(10) and isColorSame():
            logger.info("Small Blind – Strong pair hautes et assorties : re-raise agressif")
            return "raise", max_amount * 0.1
        elif isPair():
            logger.info("Small Blind – Pair : re-raise modéré")
            return "raise", max_amount * 0.03  # augmentation par rapport à 0.015
        elif allValuesAbove(10):
            logger.info("Small Blind – Deux cartes hautes : re-raise agressif")
            return "raise", max_amount * 0.03
        elif hasAceWithWeakKicker():
            logger.info("Small Blind – As avec kicker faible : re-raise pour éviter le limp")
            return "raise", max_amount * 0.03
        elif any(value >= 11 for value in values):
            # Au lieu de simplement caller, opter pour un léger raise pour ne pas laisser l'initiative
            if min_amount < max_amount * 0.05:
                logger.info("Small Blind – Carte haute marginale : re-raise léger")
                return "raise", max_amount * 0.02
            else:
                logger.info("Small Blind – Carte haute mais mise trop importante, fold")
                return "fold", 0
        elif checkPotentialStraight():
            # Cartes connectées spéculatives : préférence pour un petit raise plutôt qu'un limp
            if min_amount < max_amount * 0.05:
                logger.info("Small Blind – Cartes connectées : petit re-raise pour saisir l'initiative")
                return "raise", max_amount * 0.015
            else:
                logger.info("Small Blind – Cartes connectées mais mise trop élevée, fold")
                return "fold", 0
        elif allValuesBelow(5):
            logger.info("Small Blind – Mains très faibles : fold")
            return "fold", 0
        else:
            # Pour les holdings marginales, on call si la mise est faible ; sinon, fold
            if min_amount < max_amount * 0.05:
                logger.info("Small Blind – Main marginale : call prudente")
                return "call", min_amount
            else:
                logger.info("Small Blind – Main marginale face à une grosse mise : fold")
                return "fold", 0

    elif last_action == "BIGBLIND":
        # Quelques ajustements pour une lecture moins passive depuis la big blind
        if isPair() and allValuesAbove(10):
            logger.info("Big Blind – Strong pair hautes : re-raise agressif")
            return "raise", max_amount * 0.1
        elif anyValueAbove(10):
            # Plutôt que de simplement caller, tenter un re-raise modéré si la mise est raisonnable
            if min_amount < max_amount * 0.1:
                logger.info("Big Blind – Carte haute : re-raise modéré")
                return "raise", max_amount * 0.03
            elif min_amount < max_amount * 0.2:
                logger.info("Big Blind – Carte haute : call en mise modérée")
                return "call", min_amount
            else:
                logger.info("Big Blind – Carte haute mais mise trop élevée, fold")
                return "fold", 0
        elif isPair():
            logger.info("Big Blind – Pair : re-raise modéré")
            return "raise", max_amount * 0.03
        elif checkPotentialStraight():
            if min_amount < max_amount * 0.05 and pot < 2000:
                logger.info("Big Blind – Cartes connectées : call spéculatif")
                return "call", min_amount
            else:
                logger.info("Big Blind – Cartes connectées mais mise trop élevée, fold")
                return "fold", 0
        elif isColorSame() and any(value >= 8 for value in values):
            if min_amount < max_amount * 0.05:
                logger.info("Big Blind – Main assortie modérée : call")
                return "call", min_amount
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
            if min_amount < max_amount * 0.05:
                logger.info("Big Blind – Deux cartes hautes : call")
                return "call", min_amount
            else:
                logger.info("Big Blind – Deux cartes hautes mais mise trop élevée, fold")
                return "fold", 0
        else:
            logger.info("Big Blind – Mains faibles : fold")
            return "fold", 0

    elif last_action == "CALL":
        # AJUSTEMENT : En situation de call, préférer re-raiser avec des holdings raisonnables
        if isPair():
            logger.info("Call – Pair : re-raise pour construire le pot")
            return "raise", max_amount * 0.03  # Augmentation par rapport à la version initiale
        elif allValuesAbove(9):
            logger.info("Call – Deux cartes hautes : re-raise agressif")
            return "raise", max_amount * 0.034
        elif isColorSame() and anyValueAbove(8):
            if min_amount < max_amount * 0.1:
                logger.info("Call – Main assortie et modérément haute : re-raise pour s’emparer de l’initiative")
                return "raise", max_amount * 0.03
            else:
                logger.info("Call – Main assortie mais mise trop importante, fold")
                return "fold", 0
        elif anyValueAbove(10):
            if min_amount < 5000:
                logger.info("Call – Carte haute : re-raise modéré")
                return "raise", max_amount * 0.02
            else:
                logger.info("Call – Carte haute avec grosse mise, fold")
                return "fold", 0
        elif abs(values[0] - values[1]) <= 2:
            # Pour des cartes connectées, essayer de re-raiser légèrement si la mise le permet
            if min_amount < max_amount * 0.07:
                logger.info("Call – Cartes connectées : re-raise léger pour prendre le contrôle")
                return "raise", max_amount * 0.02
            else:
                logger.info("Call – Cartes connectées mais grosse mise, call")
                return "call", min_amount
        else:
            if min_amount < 1000:
                logger.info("Call – Main marginale face à une petite mise : call")
                return "call", min_amount
            else:
                logger.info("Call – Main marginale mais mise trop élevée, fold")
                return "fold", 0

    else:
        # Branche par défaut en l'absence de correspondance de la dernière action
        if isPair() and values[0] == 14:
            if max_amount * 0.2 >= min_amount:
                logger.info("Default – Paire d'As : re-raise important")
                return "raise", max_amount * 0.2
            else:
                logger.info("Default – Paire d'As : call faute d'opportunité de re-raise")
                return "call", min_amount
        if isPair() and allValuesAbove(10):
            if max_amount * 0.1 >= min_amount:
                logger.info("Default – High pair : re-raise")
                return "raise", max_amount * 0.1
            else:
                logger.info("Default – High pair : call")
                return "call", min_amount
        elif allValuesAbove(9) and isColorSame():
            if max_amount * 0.1 >= min_amount:
                logger.info("Default – Cartes hautes et assorties : re-raise")
                return "raise", max_amount * 0.1
            else:
                logger.info("Default – Cartes hautes et assorties : call")
                return "call", min_amount
        elif isPair():
            if min_amount <= 50000:
                logger.info("Default – Pair : call")
                return "call", min_amount
            else:
                logger.info("Default – Pair mais grosse mise, fold")
                return "fold", 0
        elif isColorSame() and anyValueAbove(9):
            if min_amount < 40000:
                logger.info("Default – Main assortie : call")
                return "call", min_amount
            else:
                logger.info("Default – Main assortie avec grosse mise, fold")
                return "fold", 0
        elif allValuesAbove(10):
            if min_amount < max_amount * 0.6:
                logger.info("Default – Cartes hautes : call")
                return "call", min_amount
            else:
                logger.info("Default – Cartes hautes mais grosse mise, fold")
                return "fold", 0
        elif anyValueAbove(10):
            if min_amount <= 5000 and pot < 4000:
                logger.info("Default – Carte haute : call")
                return "call", min_amount
            else:
                logger.info("Default – Carte haute mais grosse mise, fold")
                return "fold", 0
        elif abs(values[0] - values[1]) <= 2:
            if min_amount < max_amount * 0.2 and pot <= 5000:
                logger.info("Default – Cartes connectées : call")
                return "call", min_amount
            else:
                logger.info("Default – Cartes connectées mais grosse mise, fold")
                return "fold", 0
        else:
            logger.info("Default – Aucune main jouable : fold")
            return "fold", 0

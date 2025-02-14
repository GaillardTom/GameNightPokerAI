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

    Cette version corrige la passivité observée qui limpe ou call avec des holdings marginales
    (par exemple, 8-5 suited ou 3-4 off suit) et finit par folder face à un gros raise adverse.
    Au lieu de cela, on force dès le début soit un re‑raise agressif, soit, dans le pire des cas, un fold,
    afin de ne pas céder l'initiative et de récupérer l'initiative préflop.

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
        if len(card) == 3:  # par exemple "S10"
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
    
    # Récupération de la dernière action préflop
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

    # Correction des montants s'ils sont négatifs ou nuls
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

    # Nouvelle fonction pour repérer un As avec un kicker faible (main spéculative)
    def hasAceWithWeakKicker():
        return (14 in values) and (min(values) < 9)

    # --- Amélioration de la classification des mains ---
    # On classe les mains en quatre catégories :
    # "strong" : paires élevées (10+), ou mains non-paires très jouables
    # "playable" : paires moyennes (7-9) ou mains suited/connectées de qualité (ex. A-8 suited, 9-8 suited)
    # "marginal" : holdings borderline susceptibles de produire un flop intéressant mais pas idéales
    # "junk" : mains vraiment faibles
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
            high = max(values)
            low = min(values)
            # Si une main non-pair est suited et connectée (diff <= 1) avec des cartes d'au moins 8
            if suited and diff <= 1 and high >= 8:
                return "playable"
            # Si la main est offsuit et comporte au moins une carte haute (>= 11) et l'autre au moins 7
            if not suited and high >= 11 and low >= 7:
                return "playable"
            # Si la main est suited mais moins connectée, on la classe en "marginal"
            if suited:
                if values[0] >= 8 and values[1] >= 8:
                    return "playable"
                else:
                    return "marginal"
            return "junk"

    hand_class = classify_hand()
    logger.info(f"Classified hand: {hand_class} with values {values}")

    # --- Détermination de l'action en fonction de la position et de la classification ---
    # L'objectif est d'éviter de limper ou caller avec des mains marginales en small blind.
    # Au lieu de cela, on force dès le départ soit un re‑raise agressif (pour récupérer le contrôle),
    # soit un fold si la main est vraiment non jouable.
    if last_action == 'SMALLBLIND':
        if hand_class == "strong":
            logger.info("Small Blind – Strong hand: raise agressif (20% du max_amount)")
            return "raise", max_amount * 0.20
        elif hand_class == "playable":
            logger.info("Small Blind – Playable hand: raise agressif (12% du max_amount)")
            return "raise", max_amount * 0.12
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                logger.info("Small Blind – Marginal hand: forced re-raise (8% du max_amount) pour voir un flop bon marché")
                return "raise", max_amount * 0.08
            else:
                logger.info("Small Blind – Marginal hand face à une grosse mise: re-raise modéré (6% du max_amount)")
                return "raise", max_amount * 0.06
        else:  # junk
            logger.info("Small Blind – Junk hand: fold")
            return "fold", 0

    elif last_action == "BIGBLIND":
        if hand_class == "strong":
            logger.info("Big Blind – Strong hand: raise agressif (20% du max_amount)")
            return "raise", max_amount * 0.20
        elif hand_class == "playable":
            logger.info("Big Blind – Playable hand: raise agressif (12% du max_amount)")
            return "raise", max_amount * 0.12
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                logger.info("Big Blind – Marginal hand: raise agressif (8% du max_amount)")
                return "raise", max_amount * 0.08
            else:
                logger.info("Big Blind – Marginal hand: call pour voir le flop")
                return "call", min_amount
        else:
            logger.info("Big Blind – Junk hand: fold")
            return "fold", 0

    elif last_action == "CALL":
        if hand_class == "strong":
            logger.info("Call – Strong hand: raise agressif (20% du max_amount)")
            return "raise", max_amount * 0.20
        elif hand_class == "playable":
            logger.info("Call – Playable hand: raise agressif (15% du max_amount)")
            return "raise", max_amount * 0.15
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                logger.info("Call – Marginal hand: raise agressif (8% du max_amount)")
                return "raise", max_amount * 0.08
            else:
                logger.info("Call – Marginal hand: call pour éviter un fold prématuré")
                return "call", min_amount
        else:
            logger.info("Call – Junk hand: fold")
            return "fold", 0

    else:
        # Branche par défaut en l'absence de correspondance explicite de la dernière action
        if hand_class == "strong":
            logger.info("Default – Strong hand: raise agressif (20% du max_amount)")
            return "raise", max_amount * 0.20
        elif hand_class == "playable":
            logger.info("Default – Playable hand: raise agressif (15% du max_amount)")
            return "raise", max_amount * 0.15
        elif hand_class == "marginal":
            if min_amount < max_amount * 0.07:
                logger.info("Default – Marginal hand: raise agressif (8% du max_amount)")
                return "raise", max_amount * 0.08
            else:
                logger.info("Default – Marginal hand: call pour voir le flop")
                return "call", min_amount
        else:
            logger.info("Default – Junk hand: fold")
            return "fold", 0

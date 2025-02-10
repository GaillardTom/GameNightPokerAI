from random import randint, random

def evaluate_opponent_aggressiveness(action_histories, street):
    """
    Évalue le niveau d'agressivité de l'adversaire sur la base
    des actions passées sur la street spécifiée (ex: 'preflop').

    Paramètres:
    - action_histories (dict): historique des actions par street
    - street (str): 'preflop', 'flop', 'turn' ou 'river'

    Retourne:
    - float: un score d'agressivité (entre 0 et 1, plus proche de 1 = plus agressif)
    """
    if street not in action_histories or len(action_histories[street]) == 0:
        return 0.5  # Valeur neutre si pas d'info

    total_actions = 0
    total_raises = 0

    for act in action_histories[street]:
        # On ignore les actions de l'IA pour cibler l'agressivité adverse
        if act["name"] != "AI Player":
            total_actions += 1
            if act["action"] in ["RAISE", "BET"]:
                total_raises += 1

    if total_actions == 0:
        return 0.5

    aggressiveness_score = total_raises / total_actions
    return max(0, min(1, aggressiveness_score))


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
    - action_histories (dict):  A dict where the key is street of the game played so far.
        { "preflop": [...], "flop": [...], "turn": [...], "river": [...] }
    - logger (DcmLoggerWrapper): A logger which will add messages to match report.
        Methods available are:
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
    # -------------------------------------------------------------------------
    # 1) Évaluer l'agressivité adverse et LOGGER l'historique préflop complet
    # -------------------------------------------------------------------------
    opponent_aggressiveness = evaluate_opponent_aggressiveness(action_histories, "preflop")
    logger.info(f"[Preflop] Opponent aggressiveness: {opponent_aggressiveness:.2f}")

    # Historique complet des actions préflop : on logge chaque action
    preflop_actions = action_histories.get("preflop", [])
    logger.info("=== Historique des actions (PRE-FLOP) ===")
    for i, act in enumerate(preflop_actions):
        logger.info(
            f"Action #{i+1}: {act['action']} by {act['name']} "
            f"(amount={act.get('amount',0)}, paid={act.get('paid',0)})"
        )

    # -------------------------------------------------------------------------
    # 2) Conversion des cartes en valeurs numériques et logging de base
    # -------------------------------------------------------------------------
    card_rank_map = {
        'A': 1, '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9,
        'T': 10, 'J': 11, 'Q': 12, 'K': 13
    }
    values = []
    for card in hole_cards:
        # Ex: "S10" => len=3 => card[1:] => "10"
        if len(card) == 3:
            values.append(card_rank_map[card[1:]])
        else:
            values.append(card_rank_map[card[1]])

    logger.info(f"Player {player_name} has hole cards {hole_cards}")
    logger.info(f"Min amount: {min_amount}, Max amount: {max_amount}, Pot: {pot}")

    last_action = preflop_actions[-1]['action'] if preflop_actions else 'SMALLBLIND'
    logger.info(f"Last preflop action: {last_action}")

    # -------------------------------------------------------------------------
    # 3) Ajustement min_amount / max_amount si incorrect
    # -------------------------------------------------------------------------
    if min_amount <= 0:
        min_amount = 1
    if max_amount <= 0:
        max_amount = 10

    # -------------------------------------------------------------------------
    # 4) Fonctions internes (inchangées)
    # -------------------------------------------------------------------------
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
        return abs(values[0] - values[1]) == 1

    # Considérer l'As comme 14
    for i in range(len(values)):
        if values[i] == 1:  # As
            values[i] = 14

    # -------------------------------------------------------------------------
    # 5) Catégorisation avancée de la main préflop (inspirée d'arbres de décision)
    # -------------------------------------------------------------------------
    def classify_preflop_hand():
        """
        Retourne un code de puissance (0=très faible, 5=ultra premium).
        On s'inspire ici de ranges courantes.

        Ex.:
        - 5 => AA, KK, QQ, AKs
        - 4 => JJ, TT, AKo, AQs, KQs
        - 3 => paires moy. (77-99), AJs, broadways suités un peu moins forts
        - 2 => petites paires (22-66), suited connectors
        - 1 => mains faibles (A-little off, K9o...)
        - 0 => trash complet
        """
        v1, v2 = sorted(values, reverse=True)
        same_suit = isColorSame()

        # Paires
        if isPair():
            if v1 == 14:  # AA
                return 5
            elif v1 == 13: # KK
                return 5
            elif v1 == 12: # QQ
                return 5
            elif v1 == 11: # JJ
                return 4
            elif v1 == 10: # TT
                return 4
            elif 7 <= v1 <= 9:
                return 3
            else:
                return 2

        # Double broadway
        def isBroadway(x): return x >= 10
        if isBroadway(v1) and isBroadway(v2):
            # AK, AQ, AJ, KQ, KJ, QJ, etc.
            if v1 == 14 and v2 == 13:  # AK
                return 5 if same_suit else 4
            elif v1 == 14 and v2 == 12:  # AQ
                return 5 if same_suit else 4
            elif v1 == 13 and v2 == 12:  # KQ
                return 4 if same_suit else 3
            elif v1 == 14 and v2 == 11:  # AJ
                return 4 if same_suit else 3
            else:
                return 3 if same_suit else 2

        # Suited connectors
        if same_suit and checkPotentialStraight():
            # T9s, 98s, etc.
            if v1 >= 10:
                return 3
            else:
                return 2

        # A-x suited plus faible
        if v1 == 14 and same_suit and v2 <= 9:
            return 2

        # A-little off / K9 / Q8 ...
        if v1 == 14 and v2 >= 10:
            # A + broadway kicker => 3
            return 3
        if v1 == 14 and v2 <= 9:
            return 1

        # Connectés off
        if checkPotentialStraight():
            return 1

        # Sinon trash
        return 0

    hand_category = classify_preflop_hand()
    logger.info(f"Preflop hand category: {hand_category}")

    # Pour moduler la relance en fonction du pot (plus le pot est grand, plus on peut raiser)
    pot_factor = pot / 500 if pot > 0 else 1.0

    # -------------------------------------------------------------------------
    # 6) Décision de base selon la catégorie + agressivité
    # -------------------------------------------------------------------------
    def base_decision():
        # Catégorie 5 => ultra-premium (AA, KK, QQ, AKs)
        if hand_category == 5:
            logger.info("Ultra-premium => raise ou trap call")
            if opponent_aggressiveness > 0.6:
                # Slowplay vs aggro
                if min_amount < max_amount * 0.3:
                    return "call", min_amount
                else:
                    return "call", min_amount
            else:
                # Passive => on mise fort
                raise_percent = min(0.3 + 0.2 * pot_factor, 0.5)
                if raise_percent < 0.1:
                    raise_percent = 0.1
                if min_amount > max_amount * 0.5:
                    return "call", min_amount
                return "raise", max_amount * raise_percent

        # Catégorie 4 => premium/strong (JJ, TT, AKo, AQs, KQs)
        elif hand_category == 4:
            logger.info("Premium/strong => raise standard ou call si trop cher")
            if opponent_aggressiveness < 0.3:
                raise_percent = min(0.1 + 0.15 * pot_factor, 0.25)
            else:
                raise_percent = min(0.08 + 0.1 * pot_factor, 0.18)

            if min_amount > max_amount * 0.4:
                return "call", min_amount
            return "raise", max_amount * raise_percent

        # Catégorie 3 => mains moyennes fortes (77-99, broadways suités moins forts)
        elif hand_category == 3:
            logger.info("Good medium => raise modérée ou call/fold si trop cher")
            raise_percent = min(0.05 + 0.1 * pot_factor, 0.15)
            if min_amount > max_amount * 0.4:
                if random() < 0.7:
                    return "call", min_amount
                else:
                    return "fold", 0
            else:
                desired_raise = max_amount * raise_percent
                if desired_raise <= min_amount:
                    return "call", min_amount
                else:
                    return "raise", desired_raise

        # Catégorie 2 => spéculatives (petites paires, suited connectors)
        elif hand_category == 2:
            logger.info("Speculative => call si pas cher, small raise possible, else fold")
            if min_amount < max_amount * 0.1:
                if not (opponent_aggressiveness > 0.6):
                    # 20% chance de small raise
                    if random() < 0.2:
                        return "raise", max(min_amount * 2, max_amount * 0.05)
                return "call", min_amount
            else:
                return "fold", 0

        # Catégorie 1 => mains faibles
        elif hand_category == 1:
            logger.info("Weak => fold la plupart du temps, call si mise minime")
            if min_amount < max_amount * 0.05:
                if random() < 0.5:
                    return "call", min_amount
            return "fold", 0

        # Catégorie 0 => trash total
        else:
            logger.info("Trash => fold, sauf si min raise insignifiante")
            if min_amount < max_amount * 0.02:
                return "call", min_amount
            return "fold", 0

    # On obtient la décision de base
    decision_action, decision_amount = base_decision()

    # -------------------------------------------------------------------------
    # 7) Ajustements finaux pour conserver un style agressif / bluff
    # -------------------------------------------------------------------------
    # (a) Diminuer la fréquence des fold pour "call n’importe quoi"
    if decision_action == "fold" and min_amount < max_amount * 0.1:
        if random() < 0.25:  # 25% de chance
            logger.info("Overriding fold to call => style plus loose.")
            decision_action = "call"
            decision_amount = min_amount

    # (b) Bluff aléatoire si adversaire passif (score < 0.3) et main < 3
    if opponent_aggressiveness < 0.3 and hand_category < 3 and decision_action in ["call", "fold"]:
        if random() < 0.2:
            logger.info("Bluff raise vs passif, main < 3.")
            bluff_size = max_amount * 0.08
            if bluff_size <= min_amount:
                # On ne peut pas raise en-dessous du min => on call
                decision_action = "call"
                decision_amount = min_amount
            else:
                decision_action = "raise"
                decision_amount = bluff_size

    logger.info(f"Final preflop decision: {decision_action}, amount={decision_amount}")
    return decision_action, decision_amount

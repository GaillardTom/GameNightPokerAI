from random import randint, random

def evaluate_opponent_aggressiveness(action_histories, street):
    """
    Évalue le niveau d'agressivité de l'adversaire sur la base
    des actions passées sur la street spécifiée (ex: 'flop').

    Paramètres:
    - action_histories (dict): historique des actions par street
    - street (str): 'preflop', 'flop', 'turn', 'river'

    Retourne:
    - float: un score d'agressivité (entre 0 et 1, plus proche de 1 = plus agressif)
    """
    if street not in action_histories or len(action_histories[street]) == 0:
        return 0.5  # Valeur neutre si pas d'info

    total_actions = 0
    total_raises = 0
    for act in action_histories[street]:
        # On ignore les actions de l'IA pour cibler l’agressivité adverse
        if act["name"] != "AI Player":
            total_actions += 1
            if act["action"] in ["RAISE", "BET"]:
                total_raises += 1

    if total_actions == 0:
        return 0.5

    aggressiveness_score = total_raises / total_actions
    return max(0, min(1, aggressiveness_score))


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
    - action_histories (dict):  A dict where the key is the street of the game played so far.
        E.g. { "preflop": [...], "flop": [...], "turn": [...], "river": [...] }
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

    # 1) On cible l'agressivité sur la street actuelle (ici: flop)
    opponent_aggressiveness = evaluate_opponent_aggressiveness(action_histories, "flop")
    logger.info(f"[FLOP] Opponent aggressiveness: {opponent_aggressiveness:.2f}")

    # 2) Historique complet des actions flop : on logge chaque action
    flop_actions = action_histories.get("flop", [])
    logger.info("=== Historique des actions (FLOP) ===")
    for i, act in enumerate(flop_actions):
        logger.info(
            f"FLOP Action #{i+1}: {act['action']} by {act['name']} "
            f"(amount={act.get('amount', 0)}, paid={act.get('paid',0)})"
        )

    # 3) Logging de l'état courant
    logger.info(f"Current street: {street}")
    logger.info(f"Best hand: {best_hand}, Highest hand on table: {highest_hand}")
    logger.info(f"Pot size: {pot}, Side pots: {side_pots}")
    logger.info(f"Minimum amount: {min_amount}, Maximum amount: {max_amount}")

    # Vérification min/max si incohérents
    OPP_DRY = False
    if min_amount <= 0:
        min_amount = 500
        OPP_DRY = True
    if max_amount <= 0:
        max_amount = 501
        OPP_DRY = True

    # 4) Fonctions internes (inchangées)
    def raise_player(amount_percent):
        """
        Renvoie ('raise', montant) ou ('call', min_amount) selon amount_percent*max_amount.
        Si OPP_DRY, on fait un simple call pour éviter des erreurs.
        """
        desired_raise = max_amount * amount_percent
        if OPP_DRY:
            return "call", min_amount

        if desired_raise > max_amount:
            return "raise", max_amount
        if desired_raise > min_amount and desired_raise < max_amount:
            return "raise", desired_raise
        else:
            return "call", min_amount

    def get_last_action():
        # Retourne la dernière action sur cette street, s’il y en a
        if flop_actions:
            return flop_actions[-1]
        return None

    logger.info(f"Last Flop Action: {get_last_action()}")

    # Quelques fonctions utilitaires présentes d’origine
    def sum_raises(action_histories, player_name):
        total_raises = 0
        for key, actions in action_histories.items():
            for action in actions:
                if action.get('action') == 'RAISE' and action.get('name') == player_name:
                    total_raises += action.get('paid', 0)
        return total_raises

    def is_opponent_aggressive():
        aggressive_count = 0
        for key, actions in action_histories.items():
            for action in actions:
                if action.get('action') == 'RAISE' and action.get('name') != player_name:
                    aggressive_count += 1
        # On juge l’adversaire agressif s’il y a >= 2 relances
        return aggressive_count >= 2

    current_raise = sum_raises(action_histories, player_name)
    opp_is_aggressive = is_opponent_aggressive()
    logger.info(f"Opponent is {'aggressive' if opp_is_aggressive else 'passive'} overall")

    # 5) Classification plus fine de la force postflop (best_hand / highest_hand).
    #    On peut imaginer 9 => nuts (quinte flush / full max), 7-8 => main très forte, etc.
    #
    #    Exemples d'ordres:
    #      9 => combos type Quinte flush / Royal / Quads
    #      7-8 => full house, flush, quinte
    #      5-6 => brelan, double paire forte
    #      3-4 => double paire modérée, top pair + bon kicker
    #      2 => paire moyenne
    #      1 => hauteur ou très faible
    #
    #    Ci-dessous, classification simplifiée pour l'exemple :
    def classify_flop_hand_strength(best, highest):
        """
        Retourne un code 0 à 5 pour simplifier la logique de décision.
        5 => super main / nuts
        4 => main très forte
        3 => bonne main
        2 => moyenne
        1 => faible
        0 => quasi nulle
        """
        # S'il est >= le highest_hand, c'est potentiellement la meilleure main
        # Ex: best=9, highest=8 => on a la nuts
        if best == 9:
            return 5
        elif best >= highest and best >= 7:
            return 4
        elif best >= 5:  # ex: brelan, double paire
            return 3
        elif best >= 3:
            return 2
        elif best >= 2:
            return 1
        else:
            return 0

    flop_strength = classify_flop_hand_strength(best_hand, highest_hand)
    logger.info(f"Flop strength category: {flop_strength}")

    # 6) Décision de base selon flop_strength + aggressivité
    def base_flop_decision():
        # On peut moduler en fonction de la taille du pot
        pot_factor = (pot / 20000) if pot > 0 else 1.0

        # Cas 1: main "nuts" ou quasi-nuts => flop_strength = 5
        if flop_strength == 5:
            logger.info("Nuts or near-nuts => big raise or slowplay")
            if opp_is_aggressive:
                # On peut piéger l'adversaire
                return "call", min_amount
            else:
                # On mise plus fort
                raise_percent = min(0.3 + pot_factor * 0.2, 0.6)
                return raise_player(raise_percent)

        # Cas 2: main très forte => 4
        elif flop_strength == 4:
            logger.info("Very strong => raise pour value, ajusté à l'adversaire")
            if opponent_aggressiveness < 0.3:
                # Adversaire passif => on mise plus gros
                raise_percent = min(0.25 + pot_factor * 0.2, 0.5)
            else:
                # Adversaire agressif => on mise moins, on le laisse s'empaler
                raise_percent = min(0.15 + pot_factor * 0.1, 0.3)
            return raise_player(raise_percent)

        # Cas 3: bonne main => 3
        elif flop_strength == 3:
            logger.info("Good made hand => raise modéré ou call si trop cher")
            raise_percent = min(0.1 + pot_factor * 0.1, 0.25)
            # Si min_amount est déjà gros, on call
            if min_amount > max_amount * 0.4:
                return "call", min_amount
            else:
                return raise_player(raise_percent)

        # Cas 4: main moyenne => 2
        elif flop_strength == 2:
            logger.info("Medium => on call si la mise n'est pas trop forte, small raise possible")
            if min_amount < max_amount * 0.2:
                # Petit raise si adversaire passif
                if not opp_is_aggressive and random() < 0.3:
                    return raise_player(0.1)  # un petit 10% du max
                else:
                    return "call", min_amount
            else:
                # Mise trop chère => fold
                return "fold", 0

        # Cas 5: main faible => 1
        elif flop_strength == 1:
            logger.info("Weak => fold la plupart du temps, call si petit bet")
            if min_amount < max_amount * 0.1:
                # On call pour essayer d'améliorer
                return "call", min_amount
            else:
                return "fold", 0

        # Cas 6: main quasi nulle => 0
        else:
            logger.info("No made hand => fold unless min bet is tiny")
            if min_amount < max_amount * 0.05:
                return "call", min_amount
            else:
                return "fold", 0

    decision_action, decision_amount = base_flop_decision()

    # 7) Ajustements finaux pour style agressif / bluff
    # (a) Réduire la fréquence de fold pour "call n’importe quoi"
    if decision_action == "fold" and min_amount < max_amount * 0.1:
        if random() < 0.3:
            logger.info("Overriding fold to call => style plus loose sur le flop")
            decision_action = "call"
            decision_amount = min_amount

    # (b) Bluff aléatoire si adversaire passif (score < 0.3) + main < 3
    #     (i.e., flop_strength < 3 => 0,1,2 => on peut tenter un bluff)
    if opponent_aggressiveness < 0.3 and flop_strength < 3 and decision_action in ["call", "fold"]:
        if random() < 0.2:
            logger.info("Bluff raise vs passif, flop_strength < 3")
            bluff_size = max_amount * 0.15  # 15% du max
            # Vérif qu'on peut (légalement) faire ce raise
            if bluff_size <= min_amount:
                # On ne peut pas raiser en dessous du min
                decision_action = "call"
                decision_amount = min_amount
            else:
                decision_action = "raise"
                decision_amount = bluff_size

    logger.info(f"Final flop decision: Action={decision_action}, amount={decision_amount}")
    return decision_action, decision_amount

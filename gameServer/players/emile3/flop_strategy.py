from random import randint

def get_card_action(
    player_name,
    best_hand,      # Force numérique de votre main sur le flop (par exemple, sur une échelle de 1 à 9, 9 étant optimal)
    highest_hand,   # Force numérique de la meilleure main visible sur le board
    min_amount,     # Mise minimale à payer ou relancer
    max_amount,     # Mise maximale autorisée
    street,         # Doit être "flop" dans ce cas
    pot,            # Taille du pot principal
    side_pots,      # Liste des side pots
    action_histories,
    logger,
):
    """
    Stratégie FLOP ultra avancée pour le Texas Hold’em.

    Ce module réalise les étapes suivantes :
      1. Journalisation et définition de fonctions d’aide (calcul de relance, détection de l’agressivité adverse, etc.).
      2. Évaluation de la force de la main sur le flop à l’aide de plusieurs systèmes de classification professionnels :
            - Un système de classification « basic » basé sur la différence entre best_hand et highest_hand.
            - Un second système (modèle « pro ») avec des seuils légèrement décalés pour refléter la lecture post‑flop.
      3. Conversion de chaque classification en un score numérique, fusion par moyenne et obtention d’une classification finale.
      4. Décision stratégique (raise, call ou fold) en fonction de la classification finale, des mises et du contexte (pot, historique, agressivité adverse).
    """

    # --- 1. Journalisation et fonctions d'aide communes ---
    logger.info(f"Phase: {street}")
    logger.info(f"Best hand: {best_hand}, Highest hand: {highest_hand}")
    logger.info(f"Pot: {pot}, Min: {min_amount}, Max: {max_amount}")

    # Flag pour indiquer que, si les mises sont faibles ou si l'adversaire est « dry », on jouera prudemment
    OPP_DRY = False

    def raise_player(amount_percent):
        """Calcule la mise de relance à partir d'un pourcentage de max_amount."""
        desired_raise = max_amount * amount_percent
        if OPP_DRY:
            return "call", min_amount
        if desired_raise > max_amount:
            return "raise", max_amount
        if min_amount < desired_raise < max_amount:
            return "raise", desired_raise
        return "call", min_amount

    def get_last_action(phase):
        """Retourne la dernière action enregistrée pour la phase donnée."""
        if action_histories and phase in action_histories and action_histories[phase]:
            return action_histories[phase][-1]["action"]
        return None

    def sum_raises(action_histories, player_name):
        """Calcule la somme des relances effectuées par player_name sur toutes les phases."""
        total = 0
        if not action_histories:
            return 0
        for phase, actions in action_histories.items():
            for action in actions:
                if action.get("action") == "RAISE" and action.get("name") == player_name:
                    total += action.get("paid", 0)
        return total

    def is_opponent_aggressive():
        """Détermine si au moins deux relances ont été effectuées par des adversaires."""
        count = 0
        if not action_histories:
            return False
        for phase, actions in action_histories.items():
            for action in actions:
                if action.get("action") == "RAISE" and action.get("name") != player_name:
                    count += 1
        return count >= 2

    last_action = get_last_action(street)
    logger.info(f"Dernière action sur {street}: {last_action}")
    current_raise = sum_raises(action_histories, player_name)
    opponent_aggressive = is_opponent_aggressive()
    logger.info(f"L'adversaire est {'agressif' if opponent_aggressive else 'passif'}")

    # Ajustement des mises si elles sont nulles ou négatives
    if min_amount <= 0:
        OPP_DRY = True
        min_amount = 500
    if max_amount <= 0:
        OPP_DRY = True
        max_amount = 501

    # --- 2. Systèmes de classification avancée pour le FLOP ---
    # 2.1. Premier système : classification « basic »
    def classify_flop_basic(best, highest):
        """
        Si la main faite est au top (best == highest) :
           9  -> "monster"
           8  -> "ultra_made"
           7  -> "premium"
           6  -> "very_strong"
           5  -> "strong"
           4  -> "playable"
           <=3 -> "marginal"
        Sinon, en fonction de l'écart (diff = highest - best) :
           diff == 1 : "semi_bluff" si best >= 7, sinon "drawing"
           diff == 2 : "marginal_draw"
           diff >= 3 : "trash"
        """
        if best == highest:
            if best == 9:
                return "monster"
            elif best == 8:
                return "ultra_made"
            elif best == 7:
                return "premium"
            elif best == 6:
                return "very_strong"
            elif best == 5:
                return "strong"
            elif best == 4:
                return "playable"
            else:
                return "marginal"
        else:
            diff = highest - best
            if diff == 1:
                return "semi_bluff" if best >= 7 else "drawing"
            elif diff == 2:
                return "marginal_draw"
            else:
                return "trash"

    basic_class = classify_flop_basic(best_hand, highest_hand)

    # 2.2. Deuxième système : modèle « pro » (avec seuils légèrement décalés)
    def classify_flop_pro(best, highest):
        """
        Variante du modèle de classification pour le FLOP :
           Si best == highest :
             best >= 8  -> "monster"
             best == 7  -> "ultra_made"
             best == 6  -> "premium"
             best == 5  -> "very_strong"
             best == 4  -> "strong"
             sinon     -> "playable"
           Sinon :
             diff == 1 -> "drawing" (même si best est élevé)
             diff == 2 -> "marginal_draw"
             diff >= 3 -> "trash"
        """
        if best == highest:
            if best >= 8:
                return "monster"
            elif best == 7:
                return "ultra_made"
            elif best == 6:
                return "premium"
            elif best == 5:
                return "very_strong"
            elif best == 4:
                return "strong"
            else:
                return "playable"
        else:
            diff = highest - best
            if diff == 1:
                return "drawing"
            elif diff == 2:
                return "marginal_draw"
            else:
                return "trash"

    pro_class = classify_flop_pro(best_hand, highest_hand)

    # 2.3. Fusion des classifications
    # On attribue à chaque catégorie un score numérique (plus le score est élevé, meilleure est la main)
    class_score_map = {
        "monster": 9,
        "ultra_made": 8,
        "premium": 7,
        "very_strong": 6,
        "strong": 5,
        "playable": 4,
        "semi_bluff": 3.5,
        "drawing": 3,
        "marginal_draw": 2,
        "marginal": 1.5,
        "trash": 1
    }

    score_basic = class_score_map.get(basic_class, 1)
    score_pro = class_score_map.get(pro_class, 1)
    average_score = (score_basic + score_pro) / 2.0

    # Définition de la classification finale en fonction de la moyenne obtenue
    if average_score >= 8.5:
        final_class = "monster"
    elif average_score >= 7.5:
        final_class = "ultra_made"
    elif average_score >= 6.5:
        final_class = "premium"
    elif average_score >= 5.5:
        final_class = "very_strong"
    elif average_score >= 4.5:
        final_class = "strong"
    elif average_score >= 3.5:
        final_class = "playable"
    elif average_score >= 3:
        final_class = "semi_bluff"  # On peut aussi obtenir "drawing" si la moyenne est basse
    elif average_score >= 2:
        final_class = "marginal_draw"
    else:
        final_class = "trash"

    logger.info(f"Classifications intermédiaires : basic={basic_class}, pro={pro_class}")
    logger.info(f"Score moyen: {average_score:.2f} => Classification finale: {final_class}")
    print(f"Classification finale sur le FLOP: {final_class}")

    # --- 3. Décision stratégique en fonction de la classification finale ---
    action = "fold"
    amount = 0.0

    if final_class in {"monster", "ultra_made"}:
        # Mains de très grande force : jeu très agressif sur le flop
        if last_action in {None, "CHECK"}:
            action = "raise"
            amount = max(min_amount, max_amount * 0.35)
        else:
            action = "raise"
            amount = max(min_amount, max_amount * 0.40)
    elif final_class in {"premium", "very_strong"}:
        # Mains solides : relance modérée si le coût est raisonnable
        if min_amount < max_amount * 0.25:
            action = "raise"
            amount = max(min_amount, max_amount * 0.30)
        else:
            action = "call"
            amount = min_amount
    elif final_class in {"strong", "playable"}:
        # Mains jouables : appel si la mise est faible
        if min_amount < pot * 0.20:
            action = "raise"
            amount = max(min_amount, max_amount * 0.20)
        else:
            action = "call"
            amount = min_amount
    elif final_class in {"semi_bluff", "drawing", "marginal_draw"}:
        # Mains avec potentiel de tirage ou semi‑bluff : on appelle si le rapport mise/pot est favorable
        if min_amount <= pot * 0.15:
            action = "call"
            amount = min_amount
        else:
            action = "fold"
            amount = 0
    else:  # trash
        action = "fold"
        amount = 0

    # --- 4. Ajustement final en fonction de l'agressivité adverse ---
    if get_last_action(street) in {"raise", "bet", "re-raise"}:
        if final_class not in {"monster", "ultra_made", "premium", "very_strong", "strong"}:
            logger.info("Agressivité adverse détectée et main insuffisante : fold")
            action = "fold"
            amount = 0
        elif final_class in {"monster", "ultra_made"} and action == "raise":
            amount = max(min_amount, max_amount * 0.45)

    logger.info(f"Action retenue sur le FLOP: {action} avec le montant: {amount}")
    print(f"Action retenue sur le FLOP: {action} avec le montant: {amount}")
    return action, amount
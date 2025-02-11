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
    Stratégie pré‑flop ultra avancée pour le Texas Hold’em.
    
    Ce module réalise les étapes suivantes :
      1. Analyse et conversion des hole cards en une représentation canonique (ex. "AKs", "88").
      2. Classification de la main à l'aide de plusieurs systèmes professionnels :
           - Classification par ensembles (ultra_premium, premium, very_strong, strong, playable,
             speculative, marginal, trash) basée sur des sets pré‑établis.
           - Calcul du score selon la formule Chen.
           - Classification selon les groupes Sklansky.
      3. Fusion de ces trois systèmes pour obtenir une note moyenne de force, puis une classification
         finale.
      4. Décision stratégique (raise, call ou fold) en fonction de cette classification et du contexte (mises, pot, historique).
    """
    
    # --- 1. Conversion et analyse des cartes ---
    rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
                'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    
    def parse_card(card):
        """
        Extrait la couleur, le rang (avec conversion de "10" en "T") et la valeur numérique.
        Exemples :
          "DQ" -> ('D', 'Q', 12)
          "S10" -> ('S', 'T', 10)
        """
        suit = card[0]
        rank_str = card[1:]
        rank_char = 'T' if rank_str == "10" else rank_str[0]
        value = rank_map.get(rank_char, 0)
        return suit, rank_char, value

    # Analyse des deux cartes
    suit1, rank1, value1 = parse_card(hole_cards[0])
    suit2, rank2, value2 = parse_card(hole_cards[1])
    
    # Détermine si les cartes sont assorties et si elles forment une paire
    suited = (suit1 == suit2)
    pair = (rank1 == rank2)
    
    # Ordonne les cartes pour obtenir une représentation canonique (la plus forte en premier)
    if value1 >= value2:
        high_rank, low_rank = rank1, rank2
        high_value, low_value = value1, value2
    else:
        high_rank, low_rank = rank2, rank1
        high_value, low_value = value2, value1

    # Représentation canonique : pour une paire => "JJ", sinon "AKs" (si assorties) ou "AKo"
    if pair:
        canonical_hand = high_rank + high_rank
    else:
        canonical_hand = high_rank + low_rank + ("s" if suited else "o")
    
    logger.info(f"Player {player_name} a les hole cards {hole_cards} -> Canonical: {canonical_hand}")
    logger.info(f"Min amount: {min_amount}, Max amount: {max_amount}, Pot: {pot}")
    logger.info(f"Historique actions: {action_histories}")
    print(f"Player {player_name} a les hole cards {hole_cards} -> Canonical: {canonical_hand}")
    
    # --- 2. Récupération de la dernière action ---
    def get_last_action():
        if action_histories and "preflop" in action_histories and action_histories["preflop"]:
            return action_histories["preflop"][-1]["action"]
        return None

    last_action = get_last_action()
    logger.info(f"Dernière action: {last_action}")
    print(f"Dernière action: {last_action}")

    # --- 3. Systèmes de classification avancée ---
    # 3.1. Classification par ensembles pré‑établis
    ultra_premium_hands = {"AA", "KK"}
    premium_hands       = {"QQ", "JJ", "AKs"}
    very_strong_hands   = {"TT", "AQs", "AJs"}
    strong_hands        = {"KQs", "AKo"}
    playable_hands      = {"99", "88", "77", "AQo", "ATs", "KJs", "QJs"}
    # On considère aussi que certaines petites paires, connecteurs assortis et connecteurs one‑gap sont spéculatifs :
    suited_connectors   = {"98s", "87s", "76s", "65s", "54s"}
    suited_one_gap      = {"97s", "86s", "75s", "64s", "53s"}
    small_pairs         = {"66", "55", "44", "33", "22"}
    
    def classify_by_ensembles(canonical):
        """
        Renvoie une classification basée sur des ensembles pré‑établis.
        """
        if canonical in ultra_premium_hands:
            return "ultra_premium"
        elif canonical in premium_hands:
            return "premium"
        elif canonical in very_strong_hands:
            return "very_strong"
        elif canonical in strong_hands:
            return "strong"
        elif canonical in playable_hands:
            return "playable"
        elif canonical in suited_connectors or canonical in suited_one_gap or canonical in small_pairs:
            return "speculative"
        else:
            # Cas par défaut : pour une paire basse, on pourra considérer playable, sinon trash
            if pair:
                return "playable" if high_value >= 8 else "trash"
            else:
                gap = high_value - low_value
                if suited and gap <= 3:
                    return "speculative"
                elif not suited and gap == 1 and high_value >= 10:
                    return "marginal"
                else:
                    return "trash"
    
    original_class = classify_by_ensembles(canonical_hand)
    
    # 3.2. Calcul du score selon la formule Chen
    chen_values = {
        'A': 10, 'K': 8, 'Q': 7, 'J': 6, 'T': 5,
        '9': 4.5, '8': 4, '7': 3.5, '6': 3, '5': 2.5,
        '4': 2, '3': 1.5, '2': 1
    }
    
    def calculate_chen_score():
        # Utilise high_rank, low_rank, pair, suited, high_value, low_value
        base = chen_values.get(high_rank, 0)
        if pair:
            score = max(5, base * 2)
        else:
            score = base
            if suited:
                score += 2
            # Calcul de l'écart (gap en nombre de rangs entre les deux cartes, 0 si consécutives)
            gap = (high_value - low_value - 1)
            if gap == 0:
                if high_value < 5:  # bonus pour petites cartes connectées
                    score += 1
            elif gap == 1:
                score -= 1
            elif gap == 2:
                score -= 2
            elif gap == 3:
                score -= 4
            elif gap >= 4:
                score -= 5
            if score < 0:
                score = 0
        return score

    chen_score = calculate_chen_score()
    
    def classify_by_chen(score):
        if score >= 10:
            return "ultra_premium"
        elif score >= 8:
            return "premium"
        elif score >= 7:
            return "very_strong"
        elif score >= 6:
            return "strong"
        elif score >= 5:
            return "playable"
        elif score >= 4:
            return "speculative"
        elif score >= 3:
            return "marginal"
        else:
            return "trash"
    
    chen_class = classify_by_chen(chen_score)
    
    # 3.3. Classification selon les groupes Sklansky
    group1 = {"AA", "KK", "QQ", "JJ", "AKs"}
    group2 = {"TT", "AQs", "AJs", "KQs", "AKo"}
    group3 = {"99", "JTs", "QJs", "KJs", "ATs", "KQo"}
    group4 = {"88", "77", "QTs", "AJo", "KJo", "T9s", "98s"}
    group5 = {"66", "55", "44", "33", "22", "T8s", "97s", "87s", "76s", "65s"}
    group6 = {"T7s", "96s", "85s", "74s"}
    
    def classify_by_sklansky(canonical):
        if canonical in group1:
            return "ultra_premium"
        elif canonical in group2:
            return "premium"
        elif canonical in group3:
            return "very_strong"
        elif canonical in group4:
            return "strong"
        elif canonical in group5:
            return "playable"
        elif canonical in group6:
            return "speculative"
        else:
            return "trash"
    
    sklansky_class = classify_by_sklansky(canonical_hand)
    
    # 3.4. Fusion des classifications
    # On attribue à chaque catégorie une valeur numérique pour faire la moyenne.
    class_score_map = {
        "ultra_premium": 8,
        "premium": 7,
        "very_strong": 6,
        "strong": 5,
        "playable": 4,
        "speculative": 3,
        "marginal": 2,
        "trash": 1
    }
    
    score1 = class_score_map.get(original_class, 1)
    score2 = class_score_map.get(chen_class, 1)
    score3 = class_score_map.get(sklansky_class, 1)
    average_score = (score1 + score2 + score3) / 3.0

    # Définition de la classification finale en fonction de la moyenne
    if average_score >= 7.5:
        final_class = "ultra_premium"
    elif average_score >= 6.5:
        final_class = "premium"
    elif average_score >= 5.5:
        final_class = "very_strong"
    elif average_score >= 4.5:
        final_class = "strong"
    elif average_score >= 3.5:
        final_class = "playable"
    elif average_score >= 2.5:
        final_class = "speculative"
    elif average_score >= 1.5:
        final_class = "marginal"
    else:
        final_class = "trash"
    
    logger.info(f"Classifications intermédiaires : ensembles={original_class}, chen={chen_class}, sklansky={sklansky_class}")
    logger.info(f"Score moyen: {average_score:.2f} => Classification finale: {final_class}")
    print(f"Classification finale: {final_class}")

    # --- 4. Décision stratégique en fonction de la classification finale ---
    action = "fold"
    amount = 0.0
    
    # Ajustement de la mise en fonction de la force de la main
    if final_class in {"ultra_premium", "premium"}:
        # Mains très fortes : jeu agressif
        if last_action in {"SMALLBLIND", "BIGBLIND", None}:
            action = "raise"
            amount = max(min_amount, max_amount * 0.30)
        else:
            action = "raise"
            amount = max(min_amount, max_amount * 0.35)
    elif final_class in {"very_strong", "strong"}:
        if min_amount < max_amount * 0.15:
            action = "raise"
            amount = max(min_amount, max_amount * 0.18)
        else:
            action = "call"
            amount = min_amount
    elif final_class == "playable":
        if min_amount < max_amount * 0.10:
            action = "raise"
            amount = max(min_amount, max_amount * 0.12)
        else:
            action = "call"
            amount = min_amount
    elif final_class == "speculative":
        if min_amount <= pot * 0.10:
            action = "call"
            amount = min_amount
        else:
            # Pour varier le jeu, parfois call aléatoirement
            if randint(0, 10) == 0:
                action = "call"
                amount = min_amount
            else:
                action = "fold"
                amount = 0
    elif final_class == "marginal":
        if min_amount <= pot * 0.05:
            action = "call"
            amount = min_amount
        else:
            action = "fold"
            amount = 0
    else:  # trash
        action = "fold"
        amount = 0

    # --- 5. Ajustement final en fonction de l'historique d'agressivité ---
    if last_action in {"raise", "re-raise", "bet"}:
        if final_class not in {"ultra_premium", "premium", "very_strong", "strong"}:
            logger.info("Agressivité adverse détectée et main insuffisante : fold")
            action = "fold"
            amount = 0
        elif final_class in {"ultra_premium", "premium"} and action == "raise":
            amount = max(min_amount, max_amount * 0.40)
    
    logger.info(f"Action retenue : {action} avec le montant : {amount}")
    print(f"Action retenue : {action} avec le montant : {amount}")
    return action, amount

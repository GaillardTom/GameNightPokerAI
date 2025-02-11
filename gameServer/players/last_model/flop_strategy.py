import math
from random import randint, random

# ------------------------ Paramètres Globaux ------------------------
Q_TABLE_FLOP = {}         # Q‑table pour le FLOP (pour le Q-learning)
ALPHA_PREFLOP = 0.1       # Taux d'apprentissage

INITIAL_EPSILON = 0.3     # Epsilon initial pour l'exploration
EPSILON_DECAY = 0.01      # Décroissance d'epsilon par appel
INITIAL_TEMPERATURE = 1.0 # Température initiale pour softmax
TEMPERATURE_DECAY = 0.005 # Décroissance de la température

# ------------------------ Fonctions Utilitaires ------------------------

def softmax(q_dict, temperature):
    """Calcule la distribution softmax à partir d'un dictionnaire de Q‑valeurs."""
    if not q_dict:
        return {}
    max_q = max(q_dict.values())
    exp_vals = {act: math.exp((q - max_q) / temperature) for act, q in q_dict.items()}
    total = sum(exp_vals.values())
    return {act: exp_vals[act] / total for act in exp_vals} if total > 0 else {}

def dynamic_epsilon(call_count, opp_aggr_ratio):
    """Retourne un epsilon dynamique décroissant, mais augmenté si l'adversaire est agressif."""
    epsilon = max(0.01, INITIAL_EPSILON / (1 + call_count * EPSILON_DECAY))
    return epsilon * (1 + 0.5 * opp_aggr_ratio)

def dynamic_temperature(call_count):
    """Retourne une température dynamique décroissante pour la sélection softmax."""
    return max(0.1, INITIAL_TEMPERATURE / (1 + call_count * TEMPERATURE_DECAY))

def gain_multiplier(pot, min_amount):
    """Retourne un multiplicateur de gain basé sur le ratio pot/min_amount, plafonné à 3."""
    ratio = pot / min_amount if min_amount > 0 else 1
    return min(ratio, 3)

def shape_reward(base_reward, opp_aggr_ratio, opp_showdown_ratio, action, final_class, pot, min_amount):
    """
    Ajuste la récompense de base en tenant compte de l'agressivité adverse préflop (opp_aggr_ratio)
    et de celle constatée au showdown (opp_showdown_ratio), ainsi que du potentiel de gain.
    Les bonus sont renforcés pour les mains fortes face à des adversaires agressifs.
    """
    bonus = 1.0
    if opp_aggr_ratio > 0.6:
        if final_class in {"monster", "ultra_made", "premium"} and action in {"raise", "call"}:
            bonus = 1.3
        elif final_class in {"trash", "drawing"} and action == "raise":
            bonus = 0.8
    elif opp_aggr_ratio > 0.5:
        if final_class in {"monster", "ultra_made", "premium"} and action in {"raise", "call"}:
            bonus = 1.2
        elif final_class in {"trash", "drawing"} and action == "raise":
            bonus = 0.8
    if opp_showdown_ratio > 0.6 and final_class not in {"monster", "ultra_made", "premium"}:
        bonus *= 0.8  # Pénalité supplémentaire pour les mains faibles contre un opp très agressif au showdown
    multiplier = gain_multiplier(pot, min_amount)
    return base_reward * bonus * multiplier

def parse_card(card):
    """Extrait la couleur, le rang et la valeur numérique d'une carte."""
    rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
                '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    suit = card[0]
    rank_str = card[1:]
    rank_char = 'T' if rank_str == "10" else rank_str[0]
    return suit, rank_char, rank_map.get(rank_char, 0)

def classify_connectivity(hole_cards):
    """
    Évalue la connectivité des hole cards.
      - Gap 0 (paire) → bonus de 2.0.
      - Gap 1 → bonus de 1.0 si assorties, sinon 0.5.
      - Gap 2 → bonus de 0.3.
      - Bonus additionnel de 0.5 si les deux cartes sont hautes (≥10).
      - Bonus supplémentaire de 0.5 si les cartes sont séquentielles.
    """
    s1, r1, v1 = parse_card(hole_cards[0])
    s2, r2, v2 = parse_card(hole_cards[1])
    gap = abs(v1 - v2)
    bonus = 0.0
    if gap == 0:
        bonus = 2.0
    elif gap == 1:
        bonus = 1.0 if s1 == s2 else 0.5
    elif gap == 2:
        bonus = 0.3
    if v1 >= 10 and v2 >= 10:
        bonus += 0.5
    # Bonus pour séquentialité (ex : 7-8, 10-J)
    if gap == 1:
        bonus += 0.5
    return bonus

def get_opponent_showdown_aggressiveness(player_name, action_histories):
    """Calcule le ratio d'agressivité adverse constatée au showdown."""
    count = 0
    total = 0
    if action_histories and "showdown" in action_histories:
        for act in action_histories["showdown"]:
            if act.get("actor") != player_name:
                total += 1
                if act.get("action").lower() in {"bet", "raise"}:
                    count += 1
    return (count / total) if total > 0 else 0

# ------------------------ STRATÉGIE FLOP ------------------------
CALL_COUNT_FLOP = 0

def get_card_action(
    player_name,
    best_hand,      # Évaluation numérique (1 à 9) de la main sur le FLOP
    highest_hand,   # Score maximum sur le board
    min_amount,     # Mise minimale requise
    max_amount,     # Mise maximale autorisée
    street,         # "flop"
    pot,            # Taille du pot principal
    side_pots,      # Non utilisé ici
    action_histories,
    logger,
):
    """
    Stratégie FLOP avancée pour le Texas Hold’em.

    Intègre :
      1. Évaluation de la main par trois approches (ensembles, Chen, Sklansky)
         avec un bonus de connectivité et de séquentialité.
      2. Fusion pondérée pour obtenir une classification finale (ex. "monster", "premium", etc.).
      3. Arbre de décision adaptatif tenant compte du pot, des mises et de l'agressivité adverse.
      4. Renforcement par Q‑learning avec epsilon dynamique, sélection softmax et reward shaping
         intégrant également l'agressivité constatée au showdown.
    """
    global CALL_COUNT_FLOP, Q_TABLE_FLOP
    CALL_COUNT_FLOP += 1
    logger.info(f"[FLOP] Phase: {street}")
    logger.info(f"[FLOP] Best hand: {best_hand}, Highest board: {highest_hand}")
    logger.info(f"[FLOP] Pot: {pot}, Min: {min_amount}, Max: {max_amount}")

    # Récupération de la dernière action dans la phase
    def get_last_action_local(phase):
        if action_histories and phase in action_histories and action_histories[phase]:
            return action_histories[phase][-1]["action"].lower()
        return None
    last_act = get_last_action_local(street)

    # Détection de l'agressivité adverse
    def is_opponent_aggressive():
        count = 0
        total = 0
        if action_histories and "flop" in action_histories:
            for act in action_histories["flop"]:
                if act.get("actor") != player_name:
                    total += 1
                    if act.get("action").lower() in {"raise", "bet", "re-raise"}:
                        count += 1
        return (count >= 2), (count / total if total > 0 else 0)
    opp_aggr, opp_aggr_ratio = is_opponent_aggressive()
    logger.info(f"[FLOP] Opponent aggressiveness: {opp_aggr_ratio:.2f}")

    # Bonus de connectivité : utiliser "hole_cards" depuis l'historique si disponible
    hole_cards_for_conn = action_histories.get("hole_cards", None)
    if hole_cards_for_conn is None:
        connectivity_bonus = 0.0
    else:
        connectivity_bonus = classify_connectivity(hole_cards_for_conn)
    logger.info(f"[FLOP] Connectivity bonus: {connectivity_bonus:.2f}")

    # Classification par méthodes classiques
    def classify_flop_basic(best, highest):
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

    def classify_flop_pro(best, highest):
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

    basic_class = classify_flop_basic(best_hand, highest_hand)
    pro_class = classify_flop_pro(best_hand, highest_hand)
    score_map = {
        "monster": 9, "ultra_made": 8, "premium": 7, "very_strong": 6,
        "strong": 5, "playable": 4, "drawing": 3, "marginal_draw": 2, "trash": 1
    }
    s_basic = score_map.get(basic_class, 1)
    s_pro = score_map.get(pro_class, 1)
    weighted_avg = 0.3 * s_basic + 0.4 * s_pro + 0.3 * connectivity_bonus

    if weighted_avg >= 8:
        final_class = "monster"
    elif weighted_avg >= 7:
        final_class = "ultra_made"
    elif weighted_avg >= 6:
        final_class = "premium"
    elif weighted_avg >= 5:
        final_class = "very_strong"
    elif weighted_avg >= 4:
        final_class = "strong"
    elif weighted_avg >= 3:
        final_class = "playable"
    elif weighted_avg >= 2:
        final_class = "drawing"
    else:
        final_class = "trash"

    logger.info(f"[FLOP] Classification: basic={basic_class}, pro={pro_class} -> Final: {final_class}")

    # ------------------ Arbre de Décision FLOP ------------------
    action = "fold"
    amount = 0.0
    if final_class in {"monster", "ultra_made"}:
        if opp_aggr_ratio > 0.6:
            action = "raise"
            amount = max(min_amount, pot * 0.50)
        else:
            if opp_aggr:
                if random() < 0.3:
                    action = "call"
                    amount = min_amount
                    logger.info("[FLOP] Slow play activated (aggressive opponent).")
                else:
                    action = "raise"
                    amount = max(min_amount, pot * 0.45)
            else:
                if last_act in {None, "check"}:
                    action = "raise"
                    amount = max(min_amount, pot * 0.40)
                else:
                    action = "raise"
                    amount = max(min_amount, pot * 0.50)
    elif final_class in {"premium", "very_strong"}:
        action = "raise" if min_amount < pot * 0.15 else "call"
        amount = max(min_amount, pot * 0.20) if action == "raise" else min_amount
    elif final_class in {"playable"}:
        action = "raise" if min_amount < pot * 0.10 else "call"
        amount = max(min_amount, pot * 0.12) if action == "raise" else min_amount
    elif final_class in {"drawing", "marginal_draw"}:
        action = "call" if min_amount <= pot * 0.10 else "fold"
        amount = min_amount if action == "call" else 0
    else:
        action = "fold"
        amount = 0

    if get_last_action_local(street) in {"raise", "bet", "re-raise"}:
        if final_class not in {"monster", "ultra_made", "premium", "very_strong", "strong"}:
            logger.info("[FLOP] Aggressive action detected with weak hand -> fold")
            action = "fold"
            amount = 0
        elif final_class in {"monster", "ultra_made"} and action == "raise":
            amount = max(min_amount, pot * 0.50)
    logger.info(f"[FLOP] Initial decision: {action} with amount: {amount}")

    # ------------------ Renforcement par Q-learning ------------------
    epsilon = dynamic_epsilon(CALL_COUNT_FLOP, opp_aggr_ratio)
    temperature = dynamic_temperature(CALL_COUNT_FLOP)
    possible_actions = ["fold", "call", "raise"]
    q_vals = {act: Q_TABLE_FLOP.get((final_class, act), 0) for act in possible_actions}
    if random() < epsilon:
        chosen_action = possible_actions[randint(0, len(possible_actions)-1)]
        logger.info(f"[FLOP] Random exploration selected: {chosen_action}")
    else:
        probs = softmax(q_vals, temperature)
        r_val = random()
        cumulative = 0.0
        chosen_action = None
        for act, prob in probs.items():
            cumulative += prob
            if r_val < cumulative:
                chosen_action = act
                break
        if chosen_action is None:
            chosen_action = max(q_vals, key=q_vals.get)
    if q_vals.get(chosen_action, 0) > q_vals.get(action, 0) + 0.3:
        logger.info(f"[FLOP] Q-learning adjustment: replacing {action} with {chosen_action}")
        action = chosen_action
        if action == "fold":
            amount = 0
        elif action == "call":
            amount = min_amount
        elif action == "raise":
            if final_class in {"monster", "ultra_made"}:
                amount = max(min_amount, pot * 0.50)
            elif final_class in {"premium", "very_strong"}:
                amount = max(min_amount, pot * 0.30)
            elif final_class in {"playable"}:
                amount = max(min_amount, pot * 0.15)
            else:
                amount = max(min_amount, pot * 0.10)
    logger.info(f"[FLOP] Final decision after Q-learning: {action} with amount: {amount}")

    # ------------------ Mise à jour de la Q-table ------------------
    if final_class in {"ultra_premium", "premium"}:
        base_reward = 1.5 if action == "raise" else 1.0 if action == "call" else -2.0
    elif final_class in {"very_strong", "strong"}:
        base_reward = 1.2 if action in {"raise", "call"} else -1.2
    elif final_class in {"playable"}:
        base_reward = 0.8 if action in {"raise", "call"} else -0.8
    elif final_class in {"speculative", "marginal"}:
        base_reward = 0.6 if action == "call" else -1.0
    else:
        base_reward = 1.0 if action == "fold" else -1.5

    opp_showdown_ratio = get_opponent_showdown_aggressiveness(player_name, action_histories)
    reward = shape_reward(base_reward, opp_aggr_ratio, opp_showdown_ratio, action, final_class, pot, min_amount)
    key = (final_class, action)
    prev_q = Q_TABLE_FLOP.get(key, 0)
    Q_TABLE_FLOP[key] = (1 - ALPHA_PREFLOP) * prev_q + ALPHA_PREFLOP * reward
    logger.info(f"[FLOP] Q_TABLE updated for {key}: {Q_TABLE_FLOP[key]:.2f} (reward: {reward})")
    
    return action, amount

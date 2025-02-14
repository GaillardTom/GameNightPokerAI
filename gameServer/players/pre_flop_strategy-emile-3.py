import math
from random import randint, random

# ------------------------ PARAMÈTRES GLOBAUX ------------------------
Q_TABLE_PREFLOP = {}         # Q‑table pour le préflop (Q-learning)
REGRETS_CFR_PREFLOP = {}       # Regrets pour CFR
CALL_COUNT_PREFLOP = 0         # Compteur global préflop

ALPHA_PREFLOP = 0.1          # Taux d'apprentissage
INITIAL_EPSILON = 0.3        # Epsilon initial pour l'exploration
EPSILON_DECAY = 0.01         # Décroissance d'epsilon
INITIAL_TEMPERATURE = 1.0    # Température initiale (softmax)
TEMPERATURE_DECAY = 0.005    # Décroissance de la température
MONTE_CARLO_SAMPLES = 20     # Nombre d'échantillons pour bluff

# Poids de fusion CFR / Q
CFR_WEIGHT = 0.5

# ------------------------ FONCTIONS UTILITAIRES ------------------------

def softmax(q_dict, temperature):
    if not q_dict:
        return {}
    max_q = max(q_dict.values())
    exp_vals = {a: math.exp((v - max_q) / temperature) for a, v in q_dict.items()}
    total = sum(exp_vals.values())
    return {a: exp_vals[a] / total for a in exp_vals} if total > 0 else {}

def dynamic_epsilon(call_count, opp_aggr_ratio):
    eps_base = max(0.01, INITIAL_EPSILON / (1 + call_count * EPSILON_DECAY))
    return eps_base * (1 + 0.5 * opp_aggr_ratio)

def dynamic_temperature(call_count):
    return max(0.05, INITIAL_TEMPERATURE / (1 + call_count * TEMPERATURE_DECAY))

def gain_multiplier(pot, min_amount):
    if min_amount <= 0:
        return 1.0
    ratio = pot / min_amount
    return min(ratio, 3)

def parse_card(card):
    rank_map = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7,
                '8':8, '9':9, 'T':10, 'J':11, 'Q':12, 'K':13, 'A':14}
    suit = card[0]
    rank_str = card[1:]
    rank_char = 'T' if rank_str == "10" else rank_str[0]
    return suit, rank_char, rank_map.get(rank_char, 0)

def classify_connectivity(hole_cards):
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
    if gap == 1:
        bonus += 0.5
    return bonus

def get_opponent_showdown_aggressiveness(player_name, action_histories):
    c = 0; t = 0
    if action_histories and "showdown" in action_histories:
        for act in action_histories["showdown"]:
            if act.get("actor") != player_name:
                t += 1
                if act.get("action").lower() in {"bet", "raise"}:
                    c += 1
    return (c / t) if t > 0 else 0.0

# ===================== CFR: Extraction et Update de la Policy =====================

def cfr_policy_from_regrets(regrets_dict, final_class, possible_actions):
    local_reg = {}
    total = 0.0
    for a in possible_actions:
        key = (final_class, a)
        r = max(regrets_dict.get(key, 0.0), 0.0)
        local_reg[a] = r
        total += r
    if total <= 0:
        return {a: 1.0 / len(possible_actions) for a in possible_actions}
    return {a: local_reg[a] / total for a in possible_actions}

def cfr_update_regrets(regrets_dict, final_class, chosen_action, utility, possible_actions):
    for a in possible_actions:
        key = (final_class, a)
        old_r = regrets_dict.get(key, 0.0)
        if a == chosen_action:
            regret = 0  # u(chosen) - u(chosen) = 0
        else:
            regret = 0 - utility
        regrets_dict[key] = old_r + regret

# ===================== SHAPE REWARD =====================

def shape_reward(base_reward, opp_aggr_ratio, opp_sd_ratio, action, final_class, pot, min_amount):
    bonus = 1.0
    # Augmentation des bonus pour raises sur mains fortes face à un adversaire agressif
    if opp_aggr_ratio > 0.6:
        if final_class in {"monster", "ultra_premium", "premium"} and action in {"raise", "call"}:
            bonus = 1.5
        elif final_class in {"trash", "drawing"} and action == "raise":
            bonus = 0.7
    elif opp_aggr_ratio > 0.5:
        if final_class in {"monster", "ultra_made", "premium"} and action in {"raise", "call"}:
            bonus = 1.3
        elif final_class in {"trash", "drawing"} and action == "raise":
            bonus = 0.8

    if opp_sd_ratio > 0.7 and final_class in {"monster", "ultra_made", "premium"} and action in {"raise", "call"}:
        bonus *= 1.2
    elif opp_sd_ratio > 0.6 and final_class not in {"monster", "ultra_made", "premium"}:
        bonus *= 0.8

    if final_class in {"playable", "drawing"}:
        bluff_chance = 0.35 + 0.25 * opp_aggr_ratio
        bc = 0
        for _ in range(MONTE_CARLO_SAMPLES):
            if random() < bluff_chance:
                bc += 1
        if bc > (MONTE_CARLO_SAMPLES / 2):
            bonus *= 1.2

    if final_class == "monster" and action == "fold":
        bonus *= 0.6
    elif final_class == "trash" and action == "raise":
        bonus *= 0.9

    if opp_aggr_ratio < 0.3:
        if final_class in {"strong", "very_strong", "premium", "ultra_premium", "monster"} and action == "raise":
            bonus *= 1.3

    mul = gain_multiplier(pot, min_amount)
    return base_reward * bonus * mul

# ===================== STRATÉGIE PRE-FLOP AGRESSIVE (ENCORE PLUS AGRESSIVE) =====================

def get_pre_flop_action(
    player_name,
    hole_cards,
    min_amount,
    max_amount,
    street,  # "preflop"
    pot,
    side_pots,
    action_histories,
    logger,
):
    global CALL_COUNT_PREFLOP, Q_TABLE_PREFLOP, REGRETS_CFR_PREFLOP
    CALL_COUNT_PREFLOP += 1
    logger.info(f"[PREFLOP] hole_cards={hole_cards}, pot={pot}, min={min_amount}, max={max_amount}")

    # Détection de l'agressivité adverse préflop
    def preflop_aggression():
        c = 0; t = 0
        if action_histories and "preflop" in action_histories:
            for act in action_histories["preflop"]:
                if act.get("actor") != player_name:
                    t += 1
                    if act.get("action").lower() in {"raise", "re-raise", "bet"}:
                        c += 1
        return (c >= 2), (c / t if t > 0 else 0.0)
    opp_aggr, opp_aggr_ratio = preflop_aggression()
    logger.info(f"[PREFLOP] opp_aggr_ratio={opp_aggr_ratio:.2f}")
    opp_sd_ratio = get_opponent_showdown_aggressiveness(player_name, action_histories)
    logger.info(f"[PREFLOP] opp_showdown_ratio={opp_sd_ratio:.2f}")

    # Classification de la main (version simplifiée et agressive)
    def parse_preflop_hand(c1, c2):
        s1, r1, v1 = parse_card(c1)
        s2, r2, v2 = parse_card(c2)
        suited = (s1 == s2)
        if r1 == r2:
            return r1 + r1
        if v1 > v2:
            hi, lo = (r1, r2)
        else:
            hi, lo = (r2, r1)
        return hi + lo + ("s" if suited else "o")
    # Catégories simples : "monster", "premium", "trash"
    uprem = {"AA", "KK"}
    prem = {"QQ", "JJ", "AKs"}
    def classify_preflop_simple(canon):
        if canon in uprem:
            return "monster"
        elif canon in prem:
            return "premium"
        else:
            return "trash"
    c_hand = parse_preflop_hand(hole_cards[0], hole_cards[1])
    final_class = classify_preflop_simple(c_hand)
    logger.info(f"[PREFLOP] canonical_hand={c_hand} => final_class={final_class}")

    # --- ARBRE DE DÉCISION PRE-FLOP (STRATÉGIE ENCORE PLUS AGRESSIVE) ---
    action = "fold"
    amount = 0.0
    if final_class == "monster":
        # Mains monster : augmenter encore le raise
        if opp_aggr_ratio > 0.6:
            action = "raise"
            amount = max(min_amount, max_amount * 0.60)  # hausse plus forte
        else:
            action = "raise"
            amount = max(min_amount, max_amount * 0.55)
    elif final_class == "premium":
        # Mains premium : élargir le spectre de re-raise
        if min_amount < max_amount * 0.30:
            action = "raise"
            amount = max(min_amount, max_amount * 0.40)
        else:
            action = "call"
            amount = min_amount
    else:
        # Mains trash ou marginales : on reste agressif plutôt que de limper ou folder
        if min_amount <= pot * 0.20:
            action = "raise"   # Bluff raise agressif
            amount = max(min_amount, min_amount * 1.6)
        elif min_amount <= pot * 0.35:
            action = "call"    # On call pour voir le flop malgré un coût un peu plus élevé
            amount = min_amount
        else:
            # Au lieu de folder, on préfère call même à un coût élevé pour maintenir la pression
            action = "call"
            amount = min_amount

    # Ajustement final en cas de relance adverse
    def last_preflop_action():
        if action_histories and "preflop" in action_histories:
            if action_histories["preflop"]:
                return action_histories["preflop"][-1]["action"].lower()
        return None
    lpa = last_preflop_action()
    if lpa in {"raise", "re-raise", "bet"}:
        # Même si l'adversaire a raise, on continue d'être agressif avec toutes les mains,
        # en particulier on évite de folder sur une main trash
        if final_class == "trash":
            if min_amount <= pot * 0.30:
                pass  # conserver notre décision agressive initiale
            elif min_amount <= pot * 0.45:
                action = "call"
                amount = min_amount
            else:
                # Au lieu de folder, on call pour rester dans la main
                action = "call"
                amount = min_amount

    logger.info(f"[PREFLOP] décision initiale => {action}, montant={amount:.2f}")

    poss_actions = ["fold", "call", "raise"]
    q_vals = {a: Q_TABLE_PREFLOP.get((final_class, a), 0.0) for a in poss_actions}
    eps = dynamic_epsilon(CALL_COUNT_PREFLOP, opp_aggr_ratio)
    temp = dynamic_temperature(CALL_COUNT_PREFLOP)
    q_policy = softmax(q_vals, temp)
    cfr_policy = cfr_policy_from_regrets(REGRETS_CFR_PREFLOP, final_class, poss_actions)
    combined_policy = {}
    for a in poss_actions:
        combined_policy[a] = CFR_WEIGHT * cfr_policy.get(a, 0.0) + (1 - CFR_WEIGHT) * q_policy.get(a, 0.0)
    total_comb = sum(combined_policy.values())
    if total_comb <= 0:
        combined_policy = {a: 1.0 / len(poss_actions) for a in poss_actions}
    else:
        for a in combined_policy:
            combined_policy[a] /= total_comb

    r_draw = random()
    cumul = 0.0
    cfr_chosen_action = None
    for a, p in combined_policy.items():
        cumul += p
        if r_draw < cumul:
            cfr_chosen_action = a
            break
    if not cfr_chosen_action:
        cfr_chosen_action = max(combined_policy, key=combined_policy.get)

    # Choix final : si la valeur Q suggère mieux que la décision initiale, on l'adopte
    if q_vals.get(cfr_chosen_action, 0.0) > q_vals.get(action, 0.0) + 0.3:
        action = cfr_chosen_action
        if action == "fold":
            amount = 0
        elif action == "call":
            amount = min_amount
        elif action == "raise":
            if final_class == "monster":
                amount = max(min_amount, max_amount * 0.60)
            elif final_class == "premium":
                amount = max(min_amount, max_amount * 0.40)
            else:
                amount = max(min_amount, pot * 0.15)

    logger.info(f"[PREFLOP] décision finale => {action}, montant={amount:.2f}")

    # Mise à jour des tables de Q-learning et de regrets
    base_r = 1.0
    if final_class == "monster":
        base_r = 1.5 if action == "raise" else 1.0 if action == "call" else -2.0
    elif final_class == "premium":
        base_r = 1.2 if action in {"raise", "call"} else -1.2
    else:
        base_r = 1.0 if action == "fold" else -1.5

    rew = shape_reward(base_r, opp_aggr_ratio, opp_sd_ratio, action, final_class, pot, min_amount)
    key = (final_class, action)
    old_q = Q_TABLE_PREFLOP.get(key, 0.0)
    Q_TABLE_PREFLOP[key] = (1 - ALPHA_PREFLOP) * old_q + ALPHA_PREFLOP * rew
    REGRETS_CFR_PREFLOP[key] = REGRETS_CFR_PREFLOP.get(key, 0.0) + rew

    new_q_val = Q_TABLE_PREFLOP[key]
    reg_val = REGRETS_CFR_PREFLOP.get(key, 0.0)
    logger.info(f"[PREFLOP] final_class={final_class}, action={action}, montant={amount:.2f}, reward={rew:.2f}")
    logger.info(f"[PREFLOP] Q_TABLE[{key}]={new_q_val:.2f}, regret={reg_val:.2f}")

    return action, amount

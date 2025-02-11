import math
from random import randint, random

# ------------------------ Paramètres Globaux ------------------------
Q_TABLE_FLOP = {}         # Q‑table FLOP (Q-learning)
ALPHA_FLOP = 0.1          # Taux d'apprentissage pour le FLOP

INITIAL_EPSILON = 0.3     # Epsilon initial (exploration)
EPSILON_DECAY = 0.01      # Décroissance d'epsilon
INITIAL_TEMPERATURE = 1.0 # Température initiale pour la softmax
TEMPERATURE_DECAY = 0.005 # Décroissance de la température

CALL_COUNT_FLOP = 0       # Compteur global pour la phase FLOP

# Exemple d’un paramètre Monte-Carlo (bluff)
MONTE_CARLO_SAMPLES = 20  

# Regrets (inspiration CFR)
REGRETS_CFR_FLOP = {}

# ------------------------ Fonctions Utilitaires ------------------------

def softmax(q_dict, temperature):
    """Transforme un dictionnaire de Q‑valeurs en distribution softmax."""
    if not q_dict:
        return {}
    max_q = max(q_dict.values())
    exp_vals = {
        act: math.exp((val - max_q) / temperature)
        for act, val in q_dict.items()
    }
    total = sum(exp_vals.values())
    return {act: exp_vals[act] / total for act in exp_vals} if total > 0 else {}

def dynamic_epsilon(call_count, opp_aggr_ratio):
    """Epsilon décroissant avec le temps, augmenté si l'adversaire est agressif."""
    base_epsilon = max(0.01, INITIAL_EPSILON / (1 + call_count * EPSILON_DECAY))
    return base_epsilon * (1 + 0.5 * opp_aggr_ratio)

def dynamic_temperature(call_count):
    """Température décroissante pour la softmax."""
    return max(0.05, INITIAL_TEMPERATURE / (1 + call_count * TEMPERATURE_DECAY))

def gain_multiplier(pot, min_amount):
    """Facteur multiplicateur du reward, plafonné à 3, basé sur pot / min_amount."""
    if min_amount <= 0:
        return 1.0
    ratio = pot / min_amount
    return min(ratio, 3)

def parse_card(card):
    """Extrait la couleur, le rang et la valeur numérique d’une carte (ex: 'SA')."""
    rank_map = {
        '2': 2,'3': 3,'4': 4,'5': 5,'6': 6,'7': 7,
        '8': 8,'9': 9,'T': 10,'J': 11,'Q': 12,'K': 13,'A': 14
    }
    suit = card[0]
    rank_str = card[1:]
    rank_char = 'T' if rank_str == "10" else rank_str[0]
    return suit, rank_char, rank_map.get(rank_char, 0)

def classify_connectivity(hole_cards):
    """
    Bonus de connectivité, séquentialité, hautes cartes.
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
    if gap == 1:
        bonus += 0.5
    return bonus

def get_opponent_showdown_aggressiveness(player_name, action_histories):
    """
    Calcule l'agressivité adverse au showdown (ratio bet/raise).
    """
    c = 0
    t = 0
    if action_histories and "showdown" in action_histories:
        for act in action_histories["showdown"]:
            if act.get("actor") != player_name:
                t += 1
                if act.get("action").lower() in {"bet", "raise"}:
                    c += 1
    return (c / t) if t > 0 else 0.0

def shape_reward(base_reward, opp_aggr_ratio, opp_showdown_ratio,
                 action, final_class, pot, min_amount):
    """
    Ajuste la récompense selon :
      - agressivité FLOP (opp_aggr_ratio)
      - agressivité showdown (opp_showdown_ratio)
      - composante Monte-Carlo bluff
      - regrets CFR simplifiés (ex: monster fold => pénalité)
    """
    bonus = 1.0

    # Agressivité FLOP
    if opp_aggr_ratio > 0.6:
        if final_class in {"monster", "ultra_made", "premium"} and action in {"raise", "call"}:
            bonus = 1.4
        elif final_class in {"trash", "drawing"} and action == "raise":
            bonus = 0.75
    elif opp_aggr_ratio > 0.5:
        if final_class in {"monster", "ultra_made", "premium"} and action in {"raise", "call"}:
            bonus = 1.2
        elif final_class in {"trash", "drawing"} and action == "raise":
            bonus = 0.8

    # Agressivité showdown
    if opp_showdown_ratio > 0.6 and final_class not in {"monster", "ultra_made", "premium"}:
        bonus *= 0.8

    # Monte-Carlo bluff (ex: borderline main => plus de bluffs si adversaire agressif)
    if final_class in {"playable", "drawing"}:
        bluff_chance = 0.4 + 0.2 * opp_aggr_ratio
        bluff_count = 0
        for _ in range(MONTE_CARLO_SAMPLES):
            if random() < bluff_chance:
                bluff_count += 1
        if bluff_count > MONTE_CARLO_SAMPLES / 2:
            bonus *= 1.2

    # Regrets CFR simplifiés (ex: monster & fold => gros regret)
    if final_class == "monster" and action == "fold":
        bonus *= 0.6
    elif final_class == "trash" and action == "raise":
        bonus *= 0.9

    multi = gain_multiplier(pot, min_amount)
    return base_reward * bonus * multi

# ------------------------ STRATÉGIE FLOP ------------------------
def get_card_action(
    player_name,
    best_hand,    # évaluation 1..9
    highest_hand, # évaluation 1..9
    min_amount,
    max_amount,
    street,       # "flop"
    pot,
    side_pots,
    action_histories,
    logger,
):
    """
    Stratégie FLOP : Q-learning, CFR regrets, Monte-Carlo (bluff),
    plus agressive, en évitant la syntax error sur 'CALL_COUNT_FLOP'.
    """
    global CALL_COUNT_FLOP, Q_TABLE_FLOP  # On déclare avant toute assignation

    CALL_COUNT_FLOP += 1
    logger.info(f"[FLOP] best_hand={best_hand}, highest_hand={highest_hand}, pot={pot}, min={min_amount}, max={max_amount}")

    # 1) Calcul agressivité FLOP
    def flop_aggression():
        c = 0
        t = 0
        if action_histories and "flop" in action_histories:
            for act in action_histories["flop"]:
                if act.get("actor") != player_name:
                    t += 1
                    if act.get("action").lower() in {"raise","bet","re-raise"}:
                        c += 1
        return (c >= 2), (c / t if t > 0 else 0.0)
    opp_aggr, opp_aggr_ratio = flop_aggression()
    logger.info(f"[FLOP] opp_aggr_ratio={opp_aggr_ratio:.2f}")

    # showdown aggressiveness
    opp_sd_ratio= get_opponent_showdown_aggressiveness(player_name, action_histories)
    logger.info(f"[FLOP] opp_showdown_ratio={opp_sd_ratio:.2f}")

    # 2) Classification multi-approche
    # 2.1 Basic
    def classify_flop_basic(b, h):
        if b == h:
            if b >= 8: return "monster"
            elif b == 7: return "ultra_made"
            elif b == 6: return "premium"
            elif b == 5: return "very_strong"
            elif b == 4: return "strong"
            else:        return "playable"
        else:
            diff = h - b
            if diff == 1: return "drawing"
            elif diff == 2: return "marginal_draw"
            else:          return "trash"
    # 2.2 Pro
    def classify_flop_pro(b, h):
        if b == h:
            if b >= 8: return "monster"
            elif b == 7: return "ultra_made"
            elif b == 6: return "premium"
            elif b == 5: return "very_strong"
            elif b == 4: return "strong"
            else:        return "playable"
        else:
            diff = h - b
            if diff == 1: return "drawing"
            elif diff == 2: return "marginal_draw"
            else:          return "trash"

    sc_map = {"monster":9,"ultra_made":8,"premium":7,"very_strong":6,
              "strong":5,"playable":4,"drawing":3,"marginal_draw":2,"trash":1}

    c_basic= classify_flop_basic(best_hand, highest_hand)
    c_pro  = classify_flop_pro(best_hand, highest_hand)
    sb = sc_map.get(c_basic,1)
    sp = sc_map.get(c_pro,1)

    # connect bonus
    hole_cards_for_conn = action_histories.get("hole_cards", None)
    connectivity_bonus = 0.0
    if hole_cards_for_conn:
        connectivity_bonus = classify_connectivity(hole_cards_for_conn)

    weighted_avg= 0.3*sb + 0.4*sp + 0.3*connectivity_bonus
    if weighted_avg>=8:
        final_class="monster"
    elif weighted_avg>=7:
        final_class="ultra_made"
    elif weighted_avg>=6:
        final_class="premium"
    elif weighted_avg>=5:
        final_class="very_strong"
    elif weighted_avg>=4:
        final_class="strong"
    elif weighted_avg>=3:
        final_class="playable"
    elif weighted_avg>=2:
        final_class="drawing"
    else:
        final_class="trash"

    logger.info(f"[FLOP] basic={c_basic}, pro={c_pro}, connect={connectivity_bonus:.2f} => final_class={final_class}")

    # 3) Arbre de décision agressif
    action="fold"
    amount=0.0
    if final_class in {"monster","ultra_made"}:
        if opp_aggr_ratio>0.6:
            action="raise"
            amount= max(min_amount, pot*0.55)
        else:
            if opp_aggr and random()<0.3:
                action="call"
                amount= min_amount
                logger.info("[FLOP] slow-play vs aggressif.")
            else:
                action="raise"
                amount= max(min_amount, pot*0.45)
    elif final_class in {"premium","very_strong"}:
        if min_amount< pot*0.15:
            action="raise"
            amount= max(min_amount, pot*0.2)
        else:
            action="call"
            amount= min_amount
    elif final_class in {"strong","playable"}:
        if min_amount< pot*0.1:
            action="raise"
            amount= max(min_amount, pot*0.12)
        else:
            action="call"
            amount= min_amount
    elif final_class in {"drawing","marginal_draw"}:
        if min_amount<= pot*0.1:
            action="call"
            amount= min_amount
        else:
            action="fold"
            amount=0
    else:
        action="fold"
        amount=0

    # si l'adversaire a bet/raise => fold si main < strong
    def last_flop_action():
        if action_histories and "flop" in action_histories:
            if action_histories["flop"]:
                return action_histories["flop"][-1]["action"].lower()
        return None
    lfa= last_flop_action()
    if lfa in {"raise","re-raise","bet"} and final_class not in {"monster","ultra_made","premium","very_strong","strong"}:
        action="fold"
        amount=0

    logger.info(f"[FLOP] initial decision => {action}, amt={amount:.1f}")

    # 4) Q-learning
    possible_actions= ["fold","call","raise"]
    q_vals= {}
    for a2 in possible_actions:
        q_vals[a2]= Q_TABLE_FLOP.get((final_class,a2), 0.0)

    eps= dynamic_epsilon(CALL_COUNT_FLOP, opp_aggr_ratio)
    temp= dynamic_temperature(CALL_COUNT_FLOP)
    dist= softmax(q_vals, temp)

    if random()<eps:
        chosen_act= possible_actions[randint(0,len(possible_actions)-1)]
    else:
        r_rand= random()
        cumul=0.0
        chosen_act=None
        for a2, p in dist.items():
            cumul+=p
            if r_rand< cumul:
                chosen_act= a2
                break
        if not chosen_act:
            chosen_act= max(dist, key=dist.get)

    # override si Q-val plus haute
    if q_vals.get(chosen_act,0.0) > q_vals.get(action,0.0)+0.3:
        logger.info(f"[FLOP] Q override => {chosen_act}")
        action= chosen_act
        if action=="fold":
            amount=0
        elif action=="call":
            amount=min_amount
        elif action=="raise":
            if final_class in {"monster","ultra_made"}:
                amount= max(min_amount, pot*0.55)
            elif final_class in {"premium","very_strong"}:
                amount= max(min_amount, pot*0.3)
            elif final_class in {"strong","playable"}:
                amount= max(min_amount, pot*0.15)
            else:
                amount= max(min_amount, pot*0.1)

    logger.info(f"[FLOP] final => {action}, amt={amount:.1f}")

    # 5) calcul reward
    if final_class in {"monster","ultra_made"}:
        base_r=1.5 if action=="raise" else 1.0 if action=="call" else -2.0
    elif final_class in {"premium","very_strong"}:
        base_r=1.2 if action in {"raise","call"} else -1.2
    elif final_class in {"strong","playable"}:
        base_r=0.8 if action in {"raise","call"} else -0.8
    elif final_class in {"drawing","marginal_draw"}:
        base_r=0.6 if action=="call" else -1.0
    else:
        base_r=1.0 if action=="fold" else -1.5

    opp_show = get_opponent_showdown_aggressiveness(player_name, action_histories)
    reward= shape_reward(
        base_r,
        opp_aggr_ratio,
        opp_show,
        action,
        final_class,
        pot,
        min_amount
    )

    # 6) mise à jour Q-table
    key=(final_class,action)
    old_q= Q_TABLE_FLOP.get(key, 0.0)
    Q_TABLE_FLOP[key] = (1 - ALPHA_FLOP)*old_q + ALPHA_FLOP*reward

    # mise à jour regrets
    old_reg= REGRETS_CFR_FLOP.get(key,0.0)
    new_reg= old_reg + (reward - 0.0)
    REGRETS_CFR_FLOP[key] = new_reg

    # Sépare la variable pour éviter ValueError sur f-string
    q_val= Q_TABLE_FLOP[key]
    r_val= REGRETS_CFR_FLOP[key]
    logger.info(f"[FLOP] Q_TABLE[{key}]={q_val:.2f}, reward={reward:.2f}, regret={r_val:.2f}")

    return action, amount

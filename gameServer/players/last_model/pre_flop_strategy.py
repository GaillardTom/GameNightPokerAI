import math
from random import randint, random

# ------------------------ Paramètres Globaux ------------------------
Q_TABLE_PREFLOP = {}         # Q-table (Q-learning) pour le préflop
ALPHA_PREFLOP = 0.1          # Taux d'apprentissage

INITIAL_EPSILON = 0.3        # Epsilon initial pour l'exploration
EPSILON_DECAY = 0.01         # Décroissance d'epsilon
INITIAL_TEMPERATURE = 1.0    # Température initiale (softmax)
TEMPERATURE_DECAY = 0.005    # Décroissance de la température

# Regrets (inspiration CFR)
REGRETS_CFR_PREFLOP = {}
# Paramètre Monte-Carlo pour le bluff
MONTE_CARLO_SAMPLES = 20

# Adversary stats (exemple simplifié) : ratio folds to raise, etc.
# On peut l'extraire de l'historique. Pour l'instant, on le stocke globalement.
OPPONENT_STATS = {
    "fold_to_raise_ratio": 0.0,  # Simplifié
    "call_to_showdown_ratio": 0.0,
    # etc.
}

CALL_COUNT_PREFLOP = 0


# ------------------------ Fonctions Utilitaires ------------------------

def softmax(q_dict, temperature):
    """Transforme un dict de Q-valeurs en distribution via softmax."""
    if not q_dict:
        return {}
    max_q = max(q_dict.values())
    exp_vals = {a: math.exp((v - max_q)/temperature) for a,v in q_dict.items()}
    total = sum(exp_vals.values())
    return {a: exp_vals[a]/total for a in exp_vals} if total>0 else {}

def dynamic_epsilon(call_count, opp_aggr_ratio):
    """
    Epsilon décroissant avec le temps, augmenté par l'agressivité adversaire.
    """
    eps_base = max(0.01, INITIAL_EPSILON/(1+ call_count*EPSILON_DECAY))
    return eps_base*(1+0.5*opp_aggr_ratio)

def dynamic_temperature(call_count):
    """Température décroissante pour la sélection softmax."""
    return max(0.05, INITIAL_TEMPERATURE/(1+ call_count*TEMPERATURE_DECAY))

def gain_multiplier(pot, min_amount):
    """Renforce la reward si pot important, plafonné à x3."""
    if min_amount<=0:
        return 1.0
    ratio= pot/min_amount
    return min(ratio,3)

def parse_card(card):
    rank_map = {
        '2':2,'3':3,'4':4,'5':5,'6':6,'7':7,
        '8':8,'9':9,'T':10,'J':11,'Q':12,'K':13,'A':14
    }
    suit = card[0]
    rank_str= card[1:]
    rank_char= 'T' if rank_str=="10" else rank_str[0]
    return suit, rank_char, rank_map.get(rank_char, 0)

def classify_connectivity(hole_cards):
    """
    Bonus de connectivité, séquentialité, etc.
    """
    s1,r1,v1= parse_card(hole_cards[0])
    s2,r2,v2= parse_card(hole_cards[1])
    gap= abs(v1-v2)
    bonus=0.0
    if gap==0:
        bonus=2.0
    elif gap==1:
        bonus=1.0 if s1==s2 else 0.5
    elif gap==2:
        bonus=0.3
    if v1>=10 and v2>=10:
        bonus+=0.5
    if gap==1:
        bonus+=0.5
    return bonus

def get_opponent_showdown_aggressiveness(player_name, action_histories):
    """Calcule l'agressivité adverse au showdown."""
    c=0; t=0
    if action_histories and "showdown" in action_histories:
        for act in action_histories["showdown"]:
            if act.get("actor")!=player_name:
                t+=1
                if act.get("action").lower() in {"bet","raise"}:
                    c+=1
    return (c/t) if t>0 else 0

def shape_reward(base_reward, opp_aggr_ratio, opp_showdown_ratio, action, final_class,
                 pot, min_amount, logger):
    """
    Ajuste la reward en tenant compte:
      - agressivité preflop + showdown
      - composante Monte-Carlo pour bluff
      - regrets CFR simplifiés
      - stats adversaire (fold_to_raise, etc.)
    """
    bonus=1.0
    # 1) Agressivité preflop
    if opp_aggr_ratio>0.6:
        if final_class in {"monster","ultra_premium","premium"} and action in {"raise","call"}:
            bonus=1.4
        elif final_class in {"trash","drawing"} and action=="raise":
            bonus=0.75
    elif opp_aggr_ratio>0.5:
        if final_class in {"monster","ultra_made","premium"} and action in {"raise","call"}:
            bonus=1.2
        elif final_class in {"trash","drawing"} and action=="raise":
            bonus=0.8

    # 2) showdown agressif
    if opp_showdown_ratio>0.6 and final_class not in {"monster","ultra_premium","premium"}:
        bonus*=0.8

    # 3) Stats adversaire
    # ex: s'il fold souvent aux relances, on bluff plus
    fold_to_raise= OPPONENT_STATS.get("fold_to_raise_ratio", 0.0)
    if final_class in {"playable","speculative","marginal"} and action=="raise":
        if fold_to_raise>0.4:
            logger.info("[PREFLOP] L'adversaire fold souvent => plus de bluff rentables.")
            bonus*=1.1

    # 4) Monte-Carlo bluff
    if final_class in {"playable","drawing"}:
        bluff_chance=0.3 + 0.2*opp_aggr_ratio + 0.2*fold_to_raise
        bluff_count=0
        for _ in range(MONTE_CARLO_SAMPLES):
            if random()<bluff_chance:
                bluff_count+=1
        if bluff_count> MONTE_CARLO_SAMPLES/2:
            bonus*=1.15

    # 5) regrets CFR simplifiés
    if final_class=="monster" and action=="fold":
        bonus*=0.6
    elif final_class=="trash" and action=="raise":
        bonus*=0.9

    gm= gain_multiplier(pot, min_amount)
    return base_reward* bonus* gm

# ------------------------ STRATÉGIE PRE-FLOP ------------------------
def get_pre_flop_action(
    player_name,
    hole_cards,
    min_amount,
    max_amount,
    street,         # "preflop"
    pot,
    side_pots,
    action_histories,
    logger,
):
    """
    Stratégie préflop super-agressive et adaptative,
    combinant Q-learning, Monte-Carlo bluff, CFR regrets, 
    et un usage simplifié des stats adversaires (fold_to_raise).
    """
    global CALL_COUNT_PREFLOP, Q_TABLE_PREFLOP

    CALL_COUNT_PREFLOP+=1
    logger.info(f"[PREFLOP] hole_cards={hole_cards}, pot={pot}, min={min_amount}, max={max_amount}")

    # 1) agressivité adverse
    def preflop_aggression():
        c=0; t=0
        if action_histories and "preflop" in action_histories:
            for act in action_histories["preflop"]:
                if act.get("actor")!=player_name:
                    t+=1
                    if act.get("action").lower() in {"raise","re-raise","bet"}:
                        c+=1
        return (c>=2),(c/t if t>0 else 0.0)
    opp_aggr, opp_aggr_ratio = preflop_aggression()
    logger.info(f"[PREFLOP] opp_aggr_ratio={opp_aggr_ratio:.2f}")

    # 2) showdown agressif
    opp_sd_ratio= get_opponent_showdown_aggressiveness(player_name, action_histories)
    logger.info(f"[PREFLOP] opp_showdown_ratio={opp_sd_ratio:.2f}")

    # 3) Classification multi-approche
    def parse_preflop_hand(c1,c2):
        s1,r1,v1= parse_card(c1)
        s2,r2,v2= parse_card(c2)
        suited=(s1==s2)
        if r1==r2:
            return r1+r1
        if v1>v2:
            hi,lo=(r1,r2)
        else:
            hi,lo=(r2,r1)
        return hi+lo + ("s" if suited else "o")

    ultra_prem={"AA","KK"}
    premium   ={"QQ","JJ","AKs"}
    vstrong   ={"TT","AQs","AJs"}
    strong    ={"KQs","AKo"}
    playable  ={"99","88","77","AQo","ATs","KJs","QJs"}
    suited_conn={"98s","87s","76s","65s","54s"}
    suited_gap ={"97s","86s","75s","64s","53s"}
    smallp ={"66","55","44","33","22"}
    def classify_ensembles(canon):
        if canon in ultra_prem: return "ultra_premium"
        elif canon in premium: return "premium"
        elif canon in vstrong: return "very_strong"
        elif canon in strong: return "strong"
        elif canon in playable: return "playable"
        elif canon in suited_conn or canon in suited_gap or canon in smallp:
            return "speculative"
        else:
            return "trash"

    chen_values={'A':10,'K':8,'Q':7,'J':6,'T':5,'9':4.5,'8':4,'7':3.5,'6':3,'5':2.5,'4':2,'3':1.5,'2':1}
    def calc_chen_score(c1,c2):
        s1,r1,v1= parse_card(c1)
        s2,r2,v2= parse_card(c2)
        if v1>=v2:
            hv,hr,lv=(v1,r1,v2)
        else:
            hv,hr,lv=(v2,r2,v1)
        if r1==r2:
            return max(5, chen_values.get(hr,0)*2)
        sc= chen_values.get(hr,0)
        if s1==s2:
            sc+=2
        gap=(hv-lv)-1
        if gap==0 and hv<5: sc+=1
        elif gap==1: sc-=1
        elif gap==2: sc-=2
        elif gap==3: sc-=4
        elif gap>=4: sc-=5
        return max(sc,0)

    def classify_chen(val):
        if val>=10: return "ultra_premium"
        elif val>=8: return "premium"
        elif val>=7: return "very_strong"
        elif val>=6: return "strong"
        elif val>=5: return "playable"
        elif val>=4: return "speculative"
        elif val>=3: return "marginal"
        else: return "trash"

    g1={"AA","KK","QQ","JJ","AKs"}
    g2={"TT","AQs","AJs","KQs","AKo"}
    g3={"99","JTs","QJs","KJs","ATs","KQo"}
    g4={"88","77","QTs","AJo","KJo","T9s","98s"}
    g5={"66","55","44","33","22","T8s","97s","87s","76s","65s"}
    g6={"T7s","96s","85s","74s"}
    def classify_sklansky(canon):
        if canon in g1: return "ultra_premium"
        elif canon in g2: return "premium"
        elif canon in g3: return "very_strong"
        elif canon in g4: return "strong"
        elif canon in g5: return "playable"
        elif canon in g6: return "speculative"
        else: return "trash"

    def canonical(cards):
        c1,c2= cards
        s1,r1,v1= parse_card(c1)
        s2,r2,v2= parse_card(c2)
        if r1==r2:
            return r1+r1
        suited=(s1==s2)
        if v1>v2:
            return r1+r2+("s" if suited else "o")
        else:
            return r2+r1+("s" if suited else "o")

    c_hand= canonical(hole_cards)
    c_ens = classify_ensembles(c_hand)
    chscr= calc_chen_score(hole_cards[0], hole_cards[1])
    c_ch = classify_chen(chscr)
    c_sk = classify_sklansky(c_hand)
    c_bonus = classify_connectivity(hole_cards)

    class_map={
        "ultra_premium":8,"premium":7,"very_strong":6,"strong":5,
        "playable":4,"speculative":3,"marginal":2,"trash":1
    }
    s1= class_map.get(c_ens,1)
    s2= class_map.get(c_ch,1)
    s3= class_map.get(c_sk,1)
    wavg= 0.3*s1 + 0.4*s2 + 0.3*s3 + c_bonus
    if wavg>=9:
        final_class="monster"
    elif wavg>=8:
        final_class="ultra_premium"
    elif wavg>=7:
        final_class="premium"
    elif wavg>=6:
        final_class="very_strong"
    elif wavg>=5:
        final_class="strong"
    elif wavg>=4:
        final_class="playable"
    elif wavg>=3:
        final_class="speculative"
    elif wavg>=2:
        final_class="marginal"
    else:
        final_class="trash"
    logger.info(f"[PREFLOP] c_ens={c_ens}, c_chen={c_ch}, c_skl={c_sk}, connect={c_bonus:.2f} => final={final_class}, wavg={wavg:.2f}")

    # 4) Arbre de décision plus agressif
    action="fold"
    amount=0.0
    if final_class in {"monster","ultra_premium"}:
        if opp_aggr_ratio>0.6:
            action="raise"
            amount=max(min_amount, max_amount*0.45)
        else:
            if random()<0.3:
                action="call"
                amount=min_amount
            else:
                action="raise"
                amount=max(min_amount, max_amount*0.35)
    elif final_class in {"premium","very_strong"}:
        if min_amount< max_amount*0.2:
            action="raise"
            amount=max(min_amount, max_amount*0.25)
        else:
            action="call"
            amount=min_amount
    elif final_class in {"strong","playable"}:
        if min_amount< max_amount*0.1:
            action="raise"
            amount=max(min_amount, max_amount*0.15)
        else:
            action="call"
            amount=min_amount
    elif final_class in {"speculative","marginal"}:
        if min_amount<= pot*0.1:
            action="call"
            amount=min_amount
        else:
            action="fold"
            amount=0
    else:
        action="fold"
        amount=0

    # Si l'adversaire a bet/raise => fold si main < strong
    def last_preflop_action():
        if action_histories and "preflop" in action_histories:
            if action_histories["preflop"]:
                return action_histories["preflop"][-1]["action"].lower()
        return None
    lpa= last_preflop_action()
    if lpa in {"raise","re-raise","bet"} and final_class not in {"monster","ultra_premium","premium","very_strong","strong"}:
        action="fold"
        amount=0

    logger.info(f"[PREFLOP] decision init => {action}, amt={amount:.2f}")

    # 5) Q-learning + exploration
    poss_actions=["fold","call","raise"]
    q_vals= {}
    for act in poss_actions:
        q_vals[act]= Q_TABLE_PREFLOP.get((final_class,act),0.0)

    from random import random
    epsilon= dynamic_epsilon(CALL_COUNT_PREFLOP, opp_aggr_ratio)
    temperature= dynamic_temperature(CALL_COUNT_PREFLOP)
    # softmax
    pol= softmax(q_vals, temperature)
    if random()<epsilon:
        chosen_act= poss_actions[randint(0,len(poss_actions)-1)]
    else:
        r_draw= random()
        cumul=0.0
        chosen_act=None
        for a2,p in pol.items():
            cumul+=p
            if r_draw< cumul:
                chosen_act=a2
                break
        if not chosen_act:
            chosen_act= max(pol, key=pol.get)

    # override si Q-val plus haute
    if q_vals.get(chosen_act,0.0)> q_vals.get(action,0.0)+0.3:
        logger.info(f"[PREFLOP] Q override => {chosen_act}")
        action= chosen_act
        if action=="fold":
            amount=0
        elif action=="call":
            amount=min_amount
        elif action=="raise":
            if final_class in {"monster","ultra_premium"}:
                amount= max(min_amount, max_amount*0.4)
            elif final_class in {"premium","very_strong"}:
                amount= max(min_amount, max_amount*0.3)
            elif final_class in {"strong","playable"}:
                amount= max(min_amount, max_amount*0.15)
            else:
                amount= max(min_amount, max_amount*0.1)

    logger.info(f"[PREFLOP] final => {action}, amt={amount:.2f}")

    # 6) calcul reward
    if final_class in {"monster","ultra_premium"}:
        base_r=1.5 if action=="raise" else 1.0 if action=="call" else -2.0
    elif final_class in {"premium","very_strong"}:
        base_r=1.2 if action in {"raise","call"} else -1.2
    elif final_class in {"strong","playable"}:
        base_r=0.8 if action in {"raise","call"} else -0.8
    elif final_class in {"speculative","marginal"}:
        base_r=0.6 if action=="call" else -1.0
    else:
        base_r=1.0 if action=="fold" else -1.5

    rew= shape_reward(
        base_r,
        opp_aggr_ratio,
        get_opponent_showdown_aggressiveness(player_name, action_histories),
        action,
        final_class,
        pot,
        min_amount,
        logger
    )

    # 7) mise à jour Q-table
    key= (final_class, action)
    old_q= Q_TABLE_PREFLOP.get(key,0.0)
    Q_TABLE_PREFLOP[key] = (1-ALPHA_PREFLOP)* old_q + ALPHA_PREFLOP* rew

    # regrets cfr simplifiés
    old_reg= REGRETS_CFR_PREFLOP.get(key,0.0)
    new_reg= old_reg+ (rew - 0.0)
    REGRETS_CFR_PREFLOP[key]= new_reg

    # Pour éviter ValueError de f-string => on fait 2 variables
    new_q_val = Q_TABLE_PREFLOP[key]
    new_reg_val = REGRETS_CFR_PREFLOP[key]
    logger.info(f"[PREFLOP] Q_TABLE[{key}]={new_q_val:.2f}, rew={rew:.2f}, regret={new_reg_val:.2f}")

    return action, amount

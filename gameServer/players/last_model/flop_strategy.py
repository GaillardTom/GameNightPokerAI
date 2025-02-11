import math
from random import random, randint

# ------------------------ Paramètres Globaux ------------------------
Q_TABLE_FLOP  = {}
Q_TABLE_TURN  = {}
Q_TABLE_RIVER = {}

ALPHA_FLOP    = 0.1
ALPHA_TURN    = 0.1
ALPHA_RIVER   = 0.1

INITIAL_EPSILON = 0.3
EPSILON_DECAY   = 0.01
INITIAL_TEMPERATURE = 1.0
TEMPERATURE_DECAY   = 0.005

CALL_COUNT_FLOP  = 0
CALL_COUNT_TURN  = 0
CALL_COUNT_RIVER = 0

MONTE_CARLO_SAMPLES = 20

REGRETS_CFR_FLOP  = {}
REGRETS_CFR_TURN  = {}
REGRETS_CFR_RIVER = {}

# ------------------------ Fonctions Utilitaires Communes ------------------------

def softmax(q_dict, temperature):
    if not q_dict:
        return {}
    max_q = max(q_dict.values())
    exp_vals = {act: math.exp((val - max_q)/temperature) for act,val in q_dict.items()}
    total = sum(exp_vals.values())
    return {act: exp_vals[act]/total for act in exp_vals} if total>0 else {}

def dynamic_epsilon(call_count, opp_aggr_ratio):
    eps_base = max(0.01, INITIAL_EPSILON/(1+ call_count*EPSILON_DECAY))
    return eps_base*(1+ 0.5*opp_aggr_ratio)

def dynamic_temperature(call_count):
    return max(0.05, INITIAL_TEMPERATURE/(1+ call_count*TEMPERATURE_DECAY))

def gain_multiplier(pot, min_amount):
    if min_amount<=0:
        return 1.0
    ratio= pot/min_amount
    return min(ratio,3)

def parse_card(card):
    rank_map= {
        '2':2,'3':3,'4':4,'5':5,'6':6,'7':7,
        '8':8,'9':9,'T':10,'J':11,'Q':12,'K':13,'A':14
    }
    suit= card[0]
    rank_str= card[1:]
    rank_char= 'T' if rank_str=="10" else rank_str[0]
    return suit, rank_char, rank_map.get(rank_char,0)

def classify_connectivity(hole_cards):
    s1,r1,v1= parse_card(hole_cards[0])
    s2,r2,v2= parse_card(hole_cards[1])
    gap= abs(v1- v2)
    bonus= 0.0
    if gap==0:
        bonus=2.0
    elif gap==1:
        bonus= 1.0 if s1==s2 else 0.5
    elif gap==2:
        bonus= 0.3
    if v1>=10 and v2>=10:
        bonus+=0.5
    if gap==1:
        bonus+=0.5
    return bonus

def get_opponent_showdown_aggressiveness(player_name, action_histories):
    c=0; t=0
    if action_histories and "showdown" in action_histories:
        for act in action_histories["showdown"]:
            if act.get("actor")!= player_name:
                t+=1
                if act.get("action").lower() in {"bet","raise"}:
                    c+=1
    return (c/t) if t>0 else 0.0

def shape_reward(base_reward, opp_aggr_ratio, opp_sd_ratio, action,
                 final_class, pot, min_amount):
    bonus=1.0
    # Si adversaire très agressif
    if opp_aggr_ratio>0.6:
        if final_class in {"monster","ultra_made","premium"} and action in {"raise","call"}:
            bonus=1.4
        elif final_class in {"trash","drawing"} and action=="raise":
            bonus=0.75
    elif opp_aggr_ratio>0.5:
        if final_class in {"monster","ultra_made","premium"} and action in {"raise","call"}:
            bonus=1.2
        elif final_class in {"trash","drawing"} and action=="raise":
            bonus=0.8

    # Si showdown aggro
    if opp_sd_ratio>0.6 and final_class not in {"monster","ultra_made","premium"}:
        bonus*=0.8

    # Monte-Carlo bluff
    if final_class in {"playable","drawing"}:
        bluff_chance= 0.4
        if opp_aggr_ratio>0.6:
            bluff_chance+= 0.2
        elif opp_aggr_ratio<0.3:
            bluff_chance-= 0.1

        bc=0
        for _ in range(MONTE_CARLO_SAMPLES):
            if random()< bluff_chance:
                bc+=1
        if bc> MONTE_CARLO_SAMPLES/2:
            bonus*=1.2

    # Regrets CFR
    if final_class=="monster" and action=="fold":
        bonus*=0.6
    elif final_class=="trash" and action=="raise":
        bonus*=0.9

    # Si adversaire passif (opp_aggr_ratio<0.3) => value sur mains fortes
    if opp_aggr_ratio<0.3:
        if final_class in {"strong","very_strong","premium","ultra_made","monster"} and action=="raise":
            bonus*=1.2
        elif final_class in {"playable","drawing"} and action=="raise":
            bonus*=0.9

    mul= gain_multiplier(pot, min_amount)
    return base_reward* bonus* mul


# --------------------------- FLOP ---------------------------
def get_flop_action(
    player_name,
    best_hand,
    highest_hand,
    min_amount,
    max_amount,
    street,  # "flop"
    pot,
    side_pots,
    action_histories,
    logger,
):
    global CALL_COUNT_FLOP, Q_TABLE_FLOP
    CALL_COUNT_FLOP+=1
    logger.info(f"[FLOP] best={best_hand}, highest={highest_hand}, pot={pot}, min={min_amount}, max={max_amount}")

    # 1) Agressivité FLOP
    def flop_aggression():
        c=0; t=0
        if action_histories and "flop" in action_histories:
            for act in action_histories["flop"]:
                if act.get("actor")!= player_name:
                    t+=1
                    if act.get("action").lower() in {"raise","bet","re-raise"}:
                        c+=1
        return (c>=2),(c/t if t>0 else 0.0)
    opp_aggr, opp_aggr_ratio= flop_aggression()
    opp_sd_ratio= get_opponent_showdown_aggressiveness(player_name, action_histories)

    # Classification multi-approche
    def classify_flop_basic(b,h):
        if b==h:
            if b>=8: return "monster"
            elif b==7: return "ultra_made"
            elif b==6: return "premium"
            elif b==5: return "very_strong"
            elif b==4: return "strong"
            else:      return "playable"
        else:
            diff=h-b
            if diff==1: return "drawing"
            elif diff==2: return "marginal_draw"
            else:        return "trash"

    def classify_flop_pro(b,h):
        if b==h:
            if b>=8: return "monster"
            elif b==7: return "ultra_made"
            elif b==6: return "premium"
            elif b==5: return "very_strong"
            elif b==4: return "strong"
            else:      return "playable"
        else:
            diff= h-b
            if diff==1: return "drawing"
            elif diff==2: return "marginal_draw"
            else:        return "trash"

    sc_map= {"monster":9,"ultra_made":8,"premium":7,"very_strong":6,
             "strong":5,"playable":4,"drawing":3,"marginal_draw":2,"trash":1}
    c_basic= classify_flop_basic(best_hand, highest_hand)
    c_pro  = classify_flop_pro(best_hand, highest_hand)
    sb= sc_map.get(c_basic,1)
    sp= sc_map.get(c_pro,1)

    hole_cards_for_conn= action_histories.get("hole_cards", None)
    connect_bonus=0.0
    if hole_cards_for_conn:
        connect_bonus= classify_connectivity(hole_cards_for_conn)

    # Pondération adaptative
    if opp_aggr_ratio>0.5:
        w_basic=0.4
        w_pro  =0.6
    elif opp_aggr_ratio<0.3:
        w_basic=0.7
        w_pro  =0.3
    else:
        w_basic=0.6
        w_pro  =0.4

    weighted_avg= (w_basic* sb) + (w_pro* sp) + 0.3* connect_bonus
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

    action= "fold"
    amount= 0.0
    if final_class in {"monster","ultra_made"}:
        if opp_aggr_ratio>0.6:
            action= "raise"
            amount= max(min_amount, pot*0.55)
        else:
            if opp_aggr and random()<0.3:
                action= "call"
                amount= min_amount
            else:
                action= "raise"
                amount= max(min_amount, pot*0.45)
    elif final_class in {"premium","very_strong"}:
        if min_amount< pot*0.15:
            action= "raise"
            amount= max(min_amount, pot*0.2)
        else:
            action= "call"
            amount= min_amount
    elif final_class in {"strong","playable"}:
        if min_amount< pot*0.1:
            action= "raise"
            amount= max(min_amount, pot*0.12)
        else:
            action= "call"
            amount= min_amount
    elif final_class in {"drawing","marginal_draw"}:
        if min_amount<= pot*0.1:
            action= "call"
            amount= min_amount
        else:
            action= "fold"
            amount=0
    else:
        action= "fold"
        amount=0

    def last_flop_action():
        if action_histories and "flop" in action_histories:
            acts= action_histories["flop"]
            if acts:
                return acts[-1]["action"].lower()
        return None
    lfa= last_flop_action()
    if lfa in {"raise","re-raise","bet"} and final_class not in {"monster","ultra_made","premium","very_strong","strong"}:
        action= "fold"
        amount=0

    # Q-learning
    possible_actions= ["fold","call","raise"]
    q_vals={}
    for a2 in possible_actions:
        q_vals[a2]= Q_TABLE_FLOP.get((final_class,a2),0.0)

    eps= dynamic_epsilon(CALL_COUNT_FLOP, opp_aggr_ratio)
    temp= dynamic_temperature(CALL_COUNT_FLOP)
    dist= softmax(q_vals, temp)

    if random()< eps:
        chosen_act= possible_actions[randint(0,len(possible_actions)-1)]
    else:
        r_val= random()
        cumul=0.0
        chosen_act= None
        for a2, p in dist.items():
            cumul+= p
            if r_val< cumul:
                chosen_act= a2
                break
        if not chosen_act:
            chosen_act= max(dist, key=dist.get)

    if q_vals.get(chosen_act,0.0)> q_vals.get(action,0.0)+ 0.3:
        action= chosen_act
        if action=="fold":
            amount=0
        elif action=="call":
            amount= min_amount
        elif action=="raise":
            if final_class in {"monster","ultra_made"}:
                amount= max(min_amount, pot*0.55)
            elif final_class in {"premium","very_strong"}:
                amount= max(min_amount, pot*0.3)
            elif final_class in {"strong","playable"}:
                amount= max(min_amount, pot*0.15)
            else:
                amount= max(min_amount, pot*0.1)

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

    rew= shape_reward(base_r, opp_aggr_ratio, opp_sd_ratio, action,
                      final_class, pot, min_amount)

    key=(final_class, action)
    old_q= Q_TABLE_FLOP.get(key,0.0)
    Q_TABLE_FLOP[key]= (1- ALPHA_FLOP)* old_q + ALPHA_FLOP* rew

    old_reg= REGRETS_CFR_FLOP.get(key,0.0)
    new_reg= old_reg+ rew
    REGRETS_CFR_FLOP[key]= new_reg

    new_q= Q_TABLE_FLOP[key]
    reg_v= REGRETS_CFR_FLOP[key]
    logger.info(f"[FLOP] final_class={final_class}, action={action}, amount={amount:.2f}, reward={rew:.2f}")
    logger.info(f"[FLOP] Q_TABLE[{key}]={new_q:.2f}, regret={reg_v:.2f}")

    return action, amount


# --------------------------- TURN ---------------------------
Q_TABLE_TURN = {}
REGRETS_CFR_TURN = {}
CALL_COUNT_TURN = 0

def get_turn_action(
    player_name,
    best_hand,      # 1..9
    highest_hand,   # 1..9
    min_amount,
    max_amount,
    street,         # "turn"
    pot,
    side_pots,
    action_histories,
    logger,
):
    """
    Structure similaire au FLOP, 
    en ajustant la classification / pondération si on veut,
    et un arbre de décision potentiellement plus agressif.
    """
    global CALL_COUNT_TURN, Q_TABLE_TURN
    CALL_COUNT_TURN+=1
    logger.info(f"[TURN] best={best_hand}, highest={highest_hand}, pot={pot}, min={min_amount}, max={max_amount}")

    def turn_aggression():
        c=0; t=0
        if action_histories and "turn" in action_histories:
            for act in action_histories["turn"]:
                if act.get("actor")!= player_name:
                    t+=1
                    if act.get("action").lower() in {"raise","re-raise","bet"}:
                        c+=1
        return (c>=2),(c/t if t>0 else 0.0)
    opp_aggr, opp_aggr_ratio= turn_aggression()
    opp_sd_ratio= get_opponent_showdown_aggressiveness(player_name, action_histories)

    # Classification simplifiée
    def classify_turn_simple(b,h):
        if b==h:
            if b>=8: return "monster"
            elif b==7: return "ultra_made"
            elif b==6: return "premium"
            elif b==5: return "very_strong"
            elif b==4: return "strong"
            else:      return "playable"
        else:
            diff= h-b
            if diff==1: return "drawing"
            elif diff==2: return "marginal_draw"
            else:        return "trash"

    sc_map= {"monster":9,"ultra_made":8,"premium":7,"very_strong":6,
             "strong":5,"playable":4,"drawing":3,"marginal_draw":2,"trash":1}

    c_turn= classify_turn_simple(best_hand, highest_hand)
    final_class= c_turn
    score_c= sc_map.get(c_turn,1)

    # Arbre de décision
    action="fold"
    amount=0.0
    if final_class in {"monster","ultra_made"}:
        if opp_aggr_ratio>0.6:
            action="raise"
            amount= max(min_amount, pot*0.50)
        else:
            if opp_aggr and random()<0.3:
                action="call"
                amount= min_amount
            else:
                action="raise"
                amount= max(min_amount, pot*0.40)
    elif final_class in {"premium","very_strong"}:
        if min_amount< pot*0.2:
            action="raise"
            amount= max(min_amount, pot*0.25)
        else:
            action="call"
            amount= min_amount
    elif final_class in {"strong","playable"}:
        if min_amount< pot*0.1:
            action="raise"
            amount= max(min_amount, pot*0.15)
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

    def last_turn_action():
        if action_histories and "turn" in action_histories:
            lacts= action_histories["turn"]
            if lacts:
                return lacts[-1]["action"].lower()
        return None
    lta= last_turn_action()
    if lta in {"raise","re-raise","bet"} and final_class not in {"monster","ultra_made","premium","very_strong","strong"}:
        action="fold"
        amount=0

    # Q-learning
    poss_actions= ["fold","call","raise"]
    q_vals={}
    for a2 in poss_actions:
        q_vals[a2]= Q_TABLE_TURN.get((final_class,a2),0.0)

    eps= dynamic_epsilon(CALL_COUNT_TURN, opp_aggr_ratio)
    temp= dynamic_temperature(CALL_COUNT_TURN)
    dist= softmax(q_vals, temp)

    if random()< eps:
        chosen_act= poss_actions[randint(0,len(poss_actions)-1)]
    else:
        r_rand= random()
        cumul=0.0
        chosen_act= None
        for a2,p in dist.items():
            cumul+= p
            if r_rand< cumul:
                chosen_act= a2
                break
        if not chosen_act:
            chosen_act= max(dist, key=dist.get)

    if q_vals.get(chosen_act,0.0) > q_vals.get(action,0.0)+ 0.3:
        action= chosen_act
        if action=="fold":
            amount=0
        elif action=="call":
            amount= min_amount
        elif action=="raise":
            if final_class in {"monster","ultra_made"}:
                amount= max(min_amount, pot*0.50)
            elif final_class in {"premium","very_strong"}:
                amount= max(min_amount, pot*0.3)
            elif final_class in {"strong","playable"}:
                amount= max(min_amount, pot*0.15)
            else:
                amount= max(min_amount, pot*0.1)

    # Reward
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

    rew= shape_reward(base_r, opp_aggr_ratio, opp_sd_ratio, action,
                      final_class, pot, min_amount)

    key=(final_class,action)
    old_q= Q_TABLE_TURN.get(key,0.0)
    Q_TABLE_TURN[key]= (1- ALPHA_TURN)*old_q + ALPHA_TURN* rew

    old_reg= REGRETS_CFR_TURN.get(key,0.0)
    new_reg= old_reg+ rew
    REGRETS_CFR_TURN[key]= new_reg

    new_q= Q_TABLE_TURN[key]
    new_regv= REGRETS_CFR_TURN[key]
    print(f"[TURN] final_class={final_class}, action={action}, amount={amount:.2f}, rew={rew:.2f}")
    print(f"[TURN] Q_TABLE[{key}]={new_q:.2f}, regret={new_regv:.2f}")

    return action, amount

# --------------------------- RIVER ---------------------------
Q_TABLE_RIVER = {}
REGRETS_CFR_RIVER= {}
CALL_COUNT_RIVER= 0

def get_river_action(
    player_name,
    best_hand,
    highest_hand,
    min_amount,
    max_amount,
    street,   # "river"
    pot,
    side_pots,
    action_histories,
    logger,
):
    """
    Stratégie RIVER encore plus agressive (par ex. raise= pot*0.6 ou pot*0.7 pour monster),
    Q-learning, regrets CFR, etc.
    """
    global CALL_COUNT_RIVER, Q_TABLE_RIVER
    CALL_COUNT_RIVER+=1
    logger.info(f"[RIVER] best={best_hand}, highest={highest_hand}, pot={pot}, min={min_amount}, max={max_amount}")

    def river_aggression():
        c=0; t=0
        if action_histories and "river" in action_histories:
            for act in action_histories["river"]:
                if act.get("actor")!= player_name:
                    t+=1
                    if act.get("action").lower() in {"raise","re-raise","bet"}:
                        c+=1
        return (c>=2),(c/t if t>0 else 0.0)
    opp_aggr, opp_aggr_ratio= river_aggression()
    opp_sd_ratio= get_opponent_showdown_aggressiveness(player_name, action_histories)

    # Classification simple
    def classify_river_simple(b,h):
        if b==h:
            if b>=8: return "monster"
            elif b==7: return "ultra_made"
            elif b==6: return "premium"
            elif b==5: return "very_strong"
            elif b==4: return "strong"
            else:      return "playable"
        else:
            diff=h-b
            if diff==1: return "drawing"
            elif diff==2: return "marginal_draw"
            else:        return "trash"

    sc_map={"monster":9,"ultra_made":8,"premium":7,"very_strong":6,
            "strong":5,"playable":4,"drawing":3,"marginal_draw":2,"trash":1}
    c_river= classify_river_simple(best_hand, highest_hand)
    final_class= c_river

    # Arbre de décision RIVER
    action="fold"
    amount=0.0
    if final_class in {"monster","ultra_made"}:
        if opp_aggr_ratio>0.6:
            action= "raise"
            amount= max(min_amount, pot*0.6)  # plus agressif sur la RIVER
        else:
            if opp_aggr and random()<0.3:
                action= "call"
                amount= min_amount
            else:
                action= "raise"
                amount= max(min_amount, pot*0.5)
    elif final_class in {"premium","very_strong"}:
        if min_amount< pot*0.2:
            action= "raise"
            amount= max(min_amount, pot*0.25)
        else:
            action= "call"
            amount= min_amount
    elif final_class in {"strong","playable"}:
        if min_amount< pot*0.1:
            action= "raise"
            amount= max(min_amount, pot*0.15)
        else:
            action= "call"
            amount= min_amount
    elif final_class in {"drawing","marginal_draw"}:
        if min_amount<= pot*0.1:
            action= "call"
            amount= min_amount
        else:
            action= "fold"
            amount=0
    else:
        action= "fold"
        amount=0

    def last_river_action():
        if action_histories and "river" in action_histories:
            acts= action_histories["river"]
            if acts:
                return acts[-1]["action"].lower()
        return None
    lra= last_river_action()
    if lra in {"raise","re-raise","bet"} and final_class not in {"monster","ultra_made","premium","very_strong","strong"}:
        action= "fold"
        amount=0

    # Q-learning
    poss_actions= ["fold","call","raise"]
    q_vals={}
    for a2 in poss_actions:
        q_vals[a2]= Q_TABLE_RIVER.get((final_class,a2),0.0)

    eps= dynamic_epsilon(CALL_COUNT_RIVER, opp_aggr_ratio)
    temp= dynamic_temperature(CALL_COUNT_RIVER)
    dist= softmax(q_vals, temp)

    if random()< eps:
        chosen_act= poss_actions[randint(0,len(poss_actions)-1)]
    else:
        r_rand= random()
        cumul=0.0
        chosen_act=None
        for a2,p in dist.items():
            cumul+=p
            if r_rand< cumul:
                chosen_act= a2
                break
        if not chosen_act:
            chosen_act= max(dist, key=dist.get)

    if q_vals.get(chosen_act,0.0)> q_vals.get(action,0.0)+ 0.3:
        action= chosen_act
        if action=="fold":
            amount=0
        elif action=="call":
            amount= min_amount
        elif action=="raise":
            if final_class in {"monster","ultra_made"}:
                amount= max(min_amount, pot*0.6)
            elif final_class in {"premium","very_strong"}:
                amount= max(min_amount, pot*0.3)
            elif final_class in {"strong","playable"}:
                amount= max(min_amount, pot*0.15)
            else:
                amount= max(min_amount, pot*0.1)

    # Reward
    if final_class in {"monster","ultra_made"}:
        base_r= 1.5 if action=="raise" else 1.0 if action=="call" else -2.0
    elif final_class in {"premium","very_strong"}:
        base_r= 1.2 if action in {"raise","call"} else -1.2
    elif final_class in {"strong","playable"}:
        base_r= 0.8 if action in {"raise","call"} else -0.8
    elif final_class in {"drawing","marginal_draw"}:
        base_r= 0.6 if action=="call" else -1.0
    else:
        base_r= 1.0 if action=="fold" else -1.5

    rew= shape_reward(base_r, opp_aggr_ratio, opp_sd_ratio, action,
                      final_class, pot, min_amount)

    key=(final_class,action)
    old_q= Q_TABLE_RIVER.get(key,0.0)
    Q_TABLE_RIVER[key]= (1- ALPHA_RIVER)* old_q + ALPHA_RIVER* rew

    old_reg= REGRETS_CFR_RIVER.get(key,0.0)
    new_reg= old_reg+ rew
    REGRETS_CFR_RIVER[key]= new_reg

    new_q= Q_TABLE_RIVER[key]
    reg_v= REGRETS_CFR_RIVER[key]
    print(f"[RIVER] final_class={final_class}, action={action}, amount={amount:.2f}, reward={rew:.2f}")
    print(f"[RIVER] Q_TABLE[{key}]={new_q:.2f}, regret={reg_v:.2f}")

    return action, amount

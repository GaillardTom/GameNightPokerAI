import unittest
import logging
from pre_flop_strategy import get_pre_flop_action

suit_mapping = {"H": 1, "S": 2, "D": 3, "C": 4}  # Hearts, Spades, Diamonds, Clubs
rank_mapping = {
    "A": 1,   # Ace",
    "2": 2,   # Cards 2 through 10,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,  # Ten,
    "J": 11,  # Jack,
    "Q": 12,  # Queen,
    "K": 13,  # King,
}
# HA = Ace of Hearts
# C6 = Six of Clubs

class UnitTestsPreFlopFollowingCall(unittest.TestCase):

    def get_preflop_action(self, hole_cards):
        action_history = {"preflop": [
            {"action": "SMALLBLIND", "amount": 10, "add_amount": 10, "uuid": "1", "name": "AI Player"},
            {"action": "BIGBLIND", "amount": 20, "add_amount": 10, "uuid": "2", "name": "Player"},
            {"action": "CALL", "amount": 500, "add_amount": 500, "uuid": "1", "name": "AI Player"}
        ]}
        pre_flop_action = get_pre_flop_action(
            player_name="Player",
            hole_cards=hole_cards,
            min_amount=10,
            max_amount=1000,
            street="preflop",
            pot=500,
            side_pots=[],
            action_histories=action_history,
            logger=logging,
        )
        return pre_flop_action

    def test_double_ace(self):
        card_action = self.get_preflop_action(["CA", "SA"])
        self.assertIn(card_action[0], ['raise', 'call'])

    def test_ace_king_same_suit(self):
        card_action = self.get_preflop_action(["CA", "CK"])
        self.assertEqual('raise', card_action[0])

    def test_ace_queen_offsuit(self):
        card_action = self.get_preflop_action(["CA", "DQ"])
        self.assertIn(card_action[0], ['raise', 'call'])

    def test_small_pocket_pair(self):
        card_action = self.get_preflop_action(["C4", "S4"])
        self.assertIn(card_action[0], ['call', 'fold'])

    def test_middle_pocket_pair(self):
        card_action = self.get_preflop_action(["C8", "D8"])
        self.assertIn(card_action[0], ['raise', 'call'])

    def test_low_connectors(self):
        card_action = self.get_preflop_action(["C5", "D6"])
        self.assertIn(card_action[0], ['call', 'fold'])

    def test_high_connectors(self):
        card_action = self.get_preflop_action(["C9", "DT"])
        self.assertIn(card_action[0], ['raise', 'call'])

    def test_low_unsuited_cards(self):
        card_action = self.get_preflop_action(["C2", "D7"])
        self.assertEqual('fold', card_action[0])

    def test_suited_connectors(self):
        card_action = self.get_preflop_action(["H9", "HT"])
        self.assertIn(card_action[0], ['raise', 'call'])

    def test_suited_gappers(self):
        card_action = self.get_preflop_action(["H8", "HT"])
        self.assertIn(card_action[0], ['call', 'fold'])

    def test_king_low_kicker(self):
        card_action = self.get_preflop_action(["CK", "D2"])
        self.assertIn(card_action[0], ['call'])

    def test_jack_ten_suited(self):
        card_action = self.get_preflop_action(["SJ", "ST"])
        self.assertIn(card_action[0], ['call'])

    def test_queen_jack_suited(self):
        card_action = self.get_preflop_action(["CQ", "CJ"])
        self.assertIn(card_action[0], ['call'])

    def test_low_pocket_pair_under_pressure(self):
        card_action = self.get_preflop_action(["C3", "D3"])
        self.assertIn(card_action[0], ['call'])

    def test_ace_five_suited(self):
        card_action = self.get_preflop_action(["HA", "H5"])
        self.assertIn(card_action[0], ['call'])

    def test_king_queen_offsuit(self):
        card_action = self.get_preflop_action(["SK", "DQ"])
        self.assertIn(card_action[0], ['call'])

    def test_ten_five_offsuit(self):
        card_action = self.get_preflop_action(["CT", "H5"])
        self.assertEqual('fold', card_action[0])

    def test_seven_six_suited(self):
        card_action = self.get_preflop_action(["S7", "S6"])
        self.assertIn(card_action[0], ['call'])

    def test_five_four_suited(self):
        card_action = self.get_preflop_action(["H5", "H4"])
        self.assertIn(card_action[0], ['call'])

    def test_eight_seven_offsuit(self):
        card_action = self.get_preflop_action(["C8", "D7"])
        self.assertIn(card_action[0], ['call'])

    def test_king_jack_suited(self):
        card_action = self.get_preflop_action(["HK", "HJ"])
        self.assertIn(card_action[0], ['call'])

    def test_queen_ten_offsuit(self):
        card_action = self.get_preflop_action(["CQ", "DT"])
        self.assertIn(card_action[0], ['call'])

    def test_nine_seven_suited(self):
        card_action = self.get_preflop_action(["H9", "H7"])
        self.assertIn(card_action[0], ['call'])

    def test_ace_three_suited(self):
        card_action = self.get_preflop_action(["DA", "D3"])
        self.assertIn(card_action[0], ['call'])

    def test_ten_nine_offsuit(self):
        card_action = self.get_preflop_action(["ST", "D9"])
        self.assertIn(card_action[0], ['call'])

    def test_seven_two_offsuit(self):
        card_action = self.get_preflop_action(["S7", "D2"])
        self.assertIn(card_action[0], ['fold'])

    def test_six_three_offsuit(self):
        card_action = self.get_preflop_action(["S6", "D3"])
        self.assertIn(card_action[0], ['fold'])

    ### CHECK THIS ONE
    def test_four_two_offsuit(self):
        card_action = self.get_preflop_action(["C4", "H2"])
        self.assertIn(card_action[0], ['fold'])

    def test_eight_three_offsuit(self):
        card_action = self.get_preflop_action(["C8", "D3"])
        self.assertIn(card_action[0], ['fold'])

    def test_jack_four_offsuit(self):
        card_action = self.get_preflop_action(["HJ", "C4"])
        self.assertIn(card_action[0], ['fold', 'call'])

if __name__ == '__main__':
    unittest.main()




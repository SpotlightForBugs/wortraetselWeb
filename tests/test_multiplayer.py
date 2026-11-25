import unittest

import i18n
import multiplayer


def _room():
    room = multiplayer.new_room("ABCDE", "host", "Ana", "en", account="ana@example.com")
    room, error = multiplayer.add_player(room, "p2", "Ben")
    assert error is None
    return room


class RoomCodeTests(unittest.TestCase):
    def test_codes_are_valid_and_normalized(self):
        code = multiplayer.make_room_code()
        self.assertTrue(multiplayer.valid_code(code))
        self.assertTrue(multiplayer.valid_code(" abcde "))
        self.assertFalse(multiplayer.valid_code("ABC"))
        self.assertFalse(multiplayer.valid_code("ABCD0"))


class LobbyTests(unittest.TestCase):
    def test_joining_twice_is_a_no_op(self):
        room = _room()
        again, error = multiplayer.add_player(room, "p2", "Ben")
        self.assertIsNone(error)
        self.assertEqual(len(again["players"]), 2)

    def test_full_and_started_rooms_reject_new_players(self):
        room = _room()
        for i in range(multiplayer.MAX_PLAYERS - 2):
            room, _ = multiplayer.add_player(room, f"x{i}", "X")
        _, error = multiplayer.add_player(room, "late", "Late")
        self.assertEqual(error, "mp_room_full")
        started, _ = multiplayer.start_room(_room(), "host", word="cat")
        _, error = multiplayer.add_player(started, "late", "Late")
        self.assertEqual(error, "mp_room_started")

    def test_only_the_host_starts(self):
        _, error = multiplayer.start_room(_room(), "p2", word="cat")
        self.assertEqual(error, "mp_host_only")


class GuessTests(unittest.TestCase):
    def setUp(self):
        self.room, error = multiplayer.start_room(_room(), "host", word="cat")
        self.assertIsNone(error)

    def test_turns_hits_and_misses(self):
        room, error = multiplayer.guess(self.room, "p2", "c")
        self.assertEqual(error, "mp_not_your_turn")
        room, error = multiplayer.guess(self.room, "host", "c")
        self.assertIsNone(error)
        self.assertEqual(multiplayer.current_player(room), "host")
        room, error = multiplayer.guess(room, "host", "z")
        self.assertEqual(room["wrong_guesses"], 1)
        self.assertEqual(multiplayer.current_player(room), "p2")
        _, error = multiplayer.guess(room, "p2", "c")
        self.assertEqual(error, "mp_bad_letter")

    def test_solving_finishes_with_points_and_winner(self):
        room, _ = multiplayer.guess(self.room, "host", "z")
        room, _ = multiplayer.guess(room, "p2", "c")
        room, _ = multiplayer.guess(room, "p2", "a")
        room, _ = multiplayer.guess(room, "p2", "t")
        self.assertEqual(room["state"], "finished")
        self.assertEqual(room["result"]["status"], "won")
        self.assertEqual(room["result"]["points"], 900)
        self.assertEqual(room["result"]["winner"], "p2")
        _, error = multiplayer.guess(room, "p2", "q")
        self.assertEqual(error, "mp_not_playing")

    def test_losing_finishes_without_winner(self):
        room = self.room
        for letter in "bdefghijk":
            player = multiplayer.current_player(room)
            room, error = multiplayer.guess(room, player, letter)
            self.assertIsNone(error)
        self.assertEqual(room["result"]["status"], "lost")
        self.assertIsNone(room["result"]["winner"])


class PublicStateTests(unittest.TestCase):
    def test_word_and_accounts_stay_hidden_until_the_end(self):
        room, _ = multiplayer.start_room(_room(), "host", word="cat")
        room, _ = multiplayer.guess(room, "host", "a")
        state = multiplayer.public_state(room)
        self.assertNotIn("word", state)
        self.assertIsNone(state["result"])
        self.assertEqual(state["tiles"], ["", "a", ""])
        self.assertNotIn("account", state["players"][0])
        self.assertNotIn("cat", repr(state))


class CopyTests(unittest.TestCase):
    def test_every_language_has_every_multiplayer_string(self):
        keys = set(i18n._MULTIPLAYER_STRINGS["en"])
        for language in i18n._STRINGS:
            self.assertEqual(set(i18n._MULTIPLAYER_STRINGS[language]), keys)
            self.assertTrue(keys <= set(i18n.catalog(language)))


if __name__ == "__main__":
    unittest.main()

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


class LeaveTests(unittest.TestCase):
    def test_host_and_turn_move_on_when_a_player_leaves(self):
        room, _ = multiplayer.add_player(_room(), "p3", "Cem")
        room, _ = multiplayer.start_room(room, "host", word="cat")
        room, _ = multiplayer.guess(room, "host", "z")
        self.assertEqual(multiplayer.current_player(room), "p2")
        room, _ = multiplayer.remove_player(room, "p2")
        self.assertEqual(multiplayer.current_player(room), "p3")
        room, _ = multiplayer.remove_player(room, "host")
        self.assertEqual(room["host"], "p3")
        self.assertEqual(multiplayer.current_player(room), "p3")
        room, _ = multiplayer.remove_player(room, "p3")
        self.assertEqual(room["players"], [])
        self.assertEqual(room["state"], "waiting")

    def test_leaving_before_the_current_player_keeps_their_turn(self):
        room, _ = multiplayer.add_player(_room(), "p3", "Cem")
        room, _ = multiplayer.start_room(room, "host", word="cat")
        room, _ = multiplayer.guess(room, "host", "z")
        room, _ = multiplayer.guess(room, "p2", "q")
        self.assertEqual(multiplayer.current_player(room), "p3")
        room, _ = multiplayer.remove_player(room, "p2")
        self.assertEqual(multiplayer.current_player(room), "p3")


class RulesTests(unittest.TestCase):
    def test_a_room_needs_two_players_to_start(self):
        solo = multiplayer.new_room("ABCDE", "host", "Ana", "en", account="a@x.io")
        _, error = multiplayer.start_room(solo, "host", word="cat")
        self.assertEqual(error, "mp_need_players")

    def test_only_the_host_changes_language_between_rounds(self):
        room = _room()
        _, error = multiplayer.set_language(room, "p2", "de")
        self.assertEqual(error, "mp_host_only")
        _, error = multiplayer.set_language(room, "host", "xx")
        self.assertEqual(error, "mp_bad_language")
        room, error = multiplayer.set_language(room, "host", "de")
        self.assertIsNone(error)
        self.assertEqual(room["language"], "de")
        started, _ = multiplayer.start_room(room, "host", word="cat")
        _, error = multiplayer.set_language(started, "host", "fr")
        self.assertEqual(error, "mp_room_started")

    def test_points_are_split_by_contribution(self):
        room, _ = multiplayer.start_room(_room(), "host", word="cab")
        room, _ = multiplayer.guess(room, "host", "c")
        room, _ = multiplayer.guess(room, "host", "z")
        room, _ = multiplayer.guess(room, "p2", "a")
        room, _ = multiplayer.guess(room, "p2", "b")
        shares = room["result"]["shares"]
        self.assertEqual(room["result"]["points"], 900)
        self.assertEqual(shares, {"host": 300, "p2": 600})
        self.assertEqual([p["score"] for p in room["players"]], [300, 600])

    def test_a_lost_word_charges_whoever_missed(self):
        self.assertEqual(
            multiplayer.round_shares(
                [{"id": "a", "misses": 3}, {"id": "b", "misses": 0}], -60, "lost"
            ),
            {"a": -60, "b": 0},
        )

    def test_host_role_prefers_a_signed_in_player(self):
        room, _ = multiplayer.add_player(_room(), "p3", "Cem", account="c@x.io")
        room, _ = multiplayer.remove_player(room, "host")
        self.assertEqual(room["host"], "p3")


class AfkTests(unittest.TestCase):
    def setUp(self):
        self.room, _ = multiplayer.start_room(_room(), "host", word="cat", now=1000)

    def test_a_turn_cannot_be_skipped_early(self):
        _, error = multiplayer.skip_turn(self.room, "p2", now=1010)
        self.assertEqual(error, "mp_too_early")

    def test_strangers_cannot_skip(self):
        _, error = multiplayer.skip_turn(self.room, "nobody", now=2000)
        self.assertEqual(error, "mp_room_missing")

    def test_timeout_passes_the_turn_then_removes_an_idle_player(self):
        t = 1000 + multiplayer.TURN_SECONDS
        room, error = multiplayer.skip_turn(self.room, "p2", now=t)
        self.assertIsNone(error)
        self.assertEqual(multiplayer.current_player(room), "p2")
        self.assertEqual(room["notice"]["type"], "timeout")
        room, _ = multiplayer.guess(room, "p2", "z", now=t + 1)
        self.assertEqual(multiplayer.current_player(room), "host")
        room, _ = multiplayer.skip_turn(
            room, "p2", now=t + 1 + multiplayer.TURN_SECONDS
        )
        self.assertEqual(room["notice"]["type"], "removed")
        self.assertEqual([p["id"] for p in room["players"]], ["p2"])
        self.assertEqual(room["host"], "p2")

    def test_guessing_clears_strikes(self):
        t = 1000 + multiplayer.TURN_SECONDS
        room, _ = multiplayer.skip_turn(self.room, "p2", now=t)
        room, _ = multiplayer.guess(room, "p2", "z", now=t)
        room, _ = multiplayer.guess(room, "host", "c", now=t)
        self.assertEqual(room["players"][0]["strikes"], 0)


class StaleRoomTests(unittest.TestCase):
    def test_empty_rooms_and_idle_rooms_are_stale(self):
        room = multiplayer.new_room("ABCDE", "host", "Ana", "en", now=1000)
        self.assertFalse(multiplayer.is_stale(room, now=1000))
        self.assertFalse(
            multiplayer.is_stale(room, now=1000 + multiplayer.ROOM_TTL_SECONDS - 1)
        )
        self.assertTrue(
            multiplayer.is_stale(room, now=1000 + multiplayer.ROOM_TTL_SECONDS)
        )
        empty, _ = multiplayer.remove_player(room, "host", now=1000)
        self.assertEqual(empty["players"], [])
        self.assertTrue(multiplayer.is_stale(empty, now=1000))

    def test_activity_refreshes_updated_at(self):
        room = multiplayer.new_room("ABCDE", "host", "Ana", "en", now=1000)
        room, _ = multiplayer.add_player(room, "p2", "Ben", now=1500)
        self.assertEqual(room["updated_at"], 1500)
        room, _ = multiplayer.start_room(room, "host", word="cat", now=2000)
        self.assertEqual(room["updated_at"], 2000)
        room, _ = multiplayer.guess(room, "host", "c", now=2100)
        self.assertEqual(room["updated_at"], 2100)


if __name__ == "__main__":
    unittest.main()

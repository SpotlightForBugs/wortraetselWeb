import unittest

import game


class GuestSaveTests(unittest.TestCase):
    def test_a_solved_word_is_the_only_time_a_guest_is_asked(self):
        self.assertTrue(
            game.should_offer_save(logged_in=False, dismissed=False, solved=True)
        )
        self.assertFalse(
            game.should_offer_save(logged_in=True, dismissed=False, solved=True)
        )
        self.assertFalse(
            game.should_offer_save(logged_in=False, dismissed=True, solved=True)
        )
        self.assertFalse(
            game.should_offer_save(logged_in=False, dismissed=False, solved=False)
        )

    def test_guest_points_wait_until_there_is_an_account(self):
        self.assertEqual(game.stash_guest_points(0, 800), 800)
        self.assertEqual(game.stash_guest_points(800, -40), 760)
        self.assertEqual(game.stash_guest_points(None, 100), 100)

    def test_one_score_follows_the_player(self):
        self.assertEqual(game.displayed_score(0, 900, False), 900)
        self.assertEqual(game.displayed_score(200, 900, True), 1100)
        self.assertEqual(game.displayed_score(200, 0, True), 200)
        self.assertEqual(game.score_after_round(200, 900, None), 1100)
        self.assertEqual(game.score_after_round(200, 900, 200), 1100)
        self.assertEqual(game.score_after_round(200, 900, 1100), 1100)
        self.assertEqual(game.score_after_round(500, -100, 400), 400)
        board = game.place_player([{"username": "Ada", "score": 1200}], "Ada", 1500)
        self.assertEqual(board, [{"username": "Ada", "score": 1500}])
        board = game.place_player([{"username": "Ada", "score": 1200}], "Bea", 900)
        self.assertEqual(board[0]["username"], "Ada")
        self.assertEqual(board[1], {"username": "Bea", "score": 900})
        board = game.place_player([{"username": "Ada", "score": 1200}], "Bea", 2000)
        self.assertEqual(board[0], {"username": "Bea", "score": 2000})


if __name__ == "__main__":
    unittest.main()

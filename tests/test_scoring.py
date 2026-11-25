import unittest

import game


class LetterScoringTests(unittest.TestCase):
    def test_rarer_letters_pay_more_in_english(self):
        self.assertGreater(game.letter_value("en", "q"), game.letter_value("en", "e"))
        self.assertGreater(game.letter_value("en", "z"), game.letter_value("en", "a"))

    def test_language_tables_differ(self):
        # K is common in Turkish relative to English.
        self.assertNotEqual(game.letter_value("en", "k"), game.letter_value("tr", "k"))

    def test_hit_and_miss_use_the_same_table(self):
        self.assertEqual(
            game.score_guess("en", "cat", "c"), game.letter_value("en", "c")
        )
        miss = game.score_guess("en", "cat", "z")
        self.assertLess(miss, 0)
        self.assertEqual(miss, -max(5, game.letter_value("en", "z") // 4))

    def test_round_total_sums_each_guess(self):
        points = game.calculate_points(1, "cat", ["z", "c", "a", "t"], True, "en")
        expected = sum(game.score_guess("en", "cat", ch) for ch in "zcat")
        self.assertEqual(points, expected)


if __name__ == "__main__":
    unittest.main()

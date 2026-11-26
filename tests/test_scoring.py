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

    def test_longer_words_pay_more_per_hit(self):
        short = game.score_guess("en", "cat", "c")
        long = game.score_guess("en", "caterpillar", "c")
        self.assertGreater(long, short)
        self.assertEqual(short, game.letter_value("en", "c"))
        self.assertEqual(
            long, round(game.letter_value("en", "c") * game.word_length_factor("caterpillar"))
        )

    def test_combo_boosts_consecutive_hits(self):
        base = game.score_guess("en", "book", "b", streak=1)
        combo = game.score_guess("en", "book", "b", streak=3)
        self.assertGreater(combo, base)
        parts = game.score_guess_parts("en", "book", "b", streak=3)
        self.assertEqual(parts["points"], parts["base"] + parts["combo"])
        self.assertEqual(parts["streak"], 3)
        self.assertGreater(parts["combo"], 0)

    def test_clear_bonus_rewards_unused_lives(self):
        self.assertEqual(game.clear_bonus(0, True), 135)
        self.assertEqual(game.clear_bonus(3, True), 90)
        self.assertEqual(game.clear_bonus(0, False), 0)

    def test_round_total_replays_combo_and_clear_bonus(self):
        letters = ["z", "c", "a", "t"]
        points = game.calculate_points(1, "cat", letters, True, "en")
        streak = 0
        expected = 0
        for letter in letters:
            hit = letter in "cat"
            streak = streak + 1 if hit else 0
            expected += game.score_guess("en", "cat", letter, streak=streak)
        expected += game.clear_bonus(1, True)
        self.assertEqual(points, expected)
        without_clear = game.calculate_points(1, "cat", letters, True, "en", clear=False)
        self.assertEqual(without_clear, expected - game.clear_bonus(1, True))


if __name__ == "__main__":
    unittest.main()

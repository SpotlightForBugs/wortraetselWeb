import unittest

import game


class GuestSaveTests(unittest.TestCase):
    def test_the_first_hit_is_the_only_time_a_guest_is_asked(self):
        self.assertTrue(
            game.should_offer_save(
                logged_in=False,
                dismissed=False,
                letter_in_word=True,
                hits_before=0,
            )
        )
        self.assertFalse(
            game.should_offer_save(
                logged_in=True,
                dismissed=False,
                letter_in_word=True,
                hits_before=0,
            )
        )
        self.assertFalse(
            game.should_offer_save(
                logged_in=False,
                dismissed=True,
                letter_in_word=True,
                hits_before=0,
            )
        )
        self.assertFalse(
            game.should_offer_save(
                logged_in=False,
                dismissed=False,
                letter_in_word=False,
                hits_before=0,
            )
        )
        self.assertFalse(
            game.should_offer_save(
                logged_in=False,
                dismissed=False,
                letter_in_word=True,
                hits_before=1,
            )
        )

    def test_guest_points_wait_until_there_is_an_account(self):
        self.assertEqual(game.stash_guest_points(0, 800), 800)
        self.assertEqual(game.stash_guest_points(800, -40), 760)
        self.assertEqual(game.stash_guest_points(None, 100), 100)


if __name__ == "__main__":
    unittest.main()

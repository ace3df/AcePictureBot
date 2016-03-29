from utils import get_image_online
import functions
import time
""" Simply Tests.
These will be done while I look at it so I don't have to worry
or go more into testing other than simply this.
"""


import sys
print("Running Python Version:", sys.version)

import unittest
from functions import (login, count_command, get_level)
from time import gmtime, strftime
from tweepy import API

test_count = 0
"""tweet_text = "@Ace3DF Updated {}! Running Tests."\
    .format(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
twitter_api = login(rest=True, status=True)
twitter_api.update_status(status=tweet_text)"""


class TestFunctions(unittest.TestCase):

    user_id = "123"

    def test_level_no_level(self):
        self.assertEqual(get_level("4124"),
                         "\nYou are Level: 1\nCurrent Exp: 0\nNext Level: 25")

    def test_levl_add_cmd(self):
        self.assertTrue(count_command('222', 'waifu', 'count.ini'))

    def test_level(self):
        self.assertEqual(get_level(self.user_id),
                         "\nYou are Level: 1\nCurrent Exp: 10\nNext Level: 15")


if __name__ == '__main__':
    unittest.main()

def run_tests():
    print("Login Test:")
    api = functions.login()
    print(api)
    print("\nTest Tweet")
    msg = "@AceStatusBot Running Tests..."
    api.update_status(status=msg)
    print("\nGet Level Test:")
    print(functions.get_level(123))
    print("\nRandom Waifu Test:")
    print(functions.waifu(0))
    print("\nRandom Husbando Test:")
    print(functions.waifu(1))
    # Name should be flipped
    print("\nWaifuRegister Test:")
    print(functions.waifuregister(123, "Test Username", "rin shibuya", 0))
    # Name should return "not enough images"
    print("\nHusbandoReigster Paste Test:")
    print(functions.waifuregister(123, "Test Username", "admiral", 1))
    # Name should work
    print("\nHusbandoReigster Test:")
    print(functions.waifuregister(123, "Test Username",
                                       "admiral (kantai collection)", 1))
    print("\nMyWaifu Test:")
    print(functions.mywaifu(123, 0))
    print("\nMyHusbando Test:")
    print(functions.mywaifu(123, 1))
    print("\nRemoveWaifu Test:")
    print(functions.waifuremove(123, 0))
    print("\nRemoveHusbando Test:")
    print(functions.waifuremove(123, 1))
    print("\nRandom OTP Test:")
    print(functions.otp(""))
    print("\nRandom List Shipgirl Test:")
    m, i = functions.random_list("Shipgirl", "")
    print(m, i)
    print("\nRandom List Imouto Test:")
    m, ii = functions.random_list("Imouto", "")
    if not i:
        i = ii
    print(m, ii)
    print("\nRandom List Shota Test:")
    print(functions.random_list("Shota", ""))
    print("Sleeping for 10 seconds...")
    time.sleep(10)
    print("\nRandom List Sensei Test:")
    print(functions.random_list("Sensei", ""))
    print("\nRandom List Senpai Test:")
    m, ii = functions.random_list("Senpai", "")
    if not i:
        i = ii
    print(m, ii)
    print("\nRandom List Kouhai Test:")
    print(functions.random_list("Kouhai", ""))
    print("\nRandom List Kouhai Male Test:")
    print(functions.random_list("Kouhai", "male"))
    print("\nAiring Test:")
    print(functions.airing("One Piece"))
    print("\nTest Tweet (with Image)")
    msg = "@AceStatusBot Test Tweet with Image..."
    api.update_with_media(i, status=msg)
    print("\nTest Tweet (with Video)")
    tags = ["rating:safe", "webm", "-extremely_large_filesize",
            "-large_filesize", "-no_audio"]
    i = get_image_online(tags, 0, 1, "")
    msg = "@AceStatusBot Test Tweet with Video..."
    api.update_with_media(i, status=msg)
    print("\nFinished all Tests!")

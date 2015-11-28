import functions
import time

""" Simply Tests.
These will be done while I look at it so I don't have to worry
or go more into testing other than simply this.
"""


def run_tests():
    print("Login Test:")
    print(functions.login())
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
    print(functions.random_list("Shipgirl", ""))
    print("\nRandom List Imouto Test:")
    print(functions.random_list("Imouto", ""))
    print("\nRandom List Shota Test:")
    print(functions.random_list("Shota", ""))
    print("Sleeping for 10 seconds...")
    time.sleep(10)
    print("\nRandom List Sensei Test:")
    print(functions.random_list("Sensei", ""))
    print("\nRandom List Senpai Test:")
    print(functions.random_list("Senpai", ""))
    print("\nRandom List Kouhai Test:")
    print(functions.random_list("Kouhai", ""))
    print("\nRandom List Kouhai Male Test:")
    print(functions.random_list("Kouhai", "male"))
    print("\nAiring Test:")
    print(functions.airing("One Piece"))
    print("\nFinished all Tests!")


if __name__ == '__main__':
    run_tests()

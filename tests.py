import unittest
import warnings
import random
import os

import commands
import functions

warn_id = str(random.randint(1, 10000000))
REGISTER_IDS_DEL = []

attrs = {'name': 'twitter', 'raw_character_limit': 140, 'support_embedded': False, 'download_media': True}
bot = functions.BotProcess(functions.Source(**attrs))

class CommandsTest(unittest.TestCase):

    def test_waifu_normal(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "waifu",
                 'message': "",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.waifu.callback.callback(ctx)
        print(r, m)
        self.assertTrue("Your Waifu is" in r)
        self.assertTrue("images" in m)

    def test_waifu_husbando(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "husbando",
                 'message': "",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.waifu.callback(ctx)
        print(r, m)
        self.assertTrue("Your Husbando is" in r)
        self.assertTrue("images" in m)

    def test_waifu_series(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "waifu",
                 'message': "waifu bleach",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.waifu.callback(ctx)
        print(r, m)
        self.assertTrue("Your Waifu is" in r and "Bleach" in r)
        self.assertTrue("images" in m)

    def test_random_list_shipgirl(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "shipgirl",
                 'message': "shipgirl",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Shipgirl is" in r)
        self.assertTrue("images" in m)

    def test_random_list_shipgirl_aoki(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "shipgirl",
                 'message': "shipgirl aoki",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Shipgirl is" in r)
        self.assertTrue("images" in m)

    def test_random_list_idol(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "idol",
                 'message': "idol",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Idol is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_idol_love_live(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "idol",
                 'message': "idol love live",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Idol is" in r and "Love Live" in r)
        self.assertTrue("images" in m)

    def test_random_list_idol_idolmaster(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "idol",
                 'message': "idol idolmaster",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Idol is" in r and "Idolmaster" in r)
        self.assertTrue("images" in m)

    def test_random_list_touhou(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "touhou",
                 'message': "idol",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Touhou is" in r)
        self.assertTrue("images" in m)

    def test_random_list_vocaloid(self):
        attrs = {'bot': bot,
                 'is_patreon': True,
                 'screen_name': "TestUser",
                 'twitter_id': "123",
                 'command': "vocaloid",
                 'message': "idol",
                 'raw_data': {}
                }
        ctx = functions.UserContext(**attrs)
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Vocaloid is" in r)
        self.assertTrue("images" in m)

    def test_random_list_sensei_female(self):
        ctx.command = "sensei"
        ctx.args = "female" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Sensei is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_sensei_male(self):
        ctx.command = "sensei"
        ctx.args = "Male" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Sensei is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_senpai_female(self):
        ctx.command = "senpai"
        ctx.args = "female" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Senpai is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_senpai_male(self):
        ctx.command = "senpai"
        ctx.args = "male" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Senpai is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_kouhai_female(self):
        ctx.command = "kouhai"
        ctx.args = "female" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Kouhai is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_kouhai_male(self):
        ctx.command = "kouhai"
        ctx.args = "male" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Kouhai is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_imouto(self):
        ctx.command = "imouto"
        ctx.args = "" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Imouto is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_shota(self):
        ctx.command = "shota"
        ctx.args = "" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Shota is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_onii(self):
        ctx.command = "onii"
        ctx.args = "" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Onii-chan is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_onee(self):
        ctx.command = "onee"
        ctx.args = "" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Onee-chan is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_monstergirl(self):
        ctx.command = "monstergirl"
        ctx.args = "" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Monstergirl is" in r and "(" in r)
        self.assertTrue("images" in m)

    def test_random_list_tankgirl(self):
        ctx.command = "tankgirl"
        ctx.args = "" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Tankgirl is" in r)
        self.assertTrue("images" in m)

    def test_random_list_witchgirl(self):
        ctx.command = "witchgirl"
        ctx.args = "" 
        r, m = commands.random_list.callback(ctx)
        print(r, m)
        self.assertTrue("Your Witchgirl is" in r)
        self.assertTrue("images" in m)

    def test_otp(self):
        ctx.command = "otp"
        ctx.args = "" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your OTP is" in r and "and" in r and "(" in r)
        self.assertTrue("images" in m)
    
    def test_otp_search(self):
        ctx.command = "otp"
        ctx.args = "bleach" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your OTP is" in r and "and" in r and "(Bleach)" in r)
        self.assertTrue("images" in m)
    
    def test_otp_cross_search(self):
        ctx.command = "otp"
        ctx.args = "bleach(x)naruto" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your OTP is" in r and "and" in r and "Bleach" in r and "Naruto" in r)
        self.assertTrue("images" in m)
    
    def test_otp_yuri(self):
        ctx.command = "otp"
        ctx.args = "yuri" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your Yuri OTP is" in r and "and" in r)
        self.assertTrue("images" in m)
    
    def test_otp_yuri_search(self):
        ctx.command = "otp"
        ctx.args = "yuri bleach" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your Yuri OTP is" in r and "and" in r and "(Bleach)" in r)
        self.assertTrue("images" in m)
    
    def test_otp_yaoi(self):
        ctx.command = "otp"
        ctx.args = "yaoi" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your Yaoi OTP is" in r and "and" in r)
        self.assertTrue("images" in m)
    
    def test_otp_yaoi_search(self):
        ctx.command = "otp"
        ctx.args = "yaoi bleach" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your Yaoi OTP is" in r and "and" in r and "(Bleach)" in r)
        self.assertTrue("images" in m)
    
    def test_otp_harem(self):
        ctx.command = "harem"
        ctx.args = "" 
        r, m = commands.otp.callback(ctx)
        print(r, m)
        self.assertTrue("Your Harem OTP is" in r and "and" in r)
        self.assertTrue("images" in m)
  
    def test_pictag(self):
        ctx.command = "pictag"
        ctx.args = "solo" 
        r, m = commands.pictag.callback(ctx)
        print(r, m)
        self.assertTrue("Result(s) for: solo" == r)
        self.assertTrue("images" in m[0])
    
    def test_pictag_multi(self):
        ctx.command = "pictag"
        ctx.args = "3 solo" 
        r, m = commands.pictag.callback(ctx)
        print(r, m)
        self.assertTrue("Result(s) for: solo" == r)
        self.assertTrue(len(m) == 3)
    
    def test_airing(self):
        ctx.command = "airing"
        ctx.args = "one piece" 
        results = commands.airing.callback(ctx)
        print(results)
        self.assertTrue("Episode" in results)
    
    def test_airing_not_found(self):
        ctx.command = "airing"
        ctx.args = "robits_blaw" 
        results = commands.airing.callback(ctx)
        print(results)
        self.assertTrue("No match found for '{}'".format(ctx.args) == results)

    def test_waifuregister(self):
        # Everything should pass, making m just a normal mywaifu image
        ctx.command = "waifuregister"
        a = str(random.randint(1, 10000000))
        REGISTER_IDS_DEL.append(a)
        ctx.user_id = a
        ctx.user_ids = {'twitter': a}
        ctx.args = "hijiri_byakuren"
        r, m = commands.waifuregister.callback(ctx)
        print(r, m)
        self.assertTrue("images" in m[0])

    def test_waifuregister_flip_name(self):
        # Same as above, everything should work, name should be flipped
        ctx.command = "waifuregister"
        a = str(random.randint(1, 10000000))
        REGISTER_IDS_DEL.append(a)
        ctx.user_id = a
        ctx.user_ids = {'twitter': a}
        ctx.args = "byakuren hijiri"
        results = commands.waifuregister.callback(ctx)
        print(results)
        self.assertTrue("images" in results[1][0])

    def test_waifuregister_with_series(self):
        ctx.command = "waifuregister"
        a = REGISTER_IDS_DEL[0]
        ctx.user_id = a
        ctx.user_ids = {'twitter': a}
        ctx.args = "djeeta (granblue fantasy)"
        results = commands.waifuregister.callback(ctx)
        print(results)
        self.assertTrue("images" in results[1][0])

    def test_waifuregister_second_website(self):
        # Make sure it can handle the main website being offline
        # (switching to safebooru)
        os.environ['safebooru_online'] = 'True'
        os.environ['gelbooru_online'] = 'False'
        ctx.command = "waifuregister"
        a = str(random.randint(1, 10000000))
        ctx.user_id = a
        ctx.user_ids = {'twitter': a}
        REGISTER_IDS_DEL.append(a)
        ctx.args = "djeeta (granblue fantasy)"
        results = (commands.waifuregister.callback(ctx))
        os.environ['gelbooru_online'] = 'True'
        print(results)
        self.assertTrue("images" in results[1][0])

    def test_waifuregister_auto_replace(self):
        # Use name Asuna should auto switch to Asuna_(SAO)
        ctx.command = "waifuregister"
        a = REGISTER_IDS_DEL[0]
        ctx.user_id = a
        ctx.user_ids = {'twitter': a}
        ctx.args = "asuna"
        results = (commands.waifuregister.callback(ctx))
        print(results)
        self.assertTrue("images" in results[1][0])

    def test_waifuregister_banned_name(self):
        # Should return False (ignored)
        ctx.command = "waifuregister"
        ctx.user_id = warn_id
        ctx.user_ids = {'twitter': warn_id}
        ctx.args = "meme"
        results = (commands.waifuregister.callback(ctx))
        print(results)
        self.assertFalse(results)

    def test_warn_user(self):
        # Make sure 'warn_id' in in the warn file
        path = os.path.join('configs', 'Warned {} Users.txt'.format(ctx.bot.source.name))
        with open(path, 'r') as f:
            warned_users = f.read()
        self.assertTrue(str(warn_id) in warned_users)

    def test_mywaifudata(self):
        ctx.command = "mywaifudata"
        a = REGISTER_IDS_DEL[0]
        ctx.user_id = a
        ctx.user_ids = {'twitter': a}
        ctx.args = ""
        results = (commands.mywaifudata.callback(ctx))
        print(results)
        self.assertTrue("You first registered" in results)

if __name__ == '__main__':
    unittest.main()
 
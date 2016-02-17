# -*- coding: utf-8 -*-
from waifu_register import WaifuRegisterClass
from config import credentials, status_credentials
from spam_checker import remove_one_limit
from slugify import slugify
from config import settings
from string import capwords
from math import exp, log
from PIL import Image
import configparser
import datetime
import random
import urllib
import tweepy
import utils
import json
import os
import re


def login(rest=True, status=False):
    if status:
        consumer_token = status_credentials['consumer_key']
        consumer_secret = status_credentials['consumer_secret']
        access_token = status_credentials['access_token']
        access_token_secret = status_credentials['access_token_secret']
    else:
        consumer_token = credentials['consumer_key']
        consumer_secret = credentials['consumer_secret']
        access_token = credentials['access_token']
        access_token_secret = credentials['access_token_secret']
    auth = tweepy.OAuthHandler(consumer_token, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    if rest:
        api = tweepy.API(auth)
        return api
    else:
        return auth


def block_user(user_id, reason=""):
    path = os.path.join(settings['list_loc'], 'Blocked Users.txt')
    filename = open(path, 'r')
    blocked_users = filename.read().splitlines()
    filename.close()
    line = "{0}:{1}".format(user_id, reason)
    blocked_users.append(line)
    filename = open(path, 'w')
    for item in blocked_users:
        filename.write("%s\n" % item)
    filename.close()


def warn_user(user_id, reason=""):
    path = os.path.join(settings['list_loc'], 'Warned Users.txt')
    filename = open(path, 'r')
    warned_users = filename.read().splitlines()
    filename.close()
    count = 1
    blocked = False
    for warning in warned_users[1:]:
        line = warning.split(":")
        if str(line[0]) == str(user_id):
            warned_users.pop(count)
            block_user(user_id, reason=reason)
            blocked = True
            break
        count += 1
    if not blocked:
        line = "{0}:{1}".format(user_id, reason)
        warned_users.append(line)
    filename = open(path, 'w')
    for item in warned_users:
        filename.write("%s\n" % item)
    filename.close()


def config_get(section, key, file=0):
    if file == 0:
        file = settings['settings']
    elif file == 1:
        file = settings['count_file']
    with open(file) as fp:
        config = configparser.RawConfigParser(allow_no_value=True)
        config.read_file(fp)
        try:
            return config.get(section, key)
        except configparser.NoSectionError:
            return False
        except configparser.NoOptionError:
            return False


def config_save(section, key, result, file=0):
    if file == 0:
        file = settings['settings']
    elif file == 1:
        file = settings['count_file']
    with open(file) as fp:
        config = configparser.RawConfigParser(allow_no_value=True)
        config.read_file(fp)
        try:
            config.set(section, key, str(result))
        except configparser.NoSectionError:
            return False
        except configparser.NoOptionError:
            return False
    with open(file, 'w') as fp:
        config.write(fp)


def config_get_section_items(section, file=0):
    if file == 0:
        file = settings['settings']
    elif file == 1:
        file = settings['count_file']
    with open(file) as fp:
        config = configparser.RawConfigParser(allow_no_value=True)
        config.read_file(fp)
        try:
            return dict(config.items(section))
        except configparser.NoSectionError:
            return False
        except configparser.NoOptionError:
            return False


def config_add_section(section, file=0):
    if file == 0:
        file = settings['settings']
    elif file == 1:
        file = settings['count_file']
    with open(file) as fp:
        config = configparser.RawConfigParser(allow_no_value=True)
        config.read_file(fp)
        config.add_section(section)
    with open(file, 'w') as fp:
        config.write(fp)


def count_trigger(command, user_id="failed"):
    if not command.strip():
        return
    if "dellimits" in command.lower():
        return
    user_id = str(user_id).title()
    if user_id == "failed":
        loc = "failed"
    else:
        loc = "global"
    try:
        glob_cur_cont = int(config_get(loc, command, 1)) + 1
    except:
        glob_cur_cont = 1
    user_cur_count = int(config_get(user_id, command, 1)) + 1
    if user_cur_count == 1 and user_id != "failed":
        try:
            config_add_section(user_id, 1)
        except:
            # Already exists
            pass

    config_save(loc, command, glob_cur_cont, 1)
    if user_id != "failed":
        config_save(user_id, command, user_cur_count, 1)


def get_level(user_id):
    cmd_exp = {'default': 1,
               'my{GENDER}': 2,
               '{GENDER}': 2,
               'shipgirl': 2,
               'otp': 6,
               'vocaloid': 2,
               'imouto': 3,
               'senpai': 5,
               '{GENDER}register': 10,
               'monstergirl': 3}
    sec = config_get_section_items(str(user_id), 1)
    if not sec:
        return "\nYou are Level: 1 \nCurrent Exp: 0 \nNext Level: 25"
    user_exp = 0
    total = 0
    for cmd, count in sec.items():
        cmd = cmd.replace("waifu", "{GENDER}")
        cmd = cmd.replace("husbando", "{GENDER}")
        for i in range(0, int(count)):
            total += 1
            try:
                user_exp += cmd_exp[cmd]
            except:
                user_exp += cmd_exp['default']
    levels = 100
    xp_for_first_level = 25
    xp_for_last_level = 1000000
    B = log(1.0 * xp_for_last_level / xp_for_first_level) / (levels - 1)
    A = 1.0 * xp_for_first_level / (exp(B) - 1.0)

    def xp_for_level(i):
        x = int(A * exp(B * i))
        y = 10**int(log(x) / log(10) - 2.2)
        return int(x / y) * y

    if user_exp < xp_for_first_level:
        level = 1
        for_next = 25
    elif user_exp >= xp_for_last_level:
        level = levels
        for_next = "MAXED"
    else:
        for i in range(1, levels+1):
            level_range = xp_for_level(i) - xp_for_level(i-1)
            if user_exp < level_range:
                level = i
                for_next = level_range - user_exp
                break
    if level == 1:
        for_next = for_next - user_exp
    return ("\nYou are Level: {0}\n"
            "Current Exp: {1}\n"
            "Next Level: {2}").format(level, user_exp, for_next)


def waifu(gender, args="", otp=False, DISCORD=False):
    if gender == 0:
        list_name = "Waifu"
        end_tag = "1girl+solo"
    else:
        list_name = "Husbando"
        end_tag = "-1girl+-female"
    result = ""
    lines = utils.file_to_list(
        os.path.join(settings['list_loc'],
                     list_name + " List.txt"))
    args = ' '.join(args.split()).lower()
    matched = []
    ignore = ["high-school-dxd", "love-live",
              "aoki-hagane-no-arpeggio", "kantai-collection",
              "aikatsu", "akb0048", "idolmaster",
              "idolmaster-cinderella-girls"]
    if len(args) > 4:
        for entry in lines:
            if slugify(entry[1], word_boundary=True) in ignore:
                continue
            if slugify(args, word_boundary=True) ==\
               slugify(entry[1], word_boundary=True):
                matched.append(entry)
        # It's not really that random if there isn't that many people matched.
        if len(matched) > 5:
            result = random.choice(matched)
    if not result:
        result = random.choice(lines)

    name, show, otp_img = result
    if otp:
        return name, show, otp_img
    path_name = slugify(name,
                        word_boundary=True, separator="_")
    path = os.path.join(list_name, path_name)
    tweet_image = utils.get_image(path)
    if not tweet_image and not DISCORD:
        tags = [name.replace(" ", "_"), "solo", "-genderswap", end_tag]
        tweet_image = utils.get_image_online(tags, 0, 1,
                                             "", path)
    name = re.sub(r' \([^)]*\)', '', name)
    m = "Your {0} is {1} ({2})".format(list_name.title(),
                                       name, show)
    count_trigger(name, list_name.lower())
    return m, tweet_image
print(waifu(0))

def mywaifu(user_id, gender):
    if gender == 0:
        gender = "Waifu"
        filename = "users_waifus.json"
    else:
        gender = "Husbando"
        filename = "users_husbandos.json"
    user_waifus_file = open(
        os.path.join(settings['list_loc'], filename), 'r',
        encoding='utf-8')
    user_waifus = json.load(user_waifus_file)
    user_waifus_file.close()
    for user in user_waifus['users']:
        if int(user['twitter_id']) == user_id:
            break
    if int(user['twitter_id']) != user_id:
        count_trigger("mywaifu")
        m = ("I don't know who your {0} is!\n"
             "Use {1}Register!\n"
             "Help: {2}").format(gender, gender,
                                 config_get('Help URLs', 'include_name'))
        return m, False
    tags = user['name'] + user['tags']
    if user.get('max_page'):
        max_page = user['max_page']
    else:
        max_page = 20
    path_name = slugify(user['name'],
                        word_boundary=True, separator="_")
    path = os.path.join(settings['image_loc'],
                        gender.lower(), path_name)
    ignore_list = "user_ignore/{0}".format(user['twitter_id'])
    tweet_image = utils.get_image_online(tags, user['web_index'],
                                         max_page, ignore_list)
    if not tweet_image:
        tweet_image = utils.get_image(path, ignore_list)
    if not tweet_image:
        m = ("Failed to get an image (website could be offline).\n"
             "Help: {0}").format(config_get('Help URLs', 'website_offline'))
        remove_one_limit(user_id, "my" + gender.lower())
        return m, False
    if datetime.datetime.now().isoweekday() == 3:
        m = "#{0}Wednesday".format(gender)
    else:
        m = "#{0}AnyDay".format(gender)
    return m, tweet_image


def waifuregister(user_id, username, name, gender):
    config = configparser.RawConfigParser(allow_no_value=True)
    config.read(settings['settings'])
    help_urls = (dict(config.items('Help URLs')))
    if config_get('Websites', 'sankakucomplex') == "False":
        m = "Some websites are offline. Try again later!"
        if gender == 0:
            gender = "Waifu"
        elif gender == 1:
            gender = "Husbando"
        remove_one_limit(user_id, gender.lower() + "register", username)
        return m, False
    if name == "":
        m = "You forgot to include a name! Help: {0}".format(
            config_get('Help URLs', 'include_name'))
        return m, False
    elif len(name) >= 41:
        return False, False
    elif len(name) == 1:
        return False, False
    name = name.replace("+", "")
    name = name.replace("( ", "(").replace(" )", ")")

    register_object = WaifuRegisterClass(
        user_id, username, name, gender)
    if register_object.TEMP_bug:
        remove_one_limit(user_id, gender.lower() + "register")
        return "Some websites are offline. Try again later!"
    if register_object.offline:
        remove_one_limit(user_id, gender.lower() + "register")
        return "Some websites are offline. Try again later!"
    if register_object.disable:
        warn_user(user_id, "Banned Register - {0}".format(name))
        return False, False
    else:
        # Everything is fine so far
        register_object.start()
        if register_object.multinames:
            return register_object.multinames, False
        elif register_object.noimages:
            return "No images found for \"{0}\"! Help: {1}".format(
                capwords(register_object.org_name),
                help_urls['no_imgs_found']), False
        elif register_object.notenough:
            return "Not enough images found for \"{0}\"! Help: {1}".format(
                capwords(register_object.org_name),
                help_urls['not_enough_imgs']), False
    m, tweet_image = mywaifu(user_id, gender)
    return m, tweet_image


def waifuremove(user_id, gender):
    if gender == 0:
        gender = "Waifu"
        filename = "users_waifus.json"
    elif gender == 1:
        gender = "Husbando"
        filename = "users_husbandos.json"
    user_waifus_file = open(
        os.path.join(settings['list_loc'], filename), 'r',
        encoding='utf-8')
    user_waifus = json.load(user_waifus_file)
    user_waifus_file.close()
    removed = False
    count = 0
    for user in user_waifus['users']:
        if int(user['twitter_id']) == user_id:
            user_waifus['users'].pop(count)
            removed = True
            break
        count += 1
    if removed:
        user_waifus_file = open(
            os.path.join(settings['list_loc'], filename), 'w',
            encoding='utf-8')
        json.dump(user_waifus, user_waifus_file, indent=2, sort_keys=True)
        user_waifus_file.close()
        m = "Successfully removed!"
    else:
        m = "No {0} found!".format(gender.lower())
    return m


def otp_image(img_1, img_2):
    overlays_loc = os.path.join(settings['image_loc'], "otp_overlays")
    save_loc = os.path.join(
        settings['image_loc'], "otps", str(random.randint(5, 999999)) + ".jpg")
    try:
        urllib.request.urlretrieve(img_1, "1.jpg")
        urllib.request.urlretrieve(img_2, "2.jpg")
    except urllib.request.URLError:
        # Timeout
        return False
    otp_one = Image.open("1.jpg")
    otp_two = Image.open("2.jpg")
    overlay = random.randint(0, len(os.listdir(overlays_loc)) - 1)
    heart = os.path.join(overlays_loc, str(overlay) + ".png")
    heart = Image.open(heart)
    img_size = (450, 350)
    blank_image = Image.new("RGB", img_size)
    blank_image.paste(otp_one, (0, 0))
    blank_image.paste(otp_two, (225, 0))
    blank_image.paste(heart, (0, 0), mask=heart)
    blank_image.save(save_loc)
    os.remove("1.jpg")
    os.remove("2.jpg")
    return save_loc


def otp(args):
    args = args.lower()
    if "yuri" in args:
        args = args.replace("yuri", "")
        otp_msg = "Yuri "
        gender_one = 0
        gender_two = 0
    elif "yaoi" in args:
        args = args.replace("yuri", "")
        otp_msg = "Yaoi "
        gender_one = 1
        gender_two = 1
    else:
        otp_msg = ""
        gender_one = 0
        gender_two = 1

    safe_loop = 0
    if "(x)" in args:
        args = args.split("(x)")
        search_one = args[0].strip()
        search_two = args[1].strip()
        one_name, one_series, one_image = waifu(gender_one,
                                                search_one, True)
        two_name = one_name
        while one_name == two_name:
            safe_loop += 1
            if safe_loop == 10:
                break
            two_name, two_series, two_image = waifu(gender_two,
                                                    search_two, True)
    else:
        one_name, one_series, one_image = waifu(gender_one,
                                                args, True)
        two_name = one_name
        while one_name == two_name:
            safe_loop += 1
            if safe_loop == 10:
                break
            two_name, two_series, two_image = waifu(gender_two,
                                                    args, True)
    tweet_image = otp_image(one_image, two_image)

    if one_series == two_series:
        otp_anime = "({0})".format(one_series)
    else:
        otp_anime = "({0} / {1})".format(one_series, two_series)
    one_name = re.sub(r' \([^)]*\)', '', one_name)
    two_name = re.sub(r' \([^)]*\)', '', two_name)
    m = "Your {0}OTP is {1} and {2} {3}".format(otp_msg, one_name,
                                                two_name, otp_anime)

    return m, tweet_image


def random_list(list_name, args="", DISCORD=False):
    gender = "waifu"
    hashtag = ""
    search_for = ""
    m = False
    lines = False
    show_series = False
    scrape_images = True
    if list_name == "Shipgirl":
        if "aoki" in args:
            lines = utils.file_to_list('Shipgirl Aoki.txt')
        elif "all" in args:
            if "otp" in args:
                list_name += " OTP"
                lines = utils.file_to_list('Shipgirl All OTP.txt')
            else:
                lines = utils.file_to_list('Shipgirl Aoki.txt')
                lines += utils.file_to_list('Shipgirl.txt')
        else:
            hashtag = "#Kancolle"
            if "otp" in args:
                list_name += " OTP"
                lines = utils.file_to_list('Shipgirl OTP.txt')
            else:
                lines = utils.file_to_list('Shipgirl.txt')
    elif list_name == "Touhou":
        hashtag = "#Touhou"
        if "otp" in args:
            list_name += " OTP"
            lines = utils.file_to_list('Touhou OTP.txt')
        else:
            lines = utils.file_to_list('Touhou.txt')
    elif list_name == "Vocaloid":
        hashtag = "#Vocaloids"
        if "otp" in args:
            list_name += " OTP"
            lines = utils.file_to_list('Vocaloid OTP.txt')
        else:
            lines = utils.file_to_list('Vocaloid.txt')
    elif list_name == "Imouto":
        list_name = "Imouto"
        show_series = True
        lines = utils.file_to_list('Imouto.txt')
    elif list_name == "Idol":
        show_series = True
        if "love live" in args or "lovelive" in args:
            search_for = "Love Live!"
            hashtag = "#LoveLive"
            if "otp" in args:
                list_name = "Love Live! OTP"
                show_series = False
                lines = utils.file_to_list('Idol Love Live OTP.txt')
        elif "cinderella" in args or "cinderella" in args:
            search_for = "Idolmaster Cinderella Girls"
            hashtag = "#Idolmaster"
        elif "idolmaster" in args or "idolm@ster" in args:
            search_for = "Idolmaster"
            hashtag = "#Idolmaster"
        elif "akb0048" in args:
            search_for = "AKB0048"
            hashtag = "#akb0048"
        elif "wake" in args:
            search_for = "Wake Up Girls!"
            hashtag = "#WUG_JP"
        elif "aikatsu" in args:
            search_for = "Aikatsu!"
            hashtag = "#Aikatsu"
        if "male" in args:
            list_name = "Male Idol"
            lines = utils.file_to_list('Idol Males.txt')
        else:
            if not lines:
                lines = utils.file_to_list('Idol.txt')
                if search_for:
                    temp_lines = []
                    for line in lines:
                        if line[1] == search_for:
                            temp_lines.append(line)
                    lines = temp_lines
                    del temp_lines
    elif list_name == "Shota":
        show_series = True
        gender = "husbando"
        lines = utils.file_to_list('Shota.txt')
    elif list_name == "Onii":
        list_name = "Onii-chan"
        show_series = True
        gender = "husbando"
        lines = utils.file_to_list('Onii-chan.txt')
    elif list_name == "Onee":
        list_name = "Onee-chan"
        show_series = True
        lines = utils.file_to_list('Onee-chan.txt')
    elif list_name == "Sensei":
        show_series = True
        if "female" in args:
            lines = utils.file_to_list('Sensei Female.txt')
        elif "male" in args:
            gender = "husbando"
            lines = utils.file_to_list('Sensei Male.txt')
        else:
            lines = utils.file_to_list('Sensei Male.txt')
            lines += utils.file_to_list('Sensei Female.txt')
    elif list_name == "Senpai":
        show_series = True
        if "female" in args:
            lines = utils.file_to_list('Senpai Female.txt')
        elif "male" in args:
            gender = "husbando"
            lines = utils.file_to_list('Senpai Male.txt')
        else:
            lines = utils.file_to_list('Senpai Male.txt')
            lines += utils.file_to_list('Senpai Female.txt')
    elif list_name == "Kouhai":
        show_series = True
        if "female" in args:
            lines = utils.file_to_list('Kouhai Female.txt')
        elif "male" in args:
            gender = "husbando"
            lines = utils.file_to_list('Kouhai Male.txt')
        else:
            lines = utils.file_to_list('Kouhai Male.txt')
            lines += utils.file_to_list('Kouhai Female.txt')
    elif list_name == "Monstergirl":
        show_series = True
        scrape_images = True
        lines = utils.file_to_list('Monstergirl.txt')
    elif list_name == "Witchgirl":
        hashtag = "#s_witch"
        show_series = False
        scrape_images = True
        lines = utils.file_to_list('Witchgirl.txt')
    elif list_name == "Tankgirl":
        hashtag = "#garupan"
        show_series = False
        scrape_images = True
        lines = utils.file_to_list('Tankgirl.txt')

    # Under heavy stuff random.choice can be very weak
    # so just a quick way to make sure it's 'random random'
    random.shuffle(lines)
    entry = random.choice(lines)
    if list_name.endswith("OTP"):
        names = entry.split("(x)")
        if list_name == "Touhou":
            tags = "{0}+{1}+2girls+yuri+touhou+-asai_genji+-comic".format(
                names[0].replace(" ", "_"),
                names[1].replace(" ", "_"))
        if "love live" in list_name.lower():
            tags = "{0}+{1}+2girls+yuri+-comic".format(
                names[0].replace(" ", "_"),
                names[1].replace(" ", "_"))
        else:
            tags = "{0}+{1}+yuri+2girls+-comic".format(
                names[0].replace(" ", "_"),
                names[1].replace(" ", "_"))
        name = "{0}(x){1}".format(names[0], names[1])
    else:
        if isinstance(entry, list):
            name = entry[0]
            show = entry[1]
        else:
            name = entry
        if scrape_images:
            tags = "{0}+solo".format(name.replace(" ", "_"))
    path_name = slugify(name,
                        word_boundary=True, separator="_")
    path = "{0}/{1}".format(gender.lower(), path_name)
    tweet_image = utils.get_image(path)
    if scrape_images and not tweet_image and not DISCORD:
        tweet_image = utils.get_image_online(tags, 0, 1, "", path)

    name = re.sub(r' \([^)]*\)', '', name)
    if show_series:
        m = "Your {0} is {1} ({2}) {3}".format(list_name, name,
                                               show, hashtag)
    elif list_name.endswith("OTP"):
        name_one = re.sub(r' \([^)]*\)', '', names[0])
        name_two = re.sub(r' \([^)]*\)', '', names[1])
        name = "{0} x {1}".format(name_one, name_two)
    if not m:
        m = "Your {0} is {1} {2}".format(list_name, name, hashtag)
        if not list_name.endswith("OTP"):
            count_trigger(name, gender)
    return m, tweet_image


def airing(args):
    if len(args) <= 3:
        return False
    args = args.replace("Durarara!!x2", "Durarara!!×2")
    air_list_titles = []
    air_list_msg = []
    url = "https://www.livechart.me/summer-2015/all"
    soup = utils.scrape_site(url)
    if not soup:
        return False
    show_list = soup.find_all('h3', class_="main-title")
    today = datetime.datetime.today()
    today = today + datetime.timedelta(hours=8)
    for div in show_list:
        anime_title = div.text
        if len(anime_title) > 60:
            anime_title = anime_title[:50] + "[...]"
        air_list_titles.append(anime_title)
        ep_num_time = div.findNext('div').text
        if "ished" in ep_num_time or \
           "ished" in ep_num_time and "eatrical" in ep_num_time:
            ep_num = "Finished"
        elif "eatrical" in ep_num_time:
            ep_num = "Movie"
        else:
            try:
                if "EP" in ep_num_time:
                    ep_num = "Episode " + ep_num_time.split(":", 1)[0][2:]
                else:
                    if "Movie" in anime_title:
                        ep_num = "Movie"
                    else:
                        ep_num = "Movie/OVA/Special"
            except:
                ep_num = "New Series"

        if "Episode" in ep_num or "Movie" in ep_num:
            try:
                ep_num_time = ep_num_time.split(": ", 1)[1]
            except:
                pass
            try:
                ep_num_time = ep_num_time.split(
                    " JST", 1)[0].replace(" at", "")
                anime_time = datetime.datetime.strptime(re.sub(
                    " +", " ", ep_num_time), '%b %d %I:%M%p')
                anime_time = anime_time.replace(
                    year=datetime.datetime.today().year)
                result = anime_time - today
                msg = ("{0}\n"
                       "{1} airing in\n"
                       "{2} Days, {3} Hours and {4} Minutes").format(
                    anime_title, ep_num, result.days,
                    result.seconds//3600, (result.seconds//60) % 60)
            except:
                msg = "{0}\nNew Series\nUnknown air date!".format(anime_title)
        else:
            msg = "{0} has finished airing!".format(anime_title)
        air_list_msg.append(msg)

    try:
        found = [s for s in air_list_titles if re.sub(
            '[^A-Za-z0-9]+', '', args.lower()) in re.sub(
            '[^A-Za-z0-9]+', '', s.lower())]
        found = ''.join(found[0])
        index = air_list_titles.index(''.join(found))
        air = air_list_msg[index]
        air = ''.join(air)
    except:
        count_trigger("airing")
        return False
    return air


def source(api, status):
    lines = []
    tag_re = re.compile(r'<[^>]+>')

    def info(image):
        url = "http://iqdb.org/?url=%s" % (str(image))
        soup = utils.scrape_site(url)
        if not soup:
            return False, False, False
        if soup.find('th', text="No relevant matches"):
            return False, False, False
        site = None
        links = soup.find_all('a')
        for link in links:
            try:
                link['href']
            except:
                continue
            if link.string == "(hide)":
                # Haven't broke yet, onto low results
                return False, False, False
            if "chan.sankakucomplex.com/post/show/" in link['href']:
                if "http" not in link['href']:
                    url = "http:" + link['href']
                else:
                    url = link['href']
                site = 0
                break
            elif "http://danbooru.donmai.us/posts/" in link['href']:
                url = link['href']
                site = 1
                break
        if site is None:
            # No link found!
            return False, False, False
        soup = utils.scrape_site(url)
        if not soup:
            return False, False, False
        try:
            if site == 0:
                # Sankaku
                artist = soup.find(
                    'li', class_="tag-type-artist").find_next('a').text.title()

            elif site == 1:
                # Danbooru
                artist = soup.find(
                    'h2', text="Artist").find_next(
                    'a', class_="search-tag").text.title()
        except:
            artist = ""
        try:
            if site == 0:
                # Sankaku
                series = soup.find(
                    'li', class_="tag-type-copyright").find_next(
                    'a').text.title()
            elif site == 1:
                # Danbooru
                series = soup.find(
                    'h2', text="Copyrights").find_next(
                    'a', class_="search-tag").text.title()
        except:
            series = ""
        try:
            if site == 0:
                # Sankaku
                names = soup.find_all('li', class_="tag-type-character")
            elif site == 1:
                # Danbooru
                names = soup.find_all('li', class_="category-4")
            name = []
            for a in names:
                if site == 0:
                    a = a.find_next('a').text.title()
                elif site == 1:
                    a = a.find_next('a').find_next('a').text.title()
                name.append(re.sub(r' \([^)]*\)', '', a))
            name = list(set(name))
            if len(name) >= 2:
                names = utils.make_paste(
                    text='\n'.join(name),
                    title="Source Names")
            else:
                names = ''.join(name)
        except:
            names = ""

        return artist, series, names

    def tweeted_image(api, status):
        """Return the image url from the tweet."""
        try:
            tweet = api.get_status(status.in_reply_to_status_id)
            tweet = tweet.entities['media'][0]['media_url_https']
            if "tweet_video_thumb" in str(tweet):
                is_gif = True
            else:
                is_gif = False
            if ".mp4" in tweet:
                return "Sorry, source is a video and not an image!", False
            return tweet, is_gif
        except:
            return "Are you sure you're asking for source on an image?", False

    tweeted_image, is_gif = tweeted_image(api, status)
    if ("Are you sure" in tweeted_image) or ("source is a" in tweeted_image):
        count_trigger("source")
        return tweeted_image

    artist, series, names = info(tweeted_image)
    saucenao = u"http://saucenao.com/search.php?urlify=1&url={0}".format(
        str(tweeted_image))
    if not artist and not series and not names:
        return "No relevant source information found!\n" + saucenao
    else:
        if artist:
            artist = "By: {0}\n".format(artist)
        if names:
            names = "Character(s): {0}\n".format(names)
        if series:
            series = "From: {0}\n".format(utils.short_string(series, 25))
    handles = status.text.lower()
    handles = [word for word in handles.split() if word.startswith('@')]
    handles = list(set(handles))
    handles = ' '.join(handles).replace(
              "@" + settings["twitter_track"][0].lower(), "")
    m = "{0}{1}{2}".format(artist, names, series)
    if is_gif:
        m += "*Source is a gif so this could be inaccurate.\n"
    if (len(m) + 24) >= 120:
        m = utils.make_paste(m)
        m = "Source information is too long to Tweet:\n" + m + "\n"
    m = "{0}\n{1}{2}".format(handles, m, saucenao)
    return m.replace("&Amp;", "&")


def spookjoke():
    name = random.choice(utils.file_to_list('Sp00k.txt'))
    path_name = slugify(name,
                        word_boundary=True, separator="_")
    path = "{0}/{1}".format("spook", path_name)
    tweet_image = utils.get_image(path)
    name = re.sub(r' \([^)]*\)', '', name)
    m = "Oh oh! Looks like your command was stolen by {0}!! #Sp00ky".format(
        name)
    return m, tweet_image

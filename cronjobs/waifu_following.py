from config import credentials, settings
import tweepy
import json
import time
import sys
import os


def login():
    consumer_token = credentials['consumer_key']
    consumer_secret = credentials['consumer_secret']
    access_token = credentials['access_token']
    access_token_secret = credentials['access_token_secret']
    auth = tweepy.OAuthHandler(consumer_token, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    return tweepy.API(auth)


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


def printf(*objects, sep=' ', end='\n', file=sys.stdout):
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        print(*map(
            lambda obj: str(obj).encode(
                enc, errors='backslashreplace').decode(
                enc), objects), sep=sep, end=end, file=file)


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


def is_following(user_id):
    try:
        user_info = API.get_user(user_id)
    except tweepy.TweepError:
        return "Limited"
    if user_info.statuses_count < 10:
        return "Not Genuine"
    elif user_info.followers_count < 6:
        return "Not Genuine"
    try:
        ship = API.lookup_friendships(user_ids=(2910211797, user_id))
    except tweepy.TweepError:
        return "Limited"
    try:
        return ship[1].is_followed_by
    except TypeError:
        # Account doesn't exist anymore
        return False

def waifu_json(gender):
    global REMOVE_COUNT
    if gender == 0:
        gen_num = 0
        filename = "users_waifus.json"
    else:
        gen_num = 1
        filename = "users_husbandos.json"
    user_waifus_file = open(
        os.path.join(settings['list_loc'], filename), 'r',
        encoding='utf-8')
    user_waifus = json.load(user_waifus_file)
    user_waifus_file.close()
    count = 0
    limit = 0
    for user in user_waifus['users']:
        printf("Count: ".format(str(count)))
        printf("JSON User: ".format(user))
        is_follow = is_following(user['twitter_id'])
        printf("Following?: ".format(is_follow))
        if not is_follow:
            printf(waifuremove(user['twitter_id'], gen_num))
            warn_user(user['twitter_id'], "Not following")
            REMOVE_COUNT += 1
        limit += 1
        if limit == 5:
            limit = 0
            time.sleep(180)
        else:
            time.sleep(30)
        count += 1
        quit()
        printf("---------------------------")

API = login()
REMOVE_COUNT = 0
# Waifu
waifu_json(0)
time.sleep(30)
# Husbando
waifu_json(1)

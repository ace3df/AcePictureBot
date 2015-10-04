import sys
sys.path.append("..")
from config import settings
import functions as func
import json
import time
import os

API = func.login(REST=True)
REMOVE_COUNT = 0


def printf(*objects, sep=' ', end='\n', file=sys.stdout):
    enc = file.encoding
    if enc == 'UTF-8':
        print(*objects, sep=sep, end=end, file=file)
    else:
        print(*map(
            lambda obj: str(obj).encode(
                enc, errors='backslashreplace').decode(
                enc), objects), sep=sep, end=end, file=file)


def is_following(user_id):
    try:
        ship = API.lookup_friendships(user_ids=(2910211797, user_id))
    except:
        print("[WARNING] Hit lookup_friendships API limit!")
        # Hit API limit, sleep 20 minutes to make sure
        time.sleep(20 * 60)
        ship = API.lookup_friendships(user_ids=(2910211797, user_id))
    try:
        return ship[1].is_followed_by
    except:
        # Account doesn't exsist anymore
        return False


def waifu_json(gender):
    global REMOVE_COUNT
    if gender == 0:
        gen_num = 0
        gender = "Waifu"
        filename = "users_waifus.json"
    elif gender == 1:
        gen_num = 1
        gender = "Husbando"
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
            printf(func.waifuremove(user['twitter_id'], gen_num))
            func.warn_user(user['twitter_id'], "Not following")
            REMOVE_COUNT += 1
        limit += 1
        if limit == 5:
            limit = 0
            time.sleep(180)
        else:
            time.sleep(30)
        count += 1
        printf("---------------------------")

# Waifu
waifu_json(0)
time.sleep(30)
# Husbando
waifu_json(1)

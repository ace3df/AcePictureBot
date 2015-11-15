from spam_checker import remove_all_limit
from spam_checker import user_spam_check
import xml.etree.ElementTree as etree
from collections import OrderedDict
from utils import printf as print
from threading import Thread
from itertools import islice
from config import settings
from config import update
import functions as func
import urllib.request
import datetime
import random
import tweepy
import utils
import time
import os
import re

__program__ = "AcePictureBot"
__version__ = "2.3.5"

BLOCKED_IDS = utils.file_to_list(
                os.path.join(settings['list_loc'],
                             "Blocked Users.txt"))
IGNORE_WORDS = utils.file_to_list(
                os.path.join(settings['list_loc'],
                             "Blocked Words.txt"))
LIMITED = False
HAD_ERROR = False
LAST_STATUS_CODE = 0
TWEETS_READ = []
MOD_IDS = [2780494890, 121144139]
RATE_LIMIT_DICT = {}
USER_LAST_COMMAND = OrderedDict()
START_TIME = time.time()
HANG_TIME = time.time()
API = None
STATUS_API = None
SAPI = None
DEBUG = True


def post_tweet(_API, tweet, media="", command=False, rts=False):
    try:
        if media:
            media = media.replace("\\", "\\\\")
        if rts and command:
            print("[{0}] Tweeting: {1} ({2}): [{3}] {4}".format(
                time.strftime("%Y-%m-%d %H:%M"),
                rts.user.screen_name, rts.user.id,
                command, tweet))
        else:
            print("[{0}] Tweeting: {1}".format(
                time.strftime("%Y-%m-%d %H:%M"),
                tweet))
        if rts:
            if media:
                print("(Image: {0})".format(media))
                _API.update_with_media(media, status=tweet,
                                       in_reply_to_status_id=rts.id)
            else:
                _API.update_status(status=tweet,
                                   in_reply_to_status_id=rts.id)
        else:
            if media:
                print("(Image: {0})".format(media))
                _API.update_with_media(media, status=tweet)
            else:
                _API.update_status(status=tweet)
    except:
        pass


def tweet_command(_API, status, tweet, command):
    tweet_image = False
    user = status.user

    # Mod command
    is_mod = [True if user.id in MOD_IDS else False][0]
    if command == "DelLimits":
        if is_mod:
            their_id, cmd = tweet.split(' ', 2)
            remove_all_limit(their_id, cmd)
            print("[INFO] Removed limits for {0} - {1}".format(
                their_id, cmd))
        return False, False

    if not is_mod:
        user_is_limited = user_spam_check(user.id, user.screen_name, command)
        if isinstance(user_is_limited, str):
            # User hit limit, tweet warning
            command = ""
            tweet = user_is_limited
        elif not user_is_limited:
            # User is limited, return
            print("[{0}] User is limited! Ignoring...".format(
                time.strftime("%Y-%m-%d %H:%M")))
            return False
    if settings['count_on']:
        func.count_trigger(command, user.id)

    # Joke Commands
    if command == "spook":
        tweet, tweet_image = func.spookjoke()
    if command == "Spoiler":
        tweet = random.choice(utils.file_to_list(
                    os.path.join(settings['list_loc'],
                                 "spoilers.txt")))
    elif command == "!Level":
        tweet = func.get_level(user.id)

    # Main Commands
    if command == "Waifu":
        tweet, tweet_image = func.waifu(0, tweet)
    elif command == "Husbando":
        tweet, tweet_image = func.waifu(1, tweet)

    gender = utils.gender(status.text)
    if "Register" in command:
        follow_result = is_following(user.id)
        if follow_result == "Limited":
            tweet = ("The bot is currently limited on checking stuff.\n"
                     "Try again in 15 minutes!")
            if gender == 0:
                gender = "waifu"
            else:
                gender = "husbando"
            func.remove_one_limit(user.id, gender.lower() + "register")
        elif follow_result == "Not Genuine":
            tweet = ("Your account wasn't found to be genuine.\n"
                     "Help: {url}").format(url=func.config_get('Help URLs', 'not_genuine'))
        elif not follow_result:
            tweet = ("You must follow @AcePictureBot to register!\n"
                     "Help: {url}").format(url=func.config_get('Help URLs', 'must_follow'))
        else:
            tweet, tweet_image = func.waifuregister(user.id,
                                                    user.screen_name,
                                                    tweet, gender)

    if "My" in command:
        tweet, tweet_image = func.mywaifu(user.id, gender)

    if "Remove" in command:
        tweet = func.waifuremove(user.id, gender)

    if command == "OTP":
        tweet, tweet_image = func.otp(tweet)

    # TODO: Remove this over sometime and change kohai to kouhai on the site
    if command == "Kohai":
        command = "Kouhai"
    list_cmds = ["Shipgirl", "Touhou", "Vocaloid",
                 "Imouto", "Idol", "Shota",
                 "Onii", "Onee", "Sensei",
                 "Monstergirl", "Witchgirl", "Tankgirl",
                 "Senpai", "Kouhai"]
    if command in list_cmds:
        tweet, tweet_image = func.random_list(command, tweet)

    if command == "Airing":
        tweet = func.airing(tweet)
        # No results found.
        if not tweet:
            return False

    if command == "Source":
        tweet = func.source(_API, status)

    if tweet:
        tweet = "@{0} {1}".format(user.screen_name, tweet)
        post_tweet(_API, tweet, tweet_image, command, status)


def acceptable_tweet(status):
    global USER_LAST_COMMAND
    global IGNORE_WORDS
    global BLOCKED_IDS

    tweet = status.text
    user = status.user

    # Ignore ReTweets.
    if tweet.startswith('RT'):
        return False, False

    if DEBUG:
        if user.id not in MOD_IDS:
            return False, False

    # Reload in case of manual updates.
    BLOCKED_IDS = utils.file_to_list(
                    os.path.join(settings['list_loc'],
                                 "Blocked Users.txt"))
    IGNORE_WORDS = utils.file_to_list(
                    os.path.join(settings['list_loc'],
                                 "Blocked Words.txt"))

    # Ignore bots and bad boys.
    if str(user.id) in BLOCKED_IDS:
        return False, False

    # Ignore some messages.
    if any(word.lower() in tweet.lower()
           for word in IGNORE_WORDS):
        return False, False

    # Make sure the message has @Bot in it.
    if not any("@" + a.lower() in tweet.lower()
               for a in settings['twitter_track']):
        return False, False

    # If the user @sauce_plz add "source" to the text as every @ is later removed.
    if "sauce" in tweet.lower():
        tweet += " source"

    # Remove extra spaces.
    tweet = re.sub(' +', ' ', tweet).lstrip()

    # Remove @UserNames (usernames could trigger commands alone)
    tweet = ' '.join(re.sub('(^|\n| )(@[A-Za-z0-9_]+)', ' ', tweet).split())
    tweet = tweet.replace("#", "")

    # Find the command they used.
    command = utils.get_command(tweet)
    if command == "WaifuRegister" or command == "HusbandoRegister":
        # Cut the text off after the command word.
        reg = "({0})(?i)".format(command)
        if len(tweet) > (len(command) +
                         len(settings['twitter_track'][0]) + 2):
            tweet = re.split(reg, tweet)[2].lstrip()

    # No command is found see if acceptable for a random waifu.
    if not command:
        # Ignore quote ReTweets.
        if tweet.startswith('"@'):
            return False, False
        # Ignore if it doesn't mention the main bot only.
        if settings['twitter_track'][0] not in status.text:
            return False, False
        # Last case, check if they're not replying to a tweet.
        if status.in_reply_to_status_id is None:
            command = "Waifu"
        else:
            return False, False

    if command == "Reroll":
        try:
            command = USER_LAST_COMMAND[user.id]
            if "register" in command:
                return False, False
            elif "my" in command:
                return False, False
        except ValueError:
            return False, False
    else:
        USER_LAST_COMMAND[user.id] = command
        if len(USER_LAST_COMMAND) > 30:
            USER_LAST_COMMAND = (OrderedDict(
                islice(USER_LAST_COMMAND.items(),
                       20, None)))

    # Stop someone limiting the bot on their own.
    rate_time = datetime.datetime.now()
    rate_limit_secs = 10800
    if user.id in RATE_LIMIT_DICT:
        # User is now limited (3 hours).
        if ((rate_time - RATE_LIMIT_DICT[user.id][0])
                .total_seconds() < rate_limit_secs)\
           and (RATE_LIMIT_DICT[user.id][1] >= 15):
            return False, False
        # User limit is over.
        elif ((rate_time - RATE_LIMIT_DICT[user.id][0])
                .total_seconds() > rate_limit_secs):
            del RATE_LIMIT_DICT[user.id]
        else:
            # User found, not limited, add one to the trigger count.
            RATE_LIMIT_DICT[user.id][1] += 1
    else:
        # User not found, add them to RATE_LIMIT_DICT.
        # Before that quickly go through RATE_LIMIT_DICT
        # and remove all the finished unused users.
        for person in list(RATE_LIMIT_DICT):
            if ((rate_time - RATE_LIMIT_DICT[person][0])
               .total_seconds() > rate_limit_secs):
                del RATE_LIMIT_DICT[person]
        RATE_LIMIT_DICT[user.id] = [rate_time, 1]

    # This shouldn't happen but just in case.
    if not isinstance(command, str):
        return False, False

    tweet = tweet.lower().replace(command.lower(), " ", 1).strip()
    return tweet, command


def is_following(user_id):
    try:
        user_info = API.get_user(user_id)
    except tweepy.TweepError:
        return "Limited"
    if user_info.statuses_count < 10:
        return "Not Genuine"
    elif user_info.followers_count < 3:
        return "Not Genuine"
    try:
        ship = API.lookup_friendships(user_ids=(2910211797, user_id))
    except tweepy.TweepError:
        return "Limited"
    try:
        return ship[1].is_followed_by
    except TypeError:
        # Account doesn't exist anymore.
        return False


def status_account(status_api):
    """ Read RSS feeds and post them on the status Twitter account.
    :param status_api: The Tweepy API object for the status account.
    """
    def read_rss(url, name, pre_msg, find_xml):
        recent_id = open(os.path.join(settings['ignore_loc'],
                         name), 'r').read()
        try:
            rss = urllib.request.urlopen(url).read().decode("utf-8")
            xml = etree.fromstring(rss)
        except:
            # Don't need anymore than this for something like this
            print("Failed to read/parse {0} ({1}) RSS".format(name, url))
            return False

        if bool(find_xml['sub_listing']):
            entry = xml[0][find_xml['entries_in']]
        else:
            entry = xml[find_xml['entries_in']]
        current_id = entry.findtext(
            find_xml['entry_id'])

        if current_id == recent_id:
            return False

        with open(os.path.join(settings['ignore_loc'], name), "w") as f:
            f.write(current_id)

        if bool(find_xml['get_href']):
            msg_url = entry.find(find_xml['link_id']).get('href')
        else:
            msg_url = entry.findtext(find_xml['link_id'])

        msg_msg = re.sub('<[^<]+?>', '', entry.findtext(find_xml['msg_id']))
        msg_msg = re.sub(' +', ' ', os.linesep.join(
                         [s for s in msg_msg.splitlines() if s])).lstrip()
        msg = "{0}{1}\n{2}".format(pre_msg,
                                   utils.short_string(msg_msg, 90),
                                   msg_url)
        post_tweet(status_api, msg)

    while True:
        url = "https://github.com/ace3df/AcePictureBot/commits/master.atom"
        name = "GitCommit.txt"
        pre_msg = "[Git Commit]\n"
        find_xml = {"sub_listing": False,
                    "entries_in": 5,
                    "entry_id": "{http://www.w3.org/2005/Atom}id",
                    "link_id": "{http://www.w3.org/2005/Atom}link",
                    "get_href": True,
                    "msg_id": "{http://www.w3.org/2005/Atom}content"}
        read_rss(url, name, pre_msg, find_xml)
        time.sleep(300)


class CustomStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        global HAD_ERROR
        global HANG_TIME
        global TWEETS_READ
        HANG_TIME = time.time()
        tweet, command = acceptable_tweet(status)
        if not command:
            return True
        open(update['is_busy_file'], 'w')
        print("[{0}] Reading: {1} ({2}): {3}".format(
            time.strftime("%Y-%m-%d %H:%M"),
            status.user.screen_name, status.user.id, status.text))
        tweet_command(API, status, tweet, command)
        HAD_ERROR = False
        TWEETS_READ.append(str(status.id))
        with open(os.path.join(settings['ignore_loc'],
                               "tweets_read.txt"),
                  'w') as file:
            file.write("\n".join(TWEETS_READ))
        os.remove(update['is_busy_file'])


    def on_error(self, status_code):
        global LAST_STATUS_CODE
        global HANG_TIME
        HANG_TIME = time.time()
        if int(status_code) != int(LAST_STATUS_CODE):
            LAST_STATUS_CODE = status_code
            msg = ("[{0}] Twitter Returning Status Code: {1}.\n"
                   "More Info: https://dev.twitter.com/overview/api/response-codes").format(
                    time.strftime("%Y-%m-%d %H:%M"), status_code)
            print(msg)
            post_tweet(func.login(status=True), msg)
        return True


def start_stream(sapi=None):
    if sapi is None:
        sapi = func.login(rest=False)
    sapi = tweepy.Stream(sapi, CustomStreamListener())
    print("[INFO] Reading Twitter Stream!")
    sapi.filter(track=[x.lower() for x in settings['twitter_track']],
                async=True)
    return sapi


def handle_stream(sapi, status_api=False):
    sapi = start_stream(sapi)
    global HANG_TIME
    while True:
        time.sleep(5)
        elapsed = (time.time() - HANG_TIME)
        if elapsed > 600:
            msg = """[{0}] Crashed/Hanging!
The bot will catch up on missed messages now!""".format(
                    time.strftime("%Y-%m-%d %H:%M"))
            print(msg)
            if status_api:
                post_tweet(status_api, msg)
            sapi.disconnect()
            time.sleep(3)
            Thread(target=start_stream).start()
            Thread(target=read_notifications,
                   args=(API, True, TWEETS_READ)).start()
            HANG_TIME = time.time()


def read_notifications(_API, reply, tweets_read):
    statuses = _API.mentions_timeline()
    print("[INFO] Reading late tweets!")
    for status in reversed(statuses):
        if str(status.id) in TWEETS_READ:
            continue
        tweet, command = acceptable_tweet(status)
        if not command:
            continue
        if reply:
            print("[{0}] Reading (Late): {1} ({2}): {3}".format(
                time.strftime("%Y-%m-%d %H:%M"),
                status.user.screen_name, status.user.id,
                status.text))
            tweet_command(_API, status, tweet, command)
        TWEETS_READ.append(str(status.id))
        with open(os.path.join(settings['ignore_loc'],
                               "tweets_read.txt"),
                  'w') as file:
            file.write("\n".join(TWEETS_READ))
    print("[INFO] Finished reading late tweets!")

if __name__ == '__main__':
    # Load read IDs of already read tweets.
    TWEETS_READ = utils.file_to_list(
                    os.path.join(settings['ignore_loc'],
                                 "tweets_read.txt"))
    API = func.login(rest=True)
    SAPI = func.login(rest=False)
    STATUS_API = func.login(status=True)
    read_notifications(API, True, TWEETS_READ)
    Thread(target=status_account, args=(STATUS_API, )).start()
    Thread(target=handle_stream, args=(SAPI, STATUS_API)).start()

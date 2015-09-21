from spam_checker import remove_all_limit
from spam_checker import user_spam_check
import xml.etree.ElementTree as etree
from collections import OrderedDict
from utils import printf as print
from threading import Thread
from itertools import islice
from config import settings
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
__version__ = "2.1.1"

BLOCKED_IDS = utils.file_to_list(
                os.path.join(settings['list_loc'],
                             "Blocked Users.txt"))
IGNORE_WORDS = utils.file_to_list(
                os.path.join(settings['list_loc'],
                             "Blocked Words.txt"))
LIMITED = False
HAD_ERROR = False
TWEETS_READ = []
MOD_IDS = [2780494890, 121144139]
RATE_LIMIT_DICT = {}
USER_LAST_COMMAND = OrderedDict()
START_TIME = time.time()
HANG_TIME = time.time()
API = None
STATUS_API = None
SAPI = None
DEBUG = False


def post_tweet(_API, tweet, media=False, command=False, rts=False):
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
        # 99% of the time it's because they delete their tweets
        # Twitter gets confused and BAM!
        # The 1% is probs just twitter being twitter
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
        if not is_following(API, user.id):
            tweet = """You must follow @AcePictureBot to register!
Help: {0}""".format(func.config_get('Help URLs', 'must_follow'))
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

    if command == "Shipgirl":
        tweet, tweet_image = func.random_list(0, tweet)
    elif command == "Touhou":
        tweet, tweet_image = func.random_list(1, tweet)
    elif command == "Vocaloid":
        tweet, tweet_image = func.random_list(2)
    elif command == "Imouto":
        tweet, tweet_image = func.random_list(3)
    elif command == "Idol":
        tweet, tweet_image = func.random_list(4, tweet)
    elif command == "Shota":
        tweet, tweet_image = func.random_list(5)
    elif command == "Onii":
        tweet, tweet_image = func.random_list(6)
    elif command == "Onee":
        tweet, tweet_image = func.random_list(7)
    elif command == "Sensei":
        tweet, tweet_image = func.random_list(8, tweet)
    elif command == "Monstergirl":
        tweet, tweet_image = func.random_list(9, tweet)

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

    # Ignore retweets.
    if tweet.startswith('RT'):
        return False, False

    if DEBUG:
        if user.id not in MOD_IDS:
            return False, False

    # Reload incase of manual updates.
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

    # If the user @sauce_plz add "source" to the text
    # as every @ is later removed
    if "sauce" in tweet.lower():
        tweet += " source"

    # Remove extra spaces
    tweet = re.sub(' +', ' ', tweet)

    # Remove @UserNames (usernames could trigger commands alone)
    tweet = ' '.join(re.sub("(@[A-Za-z0-9]+)", " ", tweet).split())

    # Find the command they used.
    command = utils.get_command(tweet)
    # No command is found see if acceptable for a random waifu
    if not command:
        # Ignore Quote RTs only in this case
        if tweet.startswith('"@'):
            return False, False

        # Ignore if it doesn't mention the main bot ONLY
        if not settings['twitter_track'][0].lower() in tweet.lower():
            return False, False

        # Last case, check if they're not replying to a tweet
        if status.in_reply_to_status_id is None:
            command = "waifu"
        else:
            return False, False

    if command == "Reroll":
        try:
            command = USER_LAST_COMMAND[user.id]
            if "register" in command:
                return False, False
        except:
            return False, False
    else:
        USER_LAST_COMMAND[user.id] = command
        if len(USER_LAST_COMMAND) > 30:
            USER_LAST_COMMAND = (OrderedDict(
                islice(USER_LAST_COMMAND.items(),
                       20, None)))

    # Make sure the user isn't going ham on comamnds.
    # This is to make sure the bot doesn't get closer to being
    # limited from only one user.
    rate_time = datetime.datetime.now()

    if user.id in RATE_LIMIT_DICT:
        # User is limited (5 hours in seconds (18000))
        if ((rate_time - RATE_LIMIT_DICT[user.id][0])
                .total_seconds() < 18000)\
           and (RATE_LIMIT_DICT[user.id][1] >= 15):
            return False, False
        # User limit is over
        elif ((rate_time - RATE_LIMIT_DICT[user.id][0])
                .total_seconds() > 18000):
            del RATE_LIMIT_DICT[user.id]
        else:
            # User found, not limited, add one to the trigger count.
            RATE_LIMIT_DICT[user.id][1] += 1
    else:
        # User not found, add them to RATE_LIMIT_DICT.
        # Before that quickly go through RATE_LIMIT_DICT
        # and remove all the finished unused users.
        # As you can't edit a dict while in it
        # create a fake copy and then pass that through
        TEMP_DICT = RATE_LIMIT_DICT
        for person in TEMP_DICT:
            if ((rate_time - TEMP_DICT[person][0])
               .total_seconds() > 18000):
                del RATE_LIMIT_DICT[person]
        del TEMP_DICT
        RATE_LIMIT_DICT[user.id] = [rate_time, 1]

    # Fail check
    if not isinstance(command, str):
        return False, False
    tweet = tweet.lower().replace(command.lower(), " ").strip()
    return tweet, command


def is_following(_API=None, user_id=None):
    if _API is None:
        _API = login()
    try:
        ship = _API.lookup_friendships(user_ids=(2910211797, user_id))
    except:
        print("[WARNING] Hit lookup_friendships API limit!")
        # Hit API limit, reject them for now
        return False
    try:
        return ship[1].is_followed_by
    except:
        # Account doesn't exsist anymore
        return False


def status_account(STATUS_API):
    """ Read RSS feeds and post them on the status Twitter account."""
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
                                   utils.short_str(msg_msg, 90),
                                   msg_url)
        post_tweet(STATUS_API, msg)

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

    def on_error(self, status_code):
        print(status_code)
        return True


def start_stream(SAPI=None):
    if SAPI is None:
        SAPI = func.login(REST=False)
    sapi = tweepy.Stream(SAPI, CustomStreamListener())
    print("[INFO] Reading Twitter Stream!")
    sapi.filter(track=[x.lower() for x in settings['twitter_track']],
                async=True)
    return sapi


def handle_stream(SAPI, STATUS_API=False):
    sapi = start_stream(SAPI)
    global HANG_TIME
    # Create a loop which makes sure that the stream
    # hasn't been haning at all.
    # If it has, it will try to reconnect.

    # FOR NOW KEEP THIS AS FALSE
    while True:
        time.sleep(5)
        elapsed = (time.time() - HANG_TIME)
        if elapsed > 600:
            print("[WARNING] STREAM HANING. RESTARTING...")
            try:
                if STATUS_API:
                    # Tweet to the status bot that the stream was hanging.
                    msg = "[WARNING] " + settings['twitter_track'][0] + \
                     ":\nStream haning. Restarting..."
                    post_tweet(STATUS_API, msg)
            except:
                pass
            sapi.disconnect()
            time.sleep(3)
            # Restart the stream and catch up on late tweets.
            Thread(target=start_stream).start()
            Thread(target=read_notifications,
                   args=(API, True, TWEETS_READ)).start()
            # Restart HANG_TIME.
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
    # Get the main bot's API and STREAM request.
    API = func.login(REST=True)
    SAPI = func.login(REST=False)
    # Get the status account API.
    STATUS_API = func.login(status=True)
    # Start 2 threads:
    # First read_notifcations (for late start ups).
    # status_account (to check if there is a problem).
    # handle_stream (check if the stream has disconnected/haning).
    read_notifications(API, True, TWEETS_READ)
    Thread(target=status_account, args=(STATUS_API, )).start()
    Thread(target=handle_stream, args=(SAPI, STATUS_API)).start()

from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
import threading
import logging
import time
import sys
import os

import twython

from config import twitter_settings
try:
    from config import help_urls
except ImportError:
    help_urls = {}
from functions import (BotProcess, Source, UserContext,
                       datadog_online_check)

attrs = {'name': 'twitter', 'character_limit': 42,
         'support_embedded': False, 'download_media': True,
         'allow_new_mywaifu': True}
bot = BotProcess(Source(**attrs))


def upload_media(media):
    bot.log.info("[{}] Uploading Media: {}".format(
        time.strftime("%Y-%m-%d %H:%M"), media))
    try:
        if media.lower().endswith(".mp4"):
            return bot.api.upload_video(media=media, media_type='video/mp4')['media_id']
        else:
            with open(media, 'rb') as fp:
                return bot.api.upload_media(media=fp)['media_id']
    except twython.exceptions.TwythonError as e:
        bot.log.warning("Uploading failed.")
        bot.log.warning(e)
        return False


def post_tweet(ctx, reply_text, reply_media=None):
    bot.log.info("[{}] Tweeting: {} ({}): [{}] {}".format(
        time.strftime("%Y-%m-%d %H:%M"), ctx.screen_name,
        ctx.user_id, ctx.command, reply_text))
    media_ids = []
    try:
        if reply_media:
            if isinstance(reply_media, list):
                for media in reply_media:
                    # You can only have mp4/gif once per tweet
                    # Make sure it wont try to mix and match
                    uploaded = upload_media(media)
                    if uploaded:
                        media_ids.append(uploaded)
                    if media.endswith(".mp4") or media.endswith(".gif"):
                        break
            else:
                uploaded = upload_media(reply_media)
                if uploaded:
                    media_ids.append(uploaded)
            if not media_ids and reply_text:
                # TEMP
                # Twitter rejected upload (seems to be API problem for now)
                if ctx.command in ["mywaifu", "myhusbando", "waifuregister", "husbandoregister"]:
                    ctx.bot.check_rate_limit_per_cmd(ctx, remove=1)
                    url_help = help_urls.get('waifuregister_websites_offline', False)
                    reply_text = ("Websites are offline to get you your {}!\n"
                                  "Try again later!{}".format(ctx.command,
                        "\nHelp: " + url_help if url_help else ""))
                    reply_text = "@{0} {1}".format(ctx.screen_name, reply_text)
                # Failed to upload media
                bot.api.update_status(status=reply_text,
                                  in_reply_to_status_id=ctx.raw_data['id'])
            elif media_ids:
                bot.api.update_status(status=reply_text, media_ids=media_ids,
                                      in_reply_to_status_id=ctx.raw_data['id'])
        else:
            bot.api.update_status(status=reply_text,
                                  in_reply_to_status_id=ctx.raw_data['id'])
    except twython.exceptions.TwythonError as e:
        bot.log.warning(e)
        # Bad request, silent return
        return

def is_following(ctx):
    can_bypass_genuine = False
    if ctx.user_ids.get('discord', False):
        can_bypass_genuine = True
    elif ctx.user_ids.get('reddit', False):
        can_bypass_genuine = True
    elif ctx.user_ids.get('twitch', False):
        can_bypass_genuine = True
    limited_msg = ("The bot is currently limited by Twitter!"
                   "\nTry again in 15 minutes!")
    url_help = help_urls.get('mywaifu_not_genuine', False)
    msg = ("Your account wasn't found to be genuine."
           "{url_help}".format(url_help="\nHelp: " + url_help if url_help else ""))
    try:
        user_info = bot.api.lookup_user(user_id=ctx.user_id)
    except (twython.exceptions.TwythonAuthError, twython.exceptions.TwythonError):
        return limited_msg
    if not can_bypass_genuine:
        if user_info[0]['statuses_count'] < 10:
            return msg
        elif user_info[0]['followers_count'] < 6:
            return msg
    try:
        my_id = twitter_settings.get('my_id', '2910211797')
        friendship = bot.api.lookup_friendships(user_id="{},{}".format(my_id, ctx.user_id))
    except (twython.exceptions.TwythonAuthError, twython.exceptions.TwythonError):
        return limited_msg
    try:
        follow_result = 'followed_by' in friendship[1]['connections']
    except (TypeError, IndexError):
        # Account doesn't exist anymore.
        return False
    if not follow_result:
        # Not following
        url_help = help_urls.get('mywaifu_must_follow', False)
        msg = ("You must follow the Twitter bot to register!"
               "{url_help}".format(url_help="\nHelp: " + url_help if url_help else ""))
        return msg
    return True


def process_tweet(data):
    global tweets_read
    if 'text' not in data:
        return
    tweet_datetime = datetime.strptime(
            data['created_at'], '%a %b %d %H:%M:%S %z %Y')
    days_past = datetime.now(timezone.utc) - tweet_datetime
    if days_past.days > 1:  # Twitter can sometimes suddenly return old tweets. Nice.
        return
    if data['id_str'] in tweets_read:
        return
    if data['text'].startswith('RT'):
        if bot.settings.get('datadog', False) and bot.settings['datadog'].get('statsd_retweets', False):
            bot.datadog.statsd.increment(bot.settings['datadog']['statsd_retweets'])
        return
    # Ignore tweets from accounts tracking.
    if any(a.lower() in data['user']['screen_name'].lower() for a in bot.settings['twitter_track']):
        return
    # Ignore bots and bad boys.
    if data['user']['id_str'] in bot.settings.get('blocked_ids', []):
        return
    # Make sure the message has @Bot in it.
    if not any("@" + a.lower() in data['text'].lower() for a in bot.settings['twitter_track']):
        return
    command = bot.uses_command(data['text'])
    if not command:  # No command used.
        # Last case, check if they're not replying to a tweet.
        if data['in_reply_to_status_id_str'] is None:
            command = "waifu"
        else:
            return

    attrs = {'bot': bot,
             'screen_name': data['user']['screen_name'],
             'twitter_id': data['user']['id_str'],
             'command': command,
             'message': data['text'],
             'raw_data': data
            }
    ctx = UserContext(**attrs)
    if not bot.check_rate_limit(ctx):
        return
    bot.log.info("[{}] Reading: {} ({}): [{}] {}".format(
        time.strftime("%Y-%m-%d %H:%M"), ctx.screen_name,
        ctx.user_id, ctx.command, ctx.message))
    reply_text = None
    reply_media = []
    if not ctx.is_patreon and not ctx.is_mod:
        is_limit = bot.check_rate_limit_per_cmd(ctx)
        if not is_limit:  # User is limited, ignore them.
            bot.log.info("User is limited. Ignoreing...")
            return
        if isinstance(is_limit, str):  # User is now limited, pass warning.
            reply_text = is_limit
    elif ctx.is_patreon:
        is_limit = bot.check_rate_patreon(ctx)
        if not is_limit:
            reply_text = ("Wah! Slow down there! "
                          "It's best that you don't go overboard on using {} {}".format(
                           ctx.command, r"http://ace3df.github.io/AcePictureBot/faq_patreon/#wah-slow-down-twitter-only"))
    if command in ["waifuregister", "husbandoregister"]:
        following = is_following(ctx)
        if isinstance(following, str):
            reply_text = following
        else:
            if not following:
                return
    if reply_text is None:
        bot.commands_used[ctx.command] += 1
        reply_text, reply_media = bot.on_command(ctx)

    if ctx.command == "unwrap":
        import random
        import re
        chance = random.randint(0, 50)
        if chance >= 48:
            # Give them 1 free week of patreon only commands
            current_ids = [user_id[0] for user_id in bot.patreon_ids['patreon_guest_ids']['twitter']]
            if ctx.user_id not in current_ids:
                bot.patreon_ids['patreon_guest_ids']['twitter'].append([ctx.user_id, "Christmas Special"])
                bot.update_patreon_file(bot.patreon_ids)
                reply_text = re.sub(r'\([^)]*\)', '', reply_text)
                reply_text += "\nYou unwrapped commands for the week! https://gist.github.com/ace3df/9dcbd9ff4f540351927f66a5c2aba78d"

    if reply_text or reply_media:
        reply_text = "@{0} {1}".format(ctx.screen_name, reply_text)
        post_tweet(ctx, reply_text, reply_media)

    # Store read tweets so we don't dup later on, don't let it get too big as well.
    if len(tweets_read) > 150:
        tweets_read = tweets_read[50:]
    tweets_read.append(data['id_str'])
    with open(os.path.join(bot.config_path, "Tweets Read.txt"), 'w') as file:
        file.write("\n".join(tweets_read))


def read_notifications():
    bot.log.info("Reading Notifications.")
    statuses = bot.api.get_mentions_timeline()
    for status in reversed(statuses):
        process_tweet(status)
    bot.log.info("Finished Reading Notifications.")


class TwitterStream(twython.TwythonStreamer):
    def on_success(self, data):
        process_tweet(data)

    def on_error(self, status_code, data):
        """Called when stream returns non-200 status code
        Feel free to override this to handle your streaming data how you want it handled.
        Parameters: 
        status_code (int) – Non-200 status code sent from stream
        data (dict) – Error message sent from stream 
        """
        bot.log.warning("Problem:")
        bot.log.warning(data)
        pass

    def on_timeout(self):
        """Called when the request has timed out"""
        pass


if __name__ == '__main__':
    if not bot.settings.get('twitter_keys', False):
        raise Exception("Missing Twitter Kyes from Twitter Settings.json in /Configs/")
    if not bot.settings.get('twitter_track', False):
        raise Exception("Missing Twitter Tracking string/list from Twitter Settings.json in /Configs/")
    twitter_keys = bot.settings.pop('twitter_keys')
    if bot.settings.get('datadog', False):
        datadog_thread = threading.Thread(
            target=datadog_online_check,
            args=(bot.datadog, 'twitter.ok', 'twitter', 'Response: 200 OK'))
        datadog_thread.daemon = True
        datadog_thread.start()
    
    tweets_read_file = os.path.join(bot.config_path, "Tweets Read.txt")
    if not os.path.isfile(tweets_read_file):
        bot.log.info("Creating: {}".format(tweets_read_file))
        with open(tweets_read_file, 'w') as file:
            file.write('')
        tweets_read = []
    else:
        with open(tweets_read_file, 'r') as file:
            tweets_read = file.read().splitlines()

    api = twython.Twython(
        twitter_keys['consumer_key'],
        twitter_keys['consumer_secret'],
        twitter_keys['access_token'],
        twitter_keys['access_token_secret'])
    bot.api = api
    read_notifications()
    bot.log.info("Reading Twitter Stream.")
    stream = TwitterStream(
        twitter_keys['consumer_key'],
        twitter_keys['consumer_secret'],
        twitter_keys['access_token'],
        twitter_keys['access_token_secret'],
        timeout=120, retry_count=3, retry_in=10)
    stream.statuses.filter(track=', '.join(
                [x.lower() for x in bot.settings['twitter_track']]))

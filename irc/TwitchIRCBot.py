import sys
sys.path.append('..')
from collections import OrderedDict
from itertools import islice
from threading import Thread
import datetime
import requests
import socket
import random
import select
import time
import json
import re
import os

from utils import printf as print  # To make sure debug printing won't brake
from config import twitch_settings
from config import extra_api_keys
from config import settings
from utils import get_command
import functions as func

from imgurpython import ImgurClient

TWITCH_HOST = r"irc.twitch.tv"
TWITCH_PORT = 6667

__program__ = "AcePictureBot For Twitch Chat"
__version__ = "1.0.1"


def get_twitter_id(twitch_username):
    url = twitch_settings['url_start'] + "get/" + twitch_username.lower()
    try:
        r = requests.get(url)
    except:
        return False
    try:
        return int(r.text)
    except:
        # Still not a int?
        return "Not Found!"


class TwitchIRC:
    def __init__(self):
        self.irc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc_sock.settimeout(10)
        self.current_channel = ""

    def connect(self):
        self.irc_sock.connect((TWITCH_HOST, TWITCH_PORT))
        self.current_joined_chans = [twitch_settings['default_channel']]
        self.irc_sock.send(
            str("Pass " +
                twitch_settings['twitch_oauth_token'] +
                "\r\n").encode('UTF-8'))
        self.irc_sock.send(
            str("NICK " +
                twitch_settings['twitch_username'] + "\r\n").encode('UTF-8'))
        self.irc_sock.send(
            str("JOIN " +
                twitch_settings['default_channel'] + "\r\n").encode('UTF-8'))

    def say_welcome_message(self, channel):
        try:
            func.config_add_section(channel,
                                    twitch_settings['settings_file'])
        except:
            return

        to_add = {'active': 'True',
                  'allow_images': 'True',
                  'must_mention': 'False',
                  'rate_limit_level': '1',
                  'ads': 'True',
                  'mywaifu': 'True'}
        func.config_save_2(to_add, section=channel,
                           file=twitch_settings['settings_file'])
        msg = "Hello, my name is AcePictureBot! - "\
              "You can use over 10 commands including: Waifu, Shipgirl, OTP and many more! - "\
              "To start simply say: \"Waifu\"! "\
              "Don't forget to cheak out all the Ace Bots on Twitter: "\
              "https://twitter.com/AcePictureBot"
        self.send_message(channel, msg)
        msg = "Feel free to support the Dev: "\
              "http://ace3df.github.io/AcePictureBot/donate/ || "\
              "{0} you should read this for a list of mod only commands: "\
              "https://gist.github.com/ace3df/bf7a6e7dce4c1168e3cb".format(channel.replace("#", "@"))
        self.send_message(channel, msg)

    def timeout_channel(self):
        """Check if the bot has talked in each server in the last 2 days.
        If it hasn't it will leave."""
        while True:
            current_time = time.time()
            for channel in func.config_all_sections(twitch_settings['settings_file']):
                if channel == "#acepicturebot":
                    # Don't timeout own channel
                    continue
                if channel in CHANNEL_TIMEOUT:
                    if current_time - CHANNEL_TIMEOUT[channel] > 432000:
                        self.leave_channel(channel)
                else:
                    CHANNEL_TIMEOUT[channel] = time.time()
                time.sleep(60)

    def advertise_timer(self, channel):
        """Post a preset message to advertise the bot.
        Optional and streamer can turn off forever."""
        msgs = ["Get me in your own Twitch channel by typing: \"!apb join\"",
                r"Don't forget to check out AcePictureBot on Twitter: https://twitter.com/AcePictureBot",
                r"Get AcePictureBot for Discord! Fill in this form: http://goo.gl/forms/ajpYU8iwAI",
                r"Enjoy Yuri? Follow the Yuri Picture Bot: https://twitter.com/AceYuriBot",
                r"I have over 10 commands! Full list here: https://ace3df.github.io/AcePictureBot/commands/"]
        last_sent = ""
        while True:
            sleep_for = random.randint(40, 80)
            time.sleep(sleep_for * 60)
            if channel not in self.current_joined_chans:
                return
            temp_settings = func.config_get_section_items(
                channel,
                twitch_settings['settings_file'])
            if temp_settings['ads'] == "True":
                msg = random.choice(msgs)
                while msg == last_sent:
                    msg = random.choice(msgs)
                last_sent = msg
                self.send_message(channel, msg)

    def upload_image(self, image_loc):
        try:
            return imgur_client.upload_from_path(image_loc)['link']
        except Exception as e:
            print(e)
            return False

    def send_message(self, channel, message):
        print("{} | {}: {}".format(channel, "AcePictureBot", message))
        self.irc_sock.send("PRIVMSG {} :{}\n".format(channel, str.rstrip(message)).encode('UTF-8'))

    def join_channel(self, channel):
        print("$ Joined channel: {}".format(channel))
        self.current_joined_chans.append(str(channel))
        self.irc_sock.send("JOIN {}\n".format(str.rstrip(channel.lower())).encode('UTF-8'))
        Thread(target=self.advertise_timer, args=(channel,)).start()

    def leave_channel(self, channel):
        func.config_delete_section(channel, twitch_settings['settings_file'])
        print("$ Left channel: {}".format(channel))
        self.current_joined_chans.remove(str(channel))
        self.irc_sock.send("PART {}\n".format(str.rstrip(channel)).encode('UTF-8'))

    def on_message(self, message):
        global USER_LAST_COMMAND
        if DEBUG:
            print(message)
        if message.find('PING ') != -1:
            self.irc_sock.send(str("PING :pong\n").encode('UTF-8'))
            return
        if message.find('End of') != -1:
            return
        if message.find('.tmi.twitch.tv PART') != -1:
            return
        if message.startswith(":tmi.twitch.tv"):
            # From server - ignore
            return

        channel = [i for i in message.split() if i.startswith("#")][0]
        channel_settings = func.config_get_section_items(
            channel,
            twitch_settings['settings_file'])

        if not channel_settings:
            # Joined and haven't been able to complete say_welcome_message().
            self.say_welcome_message(channel)
            channel_settings = {'active': 'True',
                                'allow_images': 'True',
                                'must_mention': 'False',
                                'rate_limit_level': '1',
                                'ads': 'True'}
        user = message.split("!", 1)[0][1:]
        message = ' '.join(message.split(channel + " :")[1:])

        if message.startswith("!apb join"):
            if "#" + str(user) not in self.current_joined_chans:
                self.join_channel("#" + str(user))

        if message.startswith("!apb help"):
            msg = "Commands: http://ace3df.github.io/AcePictureBot/commands/ || "\
                  "Mod Commands: https://gist.github.com/ace3df/bf7a6e7dce4c1168e3cb"
            self.send_message(channel, msg)
            return

        if user == channel[1:] or user == "ace3df":
            edit_result = False
            if message.startswith("!apb leave"):
                self.leave_channel(channel)

            if message.startswith("!apb turn on"):
                # Turn on the bot in the server (DEFAULT).
                edit_result = "True"
                edit_section = "active"
                msg = "The bot will now respond to commands!"
            elif message.startswith("!apb turn off"):
                # Turn off the bot in the server.
                edit_result = "False"
                edit_section = "active"
                msg = "The bot will now ignore commands!"

            if message.startswith("!apb mention on"):
                # They will have to mentiont he bot to use a command.
                edit_result = "True"
                edit_section = "must_mention"
                msg = "You will now have to mention the bot to use a command!"
            elif message.startswith("!apb mention off"):
                # They do NOT have to mentiont he bot to use a command(DEFAULT)
                edit_result = "False"
                edit_section = "must_mention"
                msg = "You can use commands without mentioning me!"

            if message.startswith("!apb images on"):
                # Try and post an image along side commands (DEFAULT).
                edit_result = "True"
                edit_section = "allow_images"
                msg = "If possible an image will be posted along side commands!"
            elif message.startswith("!apb images off"):
                # Don't post images along side commands.
                edit_result = "False"
                edit_section = "allow_images"
                msg = "No image will be posted when using commands!"

            if message.startswith("!apb mywaifu on"):
                # Allow a user to use MyWaifu/Husbando in their chat (DEFAULT).
                edit_result = "True"
                edit_section = "mywaifu"
                msg = "Users can now use MyWaifu and MyHusbando!"
            elif message.startswith("!apb mywaifu off"):
                # Don't post images along side commands.
                edit_result = "False"
                edit_section = "mywaifu"
                msg = "Users can't use use MyWaifu and MyHusbando!"

            if message.startswith("!apb rate limit"):
                # Change the level of users rate limits (Per User).
                # 1 = 10 Commands in 5 Minutes (DEFAULT).
                # 2 = 5 Commands in 5 Minutes.
                # 3 = 2 Commands in 1 Minute.
                # Higher than 3 defaults to 3 - Lower defaults to 1.
                num = [int(s) for s in message.content.split() if s.isdigit()]
                if not num:
                    msg = "You didn't include a level number (1 - 3)! "\
                          "Limits: "\
                          "https://gist.github.com/ace3df/bf7a6e7dce4c1168e3cb"
                    self.send_message(channel, msg)
                    return
                else:
                    num = num[0]
                if num > 3:
                    num = 3
                elif num < 1:
                    num = 1
                edit_result = num
                edit_section = "rate_limit_level"
                if num == 1:
                    msg = "10 Commands in 5 Minutes (per user)."
                elif num == 2:
                    msg = "5 Commands in 5 Minutes (per user)."
                elif num == 3:
                    msg = "2 Commands in 1 Minutes (per user)."
                msg = "Rate Limit changed to:\n" + msg

            if message.startswith("!apb ads on"):
                # They will have to mentiont he bot to use a command.
                edit_result = "True"
                edit_section = "ads"
                msg = "The bot will now advertise itself every so often!"
            elif message.startswith("!apb ads off"):
                # They do NOT have to mentiont he bot to use a command(DEFAULT)
                edit_result = "False"
                edit_section = "ads"
                msg = "The bot will now not advertise itself! :( )"

            if edit_result:
                channel_settings[edit_section] = str(edit_result)
                func.config_save(channel,
                                 edit_section, str(edit_result),
                                 twitch_settings['settings_file'])
                msg = '{0} {1}'.format(msg, user)
                self.send_message(channel, msg)
                return

        if channel_settings['active'] == "False":
            return

        if channel_settings['must_mention'] == "True":
            is_in = False
            if "acepicturebot" in message.lower():
                is_in = True
            if not is_in:
                return
        msg = message.replace("🚢👧", "Shipgirl")
        msg = ' '.join(re.sub('(^|\n| )(@[A-Za-z0-9_🚢👧.]+)',
                              ' ', msg).split())
        # Find the command they used.
        command = get_command(msg)
        if not command:
            # No command was used - ignore.
            return
        if command in NO_DISCORD_CMDS or command in LATER_DISCORD_CMDS:
            # Completely ignore these.
            return

        print("{} | {}: {}".format(channel, user, message))
        # Refreash the server's timeout.
        CHANNEL_TIMEOUT[user] = time.time()

        if command == "Reroll":
            try:
                command = USER_LAST_COMMAND[user]
            except (ValueError, KeyError):
                return
        else:
            USER_LAST_COMMAND[user] = command
            if len(USER_LAST_COMMAND) > 30:
                USER_LAST_COMMAND = (OrderedDict(
                    islice(USER_LAST_COMMAND.items(),
                           20, None)))
        # Stop someone limiting the bot on their own.
        rate_time = datetime.datetime.now()
        if channel_settings['rate_limit_level'] == "1":
            rate_limit_commands = 10
            rate_limit_secs = 300
        elif channel_settings['rate_limit_level'] == "2":
            rate_limit_commands = 5
            rate_limit_secs = 300
        elif channel_settings['rate_limit_level'] == "3":
            rate_limit_commands = 2
            rate_limit_secs = 60
        if user in RATE_LIMIT_DICT:
            # User is now limited (3 hours).
            if ((rate_time - RATE_LIMIT_DICT[user][0])
                    .total_seconds() < rate_limit_secs)\
               and (RATE_LIMIT_DICT[user][1] >= rate_limit_commands):
                return
            # User limit is over.
            elif ((rate_time - RATE_LIMIT_DICT[user][0])
                    .total_seconds() > rate_limit_secs):
                del RATE_LIMIT_DICT[user]
            else:
                # User found, not limited, add one to the trigger count.
                RATE_LIMIT_DICT[user][1] += 1
        else:
            # User not found, add them to RATE_LIMIT_DICT.
            # Before that quickly go through RATE_LIMIT_DICT
            # and remove all the finished unused users.
            for person in list(RATE_LIMIT_DICT):
                if ((rate_time - RATE_LIMIT_DICT[person][0])
                   .total_seconds() > rate_limit_secs):
                    del RATE_LIMIT_DICT[person]
            RATE_LIMIT_DICT[user] = [rate_time, 1]

        msg = msg.lower().replace(command.lower(), " ", 1).strip()
        discord_image = False
        # Main Commands
        if command == "Waifu":
            msg, discord_image = func.waifu(0, msg, DISCORD=True)
        elif command == "Husbando":
            msg, discord_image = func.waifu(1, msg, DISCORD=True)

        if command == "WaifuRegister" or command == "HusbandoRegister":
            msg = "You can only register on Twitter! http://twitter.com/AcePictureBot and then connect your account here: {}".format(twitch_settings['url_start'])

        if command == "MyWaifu" or command == "MyHusbando":
            if channel_settings['mywaifu'] == "False":
                return
            if command == "MyWaifu":
                gender = "Waifu"
            else:
                gender = "Husbando"
            twitter_id = get_twitter_id(user)
            if not twitter_id:
                # Site failed.
                return
            if twitter_id == "Not Found!":
                msg = "Couldn't find your {gender}! Register your {gender} on Twitter (Follow: http://ace3df.github.io/AcePictureBot/commands/) and then link your account: {url}".format(gender=gender, url=twitch_settings['url_start'])
            else:
                # Legit id
                if command == "MyWaifu":
                    gender_id = 0
                else:
                    gender_id = 1
                skip_dups = False
                if "my{gender}+".format(gender=gender.lower()) in message.lower():
                    skip_dups = True
                if "my{gender}-".format(gender=gender.lower()) in message.lower():
                    func.delete_used_imgs(twitter_id, True)
                msg, discord_image = func.mywaifu(twitter_id, gender_id, True, skip_dups)
                if "I don't know" in msg:
                    msg = "Couldn't find your {gender}! Register your {gender} on Twitter (http://ace3df.github.io/AcePictureBot/commands/) and then link your account: {url}".format(gender=gender, url=twitch_settings['url_start'])
                elif not discord_image or discord_image is None:
                    msg = "Sorry failed to get a new image! Use the command on Twitter to help the bot store more images! You can also use My{gender}+ to skip checking for an already used image or My{gender}- to start from fresh!".format(gender=gender)
                else:
                    msg = ' '.join(re.sub("(#[A-Za-z0-9]+)", " ", msg).split())
                    msg = "@{0}'s {1}".format(user, msg)
                    if channel_settings['allow_images'] and discord_image:
                        discord_image = self.upload_image(discord_image)
                        if discord_image:
                            msg = msg + " | " + discord_image
                    self.send_message(channel, msg)
                    return


        if command == "OTP":
            msg, discord_image = func.otp(msg)

        list_cmds = ["Shipgirl", "Touhou", "Vocaloid",
                     "Imouto", "Idol", "Shota",
                     "Onii", "Onee", "Sensei",
                     "Monstergirl", "Witchgirl", "Tankgirl",
                     "Senpai", "Kouhai"]
        if command in list_cmds:
            msg, discord_image = func.random_list(command, msg, DISCORD=True)

        # Remove hashtags
        msg = ' '.join(re.sub("(#[A-Za-z0-9]+)", " ", msg).split())
        msg = '{0} @{1}'.format(msg, user)
        if channel_settings['allow_images'] and discord_image:
            discord_image = self.upload_image(discord_image)
            if discord_image:
                msg = msg + " | " + discord_image
        self.send_message(channel, msg)

    def run(self):
        line_sep_exp = re.compile(b'\r?\n')
        socketBuffer = b''
        Thread(target=self.timeout_channel).start()
        for channel in func.config_all_sections(twitch_settings['settings_file']):
            if channel == "#acepicturebot":
                continue
            self.join_channel(channel)
        while True:
            try:
                self.connected = True
                r, _, _ = select.select([self.irc_sock], [], [])
                if r:
                    socketBuffer += self.irc_sock.recv(1024)
                    msgs = line_sep_exp.split(socketBuffer)
                    socketBuffer = msgs.pop()
                    for msg in msgs:
                        msg = msg.decode('utf-8')
                        Thread(target=self.on_message, args=(msg,)).start()
            except Exception as e:
                print(e)
                raise

if __name__ == "__main__":
    DEBUG = False

    # Commands not while using through discord.
    NO_DISCORD_CMDS = ["Source", "DelLimits", "SetBirthday",
                       "Spoiler", "Airing", "DiscordConnect"]
    # Commands that will be added once Discord finishes Twitter linking
    LATER_DISCORD_CMDS = ["WaifuRemove", "HusbandoRemove",
                          "!Level"]

    RATE_LIMIT_DICT = {}
    RATE_LIMIT_DICT_MYWAIFU = {}
    CHANNEL_TIMEOUT = {}
    USER_LAST_COMMAND = OrderedDict()
    try:
        imgur_client = ImgurClient(extra_api_keys['imgur_client_id'],
                                   extra_api_keys['imgur_client_secret'])
    except:
        # Temp (probs just timeout or what not if it happens)
        # TODO: Make it cheack if this is vaild every now and then
        imgur_client = False

    if not os.path.exists(twitch_settings['settings_file']):
        open(twitch_settings['settings_file'], "w")
    while True:
        irc_object = TwitchIRC()
        try:
            irc_object.connect()
            irc_object.run()
        except Exception as e:
            print(traceback.format_exc())
            # If we get here, try to shutdown the bot then restart in 5 seconds
        irc_object.kill()
        time.sleep(5)

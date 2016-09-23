import socket
import copy
import json
import time
import os
import re


from functions import (BotProcess, Source, UserContext,
                       datadog_online_check, create_token)


attrs = {'name': 'twitch', 'character_limit': 150,
         'support_embedded': False, 'download_media': False,
         'allow_new_mywaifu': False, 'thrid_party_upload': True}
bot = BotProcess(Source(**attrs))
prefix = bot.settings.get('twitch_command_prefix', ["!apb "])  # Only used for mod settings
settings_edits = [["active", "The bot is now online for this channel!", "The bot is now offline for this channel!"],
                  ["media", "The bot will now post media (images) when it can!", "The bot will now not post any media!"],
                  ["mention", "Users must now @Mention the bot to use commands!", "Users don't need to @Mention to use commands!"]]

class TwitchBot():

    def __init__(self):
        if not bot.settings.get('twitch_nickname', False):
            raise Exception("Missing twitch_nickname in settings.")
        if not bot.settings.get('twitch_oauth', False):
            raise Exception("Missing twitch_oauth in settings.")
        if not bot.settings.get('twitch_default_channel', False):
            raise Exception("Missing twitch_default_channel in settings.")
        self.nickname = bot.settings['twitch_nickname']
        self.s = socket.socket()
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.connect(("irc.twitch.tv", 6667))
        self.s.send("PASS {}\r\n".format(bot.settings['twitch_oauth']).encode("utf-8"))
        self.s.send("NICK {}\r\n".format(self.nickname).encode("utf-8"))
        self.connected = True
        self.channel_joined_path = os.path.join(bot.config_path, "Twitch IRC Channels.json")
        self.joined_channels = []
        if not os.path.isfile(self.channel_joined_path):
            to_join = [bot.settings['twitch_default_channel']]
        else:
            with open(self.channel_joined_path, 'r') as f:
                to_join = json.load(f)
        for channel in to_join:
            self.join_chan(channel)

    def parse_irc_msg(self, msg):
        keys = ['sender', 'type', 'target']
        result = dict((key, value.lstrip(':')) for key, value in zip(keys, msg.split()))
        if result['type'] != "PRIVMSG":
            return False
        result['message'] = msg.split("PRIVMSG {} :".format(result['target'], 1))[1].replace("\r\n", "")
        result['sender'] = result['sender'].split("!", 1)[0]
        if not result.get('message', False) or "tmi.twitch.tv" in (result['message'], result['sender']):
            return False
        return result

    def join_chan(self, chan):
        chan = chan.lower()
        if not chan.startswith("#"):
            chan = "#" + chan
        if chan in self.joined_channels:  # Already joined.
            return
        if chan not in self.joined_channels:
            self.joined_channels.append(chan)
            with open(self.channel_joined_path, 'w') as f:
                json.dump(self.joined_channels, f, sort_keys=True, indent=4)
        self.s.send("JOIN {}\r\n".format(chan).encode("utf-8"))

    def leave_chan(self, chan):
        chan = chan.lower()
        if not chan.startswith("#"):
            chan = "#" + chan
        if chan not in self.joined_channels:  # Not in said chan.
            print(123)
            return
        if chan in self.joined_channels:
            print(321)
            self.joined_channels.remove(chan)
            with open(self.channel_joined_path, 'w') as f:
                json.dump(self.joined_channels, f, sort_keys=True, indent=4)
        print(chan)
        self.s.send("PART {}\r\n".format(chan).encode("utf-8"))

    def change_settings(self, channel_settings, channel, message):
        new_settings = copy.deepcopy(channel_settings)
        prefix_used = [pre for pre in prefix if message.startswith(pre)]
        args = ' '.join(message.lower().split(prefix_used[0], 1)).split()
        if len(args) < 2:
            return False
        to_edit = [edit for edit in settings_edits if edit[0] in args[0]]
        if not to_edit:
            return "Invalid setting to edit!"
        to_edit = to_edit[0]
        to_edit_name, help_on, help_off = to_edit
        on_or_off = ["active", "mention", "media"]
        if to_edit_name in on_or_off:
            if "on" in args[1]:
                new_settings[to_edit_name] = True
            elif "off" in args[1]:
                new_settings[to_edit_name] = False
            else:
                msg = "Invalid setting! Use either 'on' or 'off'!"
                return msg
            msg = help_on if new_settings[to_edit_name] else help_off
        if new_settings.items() == channel_settings.items():
            msg = "No settings changed!"
        else:
            filename = os.path.join(bot.config_path, 'Twitch Servers', "{0}.json".format(channel))
            with open(filename, 'w') as f:
                json.dump(new_settings, f, sort_keys=True, indent=4)
        return msg

    def get_channel_settings(self, channel):
        channel_settings = {'active': True,
                           'media': True,
                           'mention': False}
        path = os.path.join(bot.config_path, 'Twitch Servers')
        if not os.path.exists(path):
            os.makedirs(path)
        filename = os.path.join(path, "{0}.json".format(channel))
        if not os.path.isfile(filename):
            with open(filename, 'w') as f:
                json.dump(channel_settings, f, sort_keys=True, indent=4)
        else:
            with open(filename, 'r') as f:
                channel_settings = json.load(f)
        return channel_settings

    def main_loop(self):
        bot.log.info("IRC Connected.")
        while self.connected:
            response = self.s.recv(1024).decode("utf-8")
            if response == "PING :tmi.twitch.tv\r\n":
                self.s.send("PONG :tmi.twitch.tv\r\n".encode())
                continue
            data = self.parse_irc_msg(response)
            if not data:
                continue

            if data['sender'].lower() == self.nickname.lower():
                continue
            channel_settings = self.get_channel_settings(data['target'])
            if data['message'].startswith(tuple(prefix)) and any(cmd[0] in data['message'] for cmd in settings_edits):
                if data['sender'] == data['target'][1:] or data['sender'] in bot.settings['mod_ids'].get('twitch', []):
                    reply_text = self.change_settings(channel_settings, data['target'], data['message'])
                    if not reply_text:
                        continue
                    log_str = "{time}: {sender} in {channel}: {reply_text}".format(
                        time=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), sender=self.nickname,
                        channel=data['target'], reply_text=reply_text)
                    bot.log.info(log_str)
                    self.send_reply(data['target'], reply_text)
                    continue
            if not channel_settings['active']:
                continue
            if channel_settings['mention']:
                if "@{}".format(self.nickname.lower()) not in data['message'].lower():
                    continue
            if data['message'].lower().startswith(tuple([a + "join" for a in prefix])):
                self.join_chan(data['sender'])
                reply_text = "@{} Joined your channel!".format(data['sender'])
                self.send_reply(data['target'], reply_text)
                continue
            if "#" + data['sender'].lower() == data['target'] and data['message'].lower().startswith(tuple([a + "leave" for a in prefix])):
                self.leave_chan(data['target'])
                continue
            command = bot.uses_command(data['message'])
            if not command:
                continue
            log_str = "{time}: {sender} in {channel} [{command}]: {reply_text}".format(
                time=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), sender=data['sender'],
                channel=data['target'], command=command, reply_text=data['message'])
            bot.log.info(log_str)
            attrs = {'bot': bot,
                     'screen_name': data['sender'],
                     'twitch_id': data['sender'],
                     'command': command,
                     'message': data['message'],
                     'raw_data': response
                    }
            ctx = UserContext(**attrs)
            if not bot.check_rate_limit(ctx.user_id, or_seconds=120, or_per_user=5):
                continue
            if command in ["mywaifu", "myhusbando"]:
                if not ctx.user_ids.get('twitter', False):
                    # Don't have a Twitter account linked
                    reply_text = create_token(data['sender'], data['sender'], bot.source.name)
                    reply_text = "/w {} ".format(data['sender']) + reply_text
                    self.send_reply(data['target'], reply_text.replace("\n", "  "))
                    self.send_reply(data['target'], "@{} Check your Twitch whispers to link your account!".format(data['sender']))
                    continue
            reply_text, reply_media = bot.on_command(ctx)
            bot.commands_used[ctx.command] += 1
            reply_text = "@{} {}".format(data['sender'], reply_text)
            if isinstance(reply_media, list):
                reply_text += " " + ' '.join(reply_media)
            log_str = "{time}: {sender} in {channel} [{command}]: {reply_text}".format(
                time=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), sender=self.nickname,
                channel=data['target'], command=command, reply_text=reply_text)
            bot.log.info(log_str)
            self.send_reply(data['target'], reply_text)

    def send_reply(self, channel, reply_text):
        self.s.send("PRIVMSG {} :{}\r\n".format(channel, reply_text.replace("\n", "  ")).encode())


if __name__ == "__main__":
    twitch_bot = TwitchBot()
    twitch_bot.main_loop()

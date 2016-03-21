import sys
sys.path.append('..')
from collections import OrderedDict
from itertools import islice
import datetime
import aiohttp
import asyncio
import string
import random
import time
import json
import re
import os

from functions import (config_save, config_get, config_add_section,
                       config_save_2, config_delete_key,
                       config_delete_section, config_get_section_items,
                       random_list, waifu, mywaifu, otp)
from config import discord_settings
from utils import printf as print  # To make sure debug printing won't brake
from utils import get_command

import feedparser
import discord

import logging

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log',
                              encoding='utf-8', mode='w')
handler.setFormatter(
    logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


__program__ = "AcePictureBot For Discord"
__version__ = "1.2.0"

client = discord.Client()
# Commands not allowed to use while through discord.
NO_DISCORD_CMDS = ["Source", "DelLimits",
                   "SetBirthday", "Spoiler",
                   "DiscordConnect", "DiscordJoin",
                   "Airing"]

# Commands that will be added later.
LATER_DISCORD_CMDS = ["WaifuRemove", "HusbandoRemove",
                      "!Level"]

RATE_LIMIT_DICT = {}
CHANNEL_TIMEOUT = {}
USER_LAST_COMMAND = OrderedDict()
# TODO: Add AceAnimatedBot when it works on TwitterRSS
BOT_ACCS = ["AcePictureBot", "AceEcchiBot", "AceYuriBot", "AceYaoiBot",
            "AceNSFWBot", "AceCatgirlBot", "AceAsianBot", "AceYuriNSFWBot",
            "AceStatusBot"]
BOT_ACCS = [x.lower() for x in BOT_ACCS]
BOT_ACCS_STR = ["!apb " + x for x in BOT_ACCS]


def get_twitter_id(discord_id):
    acc_list = open(discord_settings['acc_file'], 'r').read().splitlines()
    for acc in acc_list:
        # acc[0] Twitter | acc[1] Discord ID
        acc = acc.split("||")
        if discord_id.lower() == acc[1].lower():
            return acc[0]
    return "Not Found!"


async def create_twitter_token(user):
    ran = ''.join(random.choice(
        string.ascii_lowercase + string.digits) for _ in range(5))
    file_with_id = os.path.join(discord_settings['token_loc'], ran + '.txt')
    if os.path.isfile(file_with_id):
        pass
    else:
        open(file_with_id, 'w').write(user.id)
    msg = "Link your account by tweeting to http://twitter.com/AcePictureBot"\
          "\n@AcePictureBot DiscordConnect " + ran

    await client.send_message(user, msg)


async def say_welcome_message(server=False, message=False):
    """Called when server joined or first message.

    Set up default server settings.
    :param server: Discord.Server object.
    :param message: Discord.Message object if called from on_message().
    """
    if not message:
        for channel in server.channels:
            if channel.is_default:
                if channel.is_private:
                    return
                break
    elif message.channel.is_private:
        return
    else:
        server = message.server
        channel = message.channel
    config_add_section(server.id,
                       discord_settings['server_settings'])
    to_add = {'active': 'True',
              'allow_images': 'True',
              'must_mention': 'False',
              'rate_limit_level': '1',
              'ignore_channels': '',
              'mywaifu': 'True',
              'mods': str(server.owner.id)}
    config_save_2(to_add, section=server.id,
                  file=discord_settings['server_settings'])
    msg = """Hello, my name is AcePictureBot!
You can use over 10 commands including: Waifu, Shipgirl, OTP and many more!
To start simply say: "Waifu"!
For many more commands read: http://ace3df.github.io/AcePictureBot/commands/

Don't forget to cheak out all the Ace Bots on Twitter:
https://twitter.com/AcePictureBot

Feel free to support the Dev:
http://ace3df.github.io/AcePictureBot/donate/

{0} you should read this for a list of mod only commands:
https://gist.github.com/ace3df/cd8e233fe9fe796d297d
If you don't want this bot in your server - simply kick it.
""".format(server.owner.mention)
    await client.send_message(channel, msg)


async def inv_from_cmd():
    """Check a folder for new invites."""
    # TODO: use better function name
    await client.wait_until_ready()
    while not client.is_closed:
        for inv_file in os.listdir(discord_settings['invites_loc']):
            if inv_file.endswith(".txt"):
                inv_file_clean = inv_file.split(".txt")[0]
                try:
                    await client.accept_invite(inv_file_clean)
                except:
                    # NotFound
                    pass
                os.remove(os.path.join(discord_settings['invites_loc'],
                                       inv_file))
        await asyncio.sleep(10)


async def change_game():
    """Change the accounts game to text that shows tips."""
    # TODO: Test around with spacing and think of better ones
    tips_list = ["Help: !apb help"]
    list_cmds = ["Shipgirl", "Touhou", "Vocaloid",
                 "Imouto", "Idol", "Shota",
                 "Onii-chan", "Onee-chan", "Sensei",
                 "Monstergirl", "Witchgirl", "Tankgirl",
                 "Senpai", "Kouhai"]
    for cmd in list_cmds:
        tips_list.append("Try using: " + cmd)
    await client.wait_until_ready()
    while not client.is_closed:
        await client.change_status(game=discord.Game(
            name=random.choice(tips_list)),
            idle=False)
        await asyncio.sleep(240)


async def timeout_channel():
    """Check if the bot has talkined in each server in the last 4 days."""
    await client.wait_until_ready()
    while not client.is_closed:
        current_time = time.time()
        current_server_list = client.servers
        for server in current_server_list:
            if server.id == "81515992412327936":
                # Don't timeout own channel
                continue
            if server.id in CHANNEL_TIMEOUT:
                if current_time - CHANNEL_TIMEOUT[server.id] > 345600:
                    client.leave_server(server.id)
            else:
                CHANNEL_TIMEOUT[server.id] = time.time()
        await asyncio.sleep(360)


async def rss_twitter():
    """Check servers to see if they want a bot to post into their server."""
    await client.wait_until_ready()
    RSS_URL = r"http://rss.acebot.xyz/"
    while not client.is_closed:
        current_server_list = client.servers
        for bot in BOT_ACCS:
            url = RSS_URL + bot + ".xml"
            with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    assert response.status == 200
                    text = await response.read()
            d = feedparser.parse(text)
            try:
                matches = re.search('src="([^"]+)"',
                                    d.entries[0].description)
            except:
                # TODO: Need to fix this on the RSS site side
                continue
            if not matches:
                # No image URL found / Custom text only tweet
                continue
            image_url = matches.group(0)[4:].replace("\"", "")
            print(image_url)
            message = "New Tweet from {0}: {1}"\
                .format(d.entries[0].summary_detail['value'].split(":")[0],
                        d.entries[0].guid)
            img_file_name = ''.join(
                random.choice('abcdefg0123456') for _ in range(6))\
                + '.jpg'
            img_file = open(img_file_name, 'wb')
            with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    assert response.status == 200
                    with open(img_file_name, 'wb') as fd:
                        while True:
                            chunk = await response.content.read()
                            if not chunk:
                                break
                            fd.write(chunk)
            img_file.close()
            if os.stat(img_file_name).st_size == 0:
                # Image failed to download, delete and continue on
                # TODO: Find out why this happens
                os.remove(img_file_name)
                continue
            for server in current_server_list:
                server_settings = config_get_section_items(
                    server.id, discord_settings['server_settings'])
                if not server_settings:
                    # Haven't setup server yet
                    continue
                chan = config_get(
                    server.id, bot,
                    discord_settings['server_settings'])
                if not chan:
                    # They don't use this bot
                    continue
                chan, last_id = chan.split("||")
                if last_id == d.entries[0].guid:
                    # Already posted latest entry
                    continue
                chan_obj = client.get_channel(chan)
                if chan_obj is None:
                    # Channel not found
                    config_delete_key(
                        server.id, bot,
                        discord_settings['server_settings'])
                    continue
                await client.send_file(chan_obj, open(img_file_name, 'rb'),
                                       content=message)
                to_string = "{0}||{1}".format(chan, d.entries[0].guid)
                config_save(server.id, bot,
                            to_string, discord_settings['server_settings'])
            os.remove(img_file_name)
        await asyncio.sleep(360)


@client.event
async def on_server_remove(server):
    """Called when kicked or left the server.

    Remove the server from server_settings.ini
    :param server: Discord.Server object.
    """
    config_delete_section(server.id, discord_settings['server_settings'])
    print("$ Left server: {} ({})".format(server, server.id))


@client.event
async def on_server_join(server):
    """Called when joined a server.

    Set up the default settings and say joined message.
    :param server: Discord.Server object.
    """
    server_settings = config_get_section_items(
        server.id,
        discord_settings['server_settings'])
    if server_settings:
        # Have already been in server and have saved settings.
        return
    await say_welcome_message(server)


@client.event
async def on_message(message):
    """Called when a message is said on any connected server.

    Process the message to see if they use a command or are rate limited.
    :param message: Discord.Message object.
    """
    global USER_LAST_COMMAND
    if message.server is None:
        # Private message
        # Default settings
        server_settings = {'active': 'True',
                           'allow_images': 'True',
                           'must_mention': 'False',
                           'rate_limit_level': '1',
                           'ignore_channels': '',
                           'mywaifu': 'True',
                           'mods': ''}
        try:
            await client.accept_invite(message.content)
            await client.send_message(message.channel, "Joined!")
            return
        except:
            # Invalid invite or not a invite at all
            # Send basic help message.
            if "help" in message.content[0:10]:
                await client.send_message(
                    message.channel,
                    """Commands: http://ace3df.github.io/AcePictureBot/commands/
Mod Commands: https://gist.github.com/ace3df/cd8e233fe9fe796d297d""")
                return
            elif "!apb" in message.content[0:10]:
                await client.send_message(
                    message.channel,
                    """You can only use the other !apb commands in servers!""")
                return

    if message.author == client.user:
        # Print own bot messages.
        if message.server is None:
            print("PM | {} ({}) - {}".format(message.author,
                                             message.author.id,
                                             message.content))
        else:
            print("{} ({}) | {} ({}) - {}".format(message.server,
                                                  message.server.id,
                                                  message.author,
                                                  message.author.id,
                                                  message.content))
        return
    if message.server is not None:
        # Server settings of where the message was sent from.
        server_settings = config_get_section_items(
            message.server.id,
            discord_settings['server_settings'])
        if not server_settings:
            # Joined and haven't been able to complete say_welcome_message().
            await say_welcome_message(False, message)
            server_settings = config_get_section_items(
                message.server.id,
                discord_settings['server_settings'])

    if message.content.startswith("!apb help"):
        # Send basic help message.
        await client.send_message(
            message.channel,
            """Commands: http://ace3df.github.io/AcePictureBot/commands/
Mod Commands: https://gist.github.com/ace3df/cd8e233fe9fe796d297d""")
        return

    if message.author.id in server_settings['mods'].split(", "):
        edit_result = False
        if message.content.startswith("!apb ids"):
            # Debug IDs.
            msg = """Server ID: {0.server.id}
Current Channel ID: {0.channel.id}""".format(message)
            await client.send_message(message.channel, msg)
            return

        if message.content.startswith("!apb turn on"):
            # Turn on the bot in the server (DEFAULT).
            edit_result = "True"
            edit_section = "active"
            msg = "The bot will now respond to commands!"
        elif message.content.startswith("!apb turn off"):
            # Turn off the bot in the server.
            edit_result = "False"
            edit_section = "active"
            msg = "The bot will now ignore commands!"

        if message.content.startswith("!apb images on"):
            # Try and post an image along side commands (DEFAULT).
            edit_result = "True"
            edit_section = "allow_images"
            msg = "If possible an image will be posted along side commands!"
        elif message.content.startswith("!apb images off"):
            # Don't post images along side commands.
            edit_result = "False"
            edit_section = "allow_images"
            msg = "No image will be posted when using commands!"

        if message.content.lower().startswith(tuple(BOT_ACCS_STR)):
            # TODO: Clean up the msg stuff here it looks ugly posted.
            matched_bots = [s for s in BOT_ACCS if s in message.content][0]
            current_channel = config_get(
                message.server.id, matched_bots,
                discord_settings['server_settings'])
            if current_channel:
                current_channel = current_channel.split("||")[0]
            if not message.channel_mentions:
                # Didn't mention any channels
                msg = "Please metion a single channel for this bot to post in!"
                msg = '{0.author.mention} {1}'.format(message, msg)
                await client.send_message(message.channel, msg)
                return
            for channel in message.channel_mentions:
                if channel.id == current_channel:
                    # Already in this channel, remove
                    config_delete_key(message.server.id,
                                      matched_bots,
                                      discord_settings['server_settings'])
                    msg = "Removed the bot {} from posting in #{}"\
                        .format(matched_bots.title(), channel.name)
                    msg = '{0} {1.author.mention}'.format(msg, message)
                    await client.send_message(message.channel, msg)
                    return
                else:
                    config_save(message.server.id,
                                matched_bots,
                                message.channel.id + "||temp",
                                discord_settings['server_settings'])
                    msg = "I will now post {}'s Tweets into the channel #{}"\
                        .format(matched_bots.title(), channel.name)
                    msg = '{0} {1.author.mention}'.format(msg, message)
                    await client.send_message(message.channel, msg)
                    return

        if message.content.startswith("!apb mywaifu on"):
            # Allow a user to use MyWaifu/Husbando in their chat (DEFAULT).
            edit_result = "True"
            edit_section = "mywaifu"
            msg = "Users can now use MyWaifu and MyHusbando!"
        elif message.content.startswith("!apb mywaifu off"):
            # Don't post images along side commands.
            edit_result = "False"
            edit_section = "mywaifu"
            msg = "Users can't use use MyWaifu and MyHusbando!"

        if message.content.startswith("!apb mention on"):
            # They will have to mentiont he bot to use a command.
            edit_result = "True"
            edit_section = "must_mention"
            msg = "You will now have to mention the bot to use a command!"
        elif message.content.startswith("!apb mention off"):
            # They do NOT have to mentiont he bot to use a command (DEFAULT).
            edit_result = "False"
            edit_section = "must_mention"
            msg = "You can use commands without mentioning me!"


        # ADD BOTS ADD HERE

        if message.content.startswith("!apb rate limit"):
            # Change the level of users rate limits (Per User).
            # 1 = 10 Commands in 2 Minutes (DEFAULT).
            # 2 = 5 Commands in 2 Minutes.
            # 3 = 2 Commands in 1 Minute.
            # Higher than 3 defaults to 3 - Lower defaults to 1.
            num = [int(s) for s in message.content.split() if s.isdigit()]
            if not num:
                msg = """You didn't include a level number (1 - 3)!
Per User:
1 = 10 Commands in 2 Minutes.
2 = 5 Commands in 2 Minutes.
3 = 2 Commands in 1 Minute."""
                await client.send_message(message.channel, msg)
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
                msg = "10 Commands in 2 Minutes (per user)."
            elif num == 2:
                msg = "5 Commands in 2 Minutes (per user)."
            elif num == 3:
                msg = "2 Commands in 1 Minutes (per user)."
            msg = "Rate Limit changed to:\n" + msg

        if edit_result:
            config_save(message.server.id,
                             edit_section, str(edit_result),
                             discord_settings['server_settings'])
            msg = '{0} {1.author.mention}'.format(msg, message)
            await client.send_message(message.channel, msg)
            return

        if message.content.startswith("!apb mods add"):
            if message.author.id != message.server.owner.id:
                return
            # Get all mentions in message and add to mod list.
            current_mod_list = config_get(
                message.server.id, 'mods', discord_settings['server_settings'])
            current_mod_list = current_mod_list.split(", ")
            for user in message.mentions:
                if user.id == message.server.owner.id:
                    # Can't remove yourself
                    continue
                if user.id in current_mod_list:
                    continue
                else:
                    current_mod_list.append(user.id)
            config_save(message.server.id,
                             'mods',
                             ', '.join(current_mod_list),
                             discord_settings['server_settings'])

            await client.send_message(message.channel, "Mods added!")
            return
        elif message.content.startswith("!apb mods remove"):
            if message.author.id != message.server.owner.id:
                return
            # Remove all mods mentioned.
            current_mod_list = config_get(
                message.server.id, 'mods',
                discord_settings['server_settings'])
            current_mod_list = current_mod_list.split(", ")
            for user in message.mentions:
                if user.id == message.server.owner.id:
                    # Can't remove yourself
                    continue
                if user.id in current_mod_list:
                    current_mod_list.remove(user.id)
            config_save(message.server.id,
                             'mods',
                             ', '.join(current_mod_list),
                             discord_settings['server_settings'])

            await client.send_message(message.channel, "Mods removed!")
            return

        if message.content.startswith("!apb channels add"):
            # Add a channel to the ignore list.
            current_ignore_list = config_get(
                message.server.id, 'ignore_channels',
                discord_settings['server_settings'])
            current_ignore_list = current_ignore_list.split(", ")
            channel_text = []
            for channel in message.channel_mentions:
                if channel.id in current_ignore_list:
                    continue
                else:
                    channel_text.append("#" + channel.name)
                    current_ignore_list.append(channel.id)
            config_save(message.server.id,
                             'ignore_channels',
                             ', '.join(current_ignore_list),
                             discord_settings['server_settings'])
            if not channel_text:
                msg = "No such channels or already ignoring these channels!"
            else:
                msg = "The bot will now ignore the channels: {}".format(
                    ' '.join(channel_text))
            await client.send_message(message.channel, msg)
            return
        elif message.content.startswith("!apb channels remove"):
            # Remove all mods mentioned.
            current_ignore_list = config_get(
                message.server.id,
                'ignore_channels',
                discord_settings['server_settings'])
            current_ignore_list = current_ignore_list.split(", ")
            channel_text = []
            for channel in message.channel_mentions:
                if channel.id in current_ignore_list:
                    channel_text.append("#" + channel.name)
                    current_ignore_list.remove(channel.id)
            config_save(message.server.id,
                             'ignore_channels',
                             ', '.join(current_ignore_list),
                             discord_settings['server_settings'])
            if not channel_text:
                msg = "No such channels or already not ignoring these channels!"
            else:
                msg = "The bot will now not ignore the channels: {}".format(
                    ' '.join(channel_text))
            await client.send_message(message.channel, msg)
            return

    if server_settings['active'] == "False":
        return

    if message.channel.id in server_settings['ignore_channels']:
        return

    if server_settings['must_mention'] == "True":
        is_in = False
        for user in message.mentions:
            if "acepicturebot" in user.name.lower():
                is_in = True
        if not is_in:
            return

    msg = message.content.replace("🚢👧", "Shipgirl")
    msg = ' '.join(re.sub('(^|\n| )(@[A-Za-z0-9_🚢👧.]+)',
                          ' ', msg).split())
    msg = msg.replace("#", "")

    # Find the command they used.
    command = get_command(msg)
    if not command:
        # No command was used - ignore.
        return
    if command in NO_DISCORD_CMDS:
        # Completely ignore these.
        return
    if message.server is None:
        print("PM | {} ({}) - {}".format(message.author,
                                         message.author.id,
                                         message.content))
    else:
        print("{} ({}) | {} ({}) - {}".format(message.server,
                                              message.server.id,
                                              message.author,
                                              message.author.id,
                                              message.content))
    # Refreash the server's timeout.
    if message.server is not None:
        CHANNEL_TIMEOUT[message.server.id] = time.time()

    # Can't do anything about this for now.
    # TODO: Add these when possible.
    if command in LATER_DISCORD_CMDS:
        msg = r"""This command will be added when Discord finishes Twitter account linking.
For now you can only use {0} on Twitter!
http://twitter.com/acepicturebot""".format(command)
        msg = '{0} {1.author.mention}'.format(msg, message)
        await client.send_message(message.channel, msg)
        return

    if command == "Reroll":
        try:
            command = USER_LAST_COMMAND[message.author.id]
        except (ValueError, KeyError):
            return
    else:
        USER_LAST_COMMAND[message.author.id] = command
        if len(USER_LAST_COMMAND) > 30:
            USER_LAST_COMMAND = (OrderedDict(
                islice(USER_LAST_COMMAND.items(),
                       20, None)))

    # Stop someone limiting the bot on their own.
    rate_time = datetime.datetime.now()
    if server_settings['rate_limit_level'] == "1":
        rate_limit_commands = 10
        rate_limit_secs = 120
    elif server_settings['rate_limit_level'] == "2":
        rate_limit_commands = 5
        rate_limit_secs = 120
    elif server_settings['rate_limit_level'] == "3":
        rate_limit_commands = 2
        rate_limit_secs = 60
    if message.author.id in RATE_LIMIT_DICT:
        # User is now limited (3 hours).
        if ((rate_time - RATE_LIMIT_DICT[message.author.id][0])
                .total_seconds() < rate_limit_secs)\
           and (RATE_LIMIT_DICT[message.author.id][1] >= rate_limit_commands):
            return
        # User limit is over.
        elif ((rate_time - RATE_LIMIT_DICT[message.author.id][0])
                .total_seconds() > rate_limit_secs):
            del RATE_LIMIT_DICT[message.author.id]
        else:
            # User found, not limited, add one to the trigger count.
            RATE_LIMIT_DICT[message.author.id][1] += 1
    else:
        # User not found, add them to RATE_LIMIT_DICT.
        # Before that quickly go through RATE_LIMIT_DICT
        # and remove all the finished unused users.
        for person in list(RATE_LIMIT_DICT):
            if ((rate_time - RATE_LIMIT_DICT[person][0])
               .total_seconds() > rate_limit_secs):
                del RATE_LIMIT_DICT[person]
        RATE_LIMIT_DICT[message.author.id] = [rate_time, 1]

    msg = msg.lower().replace(command.lower(), " ", 1).strip()
    discord_image = False

    # Main Commands
    if command == "Waifu":
        msg, discord_image = waifu(0, msg, DISCORD=True)
    elif command == "Husbando":
        msg, discord_image = waifu(1, msg, DISCORD=True)

    if command == "WaifuRegister" or command == "HusbandoRegister":
        msg = "You can only register on Twitter! "\
              "http://twitter.com/AcePictureBot"

    if command == "MyWaifu" or command == "MyHusbando":
        if message.server is None:
            pass
        if server_settings.get('mywaifu', 'True') == "False":
            return
        if command == "MyWaifu":
            gender = "Waifu"
        else:
            gender = "Husbando"
        twitter_id = get_twitter_id(message.author.id)
        if twitter_id == "Not Found!":
            msg = "Couldn't find your {gender}! "\
                  "Register your {gender} on Twitter "\
                  "(Follow: http://ace3df.github.io/AcePictureBot/commands/) "\
                  "and then link your account using the ID that has been PM'd"\
                  " to you!".format(gender=gender)
            await client.send_message(message.channel, msg)
            await create_twitter_token(message.author)
            return
        else:
            # Legit id
            if command == "MyWaifu":
                gender_id = 0
            else:
                gender_id = 1
            skip_dups = False
            if "my{gender}+".format(gender=gender.lower()) in message.content.lower():
                skip_dups = True
            if "my{gender}-".format(gender=gender.lower()) in message.content.lower():
                delete_used_imgs(twitter_id, True)
            msg, discord_image = mywaifu(twitter_id, gender_id,
                                              True, skip_dups)
            if "I don't know" in msg:
                msg = "Couldn't find your {gender}! "\
                      "Register your {gender} on Twitter "\
                      "(Follow: http://ace3df.github.io/AcePictureBot/commands/)".format(gender=gender)
            elif not discord_image or discord_image is None:
                msg = "Sorry failed to get a new image! "\
                      "Use the command on Twitter to help the bot store "\
                      "more images! You can also use My{gender}+ to skip "\
                      "checking for an already "\
                      "used image or My{gender}- to start from fresh!".format(gender=gender)
            else:
                msg = ' '.join(re.sub("(#[A-Za-z0-9]+)", " ", msg).split())
                msg = "{0.author.mention}'s {1}".format(message, msg)
                # TODO: Clean this up
                if server_settings['allow_images'] and discord_image:
                    try:
                        await client.send_file(message.channel,
                                               open(discord_image, 'rb'),
                                               content=msg)
                    except:
                        # discord.errors.Forbidden ?
                        # Channel doesn't allow image uploading
                        try:
                            await client.send_message(message.channel, msg)
                        except:
                            # discord.errors.Forbidden ?
                            pass
                        pass
                else:
                    try:
                        await client.send_message(message.channel, msg)
                    except:
                        # discord.errors.Forbidden ?
                        pass
                return

    if command == "OTP":
        msg, discord_image = otp(msg)

    list_cmds = ["Shipgirl", "Touhou", "Vocaloid",
                 "Imouto", "Idol", "Shota",
                 "Onii", "Onee", "Sensei",
                 "Monstergirl", "Witchgirl", "Tankgirl",
                 "Senpai", "Kouhai"]
    if command in list_cmds:
        msg, discord_image = random_list(command, msg, DISCORD=True)

    # Remove hashtags
    msg = ' '.join(re.sub("(#[A-Za-z0-9]+)", " ", msg).split())
    msg = '{0} {1.author.mention}'.format(msg, message)
    # TODO: Clean this up
    if server_settings['allow_images'] and discord_image:
        try:
            await client.send_file(message.channel,
                                   open(discord_image, 'rb'),
                                   content=msg)
        except:
            # discord.errors.Forbidden ?
            # Channel doesn't allow image uploading
            try:
                await client.send_message(message.channel, msg)
            except:
                # discord.errors.Forbidden ?
                pass
            pass
    else:
        try:
            await client.send_message(message.channel, msg)
        except:
            # discord.errors.Forbidden ?
            pass


@client.event
async def on_ready():
    if not os.path.exists(discord_settings['server_settings']):
        open(discord_settings['server_settings'], "w")
    print("Logged in as")
    print(client.user.name)
    print("------------------")


loop = asyncio.get_event_loop()

try:
    loop.create_task(timeout_channel())
    loop.create_task(rss_twitter())
    loop.create_task(inv_from_cmd())
    loop.create_task(change_game())
    loop.run_until_complete(client.login(discord_settings['email'],
                                         discord_settings['password']))
    loop.run_until_complete(client.connect())
except Exception:
    loop.run_until_complete(client.close())
finally:
    loop.close()

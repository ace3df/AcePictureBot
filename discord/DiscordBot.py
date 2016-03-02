import sys
sys.path.append('..')
from collections import OrderedDict
from itertools import islice
import datetime
import asyncio
import time
import json
import re
import os

from config import discord_settings
from utils import printf as print  # To make sure debug printing won't brake
from utils import get_command
import functions as func

import discord

# start_private_message(user)
__program__ = "AcePictureBot For Discord"
__version__ = "1.0.2"

client = discord.Client()
# Commands not while using through discord.
NO_DISCORD_CMDS = ["Source", "DelLimits", "SetBirthday", "Spoiler"]
# Commands that will be added once Discord finishes Twitter linking
LATER_DISCORD_CMDS = ["WaifuRegister", "HusbandoRegister",
                      "MyWaifu", "MyHusbando",
                      "WaifuRemove", "HusbandoRemove",
                      "!Level"]

RATE_LIMIT_DICT = {}
CHANNEL_TIMEOUT = {}
USER_LAST_COMMAND = OrderedDict()


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
    func.config_add_section(server.id,
                            discord_settings['server_settings'])
    to_add = {'active': 'True',
              'allow_images': 'True',
              'must_mention': 'False',
              'rate_limit_level': '1',
              'ignore_channels': '',
              'mods': str(server.owner.id)}
    func.config_save_2(to_add, section=server.id,
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


async def timeout_channel():
    """Check if the bot has talkined in each server in the last 4 days."""
    await client.wait_until_ready()
    while not client.is_closed:
        current_time = time.time()
        for server in client.servers:
            if server.id == "81515992412327936":
                # Don't timeout own channel
                continue
            if server.id in CHANNEL_TIMEOUT:
                if current_time - CHANNEL_TIMEOUT[server.id] > 345600:
                    client.leave_server(server.id)
            else:
                CHANNEL_TIMEOUT[server.id] = time.time()
        await asyncio.sleep(360)


@client.event
async def on_server_remove(server):
    """Called when kicked or left the server.

    Remove the server from server_settings.ini
    :param server: Discord.Server object.
    """
    func.config_delete_section(server.id, discord_settings['server_settings'])
    print("$ Left server: {} ({})".format(server, server.id))


@client.event
async def on_server_join(server):
    """Called when joined a server.

    Set up the default settings and say joined message.
    :param server: Discord.Server object.
    """
    server_settings = func.config_get_section_items(
        server.id,
        discord_settings['server_settings'])
    if server_settings:
        # Have already been in server and have saved settings.
        return
    await say_welcome_message(server)


@client.event
async def on_error(event, *args, **kwargs):
    print(event)
    await asyncio.sleep(60)


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
                           'mods': ''}
        try:
            await client.accept_invite(message)
        except (discord.HTTPException, discord.InvalidArgument):
            # Invalid invite or not a invite at all
            pass

    if message.author == client.user:
        # Print own bot messages.
        print("{} ({}) | {} ({}) - {}".format(message.server,
                                              message.server.id,
                                              message.author,
                                              message.author.id,
                                              message.content))
        return
    if message.server is not None:
        # Server settings of where the message was sent from.
        server_settings = func.config_get_section_items(
            message.server.id,
            discord_settings['server_settings'])
        if not server_settings:
            # Joined and haven't been able to complete say_welcome_message().
            await say_welcome_message(False, message)
            server_settings = func.config_get_section_items(
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
            func.config_save(message.server.id,
                             edit_section, str(edit_result),
                             discord_settings['server_settings'])
            msg = '{0} {1.author.mention}'.format(msg, message)
            await client.send_message(message.channel, msg)
            return

        if message.content.startswith("!apb mods add"):
            if message.author.id != message.server.owner.id:
                return
            # Get all mentions in message and add to mod list.
            current_mod_list = func.config_get(
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
            func.config_save(message.server.id,
                             'mods',
                             ', '.join(current_mod_list),
                             discord_settings['server_settings'])

            await client.send_message(message.channel, "Mods added!")
            return
        elif message.content.startswith("!apb mods remove"):
            if message.author.id != message.server.owner.id:
                return
            # Remove all mods mentioned.
            current_mod_list = func.config_get(
                message.server.id, 'mods',
                discord_settings['server_settings'])
            current_mod_list = current_mod_list.split(", ")
            for user in message.mentions:
                if user.id == message.server.owner.id:
                    # Can't remove yourself
                    continue
                if user.id in current_mod_list:
                    current_mod_list.remove(user.id)
            func.config_save(message.server.id,
                             'mods',
                             ', '.join(current_mod_list),
                             discord_settings['server_settings'])

            await client.send_message(message.channel, "Mods removed!")
            return

        if message.content.startswith("!apb channels add"):
            # Add a channel to the ignore list.
            current_ignore_list = func.config_get(
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
            func.config_save(message.server.id,
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
            current_ignore_list = func.config_get(
                message.server.id,
                'ignore_channels',
                discord_settings['server_settings'])
            current_ignore_list = current_ignore_list.split(", ")
            channel_text = []
            for channel in message.channel_mentions:
                if channel.id in current_ignore_list:
                    channel_text.append("#" + channel.name)
                    current_ignore_list.remove(channel.id)
            func.config_save(message.server.id,
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
    print("{} ({}) | {} ({}) - {}".format(message.server, message.server.id,
                                          message.author, message.author.id,
                                          message.content))
    # Refreash the server's timeout.
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
        msg, discord_image = func.waifu(0, msg, DISCORD=True)
    elif command == "Husbando":
        msg, discord_image = func.waifu(1, msg, DISCORD=True)

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
    msg = '{0} {1.author.mention}'.format(msg, message)
    try:
        await client.send_message(message.channel, msg)
    except:
        # discord.errors.Forbidden ?
        pass

    if server_settings['allow_images'] and discord_image:
        try:
            await client.send_file(message.channel, open(discord_image, 'rb'))
        except:
            # discord.errors.Forbidden ?
            # Channel doesn't allow image uploading
            pass


@client.event
async def on_ready():
    if not os.path.exists(discord_settings['server_settings']):
        open(discord_settings['server_settings'], "w")
    print("Logged in as")
    print(client.user.name)
    print("------------------")

loop = asyncio.get_event_loop()
loop.create_task(timeout_channel())
loop.run_until_complete(client.run(discord_settings['email'],
                                   discord_settings['password']))

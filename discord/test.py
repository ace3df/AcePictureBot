import sys
sys.path.append('..')
from utils import get_command
from config import discord_settings
from collections import OrderedDict
import functions as func
import json
import datetime
import discord
import re

client = discord.Client()
# Commands not allowed through discord.
NO_DISCORD_CMDS = ["WaifuRegister", "HusbandoRegister",
                   "MyWaifu", "MyHusbando",
                   "WaifuRemove", "HusbandoRemove",
                   "Level"]
RATE_LIMIT_DICT = {}
USER_LAST_COMMAND = OrderedDict()


@client.event
async def on_message(message):
    global USER_LAST_COMMAND

    if message.author == client.user:
        return
    server_settings = func.config_get_section_items(
        str(message.server).lower(),
        discord_settings['server_settings'])
    if str(message.author).lower() in server_settings['mods'].split(", "):
        if "!apb turn off" in message.content:
            if server_settings['turned_on']:
                func.config_save(str(message.server).lower(),
                                 'turned_on', "False",
                                 discord_settings['server_settings'])
        if "!apb turn on" in message.content:
            if not server_settings['turned_on']:
                func.config_save(str(message.server).lower(),
                                 'turned_on', "True",
                                 discord_settings['server_settings'])

        if "!apb images off" in message.content:
            if server_settings['allow_imgs']:
                func.config_save(str(message.server).lower(),
                                 'allow_imgs', "False",
                                 discord_settings['server_settings'])
        if "!apb images on" in message.content:
            if not server_settings['allow_imgs']:
                func.config_save(str(message.server).lower(),
                                 'allow_imgs', "True",
                                 discord_settings['server_settings'])

    if server_settings['turned_on'] == "False":
        return

    msg = message.content.replace("🚢👧", "Shipgirl")
    msg = ' '.join(re.sub('(^|\n| )(@[A-Za-z0-9_🚢👧.]+)',
                          ' ', msg).split())
    msg = msg.replace("#", "")

    # Find the command they used.
    command = get_command(msg)
    if command in NO_DISCORD_CMDS:
        msg = r"You can only use {0} on Twitter" \
            " - http://twitter.com/acepicturebot".format(command)
        msg = '{0} {1.author.mention}'.format(msg, message)
        await client.send_message(message.channel, msg)
        return

    if command == "Reroll":
        try:
            command = USER_LAST_COMMAND[message.author]
        except (ValueError, KeyError):
            return
    else:
        USER_LAST_COMMAND[message.author] = command
        if len(USER_LAST_COMMAND) > 30:
            USER_LAST_COMMAND = (OrderedDict(
                islice(USER_LAST_COMMAND.items(),
                       20, None)))

    # Stop someone limiting the bot on their own.
    rate_time = datetime.datetime.now()
    rate_limit_secs = 10800
    if message.author in RATE_LIMIT_DICT:
        # User is now limited (3 hours).
        if ((rate_time - RATE_LIMIT_DICT[message.author][0])
                .total_seconds() < rate_limit_secs)\
           and (RATE_LIMIT_DICT[message.author][1] >= 15):
            return False, False
        # User limit is over.
        elif ((rate_time - RATE_LIMIT_DICT[message.author][0])
                .total_seconds() > rate_limit_secs):
            del RATE_LIMIT_DICT[message.author]
        else:
            # User found, not limited, add one to the trigger count.
            RATE_LIMIT_DICT[message.author][1] += 1
    else:
        # User not found, add them to RATE_LIMIT_DICT.
        # Before that quickly go through RATE_LIMIT_DICT
        # and remove all the finished unused users.
        for person in list(RATE_LIMIT_DICT):
            if ((rate_time - RATE_LIMIT_DICT[person][0])
               .total_seconds() > rate_limit_secs):
                del RATE_LIMIT_DICT[person]
        RATE_LIMIT_DICT[message.author] = [rate_time, 1]

    # This shouldn't happen but just in case.
    if not isinstance(command, str):
        return

    msg = msg.lower().replace(command.lower(), " ", 1).strip()

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

    msg = '{0} {1.author.mention}'.format(msg, message)
    await client.send_message(message.channel, msg)
    if server_settings['allow_imgs'] and discord_image:
        await client.send_file(message.channel, open(discord_image, 'rb'))


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print('------')

client.run(discord_settings['email'], discord_settings['password'])

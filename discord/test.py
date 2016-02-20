import sys
sys.path.append('..')
from utils import get_command
from utils import printf as print
from config import discord_settings
from itertools import islice
from collections import OrderedDict
import functions as func
import time
import json
import datetime
import asyncio
import discord
import re


client = discord.Client()
# Commands not allowed through discord.
NO_DISCORD_CMDS = ["!Level", "Source", "DelLimits",
                   "SetBirthday", "Spoiler"]
# Commands that will be added once Discord finishes Twitter link
LATER_DISCORD_CMDS = ["WaifuRegister", "HusbandoRegister",
                      "MyWaifu", "MyHusbando",
                      "WaifuRemove", "HusbandoRemove"]
RATE_LIMIT_DICT = {}
USER_LAST_COMMAND = OrderedDict()
CHANNEL_TIMEOUT = {}

# TODO: Check if in a channel that the bot can speak in before doing anything
# TODO: Record down server.id been in (simple text list)
# TODO: If new server show welcome message on first join
# in #general only if possible
# if it's not possible do it on first message on another channel
# TODO: Make settings to ignore text channels

async def timeout_channel():
    # If no bot activity in the server for a whole 3 days it will disconnect.
    await client.wait_until_ready()
    while not client.is_closed:
        current_time = time.time()
        for chan in client.servers:
            if chan.id in CHANNEL_TIMEOUT:
                if current_time - CHANNEL_TIMEOUT[chan.id] > 259200:
                    client.leave_server(chan)
            else:
                CHANNEL_TIMEOUT[chan.id] = time.time()
        await asyncio.sleep(360)


@client.event
async def on_message(message):
    global USER_LAST_COMMAND
    if message.author == client.user:
        print("{} ({}) | {} ({}) - {}".format(message.server,
                                              message.server.id,
                                              message.author,
                                              message.author.id,
                                              message.content))
        await

    server_settings = func.config_get_section_items(message.server.id,
                                                    discord_settings['server_settings'])
    if not server_settings:
        # Joined a new server!
        # Save default settings and send welcome message.
        func.config_add_section(message.server.id,
                                discord_settings['server_settings'])
        func.config_save(message.server.id, "turned_on",
                         "True", discord_settings['server_settings'])
        func.config_save(message.server.id, "allow_imgs",
                         "True", discord_settings['server_settings'])
        func.config_save(message.server.id, "must_mention",
                         "False", discord_settings['server_settings'])
        func.config_save(message.server.id, "mods",
                         "81515803085639680, " + str(message.server.owner.id),
                         discord_settings['server_settings'])
        server_settings = func.config_get_section_items(
            message.server.id,
            discord_settings['server_settings'])
        msg = """Hello, my name is AcePictureBot!
You can use over 10 commands including: Waifu, Shipgirl, OTP and many more!
To start simply say: "Waifu"!
For many more commands read: http://ace3df.github.io/AcePictureBot/commands/
Don't forget to cheak out all the Ace Bots on Twitter:
https://twitter.com/AcePictureBot
@{0.server.owner} you should read this for a list of mod only commands:
https://gist.github.com/ace3df/cd8e233fe9fe796d297d
If you don't want this bot in your server - simply kick it.
""".format(message)
        await client.send_message(message.channel, msg)

    if str(message.author.id) in server_settings['mods'].split(", "):
        if "!apb server id" in message.content:
            await client.send_message(
                message.channel, message.server.id)
        if "!apb turn off" in message.content:
            if server_settings['turned_on'] == "True":
                func.config_save(message.server.id,
                                 'turned_on', "False",
                                 discord_settings['server_settings'])
                await client.send_message(
                    message.channel, "I will now ignore commands!")

        if "!apb turn on" in message.content:
            if server_settings['turned_on'] == "False":
                func.config_save(message.server.id,
                                 'turned_on', "True",
                                 discord_settings['server_settings'])
                await client.send_message(
                    message.channel, "I will now run commands!")

        if "!apb images off" in message.content:
            if server_settings['allow_imgs'] == "True":
                func.config_save(message.server.id,
                                 'allow_imgs', "False",
                                 discord_settings['server_settings'])
                await client.send_message(
                    message.channel,
                    "No image will be posted when using commands!")
        if "!apb images on" in message.content:
            if server_settings['allow_imgs'] == "False":
                func.config_save(message.server.id,
                                 'allow_imgs', "True",
                                 discord_settings['server_settings'])
                await client.send_message(
                    message.channel,
                    "If possible an image will be posted when using commands!")

        if "!apb mentions off" in message.content:
            if server_settings['must_mention'] == "True":
                func.config_save(message.server.id,
                                 'must_mention', "False",
                                 discord_settings['server_settings'])
                await client.send_message(message.channel,
                                          "You can use commands without mentioning me!")
        if "!apb mentions on" in message.content:
            if server_settings['must_mention'] == "False":
                func.config_save(message.server.id,
                                 'must_mention', "True",
                                 discord_settings['server_settings'])
                await client.send_message(message.channel,
                                          "You will now have to mention the bot to use a command!")

        if "!apb mods remove" in message.content:
                current_mod_list = func.config_get(message.server.id, 'mods',
                                                   discord_settings['server_settings'])
                current_mod_list = current_mod_list.split(", ")
                for user in message.mentions:
                    if user.id == message.server.owner.id:
                        # Can't remove yourself
                        continue
                    if str(user.id) in current_mod_list:
                        current_mod_list.remove(str(user.id))
                if len(current_mod_list) < 2:
                    current_mod_list = ', '.join(current_mod_list) + ", "
                else:
                    current_mod_list = ', '.join(current_mod_list)
                func.config_save(message.server.id,
                                 'mods',
                                 current_mod_list,
                                 discord_settings['server_settings'])
                await client.send_message(message.channel, "Mods removed!")
        if "!apb mods add" in message.content:
            current_mod_list = func.config_get(message.server.id, 'mods',
                                               discord_settings['server_settings'])
            current_mod_list = current_mod_list.split(", ")
            for user in message.mentions:
                if user.id == message.server.owner.id:
                    # Can't remove yourself
                    continue
                if str(user.id) in current_mod_list:
                    continue
                else:
                    current_mod_list.append(user.id)
            if len(current_mod_list) < 2:
                current_mod_list = ', '.join(current_mod_list) + ", "
            else:
                current_mod_list = ', '.join(current_mod_list)
            func.config_save(message.server.id, 'mods', current_mod_list,
                             discord_settings['server_settings'])
            await client.send_message(message.channel, "Mods added!")

        if "!apb help" in message.content:
            await client.send_message(
                message.channel,
                """Commands: http://ace3df.github.io/AcePictureBot/commands/
Mod Commands: https://gist.github.com/ace3df/cd8e233fe9fe796d297d""")

    if server_settings['turned_on'] == "False":
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
        return
    if command in NO_DISCORD_CMDS:
        return
    print("{} ({}) | {} ({}) - {}".format(message.server, message.server.id,
                                          message.author, message.author.id,
                                          message.content))

    CHANNEL_TIMEOUT[message.server.id] = time.time()
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
    rate_limit_secs = 120
    if message.author.id in RATE_LIMIT_DICT:
        # User is now limited (3 hours).
        if ((rate_time - RATE_LIMIT_DICT[message.author.id][0])
                .total_seconds() < rate_limit_secs)\
           and (RATE_LIMIT_DICT[message.author.id][1] >= 5):
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

    # This shouldn't happen but just in case.
    if not isinstance(command, str):
        return

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
    await client.send_message(message.channel, msg)
    if server_settings['allow_imgs'] and discord_image:
        await client.send_file(message.channel, open(discord_image, 'rb'))


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print('------')

loop = asyncio.get_event_loop()
loop.create_task(timeout_channel())
loop.run_until_complete(client.run(discord_settings['email'],
                                   discord_settings['password']))

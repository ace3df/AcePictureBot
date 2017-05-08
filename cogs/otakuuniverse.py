from functions import create_otp_image
from .utils import checks

from discord.ext import commands
import discord
from PIL import Image

import random


class OtakuUniverse:

    def __init__(self, bot):
        self.bot = bot
        self.random_roles_string = ["Hikikomori", "Baka", "Pinku", "Lolicon", "Idol",
                                    "Kuma", "Trap", "Super Saiya", "Artist", "Bishoujo", "Neko", "Ninjatart",
                                    "Pokemon Master", "Aniki", "Ookami", "Loli Hunter", "Kawaii", "Imouto", "Inu",
                                    "Milf Hunter", "Hardcore Weeb", "Waifu", "Tsundere", "Pervert", "Nintendo Fan",
                                    "Husbando", "Gamer", "Shit Taste", "PC Master Race", "Senpai", "Kamidere", "Whiteo Dayo",
                                    "Playstation Fan", "Kouhai", "Hentai Goddess", "Xbox Fan", "Minty Fresh"]
        self.random_roles = []
        self.colour_list = []
        self.rainbow_role = None
        self.rainbow_role_name = "Moderator" # "Rainbow"
        self.ou_server = None

    async def on_ready(self):
        self.ou_server = self.bot.get_server('223145422783381506')
        if self.ou_server:
            for role in self.ou_server.roles:
                if role.name == self.rainbow_role_name:
                    self.rainbow_role = role
                if role.name in self.random_roles_string:
                    self.colour_list.append(role.colour)
                    self.random_roles.append(role)

    async def on_message(self, message):
        if message.server and message.server.id not in ["223145422783381506", "177538264729780225"]:
            return
        other_roles = []
        if self.rainbow_role in message.author.roles:  # User has rainbow role.
            await self.bot.edit_role(
                self.ou_server, self.rainbow_role, colour=random.choice(self.colour_list))
        """
            for user_role in message.author.roles:
                # Go through each role and append keeping other (non-generic) roles
                if user_role not in self.random_roles:
                    other_roles.append(user_role)
            other_roles.append(self.rainbow_role)

            other_roles.append(random.choice(self.random_roles))
            await self.bot.replace_roles(message.author, *other_roles)
        """

    @commands.command(pass_context=True)
    @checks.only_allow_server(["223145422783381506", "177538264729780225"])
    async def harem(self, ctx, *, roles=""):
        first_self = "myself" in roles.lower().strip()
        if first_self:
            roles = roles.replace("myself", "").strip()
        cleaned_member = []
        for member in ctx.message.server.members:
            if member.bot or not member.roles:
                continue
            if roles:
                for role in member.roles:
                    if role.name.lower().replace(" ", "_").strip() in roles.lower().replace(" ", "_").strip():
                        cleaned_member.append(member)
            else:
                cleaned_member.append(member)
        complete_img = ""
        if len(cleaned_member) < 5:
            await self.bot.say("Not enough members found{}!".format("" if not roles else " with that role"))
            return
            
        otp_results = []
        if first_self:
            if ctx.message.author in cleaned_member:
                cleaned_member.remove(ctx.message.author)
            otp_results.append([ctx.message.author.name, "", ctx.message.author.avatar_url.replace("?size=1024", "?size=128")])
        else:
            member_one = cleaned_member.pop(random.randrange(len(cleaned_member)))
            otp_results.append([member_one.name, "", member_one.avatar_url.replace("?size=1024", "?size=128")])
        max_num = 5 if len(cleaned_member) >= 5 else len(cleaned_member)
        for x in range(0, random.randint(2, max_num)):
            temp_member = cleaned_member.pop(random.randrange(len(cleaned_member)))
            otp_results.append([temp_member.name, "", temp_member.avatar_url.replace("?size=1024", "?size=128")])

        post_media = create_otp_image(otp_results=otp_results, width_size=128, height_size=128, support_gif=True)
        end_msg_names = ""
        for result in otp_results:
            if result == otp_results[-1]:
                msg_add = result[0]
            else:
                msg_add = result[0] + " and "
            end_msg_names += msg_add

        post_message = "{} Your Harem is {}".format(ctx.message.author.mention, end_msg_names)
        await self.bot.send_file(ctx.message.channel, post_media, content=post_message)


    @commands.command(pass_context=True)
    @checks.only_allow_server(["223145422783381506", "177538264729780225"])
    async def otp(self, ctx, *, roles=""):
        first_self = "myself" in roles.lower().strip()
        if first_self:
            roles = roles.replace("myself", "").strip()
        cleaned_member = []
        for member in ctx.message.server.members:
            if "bot" not in roles and member.bot or not member.roles:
                continue
            if roles:
                for role in member.roles:
                    if role.name.lower().replace(" ", "_").strip() in roles.lower().replace(" ", "_").strip():
                        cleaned_member.append(member)
            else:
                cleaned_member.append(member)
        complete_img = ""
        if len(cleaned_member) < 3:
            await self.bot.say("Not enough members found{}!".format("" if not roles else " with that role"))
            return
        otp_results = []
        if first_self:
            if ctx.message.author in cleaned_member:
                cleaned_member.remove(ctx.message.author)
            member_one = ctx.message.author
            otp_results.append([ctx.message.author.name, "", ctx.message.author.avatar_url.replace("?size=1024", "?size=128")])
        else:
            member_one = cleaned_member.pop(random.randrange(len(cleaned_member)))
            otp_results.append([member_one.name, "", member_one.avatar_url.replace("?size=1024", "?size=128")])
        member_two = cleaned_member.pop(random.randrange(len(cleaned_member)))
        otp_results.append([member_two.name, "", member_two.avatar_url.replace("?size=1024", "?size=128")])
        # otp_results[[name, seres, image], [name, blank, avatar]]
        post_media = create_otp_image(otp_results=otp_results, width_size=128, height_size=128, support_gif=True)
        post_message = "{} Your OTP is {} x {}".format(ctx.message.author.mention, member_one.name, member_two.name)
        await self.bot.send_file(ctx.message.channel, post_media, content=post_message)
       

def setup(bot):
    bot.add_cog(OtakuUniverse(bot))
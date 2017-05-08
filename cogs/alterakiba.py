from .utils import config, checks
from .utils.paginator import Pages

from discord.ext import commands
import json
import time
import datetime
import discord
import difflib


class AlterAkiba:
    """The tag related commands."""

    def __init__(self, bot):
        self.bot = bot
        self.config = config.Config('AlterAkiba.json', loop=bot.loop, load_later=True)

    @commands.group(pass_context=True, invoke_without_command=True)
    @checks.only_allow_server(["218487696790650881", "177538264729780225"])
    async def unko(self, ctx, *, member : discord.Member = None):
        unko_history = self.config.get('unko_history', [])
        if member is None:
            # Leaderboard
            pass
        else:
            total_time_as_unko = 0
            unko_added = 0
            unko_added_ts = []
            unko_removed = 0
            unko_removed_ts = []
            timestamps_as_unko = []
            for entry in unko_history:
                removed_last = False
                if member.id != entry.get('user_id'):
                    continue
                if entry.get('result') == "added":
                    unko_added_ts.append(entry.get('timestamp'))
                    unko_added += 1
                else:
                    unko_removed_ts.append(entry.get('timestamp'))
                    unko_removed += 1
                    removed_last = True
            if unko_added == 0:
                await self.bot.say("This user hasn't been Unko'd before!")
                return

            has_unko = False
            for role in member.roles:
                if "unko" in role.name.lower():
                    has_unko = True
                    break

            print(unko_added_ts)
            if not unko_removed_ts:
                unko_removed_ts.append(time.time())
            print(unko_removed_ts)
            print(sum(unko_added_ts) - sum(unko_removed_ts))
            total_time_as_unko = abs(sum(unko_removed_ts) - sum(unko_added_ts))
            print(total_time_as_unko)
            print(removed_last)
            # if has_unko:  # User still has Unko
            if removed_last:
                total_time_as_unko -= time.time() - unko_removed_ts[-1]
            else:
                total_time_as_unko -= time.time() - unko_added_ts[-1]

            print(total_time_as_unko)

            hours, remainder = divmod(int(total_time_as_unko), 3600)
            minutes, seconds = divmod(remainder, 60)
            days, hours = divmod(hours, 24)
            if days:
                fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
            else:
                fmt = '{h} hours, {m} minutes, and {s} seconds'
            embed = discord.Embed(description="User {}'s Unko Details".format(str(member)))
            embed.colour = 0x738bd7 # blurple
            embed.set_author(name=str(member), icon_url=member.avatar_url)
            embed.add_field(name="Total Time being Unko", value=fmt.format(d=days, h=hours, m=minutes, s=seconds))
            embed.add_field(name="Unko'd Count", value=unko_added)
            embed.add_field(name="Un-Unko'd Count", value=unko_removed)
            await self.bot.say(embed=embed)

    @unko.command(pass_context=True)
    @checks.only_allow_server(["218487696790650881", "177538264729780225"])
    async def history(self, ctx, *, member : discord.Member):
        unko_history = self.config.get('unko_history', [])
        readable_history = []
        for entry in unko_history:
            if member.id != entry.get('user_id'):
                continue
            value = datetime.datetime.fromtimestamp(entry.get('timestamp'))
            readable_history.append("**{} - Unko {}**\n**Messages:**\n{}".format(
                value.strftime('%Y-%m-%d %H:%M:%S'),
                entry.get('result'),
                '\n'.join(reversed(entry.get('past_messages')))))
        if readable_history:
            try:
                p = Pages(self.bot, message=ctx.message, entries=readable_history)
                p.embed.colour = 0x738bd7 # blurple
                p.embed.set_author(name=ctx.message.author.display_name, icon_url=ctx.message.author.avatar_url)
                await p.paginate()
            except Exception as e:
                await self.bot.say(e)
        else:
            await self.bot.say('{0.name} has no unko history.'.format(member))


    async def on_member_update(self, before, after):
        if before.server.id not in ["218487696790650881", "177538264729780225"]:
            return
        if before.roles == after.roles:
            return
        has_unko = False 
        had_unko = False
        # TODO: make this not dumb, effort right now
        for role in before.roles:
            if "unko" in role.name.lower():
                had_unko = True
                break
        for role in after.roles:
            if "unko" in role.name.lower():
                has_unko = True
                break
        if not has_unko and not had_unko:
            return
        user_log = []
        async for message in self.bot.logs_from(after.server.default_channel, limit=20):
            if message.author == after:
                user_log.append(message.content)
                if len(user_log) > 3:
                    break

        unko_history = self.config.get('unko_history', [])
        if has_unko:
            result = 'added'
        elif had_unko:
            result = 'removed'
        user_entry = {'result': result, 'user_id': after.id, 'past_messages': user_log, 'timestamp': time.time()}
        unko_history.append(user_entry)
        await self.config.put('unko_history', unko_history)


def setup(bot):
    bot.add_cog(AlterAkiba(bot))
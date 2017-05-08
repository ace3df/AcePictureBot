from config import discord_settings


from discord.ext import commands
import discord


class Meta:

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def patreon(self):
        message = discord_settings.get('patreon_msg', False)
        if not message:
            return
        await self.bot.say(message)

    @commands.command()
    async def invite(self):
        perms = discord.Permissions.none()
        perms.read_messages = True
        perms.send_messages = True
        perms.embed_links = True
        perms.attach_files = True
        msg = "Use this URL to invite the bot: "
        await self.bot.say(msg + discord.utils.oauth_url(self.bot.client_id, perms))
    
    @commands.command(pass_context=True)
    @commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)
    async def feedback(self, ctx, *, content: str):
        """Gives feedback about the bot.
        This is a quick way to request features or bug fixes
        without being in the bot's server.
        The bot will communicate with you via PM about the status
        of your request if possible.
        You can only request feedback once a minute.

        https://github.com/Rapptz/RoboDanny/blob/master/cogs/buttons.py#L319
        """

        e = discord.Embed(title='Feedback', colour=0x738bd7)
        msg = ctx.message

        channel = self.bot.get_channel('280482034663686144')
        if channel is None:
            return

        e.set_author(name=str(msg.author), icon_url=msg.author.avatar_url or msg.author.default_avatar_url)
        e.description = content
        e.timestamp = msg.timestamp

        if msg.server is not None:
            e.add_field(name='Server', value='{0.name} (ID: {0.id})'.format(msg.server), inline=False)

        e.add_field(name='Channel', value='{0} (ID: {0.id})'.format(msg.channel), inline=False)
        e.set_footer(text='Author ID: ' + msg.author.id)

        await self.bot.send_message(channel, embed=e)
        await self.bot.say('Successfully sent feedback \u2705')


def setup(bot):
    bot.add_cog(Meta(bot))
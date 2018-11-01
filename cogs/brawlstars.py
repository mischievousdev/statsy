import aiohttp
import json
import time
import os

from cachetools import TTLCache
import discord
from box import Box
from discord.ext import commands

import box
from ext import utils
from ext.command import command
from ext.embeds import brawlstars
from ext.paginator import Paginator
from locales.i18n import Translator

_ = Translator('Brawl Stars', __file__)

shortcuts = {
    'juice': '2PP00',
    'pulp': 'PY9JLV'
}


class TagCheck(commands.MemberConverter):

    check = 'PYLQGRJCUV0289'

    def resolve_tag(self, tag):
        if tag in shortcuts:
            tag = shortcuts[tag]
        tag = tag.strip('#').upper().replace('O', '0')
        if any(i not in self.check for i in tag):
            return False
        else:
            return tag

    async def convert(self, ctx, argument):
        # Try to convert it to a member.
        try:
            user = await super().convert(ctx, argument)
        except commands.BadArgument:
            pass
        else:
            return user

        # Not a user so its a tag.
        tag = self.resolve_tag(argument)

        if not tag:
            raise utils.InvalidTag('Invalid bs-tag passed.')
        else:
            return tag


class Brawl_Stars:

    """Commands relating to the Brawl Stars game made by supercell."""

    def __init__(self, bot):
        self.bot = bot
        self.conv = TagCheck()
        self.cache = TTLCache(500, 180)

    async def get_band_from_profile(self, ctx, tag, message):
        profile = await self.request(ctx, f'/players/{tag}')
        try:
            return profile.band.tag
        except box.BoxKeyError:
            return await ctx.send(message)

    async def resolve_tag(self, ctx, tag_or_user, band=False):
        if not tag_or_user:
            try:
                tag = await ctx.get_tag('brawlstars')
            except KeyError:
                await ctx.send('You don\'t have a saved tag.')
                raise utils.NoTag
            else:
                if band is True:
                    return await self.get_band_from_profile(ctx, tag, 'You don\'t have a band!')
                return tag
        if isinstance(tag_or_user, discord.Member):
            try:
                tag = await ctx.get_tag('brawlstars', tag_or_user.id)
            except KeyError:
                await ctx.send('That person doesnt have a saved tag!')
                raise utils.NoTag
            else:
                if band is True:
                    return await self.get_band_from_profile(ctx, tag, 'That person does not have a band!')
                return tag
        else:
            return tag_or_user

    async def request(self, ctx, endpoint):
        try:
            self.cache[endpoint]
        except KeyError:
            async with self.bot.session.get(
                f"http://brawlapi.cf/api{endpoint}",
                headers={'Authorization': os.getenv('brawlstars')}
            ) as resp:
                try:
                    if resp.status == 200:
                        self.cache[endpoint] = await resp.json()
                    elif resp.status == 404 or resp.status == 524:
                        await ctx.send(_('The tag cannot be found!', ctx))
                        raise utils.NoTag
                    else:
                        raise utils.APIError
                except aiohttp.ContentTypeError:
                    er = discord.Embed(
                        title=_('Brawl Stars Server Down', ctx),
                        color=discord.Color.red(),
                        description='This could be caused by a maintainence break or an API issue.'
                    )
                    if ctx.bot.psa_message:
                        er.add_field(name=_('Please Note!', ctx), value=ctx.bot.psa_message)
                    await ctx.send(embed=er)

                    # end and ignore error
                    raise commands.CheckFailure

        return Box(self.cache[endpoint], camel_killer_box=True)

    @command()
    async def bssave(self, ctx, *, tag):
        """Saves a Brawl Stars tag to your discord profile.

        Ability to save multiple tags coming soon.
        """
        tag = self.conv.resolve_tag(tag)

        if not tag:
            raise utils.InvalidTag(_('Invalid tag', ctx))

        await ctx.save_tag(tag, 'brawlstars')

        await ctx.send(_('Successfully saved tag.', ctx))

    @command()
    async def bsprofile(self, ctx, tag_or_user: TagCheck=None):
        """Get general Brawl Stars player information."""
        tag = await self.resolve_tag(ctx, tag_or_user)

        async with ctx.channel.typing():
            profile = await self.request(ctx, f'/players/{tag}')
            em = await brawlstars.format_profile(ctx, profile)

        await ctx.send(embed=em)

    @command(aliases=['bsbrawler'])
    async def bsbrawlers(self, ctx, tag_or_user: TagCheck=None):
        """Get general Brawl Stars player information."""
        tag = await self.resolve_tag(ctx, tag_or_user)

        async with ctx.channel.typing():
            profile = await self.request(ctx, f'/players/{tag}')
            ems = await brawlstars.format_brawlers(ctx, profile)

        await Paginator(ctx, *ems).start()

    @command()
    @utils.has_perms()
    async def bsband(self, ctx, tag_or_user: TagCheck=None):
        """Get Brawl Stars band information."""
        tag = await self.resolve_tag(ctx, tag_or_user, band=True)

        async with ctx.channel.typing():
            band = await self.request(ctx, f'/bands/{tag}')
            ems = await brawlstars.format_band(ctx, band)

        await Paginator(ctx, *ems).start()

    @command(enabled=False)
    @utils.has_perms()
    async def bsevents(self, ctx):
        """Shows the upcoming events!"""
        async with ctx.channel.typing():
            events = await self.request(f'/events')
            ems = await brawlstars.format_events(ctx, events)

        await Paginator(ctx, *ems).start()

    @command(aliases=['bsrobo'])
    @utils.has_perms()
    async def bsroborumble(self, ctx):
        """Shows the robo rumble leaderboard"""
        async with ctx.channel.typing():
            async with ctx.session.get(f'https://leaderboard.brawlstars.com/rumbleboard.jsonp?_={int(time.time())}') as resp:
                leaderboard = json.loads((await resp.text()).replace('jsonCallBack(', '')[:-2])
            ems = brawlstars.format_robo(ctx, leaderboard)

        await Paginator(ctx, *ems).start()

    @command(aliases=['bsboss'])
    @utils.has_perms()
    async def bsbossfight(self, ctx):
        """Shows the boss fight leaderboard"""
        async with ctx.channel.typing():
            async with ctx.session.get(f'https://leaderboard.brawlstars.com/bossboard.jsonp?_={int(time.time())}') as resp:
                leaderboard = json.loads((await resp.text()).replace('jsonCallBack(', '')[:-2])
            ems = brawlstars.format_boss(ctx, leaderboard)

        await Paginator(ctx, *ems).start()


def setup(bot):
    cog = Brawl_Stars(bot)
    bot.add_cog(cog)

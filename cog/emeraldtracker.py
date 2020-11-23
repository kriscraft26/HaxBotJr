from discord import Message, Embed
from discord.ext import commands

from logger import Logger
from msgmaker import *
from reactablemessage import RMessage
from util.cmdutil import parser
from util.timeutil import now
from util.discordutil import Discord
from state.config import Config
from state.guildmember import GuildMember
from state.statistic import Statistic
from cog.datamanager import DataManager
from cog.snapshotmanager import SnapshotManager


@DataManager.register("lastUpdateTimeStr")
class EmeraldTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.provider = None
        self.parseAlert: RMessage = None
        self.lastUpdateTimeStr = "owo"

        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._snapshotManager.add("EmeraldTracker", self)
    
    async def __snap__(self):
        title = "Emerald Contribution Leader Board"
        return (
            await self.make_emerald_lb_pages(False),
            await self.make_emerald_lb_pages(True)
        )
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not self.provider:
            return
        if message.author.id == self.provider.id:
            attachments = message.attachments
            if not attachments:
                return

            text = (await attachments[0].read()).decode("utf-8")

            failedLineNum = await self.parse_gu_list(text)
            self.lastUpdateTimeStr = now().strftime("%b %d, %H:%M:%S (UTC)")

            text = f"✅ Successfully parsed! With **{failedLineNum}** failed line."
            embed = Embed(title=text)

            await self.parseAlert.message.edit(embed=embed)
            await self.parseAlert.remove_reaction("❌")

            self.provider = None
            self.parseAlert = None

    async def parse_gu_list(self, text: str):
        failedLineNum = 0
        for line in text.split("\n"):
            if not line:
                continue
            try:
                sections = line.split(" - ")
                ign = sections[0].split(" ")[-1]
                if GuildMember.is_ign_active(ign):
                    em = int(sections[2][:-1])
                    await Statistic.stats[GuildMember.ignIdMap[ign]].update_emerald(em)
            except Exception:
                failedLineNum += 1
        return failedLineNum
    
    async def make_emerald_lb_pages(self, total):
        if total:
            lb = Statistic.emeraldTotalLb
            field = "total"
            titlePrefix = "Total "
        else:
            lb = Statistic.emeraldLb
            field = "biweek"
            titlePrefix = "Bi-Weekly "

        valGetter = lambda m: Statistic.stats[m.id].emerald[field]
        filter_ = lambda m: m.status != GuildMember.REMOVED
        
        return make_entry_pages(await make_stat_entries(
            valGetter, filter_=filter_, lb=lb),
            title=titlePrefix + "Emerald Leader Board", lastUpdate=self.lastUpdateTimeStr)

    @parser("em", ["total"], "-snap", isGroup=True)
    async def display_emerald(self, ctx: commands.Context, total, snap):
        if snap:
            pages = await self._snapshotManager.get_snapshot_cmd(ctx, snap, 
                "EmeraldTracker", total)
            if not pages:
                return
        else:
            pages = await self.make_emerald_lb_pages(total)

        rMsg = RMessage(await ctx.send(pages[0]))
        await rMsg.add_pages(pages)

    @parser("em parse", parent=display_emerald)
    async def start_parse(self, ctx: commands.Context):
        if not await Discord.rank_check(ctx, "Strategist"):
            return

        if self.provider:
            alert = make_alert(f"Already an existing parse action by {self.provider}")
            await ctx.send(alert)
            return

        rMsg = RMessage(await ctx.send(embed=Embed(
            title="ℹ Your next uploaded file will be parsed")), userId=ctx.author.id)
        await rMsg.add_reaction("❌", self.parse_cancel_cb, rMsg)

        self.provider = ctx.author
        self.parseAlert = rMsg
    
    async def parse_cancel_cb(self, rMsg: RMessage):
        self.provider = None
        self.parseAlert = None

        alert = make_alert("Action canceled", color=COLOR_SUCCESS)
        await rMsg.delete()
    
    @parser("em fix", parent=display_emerald)
    async def fix_em(self, ctx: commands.Context):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return
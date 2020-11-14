from discord import Message
from discord.ext import commands

from logger import Logger
from msgmaker import *
from leaderboard import LeaderBoard
from reactablemessage import ReactableMessage, PagedMessage
from util.cmdutil import parser
from util.timeutil import now
from util.discordutil import Discord
from state.guildmember import GuildMember
from cog.datamanager import DataManager
from cog.snapshotmanager import SnapshotManager


@DataManager.register("lastUpdateTimeStr")
class EmeraldTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.provider = None
        self.parseAlert: ReactableMessage = None
        self.lastUpdateTimeStr = "owo"

        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._lb: LeaderBoard = LeaderBoard.get_lb("emerald")

        self._snapshotManager.add("EmeraldTracker", self)
    
    async def __snap__(self):
        title = "Emerald Contribution Leader Board"
        return await self._snapshotManager.make_lb_snapshot(self._lb, 
            title=title, lastUpdate=self.lastUpdateTimeStr)
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not self.provider:
            return
        if message.author.id == self.provider.id:
            attachments = message.attachments
            if not attachments:
                return

            text = (await attachments[0].read()).decode("utf-8")

            failedLineNum = self.parse_gu_list(text)
            self.lastUpdateTimeStr = now().strftime("%b %d, %H:%M:%S (UTC)")

            color = COLOR_WARNING if failedLineNum else COLOR_SUCCESS
            text = f"Successfully parsed! With **{failedLineNum}** failed line."
            alert = make_alert(text, color=color)

            await self.parseAlert.edit_message(embed=alert)
            await self.parseAlert.un_track()

            self.provider = None
            self.parseAlert = None

    def parse_gu_list(self, text: str):
        failedLineNum = 0
        for line in text.split("\n"):
            if not line:
                continue
            try:
                sections = line.split(" - ")
                ign = sections[0].split(" ")[-1]
                if GuildMember.is_ign_active(ign):
                    em = int(sections[2][:-1])
                    self._lb.set_stat(GuildMember.ignIdMap[ign], em)
            except Exception:
                failedLineNum += 1
        return failedLineNum

    @parser("em", ["acc"], ["total"], "-snap", isGroup=True)
    async def display_emerald(self, ctx: commands.Context, acc, total, snap):
        if snap:
            snapshot = await self._snapshotManager.get_snapshot_cmd(ctx, snap, 
                "EmeraldTracker")
            if not snapshot:
                return
            pages = snapshot[acc][total]
        else:
            title = "Emerald Contribution Leader Board"
            pages = await self._lb.create_pages(acc, total,
                title=title, lastUpdate=self.lastUpdateTimeStr)

        await PagedMessage(pages, ctx.channel).init()

    @parser("em parse", parent=display_emerald)
    async def start_parse(self, ctx: commands.Context):
        if not await Discord.rank_check(ctx, "Strategist"):
            return

        if self.provider:
            alert = make_alert(f"Already an existing parse action by {self.provider}")
            await ctx.send(alert)
            return

        text = "Your next uploaded file will be parsed"
        subtext = "react with ❌ to cancel this action"
        alert = make_alert(text, subtext=subtext, color=COLOR_INFO)

        msg = ReactableMessage(ctx.channel)
        msg._init_send = lambda: ctx.send(embed=alert)
        await msg.add_callback("❌", self.parse_cancel_cb, msg)

        self.provider = ctx.author
        self.parseAlert = msg
        await msg.init()
    
    async def parse_cancel_cb(self, msg: ReactableMessage):
        self.provider = None
        self.parseAlert = None

        alert = make_alert("Action canceled", color=COLOR_SUCCESS)
        await msg.edit_message(embed=alert)
        await msg.un_track()
    
    @parser("em fix", parent=display_emerald)
    async def fix_em(self, ctx: commands.Context):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return
        
        id_ = GuildMember.ignIdMap["Carrota"]
        self._lb._total[id_] = self._lb.get_total(id_) + 12608
        self._lb._rank(id_, self._lb._totalLb, self._lb.get_total)

        self._lb._acc[id_] = self._lb.get_acc(id_) + 12608
        self._lb._rank(id_, self._lb._accLb, self._lb.get_acc)

        self._lb._bw[id_] = self._lb.get_bw(id_) + 12608
        self._lb._rank(id_, self._lb._bwLb, self._lb.get_bw)
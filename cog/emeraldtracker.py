from discord import Message
from discord.ext import commands

from logger import Logger
from util.cmdutil import parser
from msgmaker import *
from reactablemessage import ReactableMessage
from pagedmessage import PagedMessage
from cog.configuration import Configuration
from cog.membermanager import MemberManager


class EmeraldTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.provider = None

        self._config: Configuration = bot.get_cog("Configuration")
        self._memberManager: MemberManager= bot.get_cog("MemberManager")
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not self.provider:
            return
        if message.author.id == self.provider.id and message.content[1:] != "em parse":
            print(message.content)

    def parse_gu_list(self, text: str):
        for line in text.split("\n"):
            sections = line.split(" - ")
            ign = sections[0].split(" ")[-1]
            if ign in self._memberManager.ignIdMap:
                member = self._memberManager.get_member_by_ign(ign)
                em = int(sections[2][:-1])
                Logger.em.info(f"{ign} em update {member.emerald} -> {em}")
                member.emerald = em

    @parser("em", isGroup=True)
    async def display_emerald(self, ctx: commands.Context):
        lb = self._memberManager.emeraldLb
        igns = self._memberManager.ignIdMap.keys()
        members = self._memberManager.members
        statSelector = lambda m: m.emerald
        title = "Emerald Contribution Leader Board"
        
        pages = make_entry_pages(make_stat_entries(lb, igns, members, statSelector),
            title=title)
        await PagedMessage(pages, ctx.channel).init()

    @parser("em parse", parent=display_emerald)
    async def start_parse(self, ctx: commands.Context):
        if not self._config.group_check(ctx, "trusted"):
            return

        if self.provider:
            alert = make_alert(f"Already an existing parse action by {self.provider}")
            await ctx.send(alert)
            return

        text = "Your next message will be parsed"
        subtext = "react with ❌ to cancel this action"
        alert = make_alert(text, subtext=subtext, color=COLOR_INFO)

        msg = ReactableMessage(ctx.channel)
        msg._init_send = lambda: ctx.send(embed=alert)
        msg.add_callback("❌", self.parse_cancel_cb, provideSelf=True)

        self.provider = ctx.author
        await msg.init()
    
    async def parse_cancel_cb(self, msg: ReactableMessage):
        self.provider = None

        alert = make_alert("Action canceled", color=COLOR_SUCCESS)
        await msg.edit_message(embed=alert)
        await msg.un_track()
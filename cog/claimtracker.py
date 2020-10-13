from datetime import datetime, timedelta
from math import trunc

from discord.ext import commands, tasks

from logger import Logger
from msgmaker import *
from reactablemessage import PagedMessage
from util.timeutil import now, add_tz_info
from util.cmdutil import parser
from cog.datamanager import DataManager
from cog.wynnapi import WynnAPI
from cog.configuration import Configuration


CLAIM_UPDATE_INTERVAL = 6
CLAIM_ALERT_INTERVAL = 10  # in minutes


@DataManager.register("_claims")
class ClaimTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self._claims = {}
        self._claimNameOrder = []
        self._allTerrs = set()

        self._config: Configuration = bot.get_cog("Configuration")
        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._terrListTracker = wynnAPI.terrList.get_tracker()

        self._hasInitClaimUpdate = False
        self._shouldAlert = False
    
    def __loaded__(self):
        self._claimNameOrder = list(self._claims.keys())
        self._order_claim_names()

        self._claim_update.start()

    @tasks.loop(seconds=CLAIM_UPDATE_INTERVAL)
    async def _claim_update(self):
        claimList = self._terrListTracker.getData()
        if not claimList:
            return
        claimList = claimList["territories"]

        if not self._hasInitClaimUpdate:
            self._allTerrs = set(claimList.keys())
            self._hasInitClaimUpdate = True
        
        for claim in self._claims:
            prevGuild = self._claims[claim]["guild"]
            currGuild = claimList[claim]["guild"]
            self._claims[claim]["guild"] = currGuild
            if prevGuild != currGuild:
                self._shouldAlert = True
                if currGuild == "HackForums":
                    emoji = "🛡️"
                elif prevGuild == "HackForums":
                    emoji = "⚔️"
                else:
                    emoji = "🏹"
                text = f"{emoji} **{claim}**  __{prevGuild}__  ->  __{currGuild}__"
                await self._config.send("claimLog", text)

            acquired = self._parse_acquired(claimList[claim]["acquired"])
            self._claims[claim]["acquired"] = acquired
        
        self._order_claim_names()
    
    @_claim_update.before_loop
    async def _before_claim_update(self):
        Logger.bot.debug("starting claim update loop")
    
    @tasks.loop(minutes=CLAIM_ALERT_INTERVAL)
    async def _claim_alert_loop(self):
        # await self._config.send("claimLog", "<@&757336179812204616>")
        if self._shouldAlert:
            await self._config.send("claimLog", "@Rocketeer", )
    
    @_claim_update.before_loop
    async def _before_claim_alert_loop(self):
        Logger.bot.debug("starting claim alert loop")
    
    def _parse_acquired(self, acquired):
        return add_tz_info(datetime.strptime(acquired, "%Y-%m-%d %H:%M:%S"))
    
    def _order_claim_names(self):
        self._claimNameOrder.sort(key=lambda c: self._claims[c]["acquired"], reverse=True)

    @parser("claim", isGroup=True)
    async def display_claims(self, ctx: commands.Context):
        if not self._claims:
            await ctx.send(decorate_text("Empty"))
            return

        entries = []
        maxTerrLen = max(map(len, self._claimNameOrder))
        maxGLen = max(map(lambda c: len(c["guild"]), self._claims.values()))
        maxDTLen = -1

        for terr in self._claimNameOrder:
            dt = now() - self._claims[terr]["acquired"]
            dt = str(timedelta(seconds=trunc(dt.total_seconds())))
            maxDTLen = len(dt)
            entries.append((terr, self._claims[terr]["guild"], dt))
        
        template = "{0:%d}  |  {1:%d}  |  {2:>%d}" % (maxTerrLen, maxGLen, maxDTLen)
        entries = list(map(lambda e: template.format(*e), entries))
        
        pages = make_entry_pages(entries, title="Claims", api=self._terrListTracker)
        await PagedMessage(pages, ctx.channel).init()
    
    @parser("claim add", "terrs...", parent=display_claims)
    async def add_claims(self, ctx: commands.Context, terrs):
        if not await self._config.perm_check(ctx, "group.staff"):
            return

        terrs = set(terrs)
        validTerrs = terrs.intersection(self._allTerrs)

        if not validTerrs:
            await ctx.send(embed=make_alert("No terrs are added."))
            return

        for terr in validTerrs:
            self._claims[terr] = {
                "guild": "None",
                "acquired": now()
            }
            self._claimNameOrder.append(terr)
        self._order_claim_names
        
        invalidTerrs = terrs.difference(self._allTerrs)

        text = f"Successfully added {len(validTerrs)} territories as claims."
        subText = f"Ignored {len(invalidTerrs)} territories." if invalidTerrs else None
        await ctx.send(embed=make_alert(text, subtext=subText, color=COLOR_SUCCESS))
    
    @parser("claim remove", "terrs...", parent=display_claims)
    async def remove_claims(self, ctx: commands.Context, terrs):
        if not await self._config.perm_check(ctx, "group.staff"):
            return

        terrs = set(terrs)
        validTerrs = terrs.intersection(set(self._claimNameOrder))

        if not validTerrs:
            await ctx.send(embed=make_alert("No terrs are removed."))
            return

        for terr in validTerrs:
            del self._claims[terr]
            self._claimNameOrder.remove(terr)
        
        invalidTerrs = terrs.difference(validTerrs)

        text = f"Successfully removed {len(validTerrs)} claims."
        subText = f"Ignored {len(invalidTerrs)} claims." if invalidTerrs else None
        await ctx.send(embed=make_alert(text, subtext=subText, color=COLOR_SUCCESS))
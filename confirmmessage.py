from discord import TextChannel
from discord.ext.commands import Context

from msgmaker import make_alert, COLOR_INFO
from reactablemessage import ReactableMessage


class ConfirmMessage(ReactableMessage):

    def __init__(self, ctx: Context, text, cb):
        super().__init__(ctx.channel, userId=ctx.author.id)
        self.text = text
        self.cb = cb
        
        self.add_callback("✅", self._on_confirm)
        self.add_callback("❌", self.delete_message)

    async def _init_send(self):
        alert = make_alert(self.text, color=COLOR_INFO)
        return await self.channel.send(embed=alert)
    
    async def _on_confirm(self):
        await self.cb(self)
        await self.un_track()
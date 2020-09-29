from inspect import iscoroutinefunction

from discord import TextChannel
from discord.ext.commands import Context

from msgmaker import make_alert, COLOR_INFO, COLOR_SUCCESS
from reactablemessage import ReactableMessage


class ConfirmMessage(ReactableMessage):

    def __init__(self, ctx: Context, text, successText, cb):
        super().__init__(ctx.channel, userId=ctx.author.id)
        self.text = text
        self.successText = successText
        self.cb = cb
        
        self.add_callback("✅", self._on_confirm)
        self.add_callback("❌", self.delete_message)

    async def _init_send(self):
        alert = make_alert(self.text, color=COLOR_INFO)
        return await self.channel.send(embed=alert)
    
    async def _on_confirm(self):
        if iscoroutinefunction(self.cb):
            await self.cb(self)
        else:
            self.cb(self)
        alert = make_alert(self.successText, color=COLOR_SUCCESS)
        await self.edit_message(embed=alert)
        await self.un_track()
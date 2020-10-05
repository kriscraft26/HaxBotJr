from reactablemessage import ReactableMessage


class PagedMessage(ReactableMessage):

    def __init__(self, pages, channel):
        super().__init__(channel, track=len(pages) - 1)
        self.pages = pages
        self.index = 0

        
    
    async def _init_send(self):
        if len(self.pages) - 1:
            await self.add_callback("⬅", self.prev_page)
            await self.add_callback("➡", self.next_page)
        return await self.channel.send(self.pages[0])

    async def next_page(self):
        if self.index < len(self.pages) - 1:
            self.index += 1
        else:
            self.index = 0
        await self.edit_message(content=self.pages[self.index])

    async def prev_page(self):
        if self.index > 0:
            self.index -= 1
        else:
            self.index = len(self.pages) - 1
        await self.edit_message(content=self.pages[self.index])
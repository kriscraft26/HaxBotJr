class PagedMessage:

    MAX_ACTIVE_MESSAGE = 5
    activeMessages = []


    def __init__(self, pages, channel):
        self.pages = pages
        self.index = 0
        self.channel = channel
        self.message = None


    async def init(self):
        self.message = await self.channel.send(self.pages[0])
        if len(self.pages) == 1:
            return
        await self.message.add_reaction("⬅")
        await self.message.add_reaction("➡")
        if len(PagedMessage.activeMessages) == PagedMessage.MAX_ACTIVE_MESSAGE:
            PagedMessage.activeMessages = PagedMessage.activeMessages[1:]
        PagedMessage.activeMessages.append(self)
    

    async def nextPage(self, member):
        if self.index < len(self.pages) - 1:
            self.index += 1
        else:
            self.index = 0
        await self.message.edit(content=self.pages[self.index])
        await self.message.remove_reaction("➡", member)
    

    async def prevPage(self, member):
        if self.index > 0:
            self.index -= 1
        else:
            self.index = len(self.pages) - 1
        await self.message.edit(content=self.pages[self.index])
        await self.message.remove_reaction("⬅", member)
    

    @staticmethod
    async def update(reaction, user):
        for pages in PagedMessage.activeMessages:
            if reaction.message.id == pages.message.id and reaction.count > 1:
                if reaction.emoji == "⬅":
                    await pages.prevPage(user)
                elif reaction.emoji == "➡":
                    await pages.nextPage(user)
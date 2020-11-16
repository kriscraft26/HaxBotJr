from inspect import iscoroutinefunction
from typing import List
from asyncio import sleep

from discord import Message, TextChannel, Reaction
from discord.ext.commands import Context

from logger import Logger
from msgmaker import *


class RMessage:

    MAX_ACTIVE_MESSAGE = 5
    activeRMsg = []

    def __init__(self, msg: Message, userId=None):
        self.userId = userId
        self.reactions = {}
        self.message = msg
        self.isResponsive = True
    
    async def add_reaction(self, emoji, cb, *args, **kwargs):
        if emoji not in self.reactions:
            self.reactions[emoji] = (cb, args, kwargs)

            self.isResponsive = False
            await self.message.add_reaction(emoji)
            await sleep(0.25)
            self.isResponsive = True

            if len(self.reactions) == 1:
                RMessage._track_message(self)
    
    async def remove_reaction(self, emoji):
        if emoji in self.reactions:
            del self.reactions[emoji]

            self.isResponsive = False
            await self.message.remove_reaction(emoji, self.message.author)
            await sleep(0.25)
            self.isResponsive = True

            if len(self.reactions) == 0:
                RMessage._untrack_message(self)
    
    async def delete(self):
        await self.message.delete()
        self.message = None
        RMessage._untrack_message(self)
    
    @classmethod
    def _track_message(cls, rMessage):
        if rMessage not in cls.activeRMsg:
            if len(cls.activeRMsg) == cls.MAX_ACTIVE_MESSAGE:
                cls.activeRMsg.pop()
            cls.activeRMsg.append(rMessage)
    
    @classmethod
    def _untrack_message(cls, rMessage):
        if rMessage in cls.activeRMsg:
            cls.activeRMsg.remove(rMessage)
    
    @classmethod
    async def update(cls, reaction: Reaction, user):
        for rMessage in cls.activeRMsg:
            if reaction.message.id == rMessage.message.id and reaction.count > 1:
                if rMessage.userId and user.id != rMessage.userId:
                    return
                if reaction.emoji in rMessage.reactions:
                    (cb, args, kwargs) = rMessage.reactions[reaction.emoji]
                    await cb(*args, **kwargs)
                if user.id != reaction.message.author.id and rMessage.message:
                    try:
                        await rMessage.message.remove_reaction(reaction, user)
                        await sleep(0.25)
                    except Exception as e:
                        Logger.bot.warning(str(e))

    async def add_pages(self, pages: list, appendCurr=False):
        if len(pages) <= 1:
            return
        
        self.index = 0
        if appendCurr:
            pages.insert(0, self.message.content)

        async def prev_pages():
            if self.index:
                self.index -= 1
            else:
                self.index = len(pages) - 1
            await self.message.edit(content=pages[self.index])
        await self.add_reaction("⬅", prev_pages)
        
        async def next_pages():
            if self.index < len(pages) - 1:
                self.index += 1
            else:
                self.index = 0
            await self.message.edit(content=pages[self.index])
        await self.add_reaction("➡", next_pages)
    
    async def add_list_selection(self, entries, cb, *arg, **kwargs):
        pages = []
        slicedEntries = slice_entries(entries, maxEntries=5)
        for i, pageEntries in enumerate(slicedEntries):
            page = "\n".join([f"[{i + 1}] {e}" for i, e in enumerate(pageEntries)])
            page += "\n" + make_page_indicator(len(slicedEntries), i)
            pages.append(decorate_text(page))
        await self.message.edit(content=pages[0])
        await self.add_pages(pages)

        for i, emoji in enumerate(["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]):
            async def selection_cb(index):
                targetEntries = slicedEntries[getattr(self, "index", 0)]
                if index < len(targetEntries):
                    await cb(targetEntries[index], *arg, **kwargs)
            await self.add_reaction(emoji, selection_cb, i)
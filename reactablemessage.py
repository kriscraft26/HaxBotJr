from inspect import iscoroutinefunction
from typing import List
from asyncio import sleep

from discord import Message, TextChannel, Reaction
from discord.ext.commands import Context

from msgmaker import *


class ReactableMessage:

    MAX_ACTIVE_MESSAGE = 5
    activeMsg = []

    def __init__(self, channel: TextChannel, userId=None, track=True):
        self._reactions = {}
        self.userId = userId
        self.msg: Message = None
        self.channel = channel
        self.track = track
    
    async def add_callback(self, reaction, cb, provideSelf=False):
        override = reaction in self._reactions
        self._reactions[reaction] = (cb, provideSelf)
        if self.msg and not override:
            await self.msg.add_reaction(reaction)
    
    async def remove_callback(self, reaction):
        self._reactions.pop(reaction, 0)
        if self.msg:
            await self.msg.remove_reaction(reaction, self.msg.author)
    
    async def _init_send(self) -> Message:
        raise NotImplementedError()

    async def init(self):
        self.msg = await self._init_send()
        
        for reaction in self._reactions:
            await self.msg.add_reaction(reaction)
        
        if self.track:
            if len(ReactableMessage.activeMsg) == ReactableMessage.MAX_ACTIVE_MESSAGE:
                await ReactableMessage.activeMsg[0].un_track()
            ReactableMessage.activeMsg.append(self)
    
    async def un_track(self):
        if self.track:
            ReactableMessage.activeMsg.remove(self)
            for reaction in self._reactions:
                await sleep(0.25)
                await self.msg.remove_reaction(reaction, self.msg.author)
    
    async def edit_message(self, **editArgs):
        await self.msg.edit(**editArgs)
    
    async def delete_message(self):
        await self.un_track()
        await self.msg.delete()
    
    @classmethod
    async def update(cls, reaction: Reaction, user):
        targetMsg: Message = reaction.message
        for msg in cls.activeMsg:
            reactionCount = reaction.count
            if targetMsg.id == msg.msg.id and reactionCount > 1:
                if user.id != targetMsg.author.id:
                    try:
                        await targetMsg.remove_reaction(reaction, user)
                    except:
                        pass
                if msg.userId and user.id != msg.userId:
                    return
                if reaction.emoji in msg._reactions:
                    (cb, provideSelf) = msg._reactions[reaction.emoji]
                    if iscoroutinefunction(cb):
                        await cb(msg) if provideSelf else await cb()
                    else:
                        cb(msg) if provideSelf else cb()
                    return


class PagedMessage(ReactableMessage):

    def __init__(self, pages, channel, userId=None, forceTrack=False):
        super().__init__(channel, track=len(pages) > 1 or forceTrack, userId=userId)
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


class ConfirmMessage(ReactableMessage):

    def __init__(self, ctx: Context, text, successText, cb):
        super().__init__(ctx.channel, userId=ctx.author.id)
        self.text = text
        self.successText = successText
        self.cb = cb
        self.isCoroutine = iscoroutinefunction(cb)

    async def _init_send(self):
        alert = make_alert(self.text, color=COLOR_INFO)
        await self.add_callback("✅", self._on_confirm)
        await self.add_callback("❌", self.delete_message)
        return await self.channel.send(embed=alert)
    
    async def _on_confirm(self):
        if self.isCoroutine:
            await self.cb(self)
        else:
            self.cb(self)
        if self.successText:
            alert = make_alert(self.successText, color=COLOR_SUCCESS)
            await self.edit_message(embed=alert)
            await self.un_track()
        else:
            await self.delete_message()


class ListSelectionMessage(PagedMessage):

    numEmojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    def __init__(self, ctx: Context, entries: List[str], cb):
        entryPages = slice_entries(entries, maxEntries=5)
        pageNum = len(entryPages)
        pages = [
            self._make_page(entries, pageNum, i) for i, entries in enumerate(entryPages)]
        super().__init__(pages, ctx.channel, userId=ctx.author.id, forceTrack=True)
        self.entryPages = entryPages
        isCoroutine = iscoroutinefunction(cb)
        self.cbs = [self._wrap_cb(i, cb, isCoroutine) for i in range(5)]
    
    async def _init_send(self):
        msg = await super()._init_send()
        for i in range(5):
            emoji = ListSelectionMessage.numEmojis[i]
            await self.add_callback(emoji, self.cbs[i])
        return msg
    
    def _wrap_cb(self, i, cb, isCoroutine):
        if isCoroutine:
            async def wrapped_cb():
                entries = self.entryPages[self.index]
                if i < len(entries):
                    await cb(self, self.entryPages[self.index][i])
        else:
            def wrapped_cb():
                entries = self.entryPages[self.index]
                if i < len(entries):
                    cb(self, self.entryPages[self.index][i])
        return wrapped_cb

    def _make_page(self, entries: List[str], pageNum, pageIndex):
        page = "\n".join([f"[{i + 1}] {e}" for i, e in enumerate(entries)])
        page += "\n" + make_page_indicator(pageNum, pageIndex)
        return decorate_text(page)
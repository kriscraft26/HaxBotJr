from discord import Message, TextChannel, Reaction


class ReactableMessage:

    MAX_ACTIVE_MESSAGE = 5
    activeMsg = []

    def __init__(self, channel: TextChannel, userId=None, track=True):
        self._reactions = {}
        self.userId = userId
        self.msg: Message = None
        self.channel = channel
        self.track = track
    
    def add_callback(self, reaction, cb):
        self._reactions[reaction] = cb
    
    async def _init_send(self) -> Message:
        raise NotImplementedError()

    async def init(self):
        self.msg = await self._init_send()
        
        for reaction in self._reactions:
            await self.msg.add_reaction(reaction)
        
        if self.track:
            if len(ReactableMessage.activeMsg) == ReactableMessage.MAX_ACTIVE_MESSAGE:
                ReactableMessage.activeMsg = ReactableMessage.activeMsg[1:]
            ReactableMessage.activeMsg.append(self)
    
    async def un_track(self):
        if self.track:
            for reaction in self._reactions:
                await self.msg.remove_reaction(reaction, self.msg.author)
            ReactableMessage.activeMsg.remove(self)
    
    async def edit_message(self, **editArgs):
        await self.msg.edit(**editArgs)
    
    async def delete_message(self):
        await self.un_track()
        await self.msg.delete()
    
    @classmethod
    async def update(cls, reaction: Reaction, user):
        targetMsg: Message = reaction.message
        for msg in cls.activeMsg:
            if targetMsg.id == msg.msg.id and reaction.count > 1:
                await targetMsg.remove_reaction(reaction, user)
                if msg.userId and user.id != msg.userId:
                    return
                if reaction.emoji in msg._reactions:
                    await msg._reactions[reaction.emoji]()
                
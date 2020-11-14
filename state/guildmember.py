from discord import Member

from logger import Logger
from event import Event
from wynnapi import WynnAPI
from state.state import State
from util.discordutil import Discord


@State.register("members")
class GuildMember:

    ACTIVE = "active"
    IDLE = "idle"
    REMOVED = "removed"

    members = {}
    ignIdMap = {}
    discordIdMap = {}
    altMap = {}

    @classmethod
    async def __loaded__(cls):
        for member in cls.members.values():
            cls.ignIdMap[member.ign] = member.id
            if member.discordId:
                cls.discordIdMap[member.discordId] = member.id
            if member.ownerId:
                if member.ownerId not in cls.altMap:
                    cls.altMap[member.ownerId] = set()
                cls.altMap[member.ownerId].add(member.id)

    @classmethod
    async def add(cls, dMember: Member, ranks):
        ign = dMember.nick.split(" ")[-1]
        id_ = await WynnAPI.get_player_id(ign)
        if not id_:
            return
        
        if id_ in cls.members:
            if id_ in cls.altMap:
                for altId in cls.altMap[id_]:
                    await cls.set_status(altId, cls.ACTIVE)
            member = cls.members[id_]
            if member.ownerId:
                return
            await cls.update(id_, dMember)
            await cls.set_status(id_, cls.ACTIVE)
        else:
            cls.members[id_] = GuildMember(id_, dMember, ranks, ign)
            cls.ignIdMap[ign] = id_
            cls.discordIdMap[dMember.id] = id_

            await Event.broadcast("memberAdd", id_)
            
        return id_

    @classmethod
    async def remove(cls, id_):
        if id_ in cls.altMap:
            for altId in cls.altMap[id_]:
                await cls.set_status(altId, cls.REMOVED)
        await cls.update(id_, None)
        if not cls.members[id_].ownerId:
            await cls.set_status(id_, cls.REMOVED)
    
    @classmethod
    async def add_alt(cls, id_, ign):
        if ign in cls.ignIdMap:
            altId_ = cls.ignIdMap[ign]
            altMember = cls.members[altId_]
            if altMember.ownerId:
                return
            altMember.ownerId = id_
            await cls.update(altId_, None)
        else:
            altId_ = await WynnAPI.get_player_id(ign)
            if not altId_:
                return
            cls.members[altId_] = GuildMember(altId_, None, None, ign, ownerId=id_)
            cls.ignIdMap[ign] = altId_

            await Event.broadcast("memberAdd", altId_)
        
        if id_ not in cls.altMap:
            cls.altMap[id_] = set()
        cls.altMap[id_].add(altId_)

        Logger.bot.info(f"Added alt {ign} to {cls.members[id_]}")
        await Event.broadcast("memberAltAdd", id_, altId_)
        return altId_
    
    @classmethod
    async def remove_alt(cls, id_):
        member = cls.members[id_]
        cls.altMap[member.ownerId].remove(id_)
        prevOwnerId = member.ownerId
        member.ownerId = None

        Logger.bot.info(f"Removed alt {member.ign} from {cls.members[prevOwnerId]}")
        await Event.broadcast("memberAltRemove", prevOwnerId, id_)

    @classmethod
    async def set_status(cls, id_, newStatus):
        member = cls.members[id_]
        prevStatus = member.status
        if prevStatus != newStatus:
            member.status = newStatus
            Logger.bot.info(f"{member.ign} status {prevStatus} -> {newStatus}")
            await Event.broadcast("memberStatusChange", id_, prevStatus)
    
    @classmethod
    async def update(cls, id_, dMember: Member):
        member = cls.members[id_]
        ranks = Discord.get_rank(dMember) if dMember else (None, None)
        if not ranks:
            ranks = (None, None)
        rank, vRank = ranks

        discordId = dMember.id if dMember else None
        if member.discordId != discordId:
            prevDiscordId = member.discordId

            prevDMember = None if prevDiscordId is None \
                else Discord.guild.get_member(prevDiscordId)
            Logger.bot.info(f"{member.ign} discord change {prevDMember} -> {dMember}")

            member.discordId = discordId
            if prevDiscordId is not None:
                del cls.discordIdMap[prevDiscordId]
                if discordId is not None:
                    cls.discordIdMap[discordId] = member.id

            await Event.broadcast("memberDiscordChange", id_, prevDiscordId)
        
        if member.rank != rank:
            Logger.bot.info(f"{member.ign} rank change {member.rank} -> {rank}")
            prevRank = member.rank
            member.rank = rank
            await Event.broadcast("memberRankChange", id_, prevRank)
        
        if member.vRank != vRank:
            Logger.bot.info(f"{member.ign} vRank change {member.vRank} -> {vRank}")
            prevVRank = member.vRank
            member.vRank = vRank
            await Event.broadcast("memberVRankChange", id_, prevVRank)
    
    @classmethod
    async def ign_check(cls, id_):
        currIgn = await WynnAPI.get_player_ign(id_)
        member = cls.members[id_]
        if member.ign != currIgn:
            prevIgn = member.ign
            member.ign = currIgn

            del cls.ignIdMap[prevIgn]
            cls.ignIdMap[currIgn] = id_

            Logger.bot.info(f"{prevIgn} changed ign to {currIgn}")
            await Event.broadcast("memberIgnChange", id_, prevIgn)
            return True
    
    @classmethod
    async def iterate(cls, filter_=None, mapper=None):
        members = cls.members.values()
        if filter_:
            members = filter(filter_, members)
        if mapper:
            members = map(mapper, members)
        for member in members:
            yield member
    
    @classmethod
    def get_member_named(cls, ign):
        id_ = cls.ignIdMap.get(ign, None)
        return cls.members[id_] if id_ else None
    
    @classmethod
    def is_ign_active(cls, ign):
        member = cls.get_member_named(ign)
        return member.status == cls.ACTIVE if member else False
    
    @classmethod
    def is_ign_member(cls, ign):
        member = cls.get_member_named(ign)
        return member.status != cls.REMOVED if member else False

    def __init__(self, id_, dMember: Member, ranks, ign, ownerId=False):
        if dMember:
            Logger.bot.info(f"Added {dMember}({dMember.nick}) as guild member")
        else:
            Logger.bot.info(f"Added alt {ign} as guild member")

        self.id = id_
        self.discordId = dMember.id if dMember else None
        
        self.ign = ign
        self.rank, self.vRank = ranks if ranks else (None, None)

        self.status = GuildMember.ACTIVE
        self.ownerId = ownerId

    def __repr__(self):
        s = "<GuildMember"
        properties = ["ign", "rank", "vRank"]
        for p in properties:
            if hasattr(self, p):
                s += f" {p}={getattr(self, p)}"
        return s + ">"
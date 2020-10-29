from typing import Set, Union, Tuple
from os import getenv
from re import match

from discord import Member, Guild, TextChannel, Message, Embed, Role
from discord.utils import find
from discord.ext import commands

from logger import Logger
from msgmaker import *
from reactablemessage import PagedMessage, ConfirmMessage
from util.cmdutil import parser
from util.discordutil import Discord
from state.config import Config
from state.state import State


class Configuration(commands.Cog):
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        for attr, val in Config.__dict__:
            if attr.startswith("channel_"):
                if val == channel.id:
                    setattr(Config, attr, None)
                    Logger.bot.info(f"{attr} set None due to channel deletion")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        for attr, val in Config.__dict__:
            if attr.startswith("user_"):
                if member.id in val:
                    val.remove(member.id)
                    Logger.bot.info(f"removed {member} from {attr} due to member removal")
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        for attr, val in Config.__dict__:
            if attr.startswith("role_"):
                if val == role.id:
                    setattr(Config, attr, None)
                    Logger.bot.info(f"{attr} set None due to role deletion")

    async def cog_check(self, ctx: commands.Context):
        return await Discord.rank_check(ctx, "Cosmonaut")

    @parser("config", isGroup=True)
    async def display_config(self, ctx: commands.Context):
        text = "\n".join(State.registry[Config])
        await ctx.send(embed=make_alert(text, title="Configuration", color=COLOR_INFO))

    def _config_change_cb(self, cb, logMsg):
        cb()
        Logger.bot.info(logMsg)
    
    async def _config_val(self, ctx, name, valGetter, valParser, type_, reset, set_):
        field = name + "_" + type_
        fieldDisplay = type_ + " " + name

        if not reset and not set_:
            val = valGetter(getattr(Config, field))
            text = str(val) if val else "Not set"
            await ctx.send(embed=make_alert(text, title=field, color=COLOR_INFO))
            return

        if reset:
            val = valGetter(getattr(Config, field))
            if not val:
                text = f"There are no {name} set as {fieldDisplay}"
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return
            text = f"Are you sure to reset {fieldDisplay}? (currently {val})"
            successText = f"Successfully reset {fieldDisplay}."

            cb = lambda: setattr(Config, field, None)
            logMsg = f"Reset {field} from {val} to None by {ctx.author}"
        else:
            val = valParser(set_)
            if not val:
                await ctx.send(embed=make_alert(f"bad {name} input"))
                return

            if getattr(Config, field) == val.id:
                text = f"{val} is already set as {fieldDisplay}."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return

            text = f"Are you sure to set {val} as {fieldDisplay}?"
            successText = f"Successfully set {val} as {fieldDisplay}."

            cb = lambda: setattr(Config, field, val.id)
            prev = getattr(Config, field)
            if prev:
                prev = valGetter(prev)
            logMsg = f"Changed {field} from {prev} to {val} by {ctx.author}"
        
        await ConfirmMessage(
            ctx, text, successText, self._config_change_cb, cb, logMsg).init()

    @parser("config channel", ["type", 
        ("xpLog", "bwReport", "memberLog", "claimLog", "claimAlert")], 
        ["reset"], "-set", parent=display_config, type="type_", set="set_")
    async def config_channel(self, ctx: commands.Context, type_, reset, set_):
        getter = Discord.guild.get_channel
        parser = Discord.parse_channel
        await self._config_val(ctx, "channel", getter, parser, type_, reset, set_)

    @parser("config role", ["type", ("claimAlert",)], ["reset"], "-set", 
        parent=display_config, type="type_", set="set_")
    async def config_role(self, ctx, type_, reset, set_):
        getter = Discord.guild.get_role
        parser = Discord.parse_role
        await self._config_val(ctx, "role", getter, parser, type_, reset, set_)
    
    @parser("config user", ["type", ("dev",)], "-remove", "-add",
        parent=display_config, type="type_")
    async def config_user(self, ctx: commands.Context, type_, remove, add):
        field = f"user_{type_}"
        users = getattr(Config, field)

        if not remove and not add:
            if users:
                text = ", ".join(map(lambda i: str(Discord.guild.get_member(i)), users))
            else:
                text = "Empty"
            await ctx.send(embed=make_alert(text, title=field, color=COLOR_INFO))
            return
        
        user = Discord.parse_user(remove or add)
        if not user:
            await ctx.send(embed=make_alert("bad user input"))
            return

        if remove:
            if user.id not in users:
                text = f"{user} is not part of {type_} users."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return
            
            text = f"Are you sure to remove {user} from {type_} users?"
            successText = f"Successfully removed {user} from {type_} users."

            cb = lambda: getattr(Config, field).remove(user.id)
            logMsg = f"Removed {user} from {field} by {ctx.author}"
        else:
            if user.id in users:
                text = f"{user} is already part of {type_} users."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return

            text = f"Are you sure to add {user} to {type_} users?"
            successText = f"Successfully added {user} to {type_} users."

            cb = lambda: getattr(Config, field).add(user.id)
            logMsg = f"Added {user} to {field} by {ctx.author}"
        
        await ConfirmMessage(
            ctx, text, successText, self._config_change_cb, cb, logMsg).init()
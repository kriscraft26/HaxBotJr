from discord.ext.commands import Context

from msgmaker import make_alert
from state.state import State


@State.register("user_dev", "channel_xpLog", "channel_bwReport", "channel_memberLog",
    "channel_claimLog", "channel_claimAlert", "role_claimAlert")
class Config:

    user_dev = set()
    
    channel_xpLog = None
    channel_bwReport = None
    channel_memberLog = None
    channel_claimLog = None
    channel_claimAlert = None
    
    role_claimAlert = None
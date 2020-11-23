from util.timeutil import now
from state.state import State


@State.register("stamps")
class APIStamp:

    stamps = {}

    @classmethod
    def set_stamp(cls, param, stamp):
        id_ = id(param)
        prevStamp = cls.stamps.get(id_, (None, None))[0]
        if prevStamp is None or stamp > prevStamp:
            cls.stamps[id_] = (stamp, now())
            return bool(prevStamp)
        return False
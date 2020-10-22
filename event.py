class Event:

    _listeners = {}

    @staticmethod
    def listen(type_, callback):
        if type_ not in Event._listeners:
            Event._listeners[type_] = set()
        Event._listeners[type_].add(callback)
    
    @staticmethod
    async def broadcast(type_, *args, **kwargs):
        if type_ in Event._listeners:
            for cb in Event._listeners[type_]:
                await cb(*args, **kwargs)
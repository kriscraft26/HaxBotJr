class AsyncDict(dict):

    def __init__(self, iterable):
        super().__init__(iterable)
        self.itemSetBuffer = {}
        self.itemDeleteBuffer = set()
        self.locked = False
    
    def __setitem__(self, key, value):
        if getattr(self, "locked", False):
            self.itemSetBuffer[key] = value
        else:
            super().__setitem__(key, value)
    
    def __delitem__(self, key):
        if self.locked:
            self.itemDeleteBuffer.add(key)
        else:
            super().__delitem__(key)
    
    def __enter__(self):
        self.lock()
    
    def __exit__(self, exceptionType, exceptionValue, traceback):
        self.unlock()
    
    def lock(self):
        self.locked = True
    
    def unlock(self):
        self.locked = False
        for key, value in self.itemSetBuffer.items():
            super().__setitem__(key, value)
        self.itemSetBuffer.clear()
        for key in self.itemDeleteBuffer:
            super().__delitem__(key)
        self.itemDeleteBuffer.clear()
    
    def _apply_modifiers(self, gen, filter_, mapper):
        if filter_:
            gen = filter(filter_, gen)
        if mapper:
            gen = map(mapper, gen)
        return gen

    async def aitems(self, filter_=None, mapper=None):
        for item in self._apply_modifiers(super().items(), filter_, mapper):
            yield item
    
    async def avalues(self, filter_=None, mapper=None):
        for value in self._apply_modifiers(super().values(), filter_, mapper):
            yield value
    
    async def akeys(self, filter_=None, mapper=None):
        for key in self._apply_modifiers(super().keys(), filter_, mapper):
            yield key
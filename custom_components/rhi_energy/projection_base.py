from __future__ import annotations

from copy import deepcopy


class PublicProjectionBase:
    def __init__(self, runtime, store, metering, interaction, manager):
        self.runtime=runtime; self.store=store; self.metering=metering; self.interaction=interaction; self.manager=manager
        self._cache={}; self._v2={}; self._callbacks={}; self._removers=[]

    def start(self):
        # Runtime has a dedicated semantic/public callback so diagnostics-only
        # recomputes do not rebuild the complete Public V2 contract.
        if hasattr(self.runtime, 'add_public_callback'):
            self._removers.append(self.runtime.add_public_callback(self.request_recompute))
        elif hasattr(self.runtime, 'add_callback'):
            self._removers.append(self.runtime.add_callback(self.request_recompute))
        for owner in (self.store,self.metering,self.interaction,self.manager):
            if hasattr(owner,'add_callback'):
                self._removers.append(owner.add_callback(self.request_recompute))
        self.recompute()

    def add_callback(self, object_id, cb):
        self._callbacks.setdefault(object_id,[]).append(cb)
        def remove():
            rows=self._callbacks.get(object_id,[])
            if cb in rows: rows.remove(cb)
        return remove

    def get_v2(self):
        return deepcopy(self._v2)

    def add_v2_callback(self, cb):
        return self.add_callback('__public_v2__',cb)

    def request_recompute(self):
        self.recompute()

    async def async_stop(self):
        for remove in self._removers:
            if callable(remove): remove()
        self._removers=[]; self._callbacks={}

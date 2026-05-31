import sys
from types import ModuleType

# Robust stub implementations for missing platform C-extensions on this host
class DummyModule:
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return DummyModule()
    def __call__(self, *args, **kwargs):
        return DummyModule()
    def __int__(self):
        return 0
    def __repr__(self):
        return "dummy_resource"
    def __str__(self):
        return "dummy_resource"
    def __contains__(self, item):
        return False
    def __iter__(self):
        return iter([])
    def __len__(self):
        return 0
    def __bool__(self):
        return True
    def __eq__(self, other):
        return isinstance(other, DummyModule)
    def __hash__(self):
        return hash(id(self))
    def __add__(self, other):
        return str(self) + str(other)
    def __radd__(self, other):
        return str(other) + str(self)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

class SelectStub:
    def select(self, r, w, x, timeout=None):
        return [], [], []
    # Do not define __getattr__, so that hasattr(select, 'epoll') returns False!

dummy = DummyModule()
sys.modules['_overlapped'] = dummy
sys.modules['_multiprocessing'] = dummy
sys.modules['select'] = SelectStub()

# Mock multiprocessing.resource_tracker to avoid POSIX spawnv_passfds calls on Windows
m = ModuleType('multiprocessing.resource_tracker')
m.register = m.unregister = m.ensure_running = lambda *args, **kw: None
m.getfd = lambda *args, **kw: -1
class FakeResourceTracker:
    def __init__(self, *args, **kw): pass
    def register(self, *args, **kw): pass
    def unregister(self, *args, **kw): pass
    def ensure_running(self, *args, **kw): pass
    def getfd(self, *args, **kw): return -1
m.ResourceTracker = FakeResourceTracker
m._resource_tracker = m
sys.modules['multiprocessing.resource_tracker'] = m

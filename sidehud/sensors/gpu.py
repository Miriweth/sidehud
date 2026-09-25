from . import amd, nvidia

_backend = None


def query():
    """First GPU that answers wins, and is used from then on."""
    global _backend
    if _backend is None:
        for mod in (nvidia, amd):
            data = mod.query()
            if data is not None:
                _backend = mod
                return data
        return None
    return _backend.query()


def backend_name():
    return _backend.__name__.rsplit(".", 1)[-1] if _backend else None

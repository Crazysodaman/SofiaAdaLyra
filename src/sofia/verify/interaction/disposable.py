"""Application-owned cleanup for disposable interaction probes."""
from sofia.application.bootstrap import SofiaApplication


def close_disposable_application(app: SofiaApplication, *, started: bool) -> None:
    """Use normal shutdown after startup; release constructor resources otherwise."""
    if started:
        app.shutdown()
        return
    try:
        app.conversation.close()
    finally:
        try:
            app.runtime.memory_system.close()
        finally:
            try:
                app.runtime.filesystem_observation_store.close()
            finally:
                app.runtime.operational_store.close()

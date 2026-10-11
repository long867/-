"""Redis lease prevents two Beat instances from dispatching the same schedule."""

import os
import socket
import time

from celery.beat import PersistentScheduler

from app.core.task_history import client


class LeaderScheduler(PersistentScheduler):
    """One active scheduler, durable local checkpoints and expiring heartbeat."""

    def __init__(self, *args, **kwargs):
        self.lazy = kwargs.get("lazy", False)
        if self.lazy:
            # Celery creates a display-only scheduler before the real one.
            self.ops_redis = self.lease = None
            super().__init__(*args, **kwargs)
            return
        self.ops_redis = client()
        self.lease = self.ops_redis.lock(
            "miningintel:ops:beat-leader", timeout=90, blocking=False
        )
        if not self.lease.acquire():
            raise RuntimeError(
                "MiningIntel Beat is already running; stop the other instance"
            )
        try:
            super().__init__(*args, **kwargs)
        except BaseException:
            self.lease.release()
            self.ops_redis.close()
            raise

    def tick(self, *args, **kwargs):
        """Refresh ownership before sending tasks; stop on Redis/lease loss."""
        self.lease.extend(90, replace_ttl=True)
        self.ops_redis.set("miningintel:ops:beat-heartbeat", str(time.time()), ex=90)
        self.ops_redis.set(
            "miningintel:ops:beat-host", f"{socket.gethostname()}:{os.getpid()}", ex=90
        )
        return min(30, super().tick(*args, **kwargs))

    def close(self):
        """Release only our own lease, even during normal shutdown."""
        if self.lazy:
            return
        try:
            super().close()
        finally:
            if self.lease.owned():
                self.ops_redis.delete(
                    "miningintel:ops:beat-heartbeat", "miningintel:ops:beat-host"
                )
                self.lease.release()
            self.ops_redis.close()

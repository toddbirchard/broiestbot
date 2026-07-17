from typing import Dict, List, Optional

import pytest


class FakeRedis:
    """Minimal in-memory Redis stand-in (mirrors `decode_responses=True` semantics)."""

    def __init__(self):
        self.store: Dict[str, Dict[str, str]] = {}

    def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        values = self.store.setdefault(name, {})
        values[key] = str(int(values.get(key, "0")) + amount)
        return int(values[key])

    def expire(self, name: str, seconds: int) -> bool:
        return name in self.store

    def hgetall(self, name: str) -> Dict[str, str]:
        return dict(self.store.get(name, {}))

    def hget(self, name: str, key: str) -> Optional[str]:
        return self.store.get(name, {}).get(key)

    def hexists(self, name: str, key: str) -> bool:
        return key in self.store.get(name, {})

    def hdel(self, name: str, *keys: str) -> int:
        values = self.store.get(name, {})
        return sum(1 for key in keys if values.pop(key, None) is not None)

    def hvals(self, name: str) -> List[str]:
        return list(self.store.get(name, {}).values())


@pytest.fixture
def redis_mock() -> FakeRedis:
    """
    In-memory Redis instance for tests.

    :returns: FakeRedis
    """
    return FakeRedis()


@pytest.fixture
def tovala_poll_results() -> Dict[str, str]:
    """
    Example result of a collective Tovala sighting between all bots.

    :returns: Dict[str, str]
    """
    return {
        "broiestbro": str(1),
        "broiestbot": str(1),
        "acleebot": str(1),
        "lmaolover": str(1),
    }

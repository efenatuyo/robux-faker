from collections import deque
from typing import Optional, Tuple, Any

class DequeDict:
    def __init__(self, maxlen: int = 100):
        self.data: dict = {}
        self.order: deque = deque()
        self.maxlen: int = maxlen

    def set(self, key: Any, value: Any) -> None:
        if key not in self.data:
            self.order.append(key)
            if len(self.order) > self.maxlen:
                old = self.order.popleft()
                self.data.pop(old, None)
        self.data[key] = value

    def get(self, key: Any) -> Optional[Any]:
        return self.data.get(key)

    def pop_left(self) -> Optional[Tuple[Any, Any]]:
        if not self.order:
            return None
        key = self.order.popleft()
        return key, self.data.pop(key, None)

    def pop_right(self) -> Optional[Tuple[Any, Any]]:
        if not self.order:
            return None
        key = self.order.pop()
        return key, self.data.pop(key, None)

    def __len__(self) -> int:
        return len(self.data)

    def keys(self) -> list:
        return list(self.order)

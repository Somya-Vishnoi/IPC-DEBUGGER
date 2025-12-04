from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from collections import deque


class IPCType(Enum):
    PIPE = auto()
    MSG_QUEUE = auto()
    SHARED_MEMORY = auto()


@dataclass
class IPCObject:
    id: str
    ipc_type: IPCType


@dataclass
class Pipe(IPCObject):
    capacity: int = 10
    buffer: deque = field(default_factory=deque)

    def __init__(self, id: str, capacity: int = 10):
        super().__init__(id=id, ipc_type=IPCType.PIPE)
        self.capacity = capacity
        self.buffer = deque()

    def can_write(self) -> bool:
        return len(self.buffer) < self.capacity

    def can_read(self) -> bool:
        return len(self.buffer) > 0

    def write(self, data: Any):
        if not self.can_write():
            raise RuntimeError("Pipe full")
        self.buffer.append(data)

    def read(self) -> Any:
        if not self.can_read():
            raise RuntimeError("Pipe empty")
        return self.buffer.popleft()


@dataclass
class MessageQueue(IPCObject):
    capacity: int = 10
    queue: deque = field(default_factory=deque)

    def __init__(self, id: str, capacity: int = 10):
        super().__init__(id=id, ipc_type=IPCType.MSG_QUEUE)
        self.capacity = capacity
        self.queue = deque()

    def can_send(self) -> bool:
        return len(self.queue) < self.capacity

    def can_recv(self) -> bool:
        return len(self.queue) > 0

    def send(self, msg: Any):
        if not self.can_send():
            raise RuntimeError("Queue full")
        self.queue.append(msg)

    def recv(self) -> Any:
        if not self.can_recv():
            raise RuntimeError("Queue empty")
        return self.queue.popleft()


@dataclass
class SharedMemory(IPCObject):
    data: Any = None
    lock_holder: Optional[str] = None     # pid
    wait_queue: deque = field(default_factory=deque)

    def __init__(self, id: str, initial_data: Any = None):
        super().__init__(id=id, ipc_type=IPCType.SHARED_MEMORY)
        self.data = initial_data
        self.lock_holder = None
        self.wait_queue = deque()

    def is_free(self) -> bool:
        return self.lock_holder is None

    def lock(self, pid: str) -> bool:
        if self.is_free():
            self.lock_holder = pid
            return True
        if self.lock_holder != pid:
            self.wait_queue.append(pid)
            return False
        return True  # already locked by same pid

    def unlock(self, pid: str):
        if self.lock_holder != pid:
            raise RuntimeError("Unlock by non-holder")
        self.lock_holder = None
        if self.wait_queue:
            next_pid = self.wait_queue.popleft()
            self.lock_holder = next_pid

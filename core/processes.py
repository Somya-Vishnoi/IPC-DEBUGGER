from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional


class ProcessState(Enum):
    READY = auto()
    RUNNING = auto()
    BLOCKED = auto()
    FINISHED = auto()


class OpType(Enum):
    WRITE_PIPE = auto()
    READ_PIPE = auto()
    SEND_MSG = auto()
    RECV_MSG = auto()
    LOCK = auto()
    UNLOCK = auto()
    READ_SHM = auto()
    WRITE_SHM = auto()
    NOP = auto()


@dataclass
class Operation:
    op_type: OpType
    target: Optional[str] = None  # pipe/queue/shm id
    data: Any = None              # data, size, or payload description


@dataclass
class Process:
    pid: str
    name: str
    operations: List[Operation]
    pc: int = 0
    state: ProcessState = ProcessState.READY
    wait_reason: Optional[str] = None

    def has_finished(self) -> bool:
        return self.pc >= len(self.operations)

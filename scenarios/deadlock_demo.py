from typing import Dict, Tuple

from core.processes import Process, Operation, OpType
from core.ipc import SharedMemory, IPCObject


def build_deadlock_scenario() -> Tuple[Dict[str, Process], Dict[str, IPCObject]]:
    shm_a = SharedMemory("A", initial_data=0)
    shm_b = SharedMemory("B", initial_data=0)

    p1 = Process(
        pid="P1",
        name="P1",
        operations=[
            Operation(OpType.LOCK, "A"),
            Operation(OpType.LOCK, "B"),
            Operation(OpType.WRITE_SHM, "A", data=1),
            Operation(OpType.UNLOCK, "B"),
            Operation(OpType.UNLOCK, "A"),
        ],
    )

    p2 = Process(
        pid="P2",
        name="P2",
        operations=[
            Operation(OpType.LOCK, "B"),
            Operation(OpType.LOCK, "A"),
            Operation(OpType.WRITE_SHM, "B", data=2),
            Operation(OpType.UNLOCK, "A"),
            Operation(OpType.UNLOCK, "B"),
        ],
    )

    processes = {p1.pid: p1, p2.pid: p2}
    ipcs = {shm_a.id: shm_a, shm_b.id: shm_b}
    return processes, ipcs
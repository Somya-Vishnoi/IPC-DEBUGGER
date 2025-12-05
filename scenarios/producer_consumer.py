from typing import Dict, Tuple

from core.processes import Process, Operation, OpType
from core.ipc import Pipe, IPCObject


def build_producer_consumer_scenario() -> Tuple[Dict[str, Process], Dict[str, IPCObject]]:
    pipe1 = Pipe("pipe1", capacity=2)

    producer = Process(
        pid="P1",
        name="Producer",
        operations=[
            Operation(OpType.WRITE_PIPE, "pipe1", data="item1"),
            Operation(OpType.WRITE_PIPE, "pipe1", data="item2"),
            Operation(OpType.WRITE_PIPE, "pipe1", data="item3"),
        ],
    )

    consumer = Process(
        pid="P2",
        name="Consumer",
        operations=[
            Operation(OpType.READ_PIPE, "pipe1"),
            Operation(OpType.READ_PIPE, "pipe1"),
            Operation(OpType.READ_PIPE, "pipe1"),
        ],
    )

    processes = {producer.pid: producer, consumer.pid: consumer}
    ipcs = {pipe1.id: pipe1}
    return processes, ipcs

import json
from typing import Dict, Any, Tuple, List

from .processes import Process, Operation, OpType
from .ipc import IPCObject, Pipe, MessageQueue, SharedMemory, IPCType


# ---------- SERIALIZATION HELPERS ----------

def _op_to_dict(op: Operation) -> Dict[str, Any]:
    return {
        "op_type": op.op_type.name,
        "target": op.target,
        "data": op.data,
    }


def _op_from_dict(d: Dict[str, Any]) -> Operation:
    op_type = OpType[d["op_type"]]
    target = d.get("target")
    data = d.get("data")
    return Operation(op_type=op_type, target=target, data=data)


def _process_to_dict(p: Process) -> Dict[str, Any]:
    return {
        "pid": p.pid,
        "name": p.name,
        "operations": [_op_to_dict(op) for op in p.operations],
    }


def _process_from_dict(d: Dict[str, Any]) -> Process:
    ops = [_op_from_dict(x) for x in d.get("operations", [])]
    return Process(
        pid=d["pid"],
        name=d.get("name", d["pid"]),
        operations=ops,
    )


def _ipc_to_dict(ipc: IPCObject) -> Dict[str, Any]:
    base = {
        "id": ipc.id,
        "type": ipc.ipc_type.name,
    }
    if isinstance(ipc, Pipe):
        base["capacity"] = ipc.capacity
    elif isinstance(ipc, MessageQueue):
        base["capacity"] = ipc.capacity
    elif isinstance(ipc, SharedMemory):
        base["initial_data"] = ipc.data
    return base


def _ipc_from_dict(d: Dict[str, Any]) -> IPCObject:
    ipc_type = IPCType[d["type"]]
    ipc_id = d["id"]

    if ipc_type == IPCType.PIPE:
        capacity = d.get("capacity", 10)
        return Pipe(ipc_id, capacity=capacity)
    elif ipc_type == IPCType.MSG_QUEUE:
        capacity = d.get("capacity", 10)
        return MessageQueue(ipc_id, capacity=capacity)
    elif ipc_type == IPCType.SHARED_MEMORY:
        initial_data = d.get("initial_data", None)
        return SharedMemory(ipc_id, initial_data=initial_data)
    else:
        raise ValueError(f"Unknown IPCType: {ipc_type}")


# ---------- PUBLIC API ----------

def scenario_to_dict(
    processes: Dict[str, Process],
    ipcs: Dict[str, IPCObject],
) -> Dict[str, Any]:
    return {
        "processes": [_process_to_dict(p) for p in processes.values()],
        "ipcs": [_ipc_to_dict(ipc) for ipc in ipcs.values()],
    }


def scenario_from_dict(d: Dict[str, Any]) -> Tuple[Dict[str, Process], Dict[str, IPCObject]]:
    proc_list = d.get("processes", [])
    ipc_list = d.get("ipcs", [])

    processes: Dict[str, Process] = {}
    ipcs: Dict[str, IPCObject] = {}

    for p_data in proc_list:
        p = _process_from_dict(p_data)
        processes[p.pid] = p

    for ipc_data in ipc_list:
        ipc = _ipc_from_dict(ipc_data)
        ipcs[ipc.id] = ipc

    return processes, ipcs


def save_scenario_to_json(
    filepath: str,
    processes: Dict[str, Process],
    ipcs: Dict[str, IPCObject],
) -> None:
    data = scenario_to_dict(processes, ipcs)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_scenario_from_json(filepath: str) -> Tuple[Dict[str, Process], Dict[str, IPCObject]]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return scenario_from_dict(data)

from typing import Dict, Any, Tuple, List
from collections import defaultdict

from .processes import Process, ProcessState, Operation, OpType
from .ipc import IPCObject, Pipe, MessageQueue, SharedMemory
from .events import Event


class SimulationEngine:
    def __init__(self, processes: Dict[str, Process], ipcs: Dict[str, IPCObject]):
        self.processes: Dict[str, Process] = processes
        self.ipcs: Dict[str, IPCObject] = ipcs
        self.time: int = 0
        self.events: List[Event] = []
        self.deadlocked: bool = False
        self._sched_index: int = 0  # simple round-robin index

        self.state_history: Dict[str, List[ProcessState]] = {pid: [] for pid in processes}
        self.block_counts_by_ipc: Dict[str, int] = defaultdict(int)
        self.block_events: List[Tuple[int, str, str]] = []  # (time, pid, resource)

    def reset(self):
        self.time = 0
        self.events.clear()
        self.deadlocked = False
        self._sched_index = 0
        for p in self.processes.values():
            p.pc = 0
            p.state = ProcessState.READY
            p.wait_reason = None
        self.state_history = {pid: [] for pid in self.processes}
        self.block_counts_by_ipc.clear()
        self.block_events.clear()

    def snapshot_states(self):
        for pid, p in self.processes.items():
            self.state_history[pid].append(p.state)

    def all_finished(self) -> bool:
        return all(p.has_finished() for p in self.processes.values())

    def step(self) -> bool:
        if self.deadlocked or self.all_finished():
            return False

        progressed = False
        num_procs = len(self.processes)
        if num_procs == 0:
            return False

        pids = list(self.processes.keys())

        for _ in range(num_procs):
            pid = pids[self._sched_index]
            proc = self.processes[pid]

            self._sched_index = (self._sched_index + 1) % num_procs

            if proc.state in (ProcessState.FINISHED, ProcessState.BLOCKED):
                continue

            if proc.has_finished():
                proc.state = ProcessState.FINISHED
                continue

            op = proc.operations[proc.pc]
            proc.state = ProcessState.RUNNING
            progressed_this = self._execute_operation(proc, op)
            progressed = progressed or progressed_this
            break

        if not progressed and not self.all_finished():
            if all(
                (p.state in (ProcessState.BLOCKED, ProcessState.FINISHED))
                for p in self.processes.values()
            ):
                self.deadlocked = True
                self.events.append(
                    Event(
                        time=self.time,
                        pid="SYSTEM",
                        action="DEADLOCK",
                        result="DETECTED",
                        details={},
                    )
                )

        self.snapshot_states()
        self.time += 1
        return progressed

    def run(self, max_steps: int = 1000):
        steps = 0
        while steps < max_steps and not self.all_finished() and not self.deadlocked:
            progressed = self.step()
            if not progressed and not self.all_finished():
                break
            steps += 1

    def _log_event(self, pid: str, action: str, result: str, **details: Any):
        ev = Event(time=self.time, pid=pid, action=action, result=result, details=details)
        self.events.append(ev)

    def _execute_operation(self, proc: Process, op: Operation) -> bool:
        pid = proc.pid
        action_desc = op.op_type.name

        if op.op_type in (
            OpType.WRITE_PIPE, OpType.READ_PIPE,
            OpType.SEND_MSG, OpType.RECV_MSG,
            OpType.LOCK, OpType.UNLOCK,
            OpType.READ_SHM, OpType.WRITE_SHM
        ):
            if op.target not in self.ipcs:
                self._log_event(pid, action_desc, "ERROR_NO_SUCH_IPC", target=op.target)
                proc.state = ProcessState.FINISHED
                proc.pc += 1
                return True

        if op.op_type == OpType.NOP:
            self._log_event(pid, "NOP", "OK")
            proc.state = ProcessState.READY
            proc.pc += 1
            return True

        ipc = self.ipcs.get(op.target) if op.target else None

        try:
            if op.op_type == OpType.WRITE_PIPE and isinstance(ipc, Pipe):
                if ipc.can_write():
                    ipc.write(op.data)
                    self._log_event(pid, "WRITE_PIPE", "OK", target=ipc.id, data=op.data)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                else:
                    self._log_event(pid, "WRITE_PIPE", "BLOCKED", target=ipc.id)
                    proc.state = ProcessState.BLOCKED
                    proc.wait_reason = f"Pipe {ipc.id} full"
                    self.block_counts_by_ipc[ipc.id] += 1
                    self.block_events.append((self.time, pid, ipc.id))
                    return False

            elif op.op_type == OpType.READ_PIPE and isinstance(ipc, Pipe):
                if ipc.can_read():
                    data = ipc.read()
                    self._log_event(pid, "READ_PIPE", "OK", target=ipc.id, data=data)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                else:
                    self._log_event(pid, "READ_PIPE", "BLOCKED", target=ipc.id)
                    proc.state = ProcessState.BLOCKED
                    proc.wait_reason = f"Pipe {ipc.id} empty"
                    self.block_counts_by_ipc[ipc.id] += 1
                    self.block_events.append((self.time, pid, ipc.id))
                    return False

            elif op.op_type == OpType.SEND_MSG and isinstance(ipc, MessageQueue):
                if ipc.can_send():
                    ipc.send(op.data)
                    self._log_event(pid, "SEND_MSG", "OK", target=ipc.id, data=op.data)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                else:
                    self._log_event(pid, "SEND_MSG", "BLOCKED", target=ipc.id)
                    proc.state = ProcessState.BLOCKED
                    proc.wait_reason = f"Queue {ipc.id} full"
                    self.block_counts_by_ipc[ipc.id] += 1
                    self.block_events.append((self.time, pid, ipc.id))
                    return False

            elif op.op_type == OpType.RECV_MSG and isinstance(ipc, MessageQueue):
                if ipc.can_recv():
                    msg = ipc.recv()
                    self._log_event(pid, "RECV_MSG", "OK", target=ipc.id, data=msg)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                else:
                    self._log_event(pid, "RECV_MSG", "BLOCKED", target=ipc.id)
                    proc.state = ProcessState.BLOCKED
                    proc.wait_reason = f"Queue {ipc.id} empty"
                    self.block_counts_by_ipc[ipc.id] += 1
                    self.block_events.append((self.time, pid, ipc.id))
                    return False

            elif op.op_type == OpType.LOCK and isinstance(ipc, SharedMemory):
                if ipc.is_free():
                    ipc.lock_holder = pid
                    self._log_event(pid, "LOCK", "OK", target=ipc.id)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                else:
                    if pid != ipc.lock_holder:
                        ipc.wait_queue.append(pid)
                        self._log_event(
                            pid, "LOCK", "BLOCKED", target=ipc.id, holder=ipc.lock_holder
                        )
                        proc.state = ProcessState.BLOCKED
                        proc.wait_reason = f"Waiting lock on {ipc.id}"
                        self.block_counts_by_ipc[ipc.id] += 1
                        self.block_events.append((self.time, pid, ipc.id))
                        return False
                    else:
                        self._log_event(pid, "LOCK", "OK_ALREADY_HELD", target=ipc.id)
                        proc.state = ProcessState.READY
                        proc.pc += 1
                        return True

            elif op.op_type == OpType.UNLOCK and isinstance(ipc, SharedMemory):
                if ipc.lock_holder != pid:
                    self._log_event(
                        pid, "UNLOCK", "ERROR_NOT_HOLDER",
                        target=ipc.id, holder=ipc.lock_holder
                    )
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                ipc.unlock(pid)
                self._log_event(pid, "UNLOCK", "OK", target=ipc.id)
                if ipc.lock_holder:
                    holder_proc = self.processes[ipc.lock_holder]
                    if holder_proc.state == ProcessState.BLOCKED:
                        holder_proc.state = ProcessState.READY
                        holder_proc.wait_reason = None
                proc.state = ProcessState.READY
                proc.pc += 1
                return True

            elif op.op_type == OpType.READ_SHM and isinstance(ipc, SharedMemory):
                if ipc.lock_holder == pid:
                    self._log_event(pid, "READ_SHM", "OK", target=ipc.id, data=ipc.data)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                else:
                    self._log_event(pid, "READ_SHM", "UNSAFE", target=ipc.id, data=ipc.data)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True

            elif op.op_type == OpType.WRITE_SHM and isinstance(ipc, SharedMemory):
                if ipc.lock_holder == pid:
                    ipc.data = op.data
                    self._log_event(pid, "WRITE_SHM", "OK", target=ipc.id, data=op.data)
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True
                else:
                    self._log_event(pid, "WRITE_SHM", "UNSAFE", target=ipc.id, data=op.data)
                    ipc.data = op.data
                    proc.state = ProcessState.READY
                    proc.pc += 1
                    return True

            else:
                self._log_event(pid, action_desc, "ERROR_BAD_IPC_TYPE", target=op.target)
                proc.state = ProcessState.READY
                proc.pc += 1
                return True

        except RuntimeError as e:
            self._log_event(pid, action_desc, "ERROR", error=str(e), target=op.target)
            proc.state = ProcessState.READY
            proc.pc += 1
            return True

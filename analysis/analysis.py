from collections import defaultdict
from typing import Dict, Any, List, Tuple

from core.engine import SimulationEngine
from core.ipc import SharedMemory


class AnalysisEngine:
    """
    Analysis layer on top of SimulationEngine:
    - Deadlock detection
    - Bottleneck detection
    - Unsafe shared memory access detection
    - Simple risk scoring (Low / Medium / High) based on features
    """

    def __init__(self, sim: SimulationEngine):
        self.sim = sim

    # ---------- DEADLOCK ----------

    def detect_deadlock(self) -> Dict[str, Any]:
        """
        Build a basic wait-for graph for shared memory locks, detect cycles.
        """
        wait_for = defaultdict(list)

        for ipc in self.sim.ipcs.values():
            if isinstance(ipc, SharedMemory):
                holder = ipc.lock_holder
                if not holder:
                    continue
                for waiting_pid in ipc.wait_queue:
                    if waiting_pid != holder:
                        wait_for[waiting_pid].append(holder)

        visited = set()
        stack = set()
        deadlocked_pids: List[str] = []

        def dfs(u: str) -> bool:
            visited.add(u)
            stack.add(u)
            for v in wait_for.get(u, []):
                if v not in visited:
                    if dfs(v):
                        return True
                elif v in stack:
                    return True
            stack.remove(u)
            return False

        for pid in list(wait_for.keys()):
            if pid not in visited:
                if dfs(pid):
                    deadlocked_pids = list(wait_for.keys())
                    break

        return {
            "is_deadlocked": self.sim.deadlocked or bool(deadlocked_pids),
            "pids": deadlocked_pids,
            "wait_for_graph": dict(wait_for),
        }

    # ---------- BOTTLENECKS ----------

    def detect_bottlenecks(self) -> List[Dict[str, Any]]:
        """
        Use block_counts_by_ipc as a rough indicator for hot/bottleneck IPC objects.
        """
        if not self.sim.block_counts_by_ipc:
            return []

        max_blocks = max(self.sim.block_counts_by_ipc.values())
        bottlenecks = []
        for ipc_id, count in self.sim.block_counts_by_ipc.items():
            if count >= max_blocks and count > 0:
                bottlenecks.append(
                    {
                        "ipc_id": ipc_id,
                        "block_count": count,
                    }
                )
        return bottlenecks

    # ---------- UNSAFE SHM ----------

    def detect_unsafe_shared_memory_accesses(self) -> List[Dict[str, Any]]:
        """
        Look at events with READ_SHM/WRITE_SHM and result 'UNSAFE'.
        """
        issues = []
        for ev in self.sim.events:
            if ev.action in ("READ_SHM", "WRITE_SHM") and ev.result == "UNSAFE":
                issues.append(
                    {
                        "time": ev.time,
                        "pid": ev.pid,
                        "action": ev.action,
                        "target": ev.details.get("target"),
                    }
                )
        return issues

    # ---------- FEATURES + RISK SCORE ----------

    def compute_features(self) -> Dict[str, Any]:
        """
        Extract a simple feature vector from the simulation run.
        Useful both for explanation and for risk scoring.
        """
        deadlock_info = self.detect_deadlock()
        is_deadlocked = bool(deadlock_info["is_deadlocked"])
        num_deadlocked_pids = len(deadlock_info["pids"])

        # total block events
        total_block_events = sum(self.sim.block_counts_by_ipc.values())
        max_block_on_single_ipc = max(self.sim.block_counts_by_ipc.values()) if self.sim.block_counts_by_ipc else 0

        # unsafe SHM
        unsafe_shm = self.detect_unsafe_shared_memory_accesses()
        num_unsafe_accesses = len(unsafe_shm)

        # size of system
        num_processes = len(self.sim.processes)
        num_ipcs = len(self.sim.ipcs)

        return {
            "is_deadlocked": is_deadlocked,
            "num_deadlocked_pids": num_deadlocked_pids,
            "total_block_events": total_block_events,
            "max_block_on_single_ipc": max_block_on_single_ipc,
            "num_unsafe_accesses": num_unsafe_accesses,
            "num_processes": num_processes,
            "num_ipcs": num_ipcs,
        }

    def compute_risk_score(self) -> Tuple[float, str]:
        """
        Simple heuristic "risk model":
        - Deadlock contributes heavily.
        - Many block events and unsafe SHM accesses raise risk.
        Returns (score in [0,1], label 'Low'/'Medium'/'High').
        """
        f = self.compute_features()

        score = 0.0

        # Deadlock is a big deal
        if f["is_deadlocked"]:
            score += 0.6
            if f["num_deadlocked_pids"] > 1:
                score += 0.1

        # Bottlenecks / blocking
        if f["total_block_events"] > 0:
            # scale by some rough factor
            score += min(0.2, f["total_block_events"] / 50.0)
        if f["max_block_on_single_ipc"] > 0:
            score += min(0.1, f["max_block_on_single_ipc"] / 30.0)

        # Unsafe shared memory access
        if f["num_unsafe_accesses"] > 0:
            score += min(0.2, f["num_unsafe_accesses"] / 10.0)

        # Slight bump for bigger systems
        if f["num_processes"] > 5 or f["num_ipcs"] > 5:
            score += 0.05

        # clamp to [0,1]
        score = max(0.0, min(1.0, score))

        # label
        if score < 0.3:
            label = "Low"
        elif score < 0.7:
            label = "Medium"
        else:
            label = "High"

        return score, label

    def risk_summary_text(self) -> str:
        score, label = self.compute_risk_score()
        return f"{label} ({score:.2f})"

    # ---------- HUMAN-READABLE ISSUE LIST ----------

    def summarize_issues(self) -> List[str]:
        msgs: List[str] = []

        dl = self.detect_deadlock()
        if dl["is_deadlocked"]:
            if dl["pids"]:
                msgs.append(f"Deadlock detected involving processes: {', '.join(dl['pids'])}")
            else:
                msgs.append("Deadlock detected (no progress and all processes blocked).")

        bns = self.detect_bottlenecks()
        for b in bns:
            msgs.append(f"Bottleneck on IPC '{b['ipc_id']}' with {b['block_count']} block events.")

        unsafe = self.detect_unsafe_shared_memory_accesses()
        for u in unsafe:
            msgs.append(
                f"Unsafe shared memory {u['action']} by {u['pid']} on {u['target']} at t={u['time']}"
            )

        # We don't put risk summary here because the GUI shows it separately.
        return msgs

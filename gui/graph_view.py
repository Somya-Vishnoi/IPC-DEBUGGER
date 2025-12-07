from typing import Dict

import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.processes import Process
from core.ipc import IPCObject, IPCType


class GraphCanvas(FigureCanvas):
    """
    Shows a simple graph of processes and IPC objects.

    - Circles: Processes
    - Squares: IPC objects (Pipe, MessageQueue, SharedMemory)
    - Edges: "process uses this IPC somewhere in its operations"
    """

    def __init__(self, parent=None):
        fig = Figure()
        super().__init__(fig)
        self.ax = fig.add_subplot(111)
        self.setParent(parent)

    def plot_graph(self, processes: Dict[str, Process], ipcs: Dict[str, IPCObject]):
        self.ax.clear()
        G = nx.Graph()

        # Add process nodes
        for pid, proc in processes.items():
            G.add_node(
                pid,
                label=proc.name,
                kind="process",
            )

        # Add IPC nodes
        for ipc_id, ipc in ipcs.items():
            if ipc.ipc_type == IPCType.PIPE:
                kind = "pipe"
            elif ipc.ipc_type == IPCType.MSG_QUEUE:
                kind = "queue"
            elif ipc.ipc_type == IPCType.SHARED_MEMORY:
                kind = "shm"
            else:
                kind = "ipc"

            G.add_node(
                ipc_id,
                label=ipc_id,
                kind=kind,
            )

        # Add edges: process <-> IPC if process has operations using that target
        for pid, proc in processes.items():
            for op in proc.operations:
                if op.target and op.target in ipcs:
                    G.add_edge(pid, op.target)

        if len(G.nodes) == 0:
            self.ax.set_title("No processes / IPC objects to display")
            self.draw()
            return

        # Layout
        pos = nx.spring_layout(G, seed=42)

        # Separate nodes by type for styling
        proc_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "process"]
        pipe_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "pipe"]
        queue_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "queue"]
        shm_nodes = [n for n, d in G.nodes(data=True) if d.get("kind") == "shm"]

        # Draw edges
        nx.draw_networkx_edges(G, pos, ax=self.ax, width=1.0)

        # Draw processes
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=proc_nodes,
            node_shape="o",
            node_size=800,
            node_color="lightblue",
            edgecolors="black",
            ax=self.ax,
            label="Process",
        )

        # Draw pipes
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=pipe_nodes,
            node_shape="s",
            node_size=700,
            node_color="lightgreen",
            edgecolors="black",
            ax=self.ax,
            label="Pipe",
        )

        # Draw queues
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=queue_nodes,
            node_shape="D",
            node_size=700,
            node_color="khaki",
            edgecolors="black",
            ax=self.ax,
            label="Message Queue",
        )

        # Draw shared memory
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=shm_nodes,
            node_shape="s",
            node_size=700,
            node_color="lightcoral",
            edgecolors="black",
            ax=self.ax,
            label="Shared Memory",
        )

        # Labels: use node id / process name
        labels = {
            n: G.nodes[n].get("label", n)
            for n in G.nodes
        }
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=9, ax=self.ax)

        self.ax.set_axis_off()
        self.ax.set_title("IPC Topology (Processes ↔ IPC Objects)")
        self.draw()
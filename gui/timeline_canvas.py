from typing import Dict, List

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.processes import ProcessState


class TimelineCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure()
        super().__init__(fig)
        self.ax = fig.add_subplot(111)
        self.setParent(parent)

    def plot_timeline(self, state_history: Dict[str, List[ProcessState]]):
        self.ax.clear()
        if not state_history:
            self.draw()
            return

        pid_list = list(state_history.keys())
        y_positions = {pid: i for i, pid in enumerate(pid_list)}

        max_t = max(len(history) for history in state_history.values())
        if max_t == 0:
            self.draw()
            return

        state_color = {
            ProcessState.READY: "lightgray",
            ProcessState.RUNNING: "green",
            ProcessState.BLOCKED: "orange",
            ProcessState.FINISHED: "blue",
        }

        for pid, history in state_history.items():
            y = y_positions[pid]
            if not history:
                continue
            start = 0
            current_state = history[0]
            for t in range(1, len(history) + 1):
                if t == len(history) or history[t] != current_state:
                    self.ax.barh(
                        y,
                        width=t - start,
                        left=start,
                        height=0.4,
                        align="center",
                        color=state_color.get(current_state, "gray"),
                        edgecolor="black",
                    )
                    start = t
                    if t < len(history):
                        current_state = history[t]

        self.ax.set_yticks(list(y_positions.values()))
        self.ax.set_yticklabels(pid_list)
        self.ax.set_xlabel("Time (ticks)")
        self.ax.set_title("Process Timeline")
        self.ax.invert_yaxis()
        self.ax.grid(True, axis="x", linestyle="--", linewidth=0.5)
        self.draw()
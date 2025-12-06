from typing import Optional

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QListWidget,
    QTabWidget,
    QFileDialog,
    QMessageBox,
)

from core.engine import SimulationEngine
from core.scenario_io import save_scenario_to_json, load_scenario_from_json
from analysis.analysis import AnalysisEngine
from scenarios.producer_consumer import build_producer_consumer_scenario
from scenarios.deadlock_demo import build_deadlock_scenario
from .timeline_canvas import TimelineCanvas
from .graph_view import GraphCanvas
from .scenario_editor import ScenarioEditorDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPC Debugger (Python, PyQt)")
        self.resize(1200, 750)

        self.sim: Optional[SimulationEngine] = None
        self.analysis: Optional[AnalysisEngine] = None

        self._build_ui()
        self.load_scenario()  # load default

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Top controls
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)

        self.scenario_combo = QComboBox()
        self.scenario_combo.addItem("Producer-Consumer (Pipe)")
        self.scenario_combo.addItem("Deadlock (Shared Memory)")

        controls_layout.addWidget(QLabel("Scenario:"))
        controls_layout.addWidget(self.scenario_combo)

        self.btn_load = QPushButton("Load Scenario")
        self.btn_run = QPushButton("Run")
        self.btn_step = QPushButton("Step")
        self.btn_reset = QPushButton("Reset")

        controls_layout.addWidget(self.btn_load)
        controls_layout.addWidget(self.btn_run)
        controls_layout.addWidget(self.btn_step)
        controls_layout.addWidget(self.btn_reset)

        # Stage 3: Save/Load JSON
        self.btn_save_json = QPushButton("Save Scenario")
        self.btn_load_json = QPushButton("Load Scenario (JSON)")
        controls_layout.addWidget(self.btn_save_json)
        controls_layout.addWidget(self.btn_load_json)

        # Stage 4: Scenario Editor
        self.btn_edit_scenario = QPushButton("Edit Scenario")
        controls_layout.addWidget(self.btn_edit_scenario)

        controls_layout.addStretch()

        self.btn_load.clicked.connect(self.load_scenario)
        self.btn_run.clicked.connect(self.run_simulation)
        self.btn_step.clicked.connect(self.step_simulation)
        self.btn_reset.clicked.connect(self.reset_simulation)
        self.btn_save_json.clicked.connect(self.save_scenario_dialog)
        self.btn_load_json.clicked.connect(self.load_scenario_dialog)
        self.btn_edit_scenario.clicked.connect(self.edit_scenario_dialog)

        # Splitter for left (visuals) and right (logs/issues)
        splitter = QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter)

        # LEFT: Tabbed views (Timeline + Graph)
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        self.tabs = QTabWidget()
        left_layout.addWidget(self.tabs)

        # Tab 1: Timeline
        self.timeline_canvas = TimelineCanvas(self)
        timeline_tab = QWidget()
        timeline_layout = QVBoxLayout()
        timeline_tab.setLayout(timeline_layout)
        timeline_layout.addWidget(self.timeline_canvas)
        self.tabs.addTab(timeline_tab, "Timeline")

        # Tab 2: IPC Graph
        self.graph_canvas = GraphCanvas(self)
        graph_tab = QWidget()
        graph_layout = QVBoxLayout()
        graph_tab.setLayout(graph_layout)
        graph_layout.addWidget(self.graph_canvas)
        self.tabs.addTab(graph_tab, "Topology Graph")

        splitter.addWidget(left_widget)

        # RIGHT: Logs + issues + risk
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        # Events log
        right_layout.addWidget(QLabel("Events Log:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        right_layout.addWidget(self.log_text, stretch=2)

        # Risk label
        risk_layout = QHBoxLayout()
        risk_layout.addWidget(QLabel("Overall Risk:"))
        self.risk_label = QLabel("Unknown")
        risk_layout.addWidget(self.risk_label)
        risk_layout.addStretch()
        right_layout.addLayout(risk_layout)

        # Issues list
        right_layout.addWidget(QLabel("Detected Issues:"))
        self.issues_list = QListWidget()
        right_layout.addWidget(self.issues_list, stretch=1)

        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    # ---------- SCENARIO HANDLING ----------

    def load_scenario(self):
        scenario_name = self.scenario_combo.currentText()
        if "Producer" in scenario_name:
            processes, ipcs = build_producer_consumer_scenario()
        elif "Deadlock" in scenario_name:
            processes, ipcs = build_deadlock_scenario()
        else:
            processes, ipcs = build_producer_consumer_scenario()

        self.sim = SimulationEngine(processes, ipcs)
        self.analysis = AnalysisEngine(self.sim)
        self.log_text.clear()
        self.issues_list.clear()

        self.timeline_canvas.plot_timeline(self.sim.state_history)
        self.graph_canvas.plot_graph(self.sim.processes, self.sim.ipcs)
        self._update_risk_label()

    def save_scenario_dialog(self):
        if not self.sim:
            QMessageBox.warning(self, "No Scenario", "No active scenario to save.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scenario as JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not filepath:
            return

        try:
            save_scenario_to_json(filepath, self.sim.processes, self.sim.ipcs)
            QMessageBox.information(self, "Saved", f"Scenario saved to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Failed to save scenario:\n{e}")

    def load_scenario_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Scenario from JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not filepath:
            return

        try:
            processes, ipcs = load_scenario_from_json(filepath)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading", f"Failed to load scenario:\n{e}")
            return

        if not processes or not ipcs:
            QMessageBox.warning(
                self,
                "Invalid Scenario",
                "Loaded file does not contain any processes or IPC objects.",
            )
            return

        self.sim = SimulationEngine(processes, ipcs)
        self.analysis = AnalysisEngine(self.sim)
        self.log_text.clear()
        self.issues_list.clear()

        self.timeline_canvas.plot_timeline(self.sim.state_history)
        self.graph_canvas.plot_graph(self.sim.processes, self.sim.ipcs)
        self._update_risk_label()

    def edit_scenario_dialog(self):
        if not self.sim:
            QMessageBox.warning(self, "No Scenario", "Load or create a scenario first.")
            return

        dlg = ScenarioEditorDialog(self.sim.processes, self.sim.ipcs, self)
        if dlg.exec_() == dlg.Accepted:
            if dlg.result_processes and dlg.result_ipcs:
                self.sim = SimulationEngine(dlg.result_processes, dlg.result_ipcs)
                self.analysis = AnalysisEngine(self.sim)
                self.log_text.clear()
                self.issues_list.clear()
                self.timeline_canvas.plot_timeline(self.sim.state_history)
                self.graph_canvas.plot_graph(self.sim.processes, self.sim.ipcs)
                self._update_risk_label()

    # ---------- SIMULATION CONTROL ----------

    def run_simulation(self):
        if not self.sim:
            return
        self.sim.run(max_steps=200)
        self._refresh_view()

    def step_simulation(self):
        if not self.sim:
            return
        self.sim.step()
        self._refresh_view()

    def reset_simulation(self):
        if not self.sim:
            return
        self.sim.reset()
        self.log_text.clear()
        self.issues_list.clear()
        self.timeline_canvas.plot_timeline(self.sim.state_history)
        self.graph_canvas.plot_graph(self.sim.processes, self.sim.ipcs)
        self._update_risk_label()

    # ---------- VIEW REFRESH ----------

    def _refresh_view(self):
        if not self.sim:
            return

        self.timeline_canvas.plot_timeline(self.sim.state_history)
        self.graph_canvas.plot_graph(self.sim.processes, self.sim.ipcs)
        self._update_logs()
        self._update_issues()
        self._update_risk_label()

    def _update_logs(self):
        if not self.sim:
            return
        lines = []
        for ev in self.sim.events:
            detail_str = ", ".join(f"{k}={v}" for k, v in ev.details.items())
            lines.append(
                f"t={ev.time:03d} | {ev.pid:>6} | {ev.action:<10} | {ev.result:<10} | {detail_str}"
            )
        self.log_text.setPlainText("\n".join(lines))
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def _update_issues(self):
        if not self.analysis:
            return
        self.issues_list.clear()
        msgs = self.analysis.summarize_issues()
        if not msgs:
            self.issues_list.addItem("No major issues detected yet.")
        else:
            for m in msgs:
                self.issues_list.addItem(m)

    def _update_risk_label(self):
        if not self.analysis:
            self.risk_label.setText("Unknown")
            return
        try:
            self.risk_label.setText(self.analysis.risk_summary_text())
        except Exception:
            # Fallback, shouldn't happen if analysis is correct
            self.risk_label.setText("Error")
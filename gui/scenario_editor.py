from typing import Dict, Any, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QHeaderView,
    QSpinBox,
    QTextEdit,
    QMessageBox,
)

from core.processes import Process, Operation, OpType
from core.ipc import IPCObject, Pipe, MessageQueue, SharedMemory, IPCType


OP_TYPE_NAMES = [
    "WRITE_PIPE",
    "READ_PIPE",
    "SEND_MSG",
    "RECV_MSG",
    "LOCK",
    "UNLOCK",
    "READ_SHM",
    "WRITE_SHM",
    "NOP",
]


class ScenarioEditorDialog(QDialog):
    """
    Simple scenario editor:
    - Tab 1: Processes & their operations
    - Tab 2: IPC objects (pipes, queues, shared memory)
    """

    def __init__(self, processes: Dict[str, Process], ipcs: Dict[str, IPCObject], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Scenario")
        self.resize(900, 600)

        # Internal representation: plain dicts, not Process/IPC objects
        self.proc_data: Dict[str, Dict[str, Any]] = self._build_proc_data(processes)
        self.ipc_data: Dict[str, Dict[str, Any]] = self._build_ipc_data(ipcs)

        self.current_proc_pid: Optional[str] = None
        self.current_ipc_id: Optional[str] = None

        self.result_processes: Optional[Dict[str, Process]] = None
        self.result_ipcs: Optional[Dict[str, IPCObject]] = None

        self._build_ui()
        self._load_initial_selection()

    # ---------- Build initial data dicts ----------

    def _build_proc_data(self, processes: Dict[str, Process]) -> Dict[str, Dict[str, Any]]:
        data: Dict[str, Dict[str, Any]] = {}
        for pid, p in processes.items():
            ops_list: List[Dict[str, Any]] = []
            for op in p.operations:
                ops_list.append(
                    {
                        "op_type": op.op_type.name,
                        "target": op.target,
                        "data": op.data,
                    }
                )
            data[pid] = {
                "pid": pid,
                "name": p.name,
                "operations": ops_list,
            }
        return data

    def _build_ipc_data(self, ipcs: Dict[str, IPCObject]) -> Dict[str, Dict[str, Any]]:
        data: Dict[str, Dict[str, Any]] = {}
        for ipc_id, ipc in ipcs.items():
            if ipc.ipc_type == IPCType.PIPE:
                d = {
                    "id": ipc_id,
                    "type": "PIPE",
                    "capacity": getattr(ipc, "capacity", 10),
                    "initial_data": None,
                }
            elif ipc.ipc_type == IPCType.MSG_QUEUE:
                d = {
                    "id": ipc_id,
                    "type": "MSG_QUEUE",
                    "capacity": getattr(ipc, "capacity", 10),
                    "initial_data": None,
                }
            elif ipc.ipc_type == IPCType.SHARED_MEMORY:
                d = {
                    "id": ipc_id,
                    "type": "SHARED_MEMORY",
                    "capacity": None,
                    "initial_data": getattr(ipc, "data", None),
                }
            else:
                continue
            data[ipc_id] = d
        return data

    # ---------- UI ----------

    def _build_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Processes tab
        proc_tab = QWidget()
        proc_layout = QHBoxLayout()
        proc_tab.setLayout(proc_layout)

        # Left: process list
        self.proc_list = QListWidget()
        self.proc_list.currentItemChanged.connect(self._on_proc_selection_changed)
        proc_layout.addWidget(self.proc_list, 1)

        # Right: process details
        proc_detail_widget = QWidget()
        proc_detail_layout = QVBoxLayout()
        proc_detail_widget.setLayout(proc_detail_layout)
        proc_layout.addWidget(proc_detail_widget, 3)

        # PID + name
        form_pid_layout = QHBoxLayout()
        form_pid_layout.addWidget(QLabel("PID:"))
        self.proc_pid_edit = QLineEdit()
        form_pid_layout.addWidget(self.proc_pid_edit)
        form_pid_layout.addWidget(QLabel("Name:"))
        self.proc_name_edit = QLineEdit()
        form_pid_layout.addWidget(self.proc_name_edit)
        proc_detail_layout.addLayout(form_pid_layout)

        # Operations table
        self.ops_table = QTableWidget(0, 3)
        self.ops_table.setHorizontalHeaderLabels(["Op Type", "Target", "Data"])
        header = self.ops_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        proc_detail_layout.addWidget(QLabel("Operations:"))
        proc_detail_layout.addWidget(self.ops_table)

        ops_btn_layout = QHBoxLayout()
        self.btn_add_op = QPushButton("Add Operation")
        self.btn_del_op = QPushButton("Delete Operation")
        self.btn_save_proc = QPushButton("Save Process")
        ops_btn_layout.addWidget(self.btn_add_op)
        ops_btn_layout.addWidget(self.btn_del_op)
        ops_btn_layout.addStretch()
        ops_btn_layout.addWidget(self.btn_save_proc)
        proc_detail_layout.addLayout(ops_btn_layout)

        self.btn_add_op.clicked.connect(self._add_operation_row)
        self.btn_del_op.clicked.connect(self._delete_operation_row)
        self.btn_save_proc.clicked.connect(self._save_current_process)

        # Bottom proc buttons
        proc_bottom_layout = QHBoxLayout()
        self.btn_add_proc = QPushButton("Add Process")
        self.btn_delete_proc = QPushButton("Delete Process")
        proc_bottom_layout.addWidget(self.btn_add_proc)
        proc_bottom_layout.addWidget(self.btn_delete_proc)
        proc_bottom_layout.addStretch()
        proc_detail_layout.addLayout(proc_bottom_layout)

        self.btn_add_proc.clicked.connect(self._add_process)
        self.btn_delete_proc.clicked.connect(self._delete_process)

        self.tabs.addTab(proc_tab, "Processes")

        # IPC tab
        ipc_tab = QWidget()
        ipc_layout = QHBoxLayout()
        ipc_tab.setLayout(ipc_layout)

        # Left: IPC list
        self.ipc_list = QListWidget()
        self.ipc_list.currentItemChanged.connect(self._on_ipc_selection_changed)
        ipc_layout.addWidget(self.ipc_list, 1)

        # Right: IPC details
        ipc_detail_widget = QWidget()
        ipc_detail_layout = QVBoxLayout()
        ipc_detail_widget.setLayout(ipc_detail_layout)
        ipc_layout.addWidget(ipc_detail_widget, 3)

        ipc_form_layout1 = QHBoxLayout()
        ipc_form_layout1.addWidget(QLabel("ID:"))
        self.ipc_id_edit = QLineEdit()
        ipc_form_layout1.addWidget(self.ipc_id_edit)
        ipc_detail_layout.addLayout(ipc_form_layout1)

        ipc_form_layout2 = QHBoxLayout()
        ipc_form_layout2.addWidget(QLabel("Type:"))
        self.ipc_type_combo = QComboBox()
        self.ipc_type_combo.addItems(["PIPE", "MSG_QUEUE", "SHARED_MEMORY"])
        ipc_form_layout2.addWidget(self.ipc_type_combo)
        ipc_detail_layout.addLayout(ipc_form_layout2)

        # Capacity for pipe/queue
        ipc_form_layout3 = QHBoxLayout()
        self.capacity_label = QLabel("Capacity:")
        self.capacity_spin = QSpinBox()
        self.capacity_spin.setRange(1, 1000)
        self.capacity_spin.setValue(10)
        ipc_form_layout3.addWidget(self.capacity_label)
        ipc_form_layout3.addWidget(self.capacity_spin)
        ipc_detail_layout.addLayout(ipc_form_layout3)

        # Initial data for shared memory
        ipc_detail_layout.addWidget(QLabel("Initial Data (Shared Memory):"))
        self.shm_data_edit = QTextEdit()
        self.shm_data_edit.setFixedHeight(60)
        ipc_detail_layout.addWidget(self.shm_data_edit)

        self.ipc_type_combo.currentTextChanged.connect(self._on_ipc_type_changed)

        ipc_btn_layout = QHBoxLayout()
        self.btn_save_ipc = QPushButton("Save IPC")
        self.btn_add_ipc = QPushButton("Add IPC")
        self.btn_delete_ipc = QPushButton("Delete IPC")
        ipc_btn_layout.addWidget(self.btn_add_ipc)
        ipc_btn_layout.addWidget(self.btn_delete_ipc)
        ipc_btn_layout.addStretch()
        ipc_btn_layout.addWidget(self.btn_save_ipc)
        ipc_detail_layout.addLayout(ipc_btn_layout)

        self.btn_add_ipc.clicked.connect(self._add_ipc)
        self.btn_delete_ipc.clicked.connect(self._delete_ipc)
        self.btn_save_ipc.clicked.connect(self._save_current_ipc)

        self.tabs.addTab(ipc_tab, "IPC Objects")

        # Dialog buttons (OK/Cancel)
        bottom_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_ok)
        bottom_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(bottom_layout)

        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)

        # Populate lists
        self._refresh_proc_list()
        self._refresh_ipc_list()
        self._on_ipc_type_changed(self.ipc_type_combo.currentText())

    def _load_initial_selection(self):
        if self.proc_list.count() > 0:
            self.proc_list.setCurrentRow(0)
        if self.ipc_list.count() > 0:
            self.ipc_list.setCurrentRow(0)

    # ---------- Process list / details ----------

    def _refresh_proc_list(self):
        self.proc_list.clear()
        for pid, pdata in self.proc_data.items():
            item = QListWidgetItem(f"{pid} ({pdata.get('name', pid)})")
            item.setData(Qt.UserRole, pid)
            self.proc_list.addItem(item)

    def _on_proc_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        # Save previous before switching
        if previous is not None:
            self._save_current_process()

        if current is None:
            self.current_proc_pid = None
            self._clear_proc_form()
            return

        pid = current.data(Qt.UserRole)
        self.current_proc_pid = pid
        self._load_proc_into_form(pid)

    def _clear_proc_form(self):
        self.proc_pid_edit.clear()
        self.proc_name_edit.clear()
        self.ops_table.setRowCount(0)

    def _load_proc_into_form(self, pid: str):
        pdata = self.proc_data.get(pid)
        if not pdata:
            self._clear_proc_form()
            return

        self.proc_pid_edit.setText(pdata["pid"])
        self.proc_name_edit.setText(pdata.get("name", pdata["pid"]))

        self.ops_table.setRowCount(0)
        for op in pdata.get("operations", []):
            self._add_operation_row(op)

    def _add_operation_row(self, op_data: Optional[Dict[str, Any]] = None):
        row = self.ops_table.rowCount()
        self.ops_table.insertRow(row)

        # Op type combo
        combo = QComboBox()
        combo.addItems(OP_TYPE_NAMES)
        if op_data and op_data.get("op_type") in OP_TYPE_NAMES:
            combo.setCurrentText(op_data["op_type"])
        self.ops_table.setCellWidget(row, 0, combo)

        # Target
        target_item = QTableWidgetItem(op_data.get("target", "") if op_data else "")
        self.ops_table.setItem(row, 1, target_item)

        # Data
        data_str = ""
        if op_data and op_data.get("data") is not None:
            data_str = str(op_data["data"])
        data_item = QTableWidgetItem(data_str)
        self.ops_table.setItem(row, 2, data_item)

    def _delete_operation_row(self):
        row = self.ops_table.currentRow()
        if row >= 0:
            self.ops_table.removeRow(row)

    def _save_current_process(self):
        pid = self.proc_pid_edit.text().strip()
        if not pid:
            return  # nothing to save

        name = self.proc_name_edit.text().strip() or pid

        # Collect operations from table
        ops_list: List[Dict[str, Any]] = []
        for row in range(self.ops_table.rowCount()):
            combo = self.ops_table.cellWidget(row, 0)
            op_type = combo.currentText() if combo else "NOP"

            target_item = self.ops_table.item(row, 1)
            data_item = self.ops_table.item(row, 2)

            target = target_item.text().strip() if target_item else ""
            data_str = data_item.text().strip() if data_item else ""

            # Try to parse data as int if numeric, else keep string
            data: Any
            if data_str == "":
                data = None
            else:
                try:
                    data = int(data_str)
                except ValueError:
                    data = data_str

            ops_list.append(
                {
                    "op_type": op_type,
                    "target": target or None,
                    "data": data,
                }
            )

        # Update dictionary
        self.proc_data[pid] = {
            "pid": pid,
            "name": name,
            "operations": ops_list,
        }
        self.current_proc_pid = pid
        self._refresh_proc_list()
        # Re-select current
        for i in range(self.proc_list.count()):
            item = self.proc_list.item(i)
            if item.data(Qt.UserRole) == pid:
                self.proc_list.setCurrentRow(i)
                break

    def _add_process(self):
        # Make a simple new PID
        base = "P"
        idx = 1
        while f"{base}{idx}" in self.proc_data:
            idx += 1
        pid = f"{base}{idx}"

        self.proc_data[pid] = {
            "pid": pid,
            "name": f"Process {idx}",
            "operations": [],
        }
        self._refresh_proc_list()
        # select new
        for i in range(self.proc_list.count()):
            item = self.proc_list.item(i)
            if item.data(Qt.UserRole) == pid:
                self.proc_list.setCurrentRow(i)
                break

    def _delete_process(self):
        current_item = self.proc_list.currentItem()
        if not current_item:
            return
        pid = current_item.data(Qt.UserRole)
        if pid in self.proc_data:
            del self.proc_data[pid]
        self._refresh_proc_list()
        self._clear_proc_form()
        self.current_proc_pid = None

    # ---------- IPC list / details ----------

    def _refresh_ipc_list(self):
        self.ipc_list.clear()
        for ipc_id, idata in self.ipc_data.items():
            item = QListWidgetItem(f"{ipc_id} ({idata.get('type')})")
            item.setData(Qt.UserRole, ipc_id)
            self.ipc_list.addItem(item)

    def _on_ipc_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if previous is not None:
            self._save_current_ipc()

        if current is None:
            self.current_ipc_id = None
            self._clear_ipc_form()
            return

        ipc_id = current.data(Qt.UserRole)
        self.current_ipc_id = ipc_id
        self._load_ipc_into_form(ipc_id)

    def _clear_ipc_form(self):
        self.ipc_id_edit.clear()
        self.ipc_type_combo.setCurrentIndex(0)
        self.capacity_spin.setValue(10)
        self.shm_data_edit.clear()

    def _load_ipc_into_form(self, ipc_id: str):
        idata = self.ipc_data.get(ipc_id)
        if not idata:
            self._clear_ipc_form()
            return

        self.ipc_id_edit.setText(idata["id"])
        type_str = idata.get("type", "PIPE")
        idx = self.ipc_type_combo.findText(type_str)
        if idx >= 0:
            self.ipc_type_combo.setCurrentIndex(idx)
        else:
            self.ipc_type_combo.setCurrentIndex(0)

        if type_str in ("PIPE", "MSG_QUEUE"):
            cap = idata.get("capacity", 10) or 10
            self.capacity_spin.setValue(int(cap))
            self.shm_data_edit.clear()
        elif type_str == "SHARED_MEMORY":
            self.capacity_spin.setValue(10)
            self.shm_data_edit.setPlainText(str(idata.get("initial_data", "")))

        self._on_ipc_type_changed(self.ipc_type_combo.currentText())

    def _on_ipc_type_changed(self, type_str: str):
        if type_str in ("PIPE", "MSG_QUEUE"):
            self.capacity_label.setEnabled(True)
            self.capacity_spin.setEnabled(True)
            self.shm_data_edit.setEnabled(False)
        elif type_str == "SHARED_MEMORY":
            self.capacity_label.setEnabled(False)
            self.capacity_spin.setEnabled(False)
            self.shm_data_edit.setEnabled(True)
        else:
            self.capacity_label.setEnabled(True)
            self.capacity_spin.setEnabled(True)
            self.shm_data_edit.setEnabled(True)

    def _save_current_ipc(self):
        ipc_id = self.ipc_id_edit.text().strip()
        if not ipc_id:
            return

        type_str = self.ipc_type_combo.currentText()
        capacity: Optional[int] = None
        initial_data: Optional[Any] = None

        if type_str in ("PIPE", "MSG_QUEUE"):
            capacity = self.capacity_spin.value()
        elif type_str == "SHARED_MEMORY":
            text = self.shm_data_edit.toPlainText().strip()
            if text == "":
                initial_data = None
            else:
                # try parse int, else keep string
                try:
                    initial_data = int(text)
                except ValueError:
                    initial_data = text

        self.ipc_data[ipc_id] = {
            "id": ipc_id,
            "type": type_str,
            "capacity": capacity,
            "initial_data": initial_data,
        }
        self.current_ipc_id = ipc_id
        self._refresh_ipc_list()
        for i in range(self.ipc_list.count()):
            item = self.ipc_list.item(i)
            if item.data(Qt.UserRole) == ipc_id:
                self.ipc_list.setCurrentRow(i)
                break

    def _add_ipc(self):
        base = "ipc"
        idx = 1
        while f"{base}{idx}" in self.ipc_data:
            idx += 1
        ipc_id = f"{base}{idx}"

        self.ipc_data[ipc_id] = {
            "id": ipc_id,
            "type": "PIPE",
            "capacity": 10,
            "initial_data": None,
        }
        self._refresh_ipc_list()
        for i in range(self.ipc_list.count()):
            item = self.ipc_list.item(i)
            if item.data(Qt.UserRole) == ipc_id:
                self.ipc_list.setCurrentRow(i)
                break

    def _delete_ipc(self):
        current_item = self.ipc_list.currentItem()
        if not current_item:
            return
        ipc_id = current_item.data(Qt.UserRole)
        if ipc_id in self.ipc_data:
            del self.ipc_data[ipc_id]
        self._refresh_ipc_list()
        self._clear_ipc_form()
        self.current_ipc_id = None

    # ---------- Build objects on OK ----------

    def _on_ok(self):
        # save current edits first
        self._save_current_process()
        self._save_current_ipc()

        # validate there is at least one process and one ipc
        if not self.proc_data:
            QMessageBox.warning(self, "Invalid Scenario", "You must have at least one process.")
            return
        if not self.ipc_data:
            QMessageBox.warning(self, "Invalid Scenario", "You must have at least one IPC object.")
            return

        # Build Process & IPCObject instances
        processes: Dict[str, Process] = {}
        ipcs: Dict[str, IPCObject] = {}

        # Build IPCs first
        for idata in self.ipc_data.values():
            ipc_id = idata["id"]
            t = idata["type"]
            if t == "PIPE":
                cap = idata.get("capacity") or 10
                ipcs[ipc_id] = Pipe(ipc_id, capacity=int(cap))
            elif t == "MSG_QUEUE":
                cap = idata.get("capacity") or 10
                ipcs[ipc_id] = MessageQueue(ipc_id, capacity=int(cap))
            elif t == "SHARED_MEMORY":
                init = idata.get("initial_data", None)
                ipcs[ipc_id] = SharedMemory(ipc_id, initial_data=init)
            else:
                QMessageBox.warning(self, "Invalid IPC", f"Unknown IPC type '{t}' for {ipc_id}")
                return

        # Build processes
        for pdata in self.proc_data.values():
            pid = pdata["pid"]
            name = pdata.get("name", pid)
            ops: List[Operation] = []

            for od in pdata.get("operations", []):
                op_type_name = od.get("op_type", "NOP")
                try:
                    op_type = OpType[op_type_name]
                except KeyError:
                    QMessageBox.warning(self, "Invalid Operation", f"Unknown op_type '{op_type_name}'")
                    return

                target = od.get("target")
                data = od.get("data", None)
                ops.append(Operation(op_type=op_type, target=target, data=data))

            processes[pid] = Process(pid=pid, name=name, operations=ops)

        self.result_processes = processes
        self.result_ipcs = ipcs
        self.accept()
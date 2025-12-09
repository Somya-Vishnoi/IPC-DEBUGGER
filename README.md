# IPC Debugger – Inter-Process Communication Visualization Tool

## 📌 Overview
Inter-Process Communication can get messy fast—deadlocks, blocking operations, unsafe memory handling, etc. This tool is built to **simulate, visualize and debug** communication between processes using **Pipes, Message Queues, and Shared Memory**. It is designed to help students and developers understand synchronization behavior rather than guess what’s happening behind the scenes.

The debugger provides timeline visualization, IPC topology graphs, real-time issue detection, risk scoring, JSON scenario import/export, and a GUI scenario editor to test custom communication setups.

---

## 🚀 Features
- Run or step-through IPC simulations
- Process timeline view showing state changes (RUNNING / BLOCKED / FINISHED)
- IPC topology graph showing communication links
- Automatic detection of:
  - **Deadlocks**
  - **Bottlenecks**
  - **Unsafe shared memory access**
- **Risk score** (Low / Medium / High)
- **Scenario Editor** to create IPC configurations visually
- **Save / Load** scenarios using JSON
- Event logs with detailed operation output

---

## 🛠 Technology Stack

| Category | Tools Used |
|----------|------------|
| **Language** | Python 3 |
| **GUI Framework** | PyQt5 |
| **Visualization** | matplotlib, networkx |
| **Data Serialization** | JSON |
| **Version Control** | Git & GitHub |
| **IDE** | VS Code |

---

## 📂 Project Structure


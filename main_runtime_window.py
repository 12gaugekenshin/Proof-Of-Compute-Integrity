import random
import json
import time
import hashlib

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QPushButton,
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QStyle,
    QFileDialog,
    QMessageBox,
    QLineEdit,
)
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QTextCursor, QColor

from settings_window import SettingsWindow

# Matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None


class MainRuntimeWindow(QMainWindow):
    def __init__(self, config, wallet_config, parent=None):
        super().__init__(parent)

        self.config = config
        self.wallet_config = wallet_config

        self.setWindowTitle("PoCI Runtime")
        self.setMinimumSize(1300, 750)

        # engine state
        self.event_index = 0
        self.theta_values = []
        self.w_values = []

        # user prompt override (for custom tests)
        self.user_prompt_override = None

        self.engine_running = False
        self.ui_updates_enabled = True

        self.buffered_events = []
        self.buffered_logs = []
        self.buffered_commits = []
        self.buffered_anomalies = []

        self.scroll_lock = False
        self.current_status_level = "idle"

        self.session_start_time = time.time()
        self.total_events = 0
        self.total_commits = 0
        self.total_anomalies = 0

        self.lm_error_shown = False

        # alert border
        self.alert_timer = QTimer(self)
        self.alert_timer.setSingleShot(True)
        self.alert_timer.timeout.connect(self.clear_alert_border)
        self.base_stylesheet = ""

        # psutil
        self.ps_process = psutil.Process() if psutil else None

        # tray
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        self.tray_icon.setVisible(True)

        tray_menu = QMenu()
        tray_menu.addAction("Restore").triggered.connect(self.restore_from_tray)
        tray_menu.addAction("Stop Engine").triggered.connect(self.stop_engine)
        tray_menu.addAction("Exit").triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_click)

        # menubar
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        file_menu.addAction("Save Run…").triggered.connect(self.save_run)
        file_menu.addAction("Load Run…").triggered.connect(self.load_run)

        settings_menu = menubar.addMenu("Settings")
        settings_menu.addAction("Open Settings…").triggered.connect(self.show_settings)

        # main layout
        central = QWidget()
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # top row
        top_row = QHBoxLayout()

        self.status_led = QLabel("●")
        self.status_led.setStyleSheet("font-size: 16px; color: #9E9E9E;")
        self.status_text = QLabel("Status: Idle")
        self.status_text.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.start_btn = QPushButton("Start Engine")
        self.stop_btn = QPushButton("Stop Engine")
        self.stop_btn.setEnabled(False)

        self.scroll_lock_btn = QPushButton("Scroll Lock")
        self.scroll_lock_btn.clicked.connect(self.toggle_scroll_lock)

        self.reset_status_btn = QPushButton("Reset Status")
        self.reset_status_btn.clicked.connect(self.reset_status)

        self.start_btn.clicked.connect(self.start_engine)
        self.stop_btn.clicked.connect(self.stop_engine)

        top_row.addWidget(self.status_led)
        top_row.addWidget(self.status_text)
        top_row.addStretch()
        top_row.addWidget(self.reset_status_btn)
        top_row.addWidget(self.scroll_lock_btn)
        top_row.addWidget(self.start_btn)
        top_row.addWidget(self.stop_btn)

        main_layout.addLayout(top_row)

        # splitter
        main_splitter = QSplitter(Qt.Horizontal)

        # ================= LEFT SIDE =====================
        left_splitter = QSplitter(Qt.Vertical)

        # event list
        self.event_list = QListWidget()

        # user prompt box under event list
        self.user_prompt_box = QLineEdit()
        self.user_prompt_box.setPlaceholderText("Type custom prompt to send to LM Studio...")

        self.user_prompt_btn = QPushButton("Send Prompt")
        self.user_prompt_btn.clicked.connect(self.send_user_prompt)

        # wrap event list + prompt UI
        event_container = QWidget()
        event_layout = QVBoxLayout()
        event_container.setLayout(event_layout)
        event_layout.addWidget(self.event_list)
        event_layout.addWidget(self.user_prompt_box)
        event_layout.addWidget(self.user_prompt_btn)

        # bottom-left: logs + stats
        bottom_left_container = QWidget()
        bottom_left_layout = QVBoxLayout()
        bottom_left_container.setLayout(bottom_left_layout)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.installEventFilter(self)

        # stats
        self.stats_widget = QWidget()
        stats_layout = QHBoxLayout()
        self.stats_widget.setLayout(stats_layout)

        self.stats_event_rate = QLabel("Events/sec: 0.0")
        self.stats_commit_rate = QLabel("Commits/sec: 0.0")
        self.stats_anomaly_rate = QLabel("Anomalies/sec: 0.0")
        self.stats_uptime = QLabel("Uptime: 0s")
        self.stats_cpu = QLabel("CPU: N/A")
        self.stats_ram = QLabel("RAM: N/A")
        self.stats_theta = QLabel("Δθ: 0.000")
        self.stats_w = QLabel("Δw: 0.000")

        for lbl in [
            self.stats_event_rate,
            self.stats_commit_rate,
            self.stats_anomaly_rate,
            self.stats_uptime,
            self.stats_cpu,
            self.stats_ram,
            self.stats_theta,
            self.stats_w,
        ]:
            lbl.setStyleSheet("font-size: 11px;")
            stats_layout.addWidget(lbl)

        bottom_left_layout.addWidget(self.log_box)
        bottom_left_layout.addWidget(self.stats_widget)

        left_splitter.addWidget(event_container)
        left_splitter.addWidget(bottom_left_container)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 2)

        # ================= GRAPH (CENTER) =====================
        graph_widget = QWidget()
        graph_layout = QVBoxLayout()
        graph_widget.setLayout(graph_layout)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)

        self.ax.set_title("Controller Output (θ and w)")
        self.ax.set_xlabel("Event Index")
        self.ax.set_ylabel("Value")
        self.ax.grid(True)

        graph_layout.addWidget(self.canvas)

        # ================= RIGHT SIDE =====================
        right_splitter = QSplitter(Qt.Vertical)
        self.commit_list = QListWidget()
        self.anomaly_list = QListWidget()
        self.anomaly_list.setMinimumHeight(160)

        right_splitter.addWidget(self.commit_list)
        right_splitter.addWidget(self.anomaly_list)

        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(graph_widget)
        main_splitter.addWidget(right_splitter)

        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 2)

        main_layout.addWidget(main_splitter)

        # timers
        self.engine_timer = QTimer()
        self.engine_timer.timeout.connect(self.engine_tick)

        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

        self.installEventFilter(self)

    # ===================================================================
    # LM STUDIO HTTP CALL
    # ===================================================================

    def lm_call(self, prompt: str) -> str | None:
        if not getattr(self.config, "lm_enabled", False):
            return None

        if requests is None:
            if not self.lm_error_shown:
                self.add_log("LM Studio disabled: 'requests' missing.")
                self.lm_error_shown = True
            return None

        endpoint = getattr(self.config, "lm_endpoint", "")
        model = getattr(self.config, "lm_model", "")
        if not endpoint or not model:
            if not self.lm_error_shown:
                self.add_log("LM Studio endpoint/model not set.")
                self.lm_error_shown = True
            return None

        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "top_p": 0.95,
                "stream": False,
            }

            t0 = time.time()
            r = requests.post(endpoint, json=payload, timeout=15)
            dt = (time.time() - t0) * 1000
            r.raise_for_status()

            data = r.json()
            text = data["choices"][0]["message"]["content"]

            self.add_log(f"LM Studio [{dt:.0f} ms]: {text[:200]}...")
            return text

        except Exception as e:
            if not self.lm_error_shown:
                self.add_log(f"LM Studio error: {e}")
                self.lm_error_shown = True
            return None

    # ===================================================================
    # SETTINGS
    # ===================================================================

    def show_settings(self):
        dlg = SettingsWindow(self)
        dlg.exec()

    # ===================================================================
    # USER PROMPT HANDLER
    # ===================================================================

    def send_user_prompt(self):
        text = self.user_prompt_box.text().strip()
        if not text:
            self.add_log("User prompt is empty.")
            return

        self.user_prompt_override = text
        self.add_log(f"User prompt queued for next tick: {text}")
        self.user_prompt_box.clear()

    # ===================================================================
    # ENGINE CONTROL
    # ===================================================================

    def start_engine(self):
        self.event_index = 0
        self.theta_values.clear()
        self.w_values.clear()
        self.total_events = 0
        self.total_commits = 0
        self.total_anomalies = 0
        self.session_start_time = time.time()

        self.event_list.clear()
        self.log_box.clear()
        self.commit_list.clear()
        self.anomaly_list.clear()

        self.engine_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.set_status_level("stable", "Running")
        self.engine_timer.start(200)

        self.add_log("Engine started.")

    def stop_engine(self):
        self.engine_running = False
        self.engine_timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.set_status_level("idle", "Stopped")
        self.add_log("Engine stopped.")

    # ===================================================================
    # ENGINE TICK
    # ===================================================================

    def engine_tick(self):
        if not self.engine_running:
            return

        self.event_index += 1
        self.total_events += 1

        # LM Studio logic
        if getattr(self.config, "lm_enabled", False):
            # use user override prompt if queued, otherwise standard heartbeat
            if self.user_prompt_override:
                prompt = self.user_prompt_override
                self.user_prompt_override = None
            else:
                prompt = f"PoCI heartbeat event {self.event_index}. Respond briefly."

            text = self.lm_call(prompt)

            if text is None:
                theta = 4.0 + random.uniform(-0.2, 0.2)
                w = 1.0 + random.uniform(-0.05, 0.05)
            else:
                # --- HASHING + NORMALIZATION + STRONGER RESPONSE ---
                h = hashlib.sha256(text.encode()).digest()
                v1 = int.from_bytes(h[:8], "big")
                v2 = int.from_bytes(h[8:16], "big")

                # wider bands: about ±0.25 on θ, ±0.12 on w
                theta_raw = 4.0 + (((v1 % 500) / 500.0) - 0.5) * 0.50
                w_raw     = 1.0 + (((v2 % 500) / 500.0) - 0.5) * 0.24

                # less damping: 50/50 blend
                if len(self.theta_values) > 0:
                    prev_theta = self.theta_values[-1]
                    prev_w = self.w_values[-1]

                    theta = (theta_raw * 0.50) + (prev_theta * 0.50)
                    w     = (w_raw     * 0.50) + (prev_w     * 0.50)
                else:
                    theta = theta_raw
                    w = w_raw

        else:
            # fallback fake controller
            theta = 4.0 + random.uniform(-0.2, 0.2)
            w = 1.0 + random.uniform(-0.05, 0.05)

        # record values
        self.theta_values.append(theta)
        self.w_values.append(w)

        # event list
        event_text = f"[{self.event_index}] θ={theta:.3f} | w={w:.3f}"

        if self.ui_updates_enabled:
            self.event_list.addItem(event_text)
            if not self.scroll_lock:
                self.event_list.scrollToBottom()
        else:
            self.buffered_events.append(event_text)

        # periodic logs
        if self.event_index % 10 == 0:
            self.add_log(f"Stable region @ event {self.event_index}")

        if self.event_index % 30 == 0:
            txid = f"com_{random.randint(10000, 99999)}"
            payload = f"payload_{self.event_index}"
            self.add_commit(txid, payload)

        # anomaly
        self.run_anomaly_engine(theta, w)

        if self.ui_updates_enabled and not self.scroll_lock:
            self.update_graph()

    # ===================================================================
    # ANOMALY ENGINE
    # ===================================================================

    def run_anomaly_engine(self, theta, w):
        if len(self.theta_values) < 2:
            return

        prev_theta = self.theta_values[-2]
        prev_w = self.w_values[-2]

        dtheta = theta - prev_theta
        dw = w - prev_w

        severity = None
        reason = None

        # more sensitive thresholds
        if abs(dtheta) > 0.20 or abs(dw) > 0.08:
            severity = "critical"
            reason = f"Sharp jump: Δθ={dtheta:.3f}, Δw={dw:.3f}"
        elif abs(dtheta) > 0.10 or abs(dw) > 0.04:
            severity = "warning"
            reason = f"Drift rise: Δθ={dtheta:.3f}, Δw={dw:.3f}"
        else:
            if random.random() < 0.03:
                severity = "info"
                reason = "Stable cluster."

        if severity:
            self.total_anomalies += 1
            if severity == "critical":
                self.set_status_level("critical", "Anomaly Detected")
            elif severity == "warning":
                self.set_status_level("warning", "Unstable Trend")
            elif severity == "info":
                if self.current_status_level not in ("warning", "critical"):
                    self.set_status_level("stable", "Running")

            msg = f"[{self.event_index}] {severity.upper()} - {reason}"
            if self.ui_updates_enabled:
                self._add_anomaly_item(severity, msg)
            else:
                self.buffered_anomalies.append((severity, msg))

            self.add_log(f"ANOMALY ({severity}): {reason}")

    def _add_anomaly_item(self, severity, msg):
        item = QListWidgetItem(msg)
        if severity == "critical":
            item.setForeground(QColor("#FF5252"))
        elif severity == "warning":
            item.setForeground(QColor("#FFAB40"))
        else:
            item.setForeground(QColor("#80CBC4"))
        self.anomaly_list.addItem(item)
        if not self.scroll_lock:
            self.anomaly_list.scrollToBottom()

    # ===================================================================
    # LOGS
    # ===================================================================

    def add_log(self, msg):
        if not self.ui_updates_enabled:
            self.buffered_logs.append(msg)
            return

        sb = self.log_box.verticalScrollBar()
        cursor = self.log_box.textCursor()

        if self.scroll_lock:
            prev = sb.value()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(msg + "\n")
            sb.setValue(prev)
        else:
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(msg + "\n")
            sb.setValue(sb.maximum())

    # ===================================================================
    # COMMITS
    # ===================================================================

    def add_commit(self, txid, payload):
        item = QListWidgetItem(f"{txid} | {payload}")

        if self.ui_updates_enabled:
            self.commit_list.addItem(item)
            if not self.scroll_lock:
                self.commit_list.scrollToBottom()
        else:
            self.buffered_commits.append(item)

        self.total_commits += 1
        self.add_log(f"Commit created: {txid}")

    # ===================================================================
    # STATS
    # ===================================================================

    def update_stats(self):
        elapsed = max(1.0, time.time() - self.session_start_time)

        uptime = int(elapsed)
        h = uptime // 3600
        m = (uptime % 3600) // 60
        s = uptime % 60

        self.stats_uptime.setText(f"Uptime: {h:02d}:{m:02d}:{s:02d}")
        self.stats_event_rate.setText(f"Events/sec: {self.total_events / elapsed:.2f}")
        self.stats_commit_rate.setText(f"Commits/sec: {self.total_commits / elapsed:.2f}")
        self.stats_anomaly_rate.setText(f"Anomalies/sec: {self.total_anomalies / elapsed:.2f}")

        if len(self.theta_values) > 1:
            dtheta = self.theta_values[-1] - self.theta_values[-2]
            dw = self.w_values[-1] - self.w_values[-2]
        else:
            dtheta = dw = 0.0

        self.stats_theta.setText(f"Δθ: {dtheta:.3f}")
        self.stats_w.setText(f"Δw: {dw:.3f}")

        if self.ps_process:
            cpu = self.ps_process.cpu_percent(interval=None)
            mem = self.ps_process.memory_info().rss / (1024 * 1024)
            self.stats_cpu.setText(f"CPU: {cpu:.1f}%")
            self.stats_ram.setText(f"RAM: {mem:.1f} MB")

    # ===================================================================
    # SAVE / LOAD
    # ===================================================================

    def save_run(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save PoCI Run", "", "PoCI Runs (*.json)")
        if not fname:
            return
        try:
            data = {
                "meta": {"version": 1, "saved_at": time.time()},
                "theta_values": self.theta_values,
                "w_values": self.w_values,
                "events": [self.event_list.item(i).text() for i in range(self.event_list.count())],
                "logs": self.log_box.toPlainText().splitlines(),
                "commits": [self.commit_list.item(i).text() for i in range(self.commit_list.count())],
                "anomalies": [self.anomaly_list.item(i).text() for i in range(self.anomaly_list.count())],
                "stats": {
                    "total_events": self.total_events,
                    "total_commits": self.total_commits,
                    "total_anomalies": self.total_anomalies,
                    "session_start_time": self.session_start_time,
                },
            }

            with open(fname, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            QMessageBox.information(self, "Saved", f"Run saved:\n{fname}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save run:\n{e}")

    def load_run(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load PoCI Run", "", "PoCI Runs (*.json)")
        if not fname:
            return
        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)

            if self.engine_running:
                self.stop_engine()

            self.event_list.clear()
            self.log_box.clear()
            self.commit_list.clear()
            self.anomaly_list.clear()
            self.theta_values.clear()
            self.w_values.clear()

            self.theta_values.extend(data.get("theta_values", []))
            self.w_values.extend(data.get("w_values", []))

            for line in data.get("events", []):
                self.event_list.addItem(line)

            self.log_box.setPlainText("\n".join(data.get("logs", [])))

            for line in data.get("commits", []):
                self.commit_list.addItem(line)

            for line in data.get("anomalies", []):
                self.anomaly_list.addItem(QListWidgetItem(line))

            stats = data.get("stats", {})
            self.total_events = stats.get("total_events", len(self.theta_values))
            self.total_commits = stats.get("total_commits", self.commit_list.count())
            self.total_anomalies = stats.get("total_anomalies", self.anomaly_list.count())
            self.session_start_time = stats.get("session_start_time", time.time())

            self.event_index = len(self.theta_values)

            self.update_graph()
            self.set_status_level("idle", f"Loaded {fname.split('/')[-1]}")

            QMessageBox.information(self, "Loaded", f"Run loaded:\n{fname}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Load failed:\n{e}")

    # ===================================================================
    # GRAPH
    # ===================================================================

    def update_graph(self):
        if not self.ui_updates_enabled:
            return

        self.ax.clear()
        self.ax.set_title("Controller Output (θ and w)")
        self.ax.set_xlabel("Event Index")
        self.ax.set_ylabel("Value")
        self.ax.grid(True)

        x = list(range(1, len(self.theta_values) + 1))

        if self.theta_values:
            self.ax.plot(x, self.theta_values, label="θ", color="purple")
        if self.w_values:
            self.ax.plot(x, self.w_values, label="w", color="blue")

        # anomaly markers (match critical Δθ threshold)
        if len(self.theta_values) > 1:
            ax_x = []
            ax_y = []
            for i in range(1, len(self.theta_values)):
                if abs(self.theta_values[i] - self.theta_values[i - 1]) > 0.20:
                    ax_x.append(i + 1)
                    ax_y.append(self.theta_values[i])
            if ax_x:
                self.ax.scatter(ax_x, ax_y, color="red", s=16, label="Anomaly")

        self.ax.legend()
        self.canvas.draw()

    # ===================================================================
    # SCROLL LOCK
    # ===================================================================

    def toggle_scroll_lock(self):
        self.scroll_lock = not self.scroll_lock
        self.scroll_lock_btn.setText("Unlock Scroll" if self.scroll_lock else "Scroll Lock")

    # ===================================================================
    # STATUS
    # ===================================================================

    def set_status_level(self, level, text=None):
        self.current_status_level = level

        if text:
            self.status_text.setText(f"Status: {text}")

        colors = {
            "stable": "#00C853",
            "warning": "#FFAB00",
            "critical": "#D50000",
            "idle": "#9E9E9E",
        }
        self.status_led.setStyleSheet(f"font-size: 16px; color: {colors.get(level, '#fff')};")

        if level == "warning":
            self.flash_alert_border("warning")
        elif level == "critical":
            self.flash_alert_border("critical")

    def reset_status(self):
        if self.engine_running:
            self.set_status_level("stable", "Running")
        else:
            self.set_status_level("idle", "Idle")
        self.clear_alert_border()

    def flash_alert_border(self, level):
        color = "#D50000" if level == "critical" else "#FFAB00"
        self.setStyleSheet(self.base_stylesheet + f"QMainWindow {{ border: 2px solid {color}; }}")
        self.alert_timer.start(2000)

    def clear_alert_border(self):
        self.setStyleSheet(self.base_stylesheet)

    # ===================================================================
    # TRAY
    # ===================================================================

    def hideEvent(self, event):
        if self.isMinimized():
            self.ui_updates_enabled = False
            self.hide()
        super().hideEvent(event)

    def tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.restore_from_tray()

    def restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.ui_updates_enabled = True

        for e in self.buffered_events:
            self.event_list.addItem(e)
        self.buffered_events.clear()

        for l in self.buffered_logs:
            self.add_log(l)
        self.buffered_logs.clear()

        for c in self.buffered_commits:
            self.commit_list.addItem(c)
        self.buffered_commits.clear()

        for sev, msg in self.buffered_anomalies:
            self._add_anomaly_item(sev, msg)
        self.buffered_anomalies.clear()

        self.update_graph()

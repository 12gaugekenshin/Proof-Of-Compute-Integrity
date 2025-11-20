import random
import json
import time

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
)
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QIcon, QTextCursor, QColor

from settings_window import SettingsWindow

# Matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Optional: CPU/RAM stats (if psutil is installed)
try:
    import psutil
except ImportError:
    psutil = None


class MainRuntimeWindow(QMainWindow):
    def __init__(self, config, wallet_config, parent=None):
        super().__init__(parent)

        self.config = config
        self.wallet_config = wallet_config

        self.setWindowTitle("PoCI Runtime")
        self.setMinimumSize(1300, 750)

        # ----------- STATE -----------
        self.event_index = 0
        self.theta_values = []
        self.w_values = []

        self.engine_running = False
        self.ui_updates_enabled = True

        # Buffers for minimized window
        self.buffered_events = []
        self.buffered_logs = []
        self.buffered_commits = []
        self.buffered_anomalies = []

        # Scroll lock flag
        self.scroll_lock = False

        # Anomaly / status state
        self.current_status_level = "idle"  # idle | stable | warning | critical

        # Session metrics
        self.session_start_time = time.time()
        self.total_events = 0
        self.total_commits = 0
        self.total_anomalies = 0

        # Alert border timer
        self.alert_timer = QTimer(self)
        self.alert_timer.setSingleShot(True)
        self.alert_timer.timeout.connect(self.clear_alert_border)
        self.base_stylesheet = ""  # if you apply a global theme later, set it here

        # psutil process handle (optional)
        self.ps_process = psutil.Process() if psutil is not None else None

        # ----------- SYSTEM TRAY -----------
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        self.tray_icon.setVisible(True)

        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Restore")
        stop_action = tray_menu.addAction("Stop Engine")
        exit_action = tray_menu.addAction("Exit")

        restore_action.triggered.connect(self.restore_from_tray)
        stop_action.triggered.connect(self.stop_engine)
        exit_action.triggered.connect(QApplication.instance().quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_click)

        # ----------- MENU BAR -----------
        menubar = self.menuBar()

        # File menu — Save/Load runs
        file_menu = menubar.addMenu("File")
        save_action = file_menu.addAction("Save Run…")
        load_action = file_menu.addAction("Load Run…")
        save_action.triggered.connect(self.save_run)
        load_action.triggered.connect(self.load_run)

        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        action_settings = settings_menu.addAction("Open Settings…")
        action_settings.triggered.connect(self.show_settings)

        # ----------- MAIN LAYOUT -----------
        central = QWidget()
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # ----------- TOP ROW (status + controls) -----------
        top_row = QHBoxLayout()

        # Status LED + text
        self.status_led = QLabel("●")
        self.status_led.setStyleSheet("font-size: 16px; color: #9E9E9E;")  # idle grey
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

        # ----------- SPLITTER -----------
        main_splitter = QSplitter(Qt.Horizontal)

        # LEFT SIDE (events + logs + stats)
        left_splitter = QSplitter(Qt.Vertical)
        self.event_list = QListWidget()

        # Logs + stats container
        bottom_left_container = QWidget()
        bottom_left_layout = QVBoxLayout()
        bottom_left_container.setLayout(bottom_left_layout)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.installEventFilter(self)

        # Stats panel (compact)
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

        left_splitter.addWidget(self.event_list)
        left_splitter.addWidget(bottom_left_container)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 2)

        # CENTER: graph
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

        # RIGHT: commits + anomalies
        right_splitter = QSplitter(Qt.Vertical)
        self.commit_list = QListWidget()

        self.anomaly_list = QListWidget()
        self.anomaly_list.setMinimumHeight(160)

        right_splitter.addWidget(self.commit_list)
        right_splitter.addWidget(self.anomaly_list)
        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 2)

        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(graph_widget)
        main_splitter.addWidget(right_splitter)

        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 2)

        main_layout.addWidget(main_splitter)

        # ----------- TIMERS -----------
        self.engine_timer = QTimer()
        self.engine_timer.timeout.connect(self.engine_tick)

        # Stats timer: 1 Hz
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

        self.installEventFilter(self)

    # =========================
    #   TRAY BEHAVIOR
    # =========================
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

        for a in self.buffered_anomalies:
            self._add_anomaly_item(*a)
        self.buffered_anomalies.clear()

        self.update_graph()

    # =========================
    #   GLOBAL EVENT FILTER
    # =========================
    def eventFilter(self, obj, event):
        # Lock scroll-related events inside the log box when scroll-locked
        if obj is self.log_box and self.scroll_lock:
            if event.type() in (
                QEvent.Wheel,
                QEvent.Scroll,
                QEvent.ScrollPrepare,
                QEvent.Resize,
                QEvent.UpdateRequest,
            ):
                return True

        return super().eventFilter(obj, event)

    # =========================
    #   SETTINGS
    # =========================
    def show_settings(self):
        dlg = SettingsWindow(self)
        dlg.exec()

    # =========================
    #   ENGINE CONTROL
    # =========================
    def start_engine(self):
        # Reset session metrics on new run
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

    # =========================
    #   STATUS LED / ALERT
    # =========================
    def set_status_level(self, level: str, text: str | None = None):
        """
        level: 'stable' | 'warning' | 'critical' | 'idle'
        """
        self.current_status_level = level

        if text is not None:
            self.status_text.setText(f"Status: {text}")

        if level == "stable":
            color = "#00C853"  # green
        elif level == "warning":
            color = "#FFAB00"  # amber
            self.flash_alert_border("warning")
        elif level == "critical":
            color = "#D50000"  # red
            self.flash_alert_border("critical")
        elif level == "idle":
            color = "#9E9E9E"  # grey
        else:
            color = "#FFFFFF"

        self.status_led.setStyleSheet(f"font-size: 16px; color: {color};")

    def reset_status(self):
        # Reset to green or idle depending on engine state
        if self.engine_running:
            self.set_status_level("stable", "Running")
        else:
            self.set_status_level("idle", "Idle")
        self.clear_alert_border()

    def flash_alert_border(self, level: str):
        """
        Light border on warning/critical for a short time.
        """
        if level == "critical":
            border_color = "#D50000"
        else:
            border_color = "#FFAB00"

        self.setStyleSheet(
            self.base_stylesheet
            + f"QMainWindow {{ border: 2px solid {border_color}; }}"
        )
        # Auto-clear after 2 seconds
        self.alert_timer.start(2000)

    def clear_alert_border(self):
        self.setStyleSheet(self.base_stylesheet)

    # =========================
    #   SCROLL LOCK
    # =========================
    def toggle_scroll_lock(self):
        self.scroll_lock = not self.scroll_lock
        self.scroll_lock_btn.setText("Unlock Scroll" if self.scroll_lock else "Scroll Lock")

    # =========================
    #   ENGINE LOOP
    # =========================
    def engine_tick(self):
        if not self.engine_running:
            return

        self.event_index += 1
        self.total_events += 1

        # Fake controller values (for now)
        theta = 4.0 + random.uniform(-0.2, 0.2)
        w = 1.0 + random.uniform(-0.05, 0.05)

        self.theta_values.append(theta)
        self.w_values.append(w)

        # -------- EVENTS --------
        event_text = f"[{self.event_index}] θ={theta:.3f} | w={w:.3f}"

        if self.ui_updates_enabled:
            self.event_list.addItem(event_text)
            if not self.scroll_lock:
                self.event_list.scrollToBottom()
        else:
            self.buffered_events.append(event_text)

        # -------- LOGS --------
        if self.event_index % 10 == 0:
            self.add_log(f"Stable region @ event {self.event_index}")

        # -------- COMMITS --------
        if self.event_index % 30 == 0:
            txid = f"com_{random.randint(10000, 99999)}"
            payload = f"payload_{self.event_index}"
            self.add_commit(txid, payload)

        # -------- ANOMALY ENGINE --------
        self.run_anomaly_engine(theta, w)

        # -------- GRAPH --------
        if self.ui_updates_enabled and not self.scroll_lock:
            self.update_graph()

    # =========================
    #   ANOMALY ENGINE
    # =========================
    def run_anomaly_engine(self, theta: float, w: float):
        """
        Simple simulated anomaly engine.
        Later: wire this into the real PoCI controller signal.
        """
        if len(self.theta_values) < 2:
            return

        prev_theta = self.theta_values[-2]
        prev_w = self.w_values[-2]

        d_theta = theta - prev_theta
        d_w = w - prev_w

        severity = None
        reason = None

        # Example rules (tunable)
        if abs(d_theta) > 0.35 or abs(d_w) > 0.12:
            severity = "critical"
            reason = f"Sharp jump detected: Δθ={d_theta:.3f}, Δw={d_w:.3f}"
        elif abs(d_theta) > 0.25 or abs(d_w) > 0.08:
            severity = "warning"
            reason = f"Elevated drift: Δθ={d_theta:.3f}, Δw={d_w:.3f}"
        else:
            if random.random() < 0.03:
                severity = "info"
                reason = "Cluster looks stable; controller within expected band."

        if severity is None:
            return

        # Count anomalies
        self.total_anomalies += 1

        # Update status LED based on severity
        if severity == "critical":
            self.set_status_level("critical", "Anomaly Detected")
        elif severity == "warning" and self.current_status_level != "critical":
            self.set_status_level("warning", "Unstable Trend")
        elif severity == "info" and self.current_status_level not in ("warning", "critical"):
            self.set_status_level("stable", "Running")

        msg = f"[{self.event_index}] {severity.upper()} - {reason}"

        if self.ui_updates_enabled:
            self._add_anomaly_item(severity, msg)
        else:
            self.buffered_anomalies.append((severity, msg))

        self.add_log(f"ANOMALY ({severity}): {reason}")

    def _add_anomaly_item(self, severity: str, msg: str):
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

    # =========================
    #   LOGGING
    # =========================
    def add_log(self, msg: str):
        if not self.ui_updates_enabled:
            self.buffered_logs.append(msg)
            return

        sb = self.log_box.verticalScrollBar()
        cursor = self.log_box.textCursor()

        if self.scroll_lock:
            prev_scroll = sb.value()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(msg + "\n")
            sb.setValue(prev_scroll)
        else:
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(msg + "\n")
            sb.setValue(sb.maximum())

    # =========================
    #   COMMITS
    # =========================
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

    # =========================
    #   STATS UPDATE
    # =========================
    def update_stats(self):
        # Uptime
        elapsed = max(1.0, time.time() - self.session_start_time)
        uptime_seconds = int(elapsed)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        self.stats_uptime.setText(f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")

        # Rates
        ev_rate = self.total_events / elapsed
        cm_rate = self.total_commits / elapsed
        an_rate = self.total_anomalies / elapsed

        self.stats_event_rate.setText(f"Events/sec: {ev_rate:.2f}")
        self.stats_commit_rate.setText(f"Commits/sec: {cm_rate:.2f}")
        self.stats_anomaly_rate.setText(f"Anomalies/sec: {an_rate:.2f}")

        # θ / w deltas
        if len(self.theta_values) > 1:
            d_theta = self.theta_values[-1] - self.theta_values[-2]
            d_w = self.w_values[-1] - self.w_values[-2]
        else:
            d_theta = 0.0
            d_w = 0.0

        self.stats_theta.setText(f"Δθ: {d_theta:.3f}")
        self.stats_w.setText(f"Δw: {d_w:.3f}")

        # CPU / RAM (if psutil available)
        if self.ps_process is not None:
            cpu = self.ps_process.cpu_percent(interval=None)
            mem_mb = self.ps_process.memory_info().rss / (1024 * 1024)
            self.stats_cpu.setText(f"CPU: {cpu:.1f}%")
            self.stats_ram.setText(f"RAM: {mem_mb:.1f} MB")
        else:
            self.stats_cpu.setText("CPU: N/A")
            self.stats_ram.setText("RAM: N/A")

    # =========================
    #   SAVE / LOAD RUNS
    # =========================
    def save_run(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save PoCI Run",
            "",
            "PoCI Runs (*.json)"
        )
        if not filename:
            return

        try:
            data = {
                "meta": {
                    "version": 1,
                    "saved_at": time.time(),
                },
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

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            QMessageBox.information(self, "Saved", f"Run saved to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save run:\n{e}")

    def load_run(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load PoCI Run",
            "",
            "PoCI Runs (*.json)"
        )
        if not filename:
            return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Stop engine if running
            if self.engine_running:
                self.stop_engine()

            # Clear current state
            self.event_list.clear()
            self.log_box.clear()
            self.commit_list.clear()
            self.anomaly_list.clear()
            self.theta_values.clear()
            self.w_values.clear()

            # Restore series
            self.theta_values.extend(data.get("theta_values", []))
            self.w_values.extend(data.get("w_values", []))

            # Restore events
            for line in data.get("events", []):
                self.event_list.addItem(line)

            # Restore logs
            self.log_box.setPlainText("\n".join(data.get("logs", [])))

            # Restore commits
            for line in data.get("commits", []):
                self.commit_list.addItem(line)

            # Restore anomalies
            for line in data.get("anomalies", []):
                # no severity info saved, default color
                item = QListWidgetItem(line)
                self.anomaly_list.addItem(item)

            # Restore stats
            stats = data.get("stats", {})
            self.total_events = stats.get("total_events", len(self.theta_values))
            self.total_commits = stats.get("total_commits", self.commit_list.count())
            self.total_anomalies = stats.get("total_anomalies", self.anomaly_list.count())
            self.session_start_time = stats.get("session_start_time", time.time())

            # Adjust index
            self.event_index = len(self.theta_values)

            # Update graph and status
            self.update_graph()
            self.set_status_level("idle", f"Loaded: {filename.split('/')[-1]}")

            QMessageBox.information(self, "Loaded", f"Run loaded from:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load run:\n{e}")

    # =========================
    #   GRAPH
    # =========================
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

        # Highlight large Δθ points as anomaly markers on graph
        if len(self.theta_values) > 1:
            anomaly_x = []
            anomaly_y = []
            for i in range(1, len(self.theta_values)):
                d_theta = self.theta_values[i] - self.theta_values[i - 1]
                if abs(d_theta) > 0.35:
                    anomaly_x.append(i + 1)
                    anomaly_y.append(self.theta_values[i])
            if anomaly_x:
                self.ax.scatter(anomaly_x, anomaly_y, color="red", s=15, label="Anomaly")

        self.ax.legend()
        self.canvas.draw()

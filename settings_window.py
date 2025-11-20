from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QFileDialog, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt

from config import PoCIConfig


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("PoCI Settings")
        self.setMinimumSize(450, 350)

        # Load current config
        self.cfg: PoCIConfig = PoCIConfig.load()

        # Layouts
        layout = QVBoxLayout()
        form = QFormLayout()

        # --- Audit Intensity ---
        self.audit_combo = QComboBox()
        self.audit_combo.addItems(["low", "normal", "high"])
        self.audit_combo.setCurrentText(self.cfg.audit_intensity)

        # --- Log Directory ---
        self.log_edit = QLineEdit(self.cfg.log_directory)
        self.log_button = QPushButton("Browse…")
        self.log_button.clicked.connect(self.select_log_dir)

        # --- Commit Frequency ---
        self.freq_edit = QLineEdit(self.cfg.commit_frequency)

        # --- RPC Endpoint ---
        self.rpc_edit = QLineEdit(self.cfg.rpc_endpoint)

        # --- Auto Start ---
        self.auto_start_box = QCheckBox("Automatically start engine on launch")
        self.auto_start_box.setChecked(self.cfg.auto_start_engine)

        # Place fields in form
        form.addRow("Audit Intensity:", self.audit_combo)
        form.addRow("Log Directory:", self.log_edit)
        form.addRow("", self.log_button)
        form.addRow("Commit Frequency:", self.freq_edit)
        form.addRow("RPC Endpoint:", self.rpc_edit)
        form.addRow("", self.auto_start_box)

        # Save / Cancel
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)

        layout.addLayout(form)
        layout.addWidget(save_btn)
        layout.addWidget(cancel_btn)

        self.setLayout(layout)

    def select_log_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Log Directory")
        if d:
            self.log_edit.setText(d)

    def save_settings(self):
        self.cfg.audit_intensity = self.audit_combo.currentText()
        self.cfg.log_directory = self.log_edit.text()
        self.cfg.commit_frequency = self.freq_edit.text()
        self.cfg.rpc_endpoint = self.rpc_edit.text()
        self.cfg.auto_start_engine = self.auto_start_box.isChecked()

        self.cfg.save()

        QMessageBox.information(self, "Saved", "Settings have been saved successfully.")
        self.close()

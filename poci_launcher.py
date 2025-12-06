import sys
import json
import secrets
from dataclasses import dataclass, asdict
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup,
    QLineEdit, QTextEdit, QFileDialog,
    QMessageBox, QStackedWidget, QFormLayout,
    QCheckBox
)
from PySide6.QtCore import Qt

# IMPORT THE OTHER WINDOWS
from main_runtime_window import MainRuntimeWindow
from config import PoCIConfig


# -------------------------
# Data Models / Config
# -------------------------

@dataclass
class WalletConfig:
    mode: str  
    address: Optional[str] = None
    pubkey: Optional[str] = None
    privkey: Optional[str] = None
    wallet_file: Optional[str] = None
    enterprise_api_base: Optional[str] = None
    enterprise_api_token: Optional[str] = None
    enterprise_pubkey: Optional[str] = None


# -------------------------
# Utility / Stub Crypto
# -------------------------

def generate_fake_keypair():
    priv = secrets.token_hex(32)
    pub = secrets.token_hex(32)
    addr = "kaspa_" + secrets.token_hex(16)
    return addr, pub, priv


def save_wallet_to_file(config: WalletConfig, parent: QWidget) -> Optional[str]:
    filename, _ = QFileDialog.getSaveFileName(
        parent,
        "Save Wallet File",
        "wallet.poci.json",
        "JSON Files (*.json);;All Files (*)"
    )
    if not filename:
        return None

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2)
    except Exception as e:
        QMessageBox.critical(parent, "Error", f"Failed to save wallet file:\n{e}")
        return None

    return filename


# -------------------------
# UI Pages
# -------------------------

class StartupChoicePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("PoCI Local Client")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        subtitle = QLabel("Choose how you'd like to configure your wallet:")
        subtitle.setAlignment(Qt.AlignCenter)

        self.generate_radio = QRadioButton("Generate New Wallet")
        self.import_radio = QRadioButton("Import Existing Wallet")
        self.enterprise_radio = QRadioButton("Enterprise Signing Mode")

        self.generate_radio.setChecked(True)

        self.group = QButtonGroup(self)
        self.group.addButton(self.generate_radio)
        self.group.addButton(self.import_radio)
        self.group.addButton(self.enterprise_radio)

        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(self.generate_radio)
        layout.addWidget(self.import_radio)
        layout.addWidget(self.enterprise_radio)
        layout.addStretch()

        self.setLayout(layout)

    def get_selected_mode(self) -> str:
        if self.generate_radio.isChecked():
            return "generate"
        elif self.import_radio.isChecked():
            return "import"
        else:
            return "enterprise"


class GenerateWalletPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.generated = False
        self.addr = None
        self.pub = None
        self.priv = None

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("Generate New Wallet")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        desc = QLabel(
            "Generate a new wallet keypair.\n"
            "This is using a placeholder generator for now."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        self.generate_button = QPushButton("Generate Wallet")
        self.generate_button.clicked.connect(self.on_generate_clicked)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("Wallet will appear here...")

        self.save_checkbox = QCheckBox("Save wallet to file")

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.result_box)
        layout.addWidget(self.save_checkbox)
        layout.addStretch()
        self.setLayout(layout)

    def on_generate_clicked(self):
        self.addr, self.pub, self.priv = generate_fake_keypair()
        self.generated = True

        text = (
            "Wallet generated:\n\n"
            f"Address: {self.addr}\n"
            f"Public Key: {self.pub}\n"
            f"Private Key: {self.priv}\n"
        )
        self.result_box.setPlainText(text)

    def build_config(self, parent) -> Optional[WalletConfig]:
        if not self.generated:
            QMessageBox.warning(parent, "Error", "Generate wallet first.")
            return None

        config = WalletConfig(
            mode="generate",
            address=self.addr,
            pubkey=self.pub,
            privkey=self.priv
        )

        if self.save_checkbox.isChecked():
            filename = save_wallet_to_file(config, parent)
            if filename:
                config.wallet_file = filename

        return config


class ImportWalletPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("Import Wallet")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        desc = QLabel("Paste your private key or load from wallet file.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        form = QFormLayout()

        self.address_edit = QLineEdit()
        self.pubkey_edit = QLineEdit()
        self.privkey_edit = QLineEdit()
        self.privkey_edit.setEchoMode(QLineEdit.Password)

        load_button = QPushButton("Load Wallet File")
        load_button.clicked.connect(self.load_wallet_file)

        form.addRow("Address:", self.address_edit)
        form.addRow("Public Key:", self.pubkey_edit)
        form.addRow("Private Key:", self.privkey_edit)
        form.addRow("", load_button)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addLayout(form)
        layout.addStretch()
        self.setLayout(layout)

    def load_wallet_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Wallet File", "", "JSON Files (*.json)"
        )
        if not filename:
            return

        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except:
            QMessageBox.critical(self, "Error", "Failed to read wallet file.")
            return

        self.address_edit.setText(data.get("address", ""))
        self.pubkey_edit.setText(data.get("pubkey", ""))
        self.privkey_edit.setText(data.get("privkey", ""))

    def build_config(self, parent) -> Optional[WalletConfig]:
        priv = self.privkey_edit.text().strip()
        if not priv:
            QMessageBox.warning(parent, "Error", "Private key required.")
            return None

        config = WalletConfig(
            mode="import",
            address=self.address_edit.text().strip() or None,
            pubkey=self.pubkey_edit.text().strip() or None,
            privkey=priv
        )
        return config


class EnterpriseModePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("Enterprise Signing Mode")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        desc = QLabel(
            "Use an external API to sign model commits.\n"
            "No wallet stored locally."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        form = QFormLayout()

        self.api_edit = QLineEdit()
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.pub_edit = QLineEdit()

        form.addRow("API Base URL:", self.api_edit)
        form.addRow("API Token:", self.token_edit)
        form.addRow("Public Key:", self.pub_edit)

        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addLayout(form)
        layout.addStretch()
        self.setLayout(layout)

    def build_config(self, parent) -> Optional[WalletConfig]:
        api = self.api_edit.text().strip()
        if not api:
            QMessageBox.warning(parent, "Error", "API URL required.")
            return None

        return WalletConfig(
            mode="enterprise",
            enterprise_api_base=api,
            enterprise_api_token=self.token_edit.text().strip() or None,
            enterprise_pubkey=self.pub_edit.text().strip() or None
        )


# -------------------------
# MAIN WINDOW (Launcher)
# -------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PoCI Client - Startup")
        self.setMinimumSize(600, 450)

        central = QWidget()
        layout = QVBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.stacked = QStackedWidget()
        self.choice_page = StartupChoicePage()
        self.generate_page = GenerateWalletPage()
        self.import_page = ImportWalletPage()
        self.enterprise_page = EnterpriseModePage()

        self.stacked.addWidget(self.choice_page)
        self.stacked.addWidget(self.generate_page)
        self.stacked.addWidget(self.import_page)
        self.stacked.addWidget(self.enterprise_page)

        nav = QHBoxLayout()
        nav.setAlignment(Qt.AlignRight)

        self.back_btn = QPushButton("Back")
        self.next_btn = QPushButton("Next")
        self.finish_btn = QPushButton("Finish & Launch")

        self.back_btn.clicked.connect(self.on_back_clicked)
        self.next_btn.clicked.connect(self.on_next_clicked)
        self.finish_btn.clicked.connect(self.on_finish_clicked)

        self.back_btn.setVisible(False)
        self.finish_btn.setVisible(False)

        nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn)
        nav.addWidget(self.finish_btn)

        layout.addWidget(self.stacked)
        layout.addLayout(nav)

        self.current_config = None

    def on_back_clicked(self):
        self.stacked.setCurrentIndex(0)
        self.back_btn.setVisible(False)
        self.next_btn.setVisible(True)
        self.finish_btn.setVisible(False)

    def on_next_clicked(self):
        mode = self.choice_page.get_selected_mode()
        if mode == "generate":
            self.stacked.setCurrentIndex(1)
        elif mode == "import":
            self.stacked.setCurrentIndex(2)
        else:
            self.stacked.setCurrentIndex(3)

        self.back_btn.setVisible(True)
        self.next_btn.setVisible(False)
        self.finish_btn.setVisible(True)

    def on_finish_clicked(self):
        idx = self.stacked.currentIndex()

        if idx == 1:
            cfg = self.generate_page.build_config(self)
        elif idx == 2:
            cfg = self.import_page.build_config(self)
        elif idx == 3:
            cfg = self.enterprise_page.build_config(self)
        else:
            QMessageBox.warning(self, "Error", "Choose a mode first.")
            return

        if cfg is None:
            return

        self.current_config = cfg

        # LOAD persistent app settings
        pocicfg = PoCIConfig.load()

        # MOVE TO MAIN RUNTIME WINDOW
        self.hide()
        self.rt = MainRuntimeWindow(
            config=pocicfg,
            wallet_config=cfg
        )
        self.rt.show()


# -------------------------
# RUN APP
# -------------------------

def main():
    from theme_dark import get_dark_theme

    app = QApplication(sys.argv)
    app.setStyleSheet(get_dark_theme())

    w = MainWindow()
    w.show()
    sys.exit(app.exec())



if __name__ == "__main__":
    main()

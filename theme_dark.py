def get_dark_theme():
    return """
    /* ============================================
       GLOBAL COLORS & DEFAULT FONT
       ============================================ */
    * {
        background-color: #121212;
        color: #E0E0E0;
        font-family: Segoe UI, Arial;
        font-size: 14px;
    }

    QWidget {
        background-color: #121212;
    }

    QLabel {
        color: #E0E0E0;
    }

    /* ============================================
       PUSH BUTTONS (Kaspa Cyan)
       ============================================ */
    QPushButton {
        background-color: #0FB5BA;     /* Kaspa Cyan */
        color: #000000;
        border: none;
        padding: 8px 14px;
        border-radius: 6px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: #19CCD2;     /* Lighter Kaspa Cyan */
    }

    QPushButton:pressed {
        background-color: #0C9FA3;     /* Darker Kaspa Cyan */
    }

    QPushButton:disabled {
        background-color: #2f2f2f;
        color: #777;
    }

    /* ============================================
       RADIO BUTTONS (Kaspa Accurate)
       ============================================ */
    QRadioButton {
        color: #E0E0E0;
        spacing: 8px;
    }

    QRadioButton::indicator {
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 2px solid #0FB5BA;   /* Kaspa Cyan */
        background-color: #121212;
    }

    QRadioButton::indicator:hover {
        border: 2px solid #19CCD2;   /* Hover Cyan */
    }

    QRadioButton::indicator:checked {
        background-color: #0FB5BA;   /* Filled when checked */
        border: 2px solid #19CCD2;
    }

    /* ============================================
       LISTS
       ============================================ */
    QListWidget {
        background-color: #181818;
        border: 1px solid #1F1F1F;
        border-radius: 6px;
    }

    QListWidget::item {
        padding: 6px;
    }

    QListWidget::item:selected {
        background-color: #9147FF;   /* PoCI Purple */
    }

    /* ============================================
       TEXT INPUTS
       ============================================ */
    QTextEdit, QLineEdit {
        background-color: #181818;
        border: 1px solid #333333;
        border-radius: 6px;
        padding: 6px;
    }

    /* ============================================
       MENUS
       ============================================ */
    QMenuBar {
        background-color: #181818;
        color: #E0E0E0;
    }

    QMenu {
        background-color: #181818;
        color: #E0E0E0;
        border: 1px solid #333333;
    }

    QMenu::item:selected {
        background-color: #0FB5BA;   /* Kaspa Cyan */
        color: #000000;
    }

    /* ============================================
       SCROLLBARS
       ============================================ */
    QScrollBar:vertical {
        background-color: #121212;
        width: 12px;
        margin: 0px;
    }

    QScrollBar::handle:vertical {
        background-color: #333333;
        min-height: 20px;
        border-radius: 6px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #444444;
    }

    /* ============================================
       SPLITTER BARS
       ============================================ */
    QSplitter::handle {
        background-color: #2A2A2A;
    }
    """

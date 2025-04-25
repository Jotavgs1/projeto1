# Stylesheets for the UI components

DATE_EDIT_STYLE = """
    QDateEdit {
        padding: 8px;
        border: 1px solid #D2D2D7;
        border-radius: 8px;
        background-color: #F5F5F7;
        font-size: 14px;
        min-width: 100px;
    }
    QDateEdit:hover {
        border-color: #28A745;
    }
    QDateEdit::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        border-left: 1px solid #D2D2D7;
        background-color: #C8E6C9;
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
    }
    QDateEdit::down-arrow {
        image: none;
        width: 0px;
        height: 0px;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid #1A1A1A;
        margin-right: 8px;
    }
    QDateEdit::drop-down:hover {
        background-color: #A5D6A7;
    }
    QDateEdit::drop-down:pressed {
        background-color: #81C784;
    }
    QCalendarWidget {
        background-color: #E8F5E9;
        border: 1px solid #D2D2D7;
        border-radius: 8px;
    }
    QCalendarWidget QWidget#qt_calendar_navigationbar {
        background-color: #C8E6C9;
        padding: 5px;
    }
    QCalendarWidget QToolButton {
        color: #1A1A1A;
        background-color: #C8E6C9;
        border: none;
        margin: 2px;
        padding: 5px;
    }
    QCalendarWidget QToolButton:hover {
        background-color: #A5D6A7;
    }
    QCalendarWidget QToolButton:pressed {
        background-color: #81C784;
    }
    QCalendarWidget QMenu {
        background-color: #E8F5E9;
        border: 1px solid #D2D2D7;
        color: #1A1A1A;
    }
    QCalendarWidget QMenu::item:selected {
        background-color: #A5D6A7;
    }
    QCalendarWidget QWidget#qt_calendar_calendarview {
        background-color: #E8F5E9;
    }
    QCalendarWidget QAbstractItemView {
        background-color: #E8F5E9;
        color: #1A1A1A;
        selection-background-color: #E6F0FA;
        selection-color: #1A1A1A;
        border: none;
    }
    QCalendarWidget QAbstractItemView:disabled {
        color: #A0A0A0;
    }
"""

COMBO_BOX_STYLE = """
    QComboBox {
        padding: 8px;
        border: 1px solid #D2D2D7;
        border-radius: 8px;
        background-color: #F5F5F7;
        font-size: 14px;
        min-width: 150px;
    }
    QComboBox:hover {
        border-color: #28A745;
    }
    QComboBox::drop-down {
        border: none;
    }
"""

CHECKBOX_STYLE = """
    QCheckBox {
        font-size: 14px;
        padding: 8px;
    }
"""

BUTTON_BOX_STYLE = """
    QPushButton {
        background-color: #28A745;
        color: #FFFFFF;
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        border: none;
    }
    QPushButton:hover {
        background-color: #218838;
    }
    QPushButton:pressed {
        background-color: #1E7E34;
    }
    QPushButton[text="Cancel"] {
        background-color: #FFFFFF;
        color: #1A1A1A;
        border: 1px solid #D2D2D7;
    }
    QPushButton[text="Cancel"]:hover {
        background-color: #F5F5F7;
    }
    QPushButton[text="Cancel"]:pressed {
        background-color: #E5E5EA;
    }
"""

LINE_EDIT_STYLE = """
    QLineEdit {
        padding: 8px;
        border: 1px solid #D2D2D7;
        border-radius: 8px;
        background-color: #F5F5F7;
        font-size: 14px;
        min-width: 200px;
    }
    QLineEdit:hover {
        border-color: #28A745;
    }
"""

BUTTON_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #1A1A1A;
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        border: 1px solid #D2D2D7;
    }
    QPushButton:hover {
        background-color: #F5F5F7;
    }
    QPushButton:pressed {
        background-color: #E5E5EA;
    }
"""

APPLY_BUTTON_STYLE = """
    QPushButton {
        background-color: #28A745;
        color: #FFFFFF;
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #218838;
    }
    QPushButton:pressed {
        background-color: #1E7E34;
    }
    QPushButton:disabled {
        background-color: #A0A0A0;
    }
"""

PROGRESS_FRAME_STYLE = """
    QFrame {
        border: 2px solid #34C759;
        border-radius: 8px;
        background-color: #F5F5F7;
        padding: 2px;
    }
"""

PROGRESS_BAR_STYLE = """
    QProgressBar {
        border: none;
        border-radius: 6px;
        background-color: #E5E5EA;
        text-align: center;
        font-size: 14px;
        color: #FFFFFF;
        height: 24px;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34C759, stop:1 #28A745);
        border-radius: 6px;
    }
"""

FRAME_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F5F5F7);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #E5E5EA;
    }
"""

SUMMARY_FRAME_STYLE = """
    QFrame {
        background-color: transparent;
        border-radius: 12px;
    }
"""

LABEL_STYLE = """
    QLabel {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F9F9FB);
        border-radius: 12px;
        padding: 20px;
        font-size: 16px;
        font-weight: bold;
        color: #1A1A1A;
        border: 1px solid #E5E5EA;
    }
"""

TABLE_STYLE = """
    QTableWidget {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F9F9FB);
        border-radius: 12px;
        border: 1px solid #E5E5EA;
        font-family: 'Inter', sans-serif;
        font-size: 14px;
    }
    QHeaderView::section {
        background-color: #E5E5EA;
        padding: 12px;
        border: none;
        font-weight: 600;
        color: #1A1A1A;
        border-bottom: 1px solid #D2D2D7;
    }
    QTableWidget::item {
        padding: 12px;
        border-bottom: 1px solid #E5E5EA;
    }
    QTableWidget::item:selected {
        background-color: #E6F0FA;
    }
    QTableWidget::item:hover {
        background-color: #E6F0FA;
    }
"""
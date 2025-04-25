import sys
import os
import json
import time
import locale
import requests
import pandas as pd
from datetime import datetime, timedelta
from dateutil import parser
import pytz
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDateEdit, QPushButton, QMessageBox, QLineEdit, QFrame, QTableWidget, QTableWidgetItem, QProgressBar,
    QDialog, QComboBox, QCheckBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, QDate, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QFontDatabase
from uuid import uuid4

# Custom print filter to suppress non-error messages
class PrintFilter:
    def __init__(self):
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def write(self, text):
        if "Error" in text or "Exception" in text:
            self.original_stderr.write(text)

    def flush(self):
        self.original_stderr.flush()

def load_config():
    """Load configurations from config.json"""
    config_file = "config.json"
    if not os.path.exists(config_file):
        print("Error: config.json file not found")
        return {}
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
            required_keys = ["vtex_account", "app_key", "app_token"]
            if not all(key in config for key in required_keys):
                print(f"Error: config.json must contain {required_keys}")
                return {}
            return config
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config.json - {e}")
        return {}

def is_date_in_brazil_interval(dt, start_date, end_date):
    """Check if the date is within the given interval in Brasília time"""
    brazil_tz = pytz.timezone("America/Sao_Paulo")
    dt_brazil = dt.astimezone(brazil_tz).date()
    return start_date <= dt_brazil <= end_date

def format_currency(value):
    """Format a value as Brazilian currency (e.g., R$ 3,00)"""
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        return locale.currency(value, grouping=True, symbol=True)
    except locale.Error:
        return f"R$ {value:,.2f}".replace(".", ",")

def fetch_order_details(order_id, config, headers, max_retries=3):
    """Fetch order details to get shipping value and shipping list price"""
    url = f"https://{config['vtex_account']}.vtexcommercestable.com.br/api/oms/pvt/orders/{order_id}"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"Error 429: Rate limit reached for order {order_id}. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            data = response.json()
            shipping_value = data.get('shippingValue', None)
            if shipping_value is not None:
                shipping_value = shipping_value / 100
            else:
                for total in data.get('totals', []):
                    if total.get('id') == 'Shipping':
                        shipping_value = total.get('value', 0) / 100
                        break
                else:
                    shipping_value = 0.0
            
            shipping_list_price = 0.0
            logistics_info = data.get('shippingData', {}).get('logisticsInfo', [])
            for item in logistics_info:
                if 'listPrice' in item:
                    shipping_list_price = item['listPrice'] / 100
                    break
            else:
                shipping_list_price = shipping_value
            
            return shipping_value, shipping_list_price
        except requests.RequestException as e:
            print(f"Error fetching details for order {order_id}: {e} (Status: {response.status_code if 'response' in locals() else 'N/A'})")
            if attempt == max_retries - 1:
                print(f"Max retries reached for order {order_id}. Assuming shipping value = 0 and shipping list price = 0.")
                return 0.0, 0.0
            time.sleep(2 ** attempt)
    return 0.0, 0.0

class FetchOrdersThread(QThread):
    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, start_date, end_date, status_filter):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.status_filter = status_filter

    def run(self):
        config = load_config()
        if not config:
            self.error.emit("Configuração inválida")
            return

        url = f"https://{config['vtex_account']}.vtexcommercestable.com.br/api/oms/pvt/orders"
        headers = {
            "X-VTEX-API-AppKey": config["app_key"],
            "X-VTEX-API-AppToken": config["app_token"],
        }

        brazil_tz = pytz.timezone("America/Sao_Paulo")
        start_dt = datetime.combine(self.start_date, datetime.min.time(), tzinfo=brazil_tz)
        end_dt = datetime.combine(self.end_date, datetime.max.time(), tzinfo=brazil_tz)
        start_utc = start_dt.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_utc = end_dt.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%S.999Z")
        date_filter = f"creationDate:[{start_utc} TO {end_utc}]"
        
        status_map = {
            "Faturado": ["invoiced"],
            "Pronto para Manuseio": ["ready-for-handling"],
            "Todos": ["invoiced", "ready-for-handling"]
        }
        statuses = status_map[self.status_filter]

        orders = []
        order_ids = set()
        total_expected = 0
        max_retries = 3
        orders_fetched = 0

        for status in statuses:
            params = {
                "per_page": 100,
                "page": 1,
                "f_creationDate": date_filter,
                "orderStatus": status,
                "orderBy": "creationDate,asc"
            }

            try:
                while True:
                    for attempt in range(max_retries):
                        try:
                            response = requests.get(url, headers=headers, params=params, timeout=10)
                            if response.status_code == 429:
                                wait_time = 2 ** attempt
                                print(f"Error 429: Rate limit reached. Waiting {wait_time} seconds...")
                                time.sleep(wait_time)
                                continue
                            response.raise_for_status()
                            break
                        except requests.RequestException as e:
                            print(f"Request error for status '{status}': {e}")
                            if attempt == max_retries - 1:
                                print(f"Max retries reached for status '{status}'. Skipping...")
                                break
                            time.sleep(2 ** attempt)

                    if response.status_code != 200:
                        break

                    data = response.json()
                    if "paging" not in data or "list" not in data:
                        print(f"Error: API response missing 'paging' or 'list' for status '{status}'")
                        break

                    total_expected += data["paging"].get("total", 0)
                    page_orders = data["list"]
                    for order in page_orders:
                        order_status = order.get('status', 'unknown')
                        order_id = order.get('orderId')
                        if order_status not in statuses:
                            continue
                        if order_id not in order_ids:
                            shipping_value, shipping_list_price = fetch_order_details(order_id, config, headers)
                            order['shippingValue'] = shipping_value * 100
                            order['shippingListPrice'] = shipping_list_price * 100
                            orders.append(order)
                            order_ids.add(order_id)
                            orders_fetched += 1
                            if total_expected > 0:
                                progress_percent = min(100, int((orders_fetched / total_expected) * 100))
                                self.progress.emit(progress_percent)

                    if not page_orders or len(page_orders) < params["per_page"]:
                        break
                    params["page"] += 1

            except Exception as e:
                print(f"Unexpected error for status '{status}': {e}")
                continue

        self.finished.emit(orders)

class FilterDialog(QDialog):
    def __init__(self, parent=None, current_status="Todos", include_freight=True):
        super().__init__(parent)
        self.setWindowTitle("Filtros")
        self.setFixedSize(300, 200)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Status filter
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-size: 14px;")
        status_layout.addWidget(status_label)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Todos", "Faturado", "Pronto para Manuseio"])
        self.status_combo.setCurrentText(current_status)
        self.status_combo.setStyleSheet("""
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
        """)
        status_layout.addWidget(self.status_combo)
        layout.addLayout(status_layout)

        # Freight filter
        self.freight_checkbox = QCheckBox("Incluir Frete")
        self.freight_checkbox.setChecked(include_freight)
        self.freight_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.freight_checkbox)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.setStyleSheet("""
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
        """)
        layout.addWidget(button_box)

    def get_filters(self):
        return self.status_combo.currentText(), self.freight_checkbox.isChecked()

class OrdersDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VTEX Orders Dashboard")
        self.setMinimumSize(1000, 700)
        self.orders = []
        self.all_orders = []  # Store all orders for filtering
        self.status_filter = "Todos"  # Default status filter
        self.include_freight = True  # Default freight inclusion

        # Load Inter font
        font_db = QFontDatabase()
        font_id = font_db.addApplicationFont(":/fonts/Inter-Regular.ttf")
        if font_id != -1:
            font_families = font_db.applicationFontFamilies(font_id)
            if font_families:
                self.app_font = QFont(font_families[0], 12)
        else:
            self.app_font = QFont("Arial", 12)
        self.setFont(self.app_font)

        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)

        # Header
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F5F5F7);
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #E5E5EA;
            }
        """)
        header_layout = QHBoxLayout(header_frame)

        title_label = QLabel("VTEX Orders Dashboard")
        title_label.setFont(QFont(self.app_font.family(), 24, QFont.Bold))
        title_label.setStyleSheet("color: #1A1A1A; margin: 0;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addWidget(header_frame)

        # Filter frame
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F5F5F7);
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #E5E5EA;
            }
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(20)

        # Date filters
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate(2025, 4, 24))
        self.start_date_edit.setMaximumDate(QDate(2025, 4, 25))
        self.start_date_edit.setStyleSheet("""
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
                background-color: #919191;
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
                background-color: #919191;
                padding: 5px;
            }
            QCalendarWidget QToolButton {
                color: #1A1A1A;
                background-color: #919191;
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
        """)
        filter_layout.addWidget(QLabel("Data Início:"))
        filter_layout.addWidget(self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate(2025, 4, 24))
        self.end_date_edit.setMaximumDate(QDate(2025, 4, 25))
        self.end_date_edit.setStyleSheet("""
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
                background-color: #919191;
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
                background-color: #919191;
                padding: 5px;
            }
            QCalendarWidget QToolButton {
                color: #1A1A1A;
                background-color: #919191;
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
        """)
        filter_layout.addWidget(QLabel("Data Fim:"))
        filter_layout.addWidget(self.end_date_edit)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Pesquisar Pedidos")
        self.search_bar.setStyleSheet("""
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
        """)
        self.search_bar.textChanged.connect(self.apply_search_filter)
        filter_layout.addWidget(self.search_bar)

        # Filter button
        self.filters_button = QPushButton("Filtros")
        self.filters_button.setStyleSheet("""
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
        """)
        self.filters_button.clicked.connect(self.open_filters_dialog)
        filter_layout.addWidget(self.filters_button)

        # Clear filters button
        self.clear_filters_button = QPushButton("Limpar Filtros")
        self.clear_filters_button.setStyleSheet("""
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
        """)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filter_layout.addWidget(self.clear_filters_button)

        # Apply filters button
        self.apply_button = QPushButton("Filtrar")
        self.apply_button.setStyleSheet("""
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
        """)
        self.apply_button.clicked.connect(self.apply_filter)
        filter_layout.addWidget(self.apply_button)
        main_layout.addWidget(filter_frame)

        # Progress bar frame
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #34C759;
                border-radius: 8px;
                background-color: #F5F5F7;
                padding: 2px;
            }
        """)
        progress_layout = QHBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet("""
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
        """)
        progress_layout.addWidget(self.progress_bar)
        self.progress_bar.hide()
        self.progress_frame.hide()
        main_layout.addWidget(self.progress_frame)

        # Pulsing animation for progress frame border
        self.pulse_animation = QPropertyAnimation(self.progress_frame, b"styleSheet")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setLoopCount(-1)
        self.pulse_animation.setKeyValueAt(0, """
            QFrame {
                border: 2px solid #34C759;
                border-radius: 8px;
                background-color: #F5F5F7;
                padding: 2px;
            }
        """)
        self.pulse_animation.setKeyValueAt(0.5, """
            QFrame {
                border: 2px solid #66D989;
                border-radius: 8px;
                background-color: #F5F5F7;
                padding: 2px;
            }
        """)
        self.pulse_animation.setKeyValueAt(1, """
            QFrame {
                border: 2px solid #34C759;
                border-radius: 8px;
                background-color: #F5F5F7;
                padding: 2px;
            }
        """)
        self.pulse_animation.setEasingCurve(QEasingCurve.InOutSine)

        # Summary frame
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-radius: 12px;
            }
        """)
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setSpacing(20)

        # Total Orders Card
        self.total_orders_label = QLabel("Total Orders\n0")
        self.total_orders_label.setAlignment(Qt.AlignCenter)
        self.total_orders_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F9F9FB);
                border-radius: 12px;
                padding: 20px;
                font-size: 16px;
                font-weight: bold;
                color: #1A1A1A;
                border: 1px solid #E5E5EA;
            }
        """)
        summary_layout.addWidget(self.total_orders_label)

        # Subtotal Card
        self.subtotal_label = QLabel("Subtotal\nR$ 0,00")
        self.subtotal_label.setAlignment(Qt.AlignCenter)
        self.subtotal_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F9F9FB);
                border-radius: 12px;
                padding: 20px;
                font-size: 16px;
                font-weight: bold;
                color: #1A1A1A;
                border: 1px solid #E5E5EA;
            }
        """)
        summary_layout.addWidget(self.subtotal_label)

        # Freight Subtotal Card
        self.freight_subtotal_label = QLabel("Subtotal Frete\nR$ 0,00")
        self.freight_subtotal_label.setAlignment(Qt.AlignCenter)
        self.freight_subtotal_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F9F9FB);
                border-radius: 12px;
                padding: 20px;
                font-size: 16px;
                font-weight: bold;
                color: #1A1A1A;
                border: 1px solid #E5E5EA;
            }
        """)
        summary_layout.addWidget(self.freight_subtotal_label)

        main_layout.addWidget(summary_frame)

        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID do Pedido", "Data de Criação", "Status", "Valor do Pedido (R$)"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet("""
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
        """)
        main_layout.addWidget(self.table, stretch=1)

        # Initial load
        self.apply_filter()

    def apply_filter(self):
        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()
        start_date = start_qdate.toPython()
        end_date = end_qdate.toPython()

        if end_date < start_date:
            QMessageBox.warning(self, "Erro", "Data Fim não pode ser anterior à Data Início.")
            return
        if (end_date - start_date).days > 7:
            QMessageBox.warning(self, "Erro", "O intervalo de datas não pode exceder 7 dias.")
            return

        self.apply_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.progress_frame.show()
        self.pulse_animation.start()

        self.fetch_thread = FetchOrdersThread(start_date, end_date, self.status_filter)
        self.fetch_thread.progress.connect(self.update_progress)
        self.fetch_thread.finished.connect(self.on_fetch_finished)
        self.fetch_thread.error.connect(self.on_fetch_error)
        self.fetch_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def on_fetch_finished(self, orders):
        self.all_orders = orders  # Store all orders for filtering
        self.orders = orders
        self.apply_search_filter()  # Apply search filter after fetching
        self.progress_bar.hide()
        self.progress_frame.hide()
        self.pulse_animation.stop()
        self.apply_button.setEnabled(True)

    def on_fetch_error(self, message):
        QMessageBox.critical(self, "Erro", message)
        self.progress_bar.hide()
        self.progress_frame.hide()
        self.pulse_animation.stop()
        self.apply_button.setEnabled(True)

    def apply_search_filter(self):
        search_text = self.search_bar.text().lower()
        if not self.all_orders:
            self.orders = []
        else:
            self.orders = [
                order for order in self.all_orders
                if search_text in order['orderId'].lower()
            ]
        self.update_table()

    def open_filters_dialog(self):
        dialog = FilterDialog(self, self.status_filter, self.include_freight)
        if dialog.exec():
            self.status_filter, self.include_freight = dialog.get_filters()
            self.apply_filter()  # Re-fetch with new status filter
        dialog.deleteLater()

    def clear_filters(self):
        self.search_bar.clear()
        self.status_filter = "Todos"
        self.include_freight = True
        self.apply_filter()  # Re-fetch with default filters

    def update_table(self):
        orders_data = []
        subtotal = 0.0
        freight_subtotal = 0.0

        if self.orders:
            for order in self.orders:
                try:
                    creation_date = parser.isoparse(order['creationDate'])
                    start_date = self.start_date_edit.date().toPython()
                    end_date = self.end_date_edit.date().toPython()
                    if not is_date_in_brazil_interval(creation_date, start_date, end_date):
                        continue
                    order_value = order.get('totalValue', 0) / 100
                    shipping_list_price = order.get('shippingListPrice', order.get('shippingValue', 0)) / 100
                    freight_subtotal += shipping_list_price
                    display_value = order_value if self.include_freight else max(0.0, order_value - shipping_list_price)
                    subtotal += display_value
                    orders_data.append({
                        "ID do Pedido": order['orderId'],
                        "Data de Criação": creation_date.astimezone(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S"),
                        "Status": order['status'],
                        "Valor do Pedido (R$)": format_currency(display_value),
                        "creation_date_raw": creation_date
                    })
                except ValueError as e:
                    print(f"Error parsing date for order {order['orderId']}: {e}")
                    continue

            orders_data.sort(key=lambda x: x["creation_date_raw"])
            orders_data = [
                {
                    "ID do Pedido": order["ID do Pedido"],
                    "Data de Criação": order["Data de Criação"],
                    "Status": order["Status"],
                    "Valor do Pedido (R$)": order["Valor do Pedido (R$)"],
                }
                for order in orders_data
            ]

        self.table.setRowCount(len(orders_data))
        for row_idx, order in enumerate(orders_data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(order["ID do Pedido"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(order["Data de Criação"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(order["Status"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(order["Valor do Pedido (R$)"]))
        self.table.resizeColumnsToContents()

        self.total_orders_label.setText(f"Total Orders\n{len(orders_data)}")
        self.subtotal_label.setText(f"Subtotal\n{format_currency(subtotal)}")
        self.freight_subtotal_label.setText(f"Subtotal Frete\n{format_currency(freight_subtotal)}")
        if not orders_data:
            QMessageBox.information(self, "Informação", "Nenhum pedido encontrado para o intervalo e status selecionados.")

def main():
    sys.stdout = PrintFilter()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    app = QApplication(sys.argv)
    window = OrdersDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
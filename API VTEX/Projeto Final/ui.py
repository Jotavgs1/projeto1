from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDateEdit, QPushButton, QMessageBox, QLineEdit, QFrame, QTableWidget, QTableWidgetItem, QProgressBar,
    QDialog, QComboBox, QCheckBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, QDate, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QFontDatabase
import pytz
from dateutil import parser

from utils import is_date_in_brazil_interval, format_currency
from api import FetchOrdersThread
from styles import (
    DATE_EDIT_STYLE, COMBO_BOX_STYLE, CHECKBOX_STYLE, BUTTON_BOX_STYLE,
    LINE_EDIT_STYLE, BUTTON_STYLE, APPLY_BUTTON_STYLE, PROGRESS_FRAME_STYLE,
    PROGRESS_BAR_STYLE, FRAME_STYLE, SUMMARY_FRAME_STYLE, LABEL_STYLE, TABLE_STYLE
)

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
        self.status_combo.setStyleSheet(COMBO_BOX_STYLE)
        status_layout.addWidget(self.status_combo)
        layout.addLayout(status_layout)

        # Freight filter
        self.freight_checkbox = QCheckBox("Incluir Frete")
        self.freight_checkbox.setChecked(include_freight)
        self.freight_checkbox.setStyleSheet(CHECKBOX_STYLE)
        layout.addWidget(self.freight_checkbox)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.setStyleSheet(BUTTON_BOX_STYLE)
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
        font_id = QFontDatabase.addApplicationFont(":/fonts/Inter-Regular.ttf")
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
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
        header_frame.setStyleSheet(FRAME_STYLE)
        header_layout = QHBoxLayout(header_frame)

        title_label = QLabel("VTEX Orders Dashboard")
        title_label.setFont(QFont(self.app_font.family(), 24, QFont.Bold))
        title_label.setStyleSheet("color: #1A1A1A; margin: 0;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addWidget(header_frame)

        # Filter frame
        filter_frame = QFrame()
        filter_frame.setStyleSheet(FRAME_STYLE)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(20)

        # Date filters
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate(2025, 4, 24))
        self.start_date_edit.setMaximumDate(QDate(2025, 4, 25))
        self.start_date_edit.setStyleSheet(DATE_EDIT_STYLE)
        filter_layout.addWidget(QLabel("Data Início:"))
        filter_layout.addWidget(self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate(2025, 4, 24))
        self.end_date_edit.setMaximumDate(QDate(2025, 4, 25))
        self.end_date_edit.setStyleSheet(DATE_EDIT_STYLE)
        filter_layout.addWidget(QLabel("Data Fim:"))
        filter_layout.addWidget(self.end_date_edit)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Pesquisar Pedidos")
        self.search_bar.setStyleSheet(LINE_EDIT_STYLE)
        self.search_bar.textChanged.connect(self.apply_search_filter)
        filter_layout.addWidget(self.search_bar)

        # Filter button
        self.filters_button = QPushButton("Filtros")
        self.filters_button.setStyleSheet(BUTTON_STYLE)
        self.filters_button.clicked.connect(self.open_filters_dialog)
        filter_layout.addWidget(self.filters_button)

        # Clear filters button
        self.clear_filters_button = QPushButton("Limpar Filtros")
        self.clear_filters_button.setStyleSheet(BUTTON_STYLE)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filter_layout.addWidget(self.clear_filters_button)

        # Apply filters button
        self.apply_button = QPushButton("Filtrar")
        self.apply_button.setStyleSheet(APPLY_BUTTON_STYLE)
        self.apply_button.clicked.connect(self.apply_filter)
        filter_layout.addWidget(self.apply_button)
        main_layout.addWidget(filter_frame)

        # Progress bar frame
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet(PROGRESS_FRAME_STYLE)
        progress_layout = QHBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)
        progress_layout.addWidget(self.progress_bar)
        self.progress_bar.hide()
        self.progress_frame.hide()
        main_layout.addWidget(self.progress_frame)

        # Pulsing animation for progress frame border
        self.pulse_animation = QPropertyAnimation(self.progress_frame, b"styleSheet")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setLoopCount(-1)
        self.pulse_animation.setKeyValueAt(0, PROGRESS_FRAME_STYLE)
        self.pulse_animation.setKeyValueAt(0.5, """
            QFrame {
                border: 2px solid #66D989;
                border-radius: 8px;
                background-color: #F5F5F7;
                padding: 2px;
            }
        """)
        self.pulse_animation.setKeyValueAt(1, PROGRESS_FRAME_STYLE)
        self.pulse_animation.setEasingCurve(QEasingCurve.InOutSine)

        # Summary frame
        summary_frame = QFrame()
        summary_frame.setStyleSheet(SUMMARY_FRAME_STYLE)
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setSpacing(20)

        # Total Orders Card
        self.total_orders_label = QLabel("Total Orders\n0")
        self.total_orders_label.setAlignment(Qt.AlignCenter)
        self.total_orders_label.setStyleSheet(LABEL_STYLE)
        summary_layout.addWidget(self.total_orders_label)

        # Subtotal Card
        self.subtotal_label = QLabel("Subtotal\nR$ 0,00")
        self.subtotal_label.setAlignment(Qt.AlignCenter)
        self.subtotal_label.setStyleSheet(LABEL_STYLE)
        summary_layout.addWidget(self.subtotal_label)

        # Freight Subtotal Card
        self.freight_subtotal_label = QLabel("Subtotal Frete\nR$ 0,00")
        self.freight_subtotal_label.setAlignment(Qt.AlignCenter)
        self.freight_subtotal_label.setStyleSheet(LABEL_STYLE)
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
        self.table.setStyleSheet(TABLE_STYLE)
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
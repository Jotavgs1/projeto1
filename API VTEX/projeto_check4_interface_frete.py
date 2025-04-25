import requests
import json
import os
import time
import pandas as pd
from dateutil import parser
from datetime import datetime, timedelta
import pytz
from PySide6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDateEdit, QPushButton, QMessageBox, QComboBox, QCheckBox
from PySide6.QtCore import Qt, QDate
import sys
import locale

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
            # Try direct shippingValue
            shipping_value = data.get('shippingValue', None)
            if shipping_value is not None:
                shipping_value = shipping_value / 100  # Convert to BRL
                print(f"Order {order_id}: Shipping Value (direct) = {format_currency(shipping_value)}")
            else:
                # Fallback to totals
                for total in data.get('totals', []):
                    if total.get('id') == 'Shipping':
                        shipping_value = total.get('value', 0) / 100  # Convert to BRL
                        print(f"Order {order_id}: Shipping Value (totals) = {format_currency(shipping_value)}")
                        break
                else:
                    shipping_value = 0.0
                    print(f"Order {order_id}: No shipping value found in totals, assuming 0.")
            
            # Try shippingListPrice from logisticsInfo
            shipping_list_price = 0.0
            logistics_info = data.get('shippingData', {}).get('logisticsInfo', [])
            for item in logistics_info:
                if 'listPrice' in item:
                    shipping_list_price = item['listPrice'] / 100  # Convert to BRL
                    print(f"Order {order_id}: Shipping List Price (logisticsInfo) = {format_currency(shipping_list_price)}")
                    break
            else:
                print(f"Order {order_id}: No Shipping List Price found, using shippingValue = {format_currency(shipping_value)}")
                shipping_list_price = shipping_value
            
            return shipping_value, shipping_list_price
        except requests.RequestException as e:
            print(f"Error fetching details for order {order_id}: {e} (Status: {response.status_code if 'response' in locals() else 'N/A'})")
            if attempt == max_retries - 1:
                print(f"Max retries reached for order {order_id}. Assuming shipping value = 0 and shipping list price = 0.")
                return 0.0, 0.0
            time.sleep(2 ** attempt)
    return 0.0, 0.0

def fetch_orders(start_date, end_date, status_filter):
    """Fetch VTEX orders for the given date range and status filter"""
    config = load_config()
    if not config:
        return []

    # API configuration
    url = f"https://{config['vtex_account']}.vtexcommercestable.com.br/api/oms/pvt/orders"
    headers = {
        "X-VTEX-API-AppKey": config["app_key"],
        "X-VTEX-API-AppToken": config["app_token"],
    }

    # Convert dates to UTC for API (Brasília is UTC-3)
    brazil_tz = pytz.timezone("America/Sao_Paulo")
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=brazil_tz)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=brazil_tz)
    start_utc = start_dt.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_utc = end_dt.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%S.999Z")
    date_filter = f"creationDate:[{start_utc} TO {end_utc}]"
    
    # Define statuses to fetch
    status_map = {
        "Faturado": ["invoiced"],
        "Pronto para Manuseio": ["ready-for-handling"],
        "Todos": ["invoiced", "ready-for-handling"]
    }
    statuses = status_map[status_filter]

    orders = []
    order_ids = set()  # Track unique order IDs to avoid duplicates
    total_expected = 0
    max_retries = 3

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
                    print(f"\nFetching page {params['page']} for status '{status}' (Attempt {attempt + 1}/{max_retries})...")
                    print(f"Parameters: {params}")
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
                print(f"API response for status '{status}': {json.dumps(data, indent=2)}")

                # Verify response structure
                if "paging" not in data or "list" not in data:
                    print(f"Error: API response missing 'paging' or 'list' for status '{status}'")
                    break

                total_expected += data["paging"].get("total", 0)
                print(f"Expected total (API) for status '{status}': {data['paging'].get('total', 0)}")
                page_orders = data["list"]
                print(f"\nOrders found on page {params['page']} for status '{status}':")
                for order in page_orders:
                    order_status = order.get('status', 'unknown')
                    order_id = order.get('orderId')
                    print(f" - Order {order_id}: Status {order_status}, Date {order['creationDate']}, Value {order.get('totalValue', 0)}")
                    if order_status not in statuses:
                        print(f"   Warning: Order {order_id} has unexpected status: {order_status}")
                        continue
                    if order_id not in order_ids:  # Avoid duplicates
                        # Fetch shipping value and shipping list price
                        shipping_value, shipping_list_price = fetch_order_details(order_id, config, headers)
                        order['shippingValue'] = shipping_value * 100  # Store in cents
                        order['shippingListPrice'] = shipping_list_price * 100  # Store in cents
                        orders.append(order)
                        order_ids.add(order_id)
                print(f"Page {params['page']} for status '{status}': {len(page_orders)} orders")

                # Stop if no more orders or page is empty
                if not page_orders or len(page_orders) < params["per_page"]:
                    break

                params["page"] += 1

        except Exception as e:
            print(f"Unexpected error for status '{status}': {e}")
            continue

    # Summary of fetched orders
    print(f"\nTotal orders fetched: {len(orders)} (Expected: {total_expected})")
    
    # Check for specific missing orders
    missing_orders = [
        "1527370727164-01",
        "1527370727166-01",
        "1527380727170-01"
    ]
    found_orders = [order['orderId'] for order in orders]
    for missing_id in missing_orders:
        if missing_id not in found_orders:
            print(f"Warning: Order {missing_id} not found in API response")
        else:
            print(f"Confirmed: Order {missing_id} found")

    return orders

class OrdersDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VTEX Orders Dashboard - Date, Status, and Freight Filter")
        self.setGeometry(100, 100, 800, 600)

        # Store orders data for dynamic updates
        self.orders = []
        self.include_freight = True

        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("VTEX Orders Dashboard")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title_label)

        # Filter layout
        filter_layout = QHBoxLayout()
        
        # Date filters
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate(2025, 4, 24))
        self.start_date_edit.setMaximumDate(QDate(2025, 4, 25))
        filter_layout.addWidget(QLabel("Data Início:"))
        filter_layout.addWidget(self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate(2025, 4, 24))
        self.end_date_edit.setMaximumDate(QDate(2025, 4, 25))
        filter_layout.addWidget(QLabel("Data Fim:"))
        filter_layout.addWidget(self.end_date_edit)

        # Status filter
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Todos", "Faturado", "Pronto para Manuseio"])
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_combo)

        # Freight filter
        self.freight_checkbox = QCheckBox("Incluir Frete")
        self.freight_checkbox.setChecked(True)
        self.freight_checkbox.stateChanged.connect(self.update_table)
        filter_layout.addWidget(self.freight_checkbox)

        filter_button = QPushButton("Filtrar")
        filter_button.clicked.connect(self.apply_filter)
        filter_layout.addWidget(filter_button)
        main_layout.addLayout(filter_layout)

        # Orders table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID do Pedido", "Data de Criação", "Status", "Valor do Pedido (R$)"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet("QTableWidget { font-size: 12px; }")
        main_layout.addWidget(self.table)

        # Summary
        self.summary_label = QLabel("Total Orders: 0 | Subtotal: R$ 0,00")
        self.summary_label.setAlignment(Qt.AlignCenter)
        self.summary_label.setStyleSheet("font-size: 14px; margin: 10px;")
        main_layout.addWidget(self.summary_label)

        # Initial load
        self.apply_filter()

    def apply_filter(self):
        start_qdate = self.start_date_edit.date()
        end_qdate = self.end_date_edit.date()
        start_date = start_qdate.toPython()
        end_date = end_qdate.toPython()
        status_filter = self.status_combo.currentText()

        # Validate date range
        if end_date < start_date:
            QMessageBox.warning(self, "Erro", "Data Fim não pode ser anterior à Data Início.")
            return
        if (end_date - start_date).days > 7:
            QMessageBox.warning(self, "Erro", "O intervalo de datas não pode exceder 7 dias.")
            return

        # Fetch orders
        self.orders = fetch_orders(start_date, end_date, status_filter)
        self.include_freight = self.freight_checkbox.isChecked()
        self.update_table()

    def update_table(self):
        """Update table and subtotal based on current orders and freight filter"""
        orders_data = []
        subtotal = 0.0
        include_freight = self.freight_checkbox.isChecked()

        if self.orders:
            print("\nPreparing order data for display...")
            for order in self.orders:
                try:
                    creation_date = parser.isoparse(order['creationDate'])
                    # Check if date is within the interval in Brasília
                    start_date = self.start_date_edit.date().toPython()
                    end_date = self.end_date_edit.date().toPython()
                    if not is_date_in_brazil_interval(creation_date, start_date, end_date):
                        print(f"Order {order['orderId']} ignored: Date {creation_date} outside selected interval")
                        continue
                    order_value = order.get('totalValue', 0) / 100
                    shipping_list_price = order.get('shippingListPrice', order.get('shippingValue', 0)) / 100
                    display_value = order_value if include_freight else max(0.0, order_value - shipping_list_price)
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

            # Sort by creation date
            orders_data.sort(key=lambda x: x["creation_date_raw"])

            # Remove sorting column
            orders_data = [
                {
                    "ID do Pedido": order["ID do Pedido"],
                    "Data de Criação": order["Data de Criação"],
                    "Status": order["Status"],
                    "Valor do Pedido (R$)": order["Valor do Pedido (R$)"],
                }
                for order in orders_data
            ]

        # Update table
        self.table.setRowCount(len(orders_data))
        for row_idx, order in enumerate(orders_data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(order["ID do Pedido"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(order["Data de Criação"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(order["Status"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(order["Valor do Pedido (R$)"]))

        # Resize columns
        self.table.resizeColumnsToContents()

        # Update summary
        self.summary_label.setText(f"Total Orders: {len(orders_data)} | Subtotal: {format_currency(subtotal)}")
        if not orders_data:
            QMessageBox.information(self, "Informação", "Nenhum pedido encontrado para o intervalo e status selecionados.")

        print(f"\nSummary:")
        print(f"Total Orders Loaded: {len(orders_data)}")
        print(f"Subtotal: {format_currency(subtotal)}")
        status_counts = {}
        for order in self.orders:
            status = order.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        print("By Status (all orders returned):")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

def main():
    app = QApplication(sys.argv)
    window = OrdersDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
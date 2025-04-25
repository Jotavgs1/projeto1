import requests
import json
import os
import time
import pandas as pd
from dateutil import parser
from datetime import datetime
import pytz
from PySide6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt
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

def is_date_in_brazil_day(dt, target_date="2025-04-24"):
    """Check if the date is 24/04/2025 in Brasília time"""
    brazil_tz = pytz.timezone("America/Sao_Paulo")
    dt_brazil = dt.astimezone(brazil_tz)
    return dt_brazil.strftime("%Y-%m-%d") == target_date

def format_currency(value):
    """Format a value as Brazilian currency (e.g., R$ 3,00)"""
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        return locale.currency(value, grouping=True, symbol=True)
    except locale.Error:
        # Fallback if pt_BR.UTF-8 is not available
        return f"R$ {value:,.2f}".replace(".", ",")

def fetch_orders():
    """Fetch VTEX orders with status 'ready-for-handling' for 24/04/2025 (Brasília)"""
    config = load_config()
    if not config:
        return [], 0.0

    # API configuration
    url = f"https://{config['vtex_account']}.vtexcommercestable.com.br/api/oms/pvt/orders"
    headers = {
        "X-VTEX-API-AppKey": config["app_key"],
        "X-VTEX-API-AppToken": config["app_token"],
    }

    # Date filter for 24/04/2025 in Brasília (UTC-3)
    date_filter = "creationDate:[2025-04-24T03:00:00.000Z TO 2025-04-25T02:59:59.999Z]"
    
    params = {
        "per_page": 100,
        "page": 1,
        "f_creationDate": date_filter,
        "orderStatus": "ready-for-handling",
        "orderBy": "creationDate,asc"
    }

    orders = []
    total_expected = 0
    max_retries = 3

    try:
        while True:
            for attempt in range(max_retries):
                print(f"\nFetching page {params['page']} (Attempt {attempt + 1}/{max_retries})...")
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
                    print(f"Request error: {e}")
                    if attempt == max_retries - 1:
                        print("Max retries reached. Aborting...")
                        return [], 0.0
                    time.sleep(2 ** attempt)

            data = response.json()
            print(f"API response: {json.dumps(data, indent=2)}")

            # Verify response structure
            if "paging" not in data or "list" not in data:
                print("Error: API response missing 'paging' or 'list'")
                return [], 0.0

            total_expected = data["paging"].get("total", 0)
            print(f"Expected total (API): {total_expected}")
            page_orders = data["list"]
            print(f"\nOrders found on page {params['page']}:")
            for order in page_orders:
                status = order.get('status', 'unknown')
                print(f" - Order {order['orderId']}: Status {status}, Date {order['creationDate']}, Value {order.get('totalValue', 0)}")
                if status != "ready-for-handling":
                    print(f"   Warning: Order {order['orderId']} has unexpected status: {status}")
            orders.extend(page_orders)
            print(f"Page {params['page']}: {len(page_orders)} orders")

            # Stop if no more orders or page is empty
            if not page_orders or len(page_orders) < params["per_page"]:
                break

            params["page"] += 1

    except Exception as e:
        print(f"Unexpected error: {e}")
        return [], 0.0

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

    # Prepare data for display and calculate subtotal
    orders_data = []
    subtotal = 0.0
    if orders:
        print("\nPreparing order data for display...")
        for order in orders:
            try:
                # Validate status
                if order.get('status') != "ready-for-handling":
                    print(f"Order {order['orderId']} ignored: Status {order.get('status')} != ready-for-handling")
                    continue
                
                creation_date = parser.isoparse(order['creationDate'])
                # Check if date is 24/04/2025 in Brasília
                if not is_date_in_brazil_day(creation_date):
                    print(f"Order {order['orderId']} ignored: Date {creation_date} outside 24/04/2025 in Brasília")
                    continue
                order_value = order.get('totalValue', 0) / 100  # Convert from cents to reais
                subtotal += order_value
                orders_data.append({
                    "ID do Pedido": order['orderId'],
                    "Data de Criação": creation_date.astimezone(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S"),
                    "Status": order['status'],
                    "Valor do Pedido (R$)": format_currency(order_value),
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

    print(f"\nSummary:")
    print(f"Total Orders Loaded: {len(orders_data)}")
    print(f"Subtotal: {format_currency(subtotal)}")
    status_counts = {}
    for order in orders:
        status = order.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    print("By Status (all orders returned):")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")

    return orders_data, subtotal

class OrdersDashboard(QMainWindow):
    def __init__(self, orders_data, subtotal):
        super().__init__()
        self.setWindowTitle("VTEX Orders Dashboard - 24/04/2025")
        self.setGeometry(100, 100, 800, 600)

        # Main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("VTEX Orders with Status 'ready-for-handling' (24/04/2025)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # Orders table
        self.table = QTableWidget()
        self.table.setRowCount(len(orders_data))
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID do Pedido", "Data de Criação", "Status", "Valor do Pedido (R$)"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet("QTableWidget { font-size: 12px; }")

        # Populate table
        for row_idx, order in enumerate(orders_data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(order["ID do Pedido"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(order["Data de Criação"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(order["Status"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(order["Valor do Pedido (R$)"]))

        # Resize columns
        self.table.resizeColumnsToContents()

        layout.addWidget(self.table)

        # Summary
        summary_label = QLabel(f"Total Orders: {len(orders_data)} | Subtotal: {format_currency(subtotal)}")
        summary_label.setAlignment(Qt.AlignCenter)
        summary_label.setStyleSheet("font-size: 14px; margin: 10px;")
        layout.addWidget(summary_label)

def main():
    orders_data, subtotal = fetch_orders()
    
    app = QApplication(sys.argv)
    window = OrdersDashboard(orders_data, subtotal)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
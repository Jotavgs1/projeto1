import time
import requests
import pytz
from datetime import datetime
from PySide6.QtCore import QThread, Signal

from utils import load_config

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
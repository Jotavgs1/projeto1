import sys
import os
import json
import locale
import pytz
from datetime import datetime

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
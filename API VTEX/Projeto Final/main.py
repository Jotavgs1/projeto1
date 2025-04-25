import sys
import os
from PySide6.QtWidgets import QApplication

from utils import PrintFilter
from ui import OrdersDashboard

def main():
    sys.stdout = PrintFilter()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    app = QApplication(sys.argv)
    window = OrdersDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
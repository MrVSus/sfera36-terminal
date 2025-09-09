from PySide2.QtWidgets import QApplication, QMainWindow
from core.processor import CPU
from ui.pages.terminal_window import TerminalPage

import os, sys
from PySide2 import QtCore

plugin_path = os.path.join(os.path.dirname(QtCore.__file__), "plugins", "platforms")
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cpu = CPU()
        self.setWindowTitle("Сфера-36 — Терминал")
        self.resize(800, 600)

        self.terminal_page = TerminalPage(self.cpu)
        self.setCentralWidget(self.terminal_page)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


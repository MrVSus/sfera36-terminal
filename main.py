from PySide6.QtWidgets import QApplication, QMainWindow
from core.processor import CPU
from ui.pages.terminal_window import TerminalPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cpu = CPU()
        self.setWindowTitle("Сфера-36 — Терминал")
        self.resize(800, 600)

        self.terminal_page = TerminalPage(self.cpu)
        self.setCentralWidget(self.terminal_page)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


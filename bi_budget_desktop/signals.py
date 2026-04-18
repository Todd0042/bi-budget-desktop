from PySide6.QtCore import QObject, Signal

class AppSignals(QObject):
    data_changed = Signal()

signals = AppSignals()

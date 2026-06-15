"""Helper functions for PyQt5 gui"""
from PyQt5.QtWidgets import QMessageBox



def warning_message(parent = None, message: str = None) -> None:
    """
    Warning
    """
    QMessageBox.warning(parent, 'Warning', message, QMessageBox.Ok)
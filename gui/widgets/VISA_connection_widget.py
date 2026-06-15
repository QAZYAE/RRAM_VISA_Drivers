"""Connection widget for VISA instrument"""
import os

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget



class VISAConnect(QWidget):
    """Connection widget for the VISA Instrument for PyQt5. Implements the address string, 
        check and reset buttons.
    """
    def __init__(self, *args, **kwargs):
        """Connection widget for the VISA Instrument for PyQt5. Implements the address string, 
        check and reset buttons.
        """
        super().__init__(*args, **kwargs)
        self.ui = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ui', 'VISAConnect.ui'), self)
    
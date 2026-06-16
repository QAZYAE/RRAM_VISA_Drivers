"""Connection widget for VISA instrument"""
import os
from typing import Union, Callable

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget

from RRAM_VISA_Drivers.gui.gui_connection import check_VISA_connection, reset_instrument
from RRAM_VISA_Drivers.gui.service_pyqt5 import warning_message



class VISAConnect(QWidget):
    """Connection widget for the VISA Instrument for PyQt5. Implements the address string, 
        check and reset buttons.
    """
    def __init__(
        self,
        check_function: Union[Callable, None],
        reset_function: Union[Callable, None],
        parent = None,
        instrument_name: str = 'Instrument', 
        initial_address: str = '',
        visa_library_path: str = '', 
    ):
        """Connection widget for the VISA Instrument for PyQt5. Implements the address string, 
        check and reset buttons.

        Args:
            check_function (Callable | None): Function that checks instrument connection.
            reset_function (Callable | None): Function that resets the instrument.
            instrument_name (str, optional): Instrument label. Defaults to 'Instrument'.
            initial_address (str, optional): Initial VISA-address. Defaults to ''.
            visa_library_path (str, optional): Path to visa library. Defaults to ''.
        """
        # Init
        super().__init__(parent)
        self.ui = uic.loadUi(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ui', 'VISAConnect.ui'), self)
        # Attributes
        if check_function is None:
            self.check_function = lambda visa_addr, visa_lib_path: check_VISA_connection(visa_addr, 'Instrument', visa_lib_path)
        else:
            self.check_function = check_function
        if reset_function is None:
            self.reset_function = reset_instrument
        else:
            self.reset_function = reset_function
        self.visa_library_path = visa_library_path
        self.label_inst_name.setText(instrument_name)
        self.comboBox.setEditText(initial_address)
        self.label_response.setText('Connection has not been verified')
        self.block = False  # Block flag while the communication is happening
        # Connecting buttons
        self.btn_check.clicked.connect(self.check_connection)
        self.btn_reset.clicked.connect(self.reset_instrument)
    
    
    def check_connection(self) -> None:
        """
        Check connection with the instrument.
        """
        self.label_response.setText('Checking...')
        self.label_response.repaint()
        self.block = True
        try:
            flag, response = self.check_function(self.comboBox.currentText().strip(), 
                                                 self.visa_library_path)
            if flag == 1:  # Connected, but the IDN response is wrong
                self.label_response.setText('  ' + response + ' 🞩')
                warning_message(self, 'Wrong instrument!')
                self.block = False
            elif flag == 2:  # Connected, the instrument is right
                self.label_response.setText('  ' + response + ' ✓')
                self.block = False
            else:  # Connection error
                raise ConnectionError(response)
        except ConnectionError as e:
            self.label_response.setText('  ' + "Can't connect to the instrument.")
            warning_message(self, "Can't connect to the instrument." + f'\n{e}')
            self.block = False
        except Exception as e:
            self.label_response.setText('  ' + "Can't connect to the instrument.")
            warning_message(self, 'An error occurred:\n' + f'{type(e).__name__}: {e}')  
            self.block = False
        
        
    def reset_instrument(self) -> None:
        """
        Reset the instrument.
        """
        self.label_response.setText('Resetting...')
        self.label_response.repaint()
        self.block = True
        try:
            flag, response = self.reset_function(self.comboBox.currentText().strip(), 
                                                 self.visa_library_path)
            if flag:
                self.label_response.setText('  ' + 'The instrument was reset')
                self.block = False
            else:
                warning_message(self, "Could not reset the instrument!\n" + response)
                self.label_response.setText('Could not reset the instrument')
                self.block = False
        except Exception as e:
            warning_message(self, 'An error occurred:\n' + f'{type(e).__name__}: {e}')
            self.label_response.setText('Could not reset the instrument')
            self.block = False
            
            
    def blocked(self) -> bool:
        """Check whether the communication is happening.

        Returns:
            block (bool): If True, the communication with the instrument is happening.
        """
        return self.block
            
            
    def address(self) -> str:
        """Get current address of the instrument.

        Returns:
            address (str): Current address in the combobox.
        """
        return self.comboBox.currentText().strip()
    
    
    def update_resources(self, resources: list[str]) -> None:
        """Update VISA-resources in the combobox.

        Args:
            resources (list[str]): VISA-resources.
        """
        text = self.comboBox.currentText()
        self.comboBox.clear()
        self.comboBox.addItems(resources)
        self.comboBox.setEditText(text)

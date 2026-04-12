"""
General driver class
"""
import logging
from logging.handlers import RotatingFileHandler
import os
from configparser import ConfigParser
        
        
        
class GeneralDriver:
    """General driver class which implements logging functionality.
    """
    def __init__(self) -> None:
        """
        General driver class which implements logging functionality.
        """
        # RRAM_VISA_Drivers path
        self.drivers_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        # Settings
        self.settings = ConfigParser()
        self.update_settings()
        # Logging
        if eval(self.settings['logger']['clear_on_start']):
            if os.path.isfile(self.log_path):
                os.remove(self.log_path)
            if os.path.isfile(self.log_path + '.1'):
                os.remove(self.log_path + '.1')
        self.logger = logging.getLogger('Driver')
        self.set_logging_level(self.settings['logger']['level'])
        handler = RotatingFileHandler(
            self.log_path, 
            mode='w', 
            encoding='utf-8', 
            maxBytes=float(self.settings['logger']['max_bytes']), 
            backupCount=1
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)
        
    
    def update_settings(self) -> None:
        """Update driver settings from `driver_settings.ini` file."""
        # Reading settings
        self.settings.read(os.path.join(self.drivers_path, 'driver_settings.ini'))
        self.log_path = self.settings['logger']['path']
        if self.log_path == '':
            self.log_path = os.path.join(self.drivers_path, 'driver.log')
        if hasattr(self, 'logger'):
            self.set_logging_level(self.settings['logger']['level'])
        
        
    def set_logging_level(self, level: str) -> None:
        """Set driver's logger level.

        Args:
            level (str): Logging level: debug | info | warning | error | critical.
        """
        self.logger.setLevel(level.rstrip().upper())
        
        
    def stop_experiment(self) -> None:
        """
        General method, raises need_stop to True. Can be overwritten.
        """
        self.need_stop = True
        
        
    def terminal_command(self, command: str) -> str:
        """Execute `self.command` in the driver class and get the response as a str.
        For example, to write an SCPI command to the instrument that is labeled `A` in
        the driver, send `A.write('SCPI_command')` command.

        Args:
            command (str): command to the driver.

        Returns:
            str: Driver's response.
        """
        try:
            response = str(eval('self.' + command))
        except Exception as e:
            response = f'ERROR: {type(e).__name__}: {e}'
        return response
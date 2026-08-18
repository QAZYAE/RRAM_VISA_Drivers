"""
General driver class
"""
import logging
from logging.handlers import RotatingFileHandler
import os
from configparser import ConfigParser
import numpy as np
import shutil
from datetime import datetime
        
        
        
class GeneralDriver:
    """General driver class which implements logging functionality.
    
    Attributes:

        drivers_path (str): Path to the driver folder.
        settings (ConfigParser): Settings config parser.
        log_path (str): Path to log file.
        scpi_log_path (str): Path to scpi log file.
        logger (logging.Logger): Driver logger.
        scpi_logger (logging.Logger | None): SCPI logger for low-level commands.
        need_stop (bool): Flag for stopping the experiment.
        save_failed_logs (bool): If True, saves logs to the folder on driver fail.
        failed_logs_folder (str): Path to folder where failed logs are saved.
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
        self.logger = self.create_logger(
            path=self.log_path,
            clear_on_start=eval(self.settings['logger']['clear_on_start']),
            logging_level=self.settings['logger']['level'],
            logger_name='Driver'
        )
        if eval(self.settings['logger']['scpi_log']):
            self.scpi_logger = self.create_logger(
                path=self.scpi_log_path,
                clear_on_start=eval(self.settings['logger']['clear_on_start']),
                logging_level='DEBUG',
                logger_name='SCPI'
            )
        else:
            self.scpi_logger = None
        # Check if save log folder exists
        if eval(self.settings['logger']['save_failed_logs']):
            self.save_failed_logs = True
            self.create_failed_logs_folder()
        else:
            self.save_failed_logs = False
        
    
    def update_settings(self) -> None:
        """Update driver settings from `driver_settings.ini` file."""
        # Reading settings
        self.settings.read(os.path.join(self.drivers_path, 'driver_settings.ini'))
        self.log_path = self.settings['logger']['path']
        if self.log_path == '':
            self.log_path = os.path.join(self.drivers_path, 'driver.log')
        self.scpi_log_path = self.settings['logger']['scpi_log_path']
        if self.scpi_log_path == '':
            self.scpi_log_path = os.path.join(self.drivers_path, 'scpi.log')
        if hasattr(self, 'logger'):
            self.set_logging_level(self.settings['logger']['level'])
            
            
    def create_logger(self, path: str, clear_on_start: bool, logging_level: str, logger_name: str) -> logging.Logger:
        """Create a logger

        Args:
            path (str): Path to the log file.
            clear_on_start (bool): If True, the log file clears on initiating the driver.
            logging_level (str): Initial logginh level.

        Returns:
            logger (logging.Logger): Logger instance.
        """
        if clear_on_start:
            if os.path.isfile(path):
                os.remove(path)
            if os.path.isfile(path + '.1'):
                os.remove(path + '.1')
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging_level.strip().upper())
        handler = RotatingFileHandler(
            path, 
            mode='w', 
            encoding='utf-8', 
            maxBytes=float(self.settings['logger']['max_bytes']), 
            backupCount=1
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        return logger
        
        
    def set_logging_level(self, level: str) -> None:
        """Set driver's logger level.

        Args:
            level (str): Logging level: debug | info | warning | error | critical.
        """
        self.logger.setLevel(level.strip().upper())
        
    
    def create_failed_logs_folder(self):
        """Check if failed logs folder exists or create it"""
        folder = str(self.settings['logger']['failed_logs_folder']).strip()
        if folder == '':
            self.failed_logs_folder = os.path.join(self.drivers_path, 'failed_logs')
        else:
            self.failed_logs_folder = folder
        if not os.path.isdir(self.failed_logs_folder):
            try:
                os.makedirs(self.failed_logs_folder)
            except Exception as e:
                print(f'Could not create a Failed logs folder!\n{type(e).__name__}: {e}')
                self.save_failed_logs = False
        
        
    def save_logs(self) -> None:
        """Save a copy of logs to the log folder"""
        if not self.save_failed_logs:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        try:
            shutil.copy2(src=self.log_path,
                        dst=os.path.join(self.failed_logs_folder, f'{timestamp}.driver.log'))
            if self.scpi_logger is not None:
                shutil.copy2(src=self.scpi_log_path,
                             dst=os.path.join(self.failed_logs_folder, f'{timestamp}.scpi.log'))
        except Exception as e:
            print(f'Could not copy the log files!\n{type(e).__name__}: {e}')
        
        
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
    
    
    def random_values(self, array_number: int = 1, length: int = 1, limits: tuple[int, int] = (100, 100000)) -> tuple[np.ndarray]:
        """Generate a sample of random values.

        Args:
            array_number (int, optional): Number of random arrays. Defaults to 1.
            length (int, optional): Length of random arrays. Defaults to 1.
            limits (tuple[int, int], optional): Limits of random generation. Defaults to (100, 100000)

        Returns:
            tuple[np.ndarray]: Random resistance sample.
        """
        result = []
        for _ in range(array_number):
            rnd = np.random.randint(*limits, length)
            if length == 1:
                result.append(rnd[0])
            else:
                result.append(rnd)
        if array_number == 1:
            return result[0]
        return tuple(result)
        
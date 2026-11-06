"""
Драйвер для измерения кроссбаров 1T1R 32x8 на установке в ЦИРе. Использует два 
модуля B2902B, коммутатор 34980A и плату, коммуницирующую по COM-порту. 
Первые пины на коннекторах D-Sub 25 устройств B2902B должны быть соединены проводом.
"""
from RRAM_VISA_Drivers.drivers.ITC_1T1R_32x8_switched import ITC_1T1R_32x8_switched
from RRAM_VISA_Drivers.core import COM
from typing import Union
import time
import numpy as np



class ITC_1T1R_32x8_switched_COM(ITC_1T1R_32x8_switched):
    """Driver for measuring 1T1R 32x8 crossbar arrays with a switch unit."""
    sim: str = False  # True for simulation mode
    com_sense: bool = False  # If True, sense takes data from COM port
    
    def __init__(
        self, 
        B2902B_1_address: str, 
        B2902B_2_address: str, 
        Switch_address: str,
        COM_port: str,
        VISA_library_path: str = ''
    ) -> None:
        """Driver for measuring 1T1R 32x8 crossbar arrays with a switch unit.

        Args:
            B2902B_1_address (str): VISA-address for Keysight B2902B which controls
                Bit Line (1st channel) and Net Line (2nd channel).
            B2902B_2_address (str): VISA-address for Keysight B2902B which controls
                Word Line (1st channel).
            Switch_address (str): VISA-address for Keysight 34980A which controls
                cell selection.
            VISA_library_path (str, optional): Path to VISA library. If not provided, 
                pyvisa tries to find the library on the computer. Defaults to ''.
        """
        for address in [B2902B_1_address, B2902B_2_address, Switch_address, COM_port]:
            if address is None or address == '':
                self.sim = True
        super().__init__(B2902B_1_address, B2902B_2_address, Switch_address, VISA_library_path)
        # Init COM port
        if self.sim:
            port = None
        else:
            port = COM_port
        self.COM = COM(
            port = port,
            baudrate = int(self.settings['COM']['baudrate']),
            timeout = float(self.settings['COM']['timeout'])
        )
        print('COM driver init success')
        self.logger.info('COM drier init success')
        
        
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'ITC_1T1R_32x8_driver: uses two Keysight B2902B Source-Measure ' + \
                'modules and a Keysight_34980A Switch unit + COM measurement board for measuring 32x8 1T1R ' + \
                'memristive crossbar arrays'
                
    
    def disconnect(self) -> tuple[bool, str]:
        """Disconnect instruments on closing the app.

        Returns:
            flag, response (tuple[bool, str]): Disconnected flag (True if instruments were 
            successfully disconnected), response or error.
        """
        f1, r1 = super().disconnect()
        f2, r2 = self.COM.close()
        return f1 and f2, r1 + r2
    
    
    def config_COM_command(self, command: str, response_type: str) -> tuple[bool, str]:
        """Configure COM mode and send command to the measurement board.

        Args:
            command (str): Command to measurement board.
            response_type (str): Type of response: 

        Returns:
            tuple[bool, str]: _description_
        """
        flag, resp = self.COM.write(command)
        self.com_sense = True
        self.com_resp_type = response_type
        self.trigger_interval = float(self.settings['COM']['read_interval'])
        if not flag:
            self.logger.error(f'Error while writing COM command!\nCommand: {command}\nError: {resp}')
            return False, f'Error while writing COM command!\nCommand: {command}\nError: {resp}'
        if response_type == 'Resistance':
            return True, f'Command sent to COM: {command}'
        elif self.com_resp_type == 'Boolean flag':
            self.logger.debug(f'Command sent to COM: {command}')
            data = self.sense()
            if int(data):
                return True, f'Flag recieved from COM: {data}'
            else:
                return False, f'Got False flag from COM! Stopping the experiment'
        
    
    
    def sense(self, acquire_attempts: int = 200, vol: Union[float, None] = None) -> Union[tuple[float, float], str]:
        """Read sense data from the instruments. Updates the result queue and returns a 
            result from the queue.
        
        Args:
            acquire_attempts (int, optional): Number of attempts to communicate with the instrument
                and acquire sense data. Defaults to 1000.
            trigger (bool, optional): If True, sends trigger command before acquire.

        Returns:
            resistance (float): First resistance in the queue.
        """
        if self.com_sense:
            for i in range(int(self.settings['COM']['read_attempts'])):
                flag, data = self.COM.read()
                self.logger.debug(f'Sense COM attempt {i}: DATA: {data.decode()}')
                if flag:
                    break
                time.sleep(self.trigger_interval)
            if not flag:
                self.logger.error(f'.sense(): COM error: {data.decode()}')
                return f'.sense(): COM error: {data.decode()}'
            self.logger.debug(f'COM: data acquired in {i} attempts')       
            self.com_sense = False
            if self.com_resp_type == 'Resistance':
                try:
                    res = float(data.decode())
                    return [res, time.time(), np.nan, np.nan, np.nan, np.nan]
                except Exception as e:
                    self.logger.error(f'Could not convert COM response to float: {data.decode()}: {type(e).__name__}: {e}')
                    print(f'Could not convert COM response to float: {data.decode()}: {type(e).__name__}: {e}')
            elif self.com_resp_type == 'Boolean flag':
                return data.decode()
            else:
                raise RuntimeError('Unknown response type in COM sense')
        else:
            return super().sense(acquire_attempts, vol)
        
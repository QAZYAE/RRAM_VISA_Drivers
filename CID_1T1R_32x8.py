"""
Драйвер для измерения кроссбаров 1T1R 32x8 на установке в ЦИРе. Использует два 
модуля B2902B и коммутатор 34980A. Первые пины на коннекторах D-Sub 25 устройств
B2902B должны быть соединены проводом.
"""

import pyvisa 
import numpy as np
from SMU_drivers.Keysight_B2902B import B2902B
from Switch_drivers.Keysight_34980A_1T1R_32x8 import Keysight_34980A_1T1R_32x8



class CID_1T1R_32x8_driver:
    """Driver for measuring 1T1R 32x8 crossbar arrays.
    """
    def __init__(
        self, 
        B2902B_1_address: str, 
        B2902B_2_address: str, 
        Switch_address: str,
        VISA_library_path: str = ''
    ) -> None:
        """Driver for measuring 1T1R 32x8 crossbar arrays.

        Args:
            B2902B_1_address (str): VISA-adress for Keysight B2902B which controls
                Bit Line (1st channel) and Net Line (2nd channel).
            B2902B_2_address (str): VISA-adress for Keysight B2902B which controls
                Word Line (1st channel).
            Switch_address (str): VISA-adress for Keysight 34980A which controls
                cell selection.
            VISA_library_path (str, optional): Path to VISA library. If not provided, 
                pyvisa tries to find the library on the computer. Defaults to ''.
        """
        # Creating ResourceManager
        if VISA_library_path == '':
            self.rm = pyvisa.ResourceManager()
        else:
            self.rm = pyvisa.ResourceManager(VISA_library_path)
        # Opening resources
        A_res = self.rm.open_resource(B2902B_1_address)
        B_res = self.rm.open_resource(B2902B_2_address)
        Switch_res = self.rm.open_resource(Switch_address)
        # Creating driver instances for the instruments
        self.A = B2902B(resource=A_res, instrument_name='B2902B_A')  # Controls BL and NL
        self.B = B2902B(resource=B_res, instrument_name='B2902B_B')  # Controls WL
        self.switch = Keysight_34980A_1T1R_32x8(  # Controls cell selection in crossbar array
            resource=Switch_res, 
            config_path='config/Keysight_34980A_1T1R_32x8.json'
        )
        # Checking connections and instrument types
        for inst, name in zip([self.A, self.B, self.switch], 
                              ['B2902B_A', 'B2902B_B', 'Switch unit']):
            flag = inst.check_instument_connection()
            inst.get_errors()  # Clear error queue
            if not flag:
                raise ConnectionError(f'Could not connect to an instrument: {name}')
        resps = []  # Response list
        # Resetting instruments 
        for inst in [self.A, self.B]:
            resps.append(inst.clear())
            resps.append(inst.memory_reset())
            resps.append(inst.set_standby_zero())
            resps.append(inst.set_output_state('on'))
        # Configuring data output
        resps.append(self.A.set_data_format('voltage,current'))
        resps.append(self.B.set_data_format('voltage,current'))
        # Configuring triggers: Arm trigger is linked via pin 1 on D-Sub 25 connector
        resps.append(self.A.SMU1.set_arm_BUS())
        resps.append(self.A.SMU2.set_arm_BUS())
        resps.append(self.B.SMU1.set_arm_external(pin=1))  # todo: Вынести номер пина в файл конфигурации
        resps.append(self.A.set_external_trigger_link(pin=1, trigger_layer='arm', function='output', channel=1))
        resps.append(self.B.set_external_trigger_link(pin=1, trigger_layer='arm', function='input', channel=1))
        for r in resps:
            if r.startswith('ERROR'):
                raise ConnectionError(r)
        # Checking error queues
        for inst, name in zip([self.A, self.B, self.switch], 
                              ['B2902B_A', 'B2902B_B', 'Switch unit']):
            err = inst.get_errors()
            if err is not None:
                raise ConnectionError(f'Error in {name} error queue: {err}')
        
        
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'CID_1T1R_32x8_driver: uses with two Keysight B2902B Source-Measure ' + \
               'modules and a Keysight_34980A Switch unit for measuring 32x8 1T1R ' + \
               'memristor crossbar arrays'
        
        
    def clear_instruments(self) -> bool:
        """Clear SMU instruments on ticket end or when terminated.

        Returns:
            cleared (bool): True if instruments were cleared.
        """
        r1 = self.A.clear()
        r2 = self.B.clear()
        if r1.startswith('ERROR') or r2.startswith('ERROR'):
            return False
        return True
            
        
    def connect_cell(self, wl: int, bl: int) -> str:
        """Connect cell via switch unit. wl and bl are 0 through 7 and 0 through 31.

        Args:
            wl (int): Word Line (0 through 7).
            bl (int): Bit Line (0 through 31).

        Returns:
            response (str): Error if an error occured.
        """
        return self.switch.connect_cell(row=wl+1, col=bl+1)
        
        
    def disconnect(self) -> tuple[bool, str]:
        """Disconnect instruments on closing the app.

        Returns:
            flag, response (tuple[bool, str]): Disconnected flag (True if instruments were 
            successfully disconnected), response or error.
        """
        resps = []  # Response list
        resps.append(self.switch.disconnect_all())
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.A.set_output_state('off'))
        resps.append(self.B.set_output_state('off'))
        self.rm.close()
        for r in resps:
            if r.startswith('ERROR'):
                return False, r
        return True, 'VISA-instruments were disconnected'
            
        
        
    def sense(self) -> np.ndarray:
        """_summary_

        Returns:
            np.ndarray: _description_
        """
        
        
    def config(self, task: dict) -> str:
        """_summary_

        Args:
            task (dict): _description_

        Returns:
            str: _description_
        """
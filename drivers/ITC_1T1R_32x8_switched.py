"""
Драйвер для измерения кроссбаров 1T1R 32x8 на установке в ЦИРе. Использует два 
модуля B2902B и коммутатор 34980A. Первые пины на коннекторах D-Sub 25 устройств
B2902B должны быть соединены проводом.
"""

import pyvisa 
import os
from RRAM_VISA_Drivers.SMU_drivers import B2902B_1T1R_32x8_driver
from RRAM_VISA_Drivers.Switch_drivers import Keysight_34980A_1T1R_32x8
 


class ITC_1T1R_32x8_switched(B2902B_1T1R_32x8_driver):
    """Driver for measuring 1T1R 32x8 crossbar arrays with a switch unit.
    """
    sim: str = False  # True for simulation mode
    
    def __init__(
        self, 
        B2902B_1_address: str, 
        B2902B_2_address: str, 
        Switch_address: str,
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
        # Check if in simulation mode
        self.sim = False
        for address in [B2902B_1_address, B2902B_2_address, Switch_address]:
            if address is None or address == '':
                self.sim = True
        if self.sim:
            A_res, B_res, Switch_res = None, None, None
        else:
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
        super().__init__(A_res, B_res, self.sim)
        self.switch = Keysight_34980A_1T1R_32x8(  # Controls cell selection in crossbar array
            resource=Switch_res, 
            config_path=os.path.join(self.drivers_path, 'Switch_drivers', 'config', 'Keysight_34980A_1T1R_32x8.json')
        )
        print('ITC_1T1R_32x8_switched init success')
        self.logger.info('ITC_1T1R_32x8_switched init success')
        
        
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'CID_1T1R_32x8_driver: uses two Keysight B2902B Source-Measure ' + \
               'modules and a Keysight_34980A Switch unit for measuring 32x8 1T1R ' + \
               'memristive crossbar arrays'
               
               
    # .clear_instruments() in parent class
            
        
    def connect_cell(self, wl: int, bl: int) -> tuple[bool, str]:
        """Connect cell via switch unit. wl and bl are 0 through 7 and 0 through 31.

        Args:
            wl (int): Word Line (0 through 7).
            bl (int): Bit Line (0 through 31).

        Returns:
            flag, response (tuple[bool, str]): Connected flag (True if the cell was
            successfully disconnected), response or error.
        """
        self.logger.info(f'Connecting cell {wl}-{bl}')
        resp = self.switch.connect_cell(row=wl+1, column=bl+1)
        if resp.startswith('ERROR'):
            self.logger.error(f'Error connecting cell {wl}-{bl}: {resp}')
            return False, resp
        return True, resp
    
    
    def connect_multiple_cells(self, wl: list[int], bl: list[int]) -> tuple[bool, str]:
        """Connect multiple cells via switch unit. wl and bl are 0 through 7 and 0 through 31.

        Args:
            wl (list[int]): Word Lines to connect (0 through 7).
            bl (list[int]): Bit Lines to connect (0 through 31).

        Returns:
            flag, response (tuple[bool, str]): Connected flag (True if the cell was
            successfully disconnected), response or error.
        """
        self.logger.info(f'Connecting multiple cells: rows: {wl}, columns: {bl}')
        resp = self.switch.connect_multiple_cells(rows=[row+1 for row in wl], columns=[col+1 for col in bl])
        if resp.startswith('ERROR'):
            self.logger.error(f'Error connecting multiple cells: rows {wl}, columns: {bl}:\n{resp}')
            return False, resp
        return True, resp
        
        
    def disconnect(self) -> tuple[bool, str]:
        """Disconnect instruments on closing the app.

        Returns:
            flag, response (tuple[bool, str]): Disconnected flag (True if instruments were 
            successfully disconnected), response or error.
        """
        resps = []  # Response list
        resps.append(self.switch.disconnect_all())
        _flag, r = super().disconnect()
        resps.append(r)
        # Closing resource manager
        if not self.sim:
            try:
                self.rm.close()
            except Exception as e:
                resps.append('ERROR: ' + str(e))
        # Checking errors
        for r in resps:
            if r.startswith('ERROR'):
                self.logger.critical(f'Could not disconnect the instruments!\n\t{r}')
                return False, r
        self.logger.info('VISA-instruments were disconnected')
        return True, 'VISA-instruments were disconnected'
    
    
    def standby(self) -> tuple[bool, str]:
        """Turns on Standby mode and clears all instruments.

        Returns:
            flag, response (tuple[bool, str]): Standby flag (True if standby mode
            was turned on successfully), response or error.
        """
        flag1, r1 = super().standby()
        r2 = self.switch.standby()
        if r2.startswith('ERROR'):
            flag2 = False
        else:
            flag2 = True
        flag = flag1 and flag2
        if flag:
            self.logger.info('Instruments are in standby mode')
            return True, 'Instruments are in standby mode'
        self.logger.error(f'Standby error: {r1}\n{r2}')
        return False, f'{r1}\n{r2}'
    
    
    def _panic_attempt(self) -> tuple[bool, str]:
        """Panic once to immediately stop the experiment.

        Returns:
            flag, response (tuple[bool, str]): Resolved flag (True if panic was resolved), 
            response or error.
        """
        flag, resp = self.standby()
        resps = [resp]  # Response list
        if not flag:
            resps.append(self.A.clear())
            resps.append(self.B.clear())
            resps.append(self.A.set_output_state('off'))
            resps.append(self.B.set_output_state('off'))
        for smu in [self.A.SMU1, self.A.SMU2, self.B.SMU1]:
            resps.append(smu.set_base_voltage_immediate(0, current_compliance=1e-8))
        self.logger.debug('\t' + '\t\n'.join(resps))
        for r in resps:
            if r.startswith('ERROR'):
                flag = False
                self.logger.info('Panic attempt failed!')
        if not flag:
            resps.append(self.switch.standby())
        return flag, '\n'.join(resps)
        
        
    def panic(self) -> tuple[bool, str]:
        """Panic mode for immediately stopping the experiment.

        Returns:
            flag, response (tuple[bool, str]): Resolved flag (True if panic was resolved), 
            response or error.
        """
        resps = []
        for i in range(5):
            self.logger.debug(f'Panic attempt {i}')
            flag, response = self._panic_attempt()
            resps.append(response)
            if flag:
                break
        if flag:
            resps.append(self.A.set_output_state('on'))
            resps.append(self.B.set_output_state('on'))
            self.logger.critical('Panic resolved!')
        else:
            self.logger.error('Panic was not resolved!\n\t' + '\n\t'.join(resps))
        return flag, '\n'.join(resps)
    
    
    # ._random_sense() in parent class
            
        
    # .sense() in parent class
        
        
    # .config_iv_dc() in parent class

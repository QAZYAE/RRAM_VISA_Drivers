"""
Driver for Keysight 34980A with 1T1R 32x8 measurement scheme
"""
import pyvisa
import json
from typing import Union
from RRAM_VISA_Drivers.Switch_drivers.Keysight_34980A_modules import Keysight_34922A_70ch_MUX, Keysight_34932A_2x4x16_Matrix
from RRAM_VISA_Drivers.core import VISA_instrument



class Keysight_34980A_1T1R_32x8(VISA_instrument):
    """Handles communicating with Keysight 34980A Multifunction Switch/Measure unit for commutating 
    1T1R 8x32 crossbar arrays.
    WL and NL channels are connected via matrix module, using Hi and Lo lines. GND_row is used to connect 
    all unselected WL to GND, SMU_row is used for measurement. BL is connected via one half of the 70ch MUX.

    Attributes:
        resource (pyvisa.Resource): Keysight 34980A Multifunction Switch/Measure Unit resource.
        sim (bool): True if program is in simulation mode.
        one_SMU (bool): True if in one-SMU mode where BL and NL are connected to Hi/Lo via switch unit.
        WLNL (dict): Dictionary of WL-NL channels.
        BL (dict): Dictionary of BL channels.
        GND_row (int): Matrix row where GND is connected for grounding unselected WL.
        SMU_row (int): Matrix row where SMUs are connected for WL and NL measurements.
        switch_hi_row (int): Row where SMU Hi is connected (one-SMU mode).
        switch_lo_row (int): Row where SMU Lo is connected (one-SMU mode).
        switch_BL_col (int): Column where BL is connected (one-SMU mode).
        switch_NL_col (int): Column where NL is connected (one-SMU mode).
        MUX (Keysight_34922A_70ch_MUX): object for handling MUX commands (BL). 
        MAT (Keysight_34932A_2x4x16_Matrix): object for handling Matrix commands (WL and NL).
    """
    def __init__(self, resource: Union[pyvisa.Resource, None], config_path: str, one_SMU: bool = False) -> None:
        """Handles communicating with Keysight 34980A Multifunction Switch/Measure unit for commutating 
        1T1R 8x32 crossbar arrays.

        Args:
            resource (pyvisa.Resource | None): Keysight 34980A resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            config_path (str): Path to the configuration file.
            one_SMU (bool, optional): True for one-SMU mode where BL and NL are connected to Hi/Lo
                via switch unit. Defaults to False.
        """
        IDN_response = 'Agilent Technologies,34980A,'
        super().__init__(resource, IDN_response)
        self.one_SMU: bool = one_SMU
        with open(config_path, 'r', encoding='utf-8') as file:
            scheme_data = json.load(file)
        self.WLNL: dict = scheme_data['WLNL_channels']
        self.BL: dict = scheme_data['BL_channels']
        self.GND_row: int = scheme_data['GND_row']
        self.SMU_row: int = scheme_data['SMU_row']
        self.switch_hi_row: int = scheme_data['Switch_HI_row']
        self.switch_lo_row: int = scheme_data['Switch_LO_row']
        self.switch_BL_col: int = scheme_data['Switch_BL_column']
        self.switch_NL_col: int = scheme_data['Switch_NL_column']
        self.MUX = Keysight_34922A_70ch_MUX(resource, scheme_data['BL_slot'])
        self.MAT = Keysight_34932A_2x4x16_Matrix(resource, scheme_data['WLNL_slot'])
        # Checking connection
        flag = self.check_instrument_connection()
        self.get_errors()  # Clearing error queue
        if not flag: 
            print('Switch unit init ERROR')
            raise ConnectionError('Could not connect to the Switch unit!')
        # Turning standby mode on
        resp = self.standby()
        if resp.startswith('ERROR'):
            print('Switch unit init ERROR')
            raise ConnectionError(resp)
        # Checking error queue
        err = self.get_errors()
        if err is not None:
            print('Switch unit init ERROR')
            raise ConnectionError(f'Error in the Switch unit error queue: {err}')
        print('Switch unit init success')
    
    
    def disconnect_all(self) -> str:
        """Disconnects all MUX channels and Matrix intersections in corresponding modules.

        Returns:
            response (str): Error if an error occurred.
        """
        if self.sim:
            return 'Simulation: All MUX channels and matrix intersections were disconnected'
        resp_mux = self.MUX.disconnect_all()
        resp_mat = self.MAT.disconnect_all()
        for resp in [resp_mat, resp_mux]:
            if resp.startswith('ERROR'):
                return resp
        return 'All MUX channels and matrix intersections were disconnected.'
    
    
    def standby(self) -> str:
        """Turns on Standby mode:
            All MUX channels are disconnected.
            All WL/NL matrix column are connected to the GND row (All WL are grounded).

        Returns:
            response (str): Error if an error occurred.
        """
        self.mode = 'standby'
        if self.sim:
            return 'Simulation: Switch unit in Standby mode.'
        resps = []
        resps.append(self.MUX.disconnect_all())
        resps.append(self.MAT.disconnect_all_except((self.GND_row, self.SMU_row)))
        resps.append(self.MAT.configure_row_and_check(self.GND_row,
                        [True if v in self.WLNL.values() else False for v in range(1, 17)]))
        resps.append(self.MAT.configure_row_and_check(self.SMU_row, [False for _ in range(16)]))
        if self.one_SMU:
            resps.append(self.MAT.configure_row_and_check(self.switch_hi_row, [False for _ in range(16)]))
            resps.append(self.MAT.configure_row_and_check(self.switch_lo_row, [False for _ in range(16)]))
        for resp in resps:
            if resp.startswith('ERROR') or resp.startswith('Exception'):
                return resp
        return 'Switch unit in Standby mode.'
    
    
    def connect_cell(self, row: int, column: int, switch_type: str = 'SET') -> str:
        """Connect crossbar cell in WL row and BL column.
        WARNING: Channel addresses are 1 through 8 for row and 1 through 32 for column.

        Args:
            row (int): Row number (Word Line and Net Line): 1 through 8.
            column (int): Column number (Bit Line): 1 through 32.
            switch_type (str, optional): Switch type ('SET' or 'RESET'). 
                Used in one-SMU mode only. Defaults to 'SET'.

        Returns:
            response (str): Error if an error occurred.
        """
        self.mode = 'connected'
        if self.sim:
            return f'Simulation: Cell {row}-{column} was connected.'
        if f'WLNL{row}' not in self.WLNL.keys():
            raise RuntimeError('Wrong WL number')
        if f'BL{column}' not in self.BL.keys():
            raise RuntimeError('Wrong BL number')
        resps = []
        gnd_list = [True if v in self.WLNL.values() else False for v in range(1, 17)]
        smu_list = [False for _ in range(16)]
        gnd_list[self.WLNL[f'WLNL{row}'] - 1] = False
        smu_list[self.WLNL[f'WLNL{row}'] - 1] = True
        resps.append(self.MAT.configure_row_and_check(self.GND_row, gnd_list))
        resps.append(self.MAT.configure_row_and_check(self.SMU_row, smu_list))
        if self.one_SMU:
            switch_hi_list = [False for _ in range(16)]
            switch_lo_list = [False for _ in range(16)]
            if switch_type == 'SET':
                switch_hi_list[self.switch_NL_col - 1] = True
                switch_lo_list[self.switch_BL_col - 1] = True
            else:
                switch_hi_list[self.switch_BL_col - 1] = True
                switch_lo_list[self.switch_NL_col - 1] = True
            resps.append(self.MAT.configure_row_and_check(self.switch_hi_row, switch_hi_list))
            resps.append(self.MAT.configure_row_and_check(self.switch_lo_row, switch_lo_list))
        resps.append(self.MUX.connect_exclusive(self.BL[f'BL{column}']))
        for resp in resps:
            if resp.startswith('ERROR') or resp.startswith('Exception'):
                self.disconnect_all()
                return resp + ' | All MUX channels and Matrix intersections were disconnected.'
        return f'Cell {row}-{column} was connected.'
    
    
    def change_switch_type(self, switch_type: str) -> str:
        """Change switch type. Method is used only in one-SMU mode.

        Args:
            switch_type (str): New switch type ('SET' or 'RESET').

        Returns:
            response (str): Error if an error occurred.
        """
        if not self.one_SMU:
            return
        if self.mode == 'standby':
            return 
        resps = []
        switch_hi_list = [False for _ in range(16)]
        switch_lo_list = [False for _ in range(16)]
        if switch_type == 'SET':
            switch_hi_list[self.switch_NL_col - 1] = True
            switch_lo_list[self.switch_BL_col - 1] = True
        else:
            switch_hi_list[self.switch_BL_col - 1] = True
            switch_lo_list[self.switch_NL_col - 1] = True
        resps.append(self.MAT.configure_row_and_check(self.switch_hi_row, switch_hi_list))
        resps.append(self.MAT.configure_row_and_check(self.switch_lo_row, switch_lo_list))
        for resp in resps:
            if resp.startswith('ERROR') or resp.startswith('Exception'):
                self.disconnect_all()
                return resp + ' | All MUX channels and Matrix intersections were disconnected.'
        return f'The switch type was changed to {switch_type}'
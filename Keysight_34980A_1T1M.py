import pyvisa
from typing import Union



def twodig(number: int) -> str:
    """Makes a two digit number by adding 0 if number is one digit, also converts it to str.

    Args:
        number (int): number to convert.

    Returns:
        str: converted string.
    """
    if number < 1 or number > 99:
        raise RuntimeError(f'twodig function: wrong number "{number}": it must have 1 or 2 digits.')
    if 1 <= number <= 9:
        return f'0{number}'
    return str(number)


def _write(self, commands: Union[list, str], stop_exception: bool = False) -> list:
    """CLASS METHOD:
    Send sequence of SCPI commands to the instrument. Prints exception if an exception occurs.

    Args:
        commands (Union[list, str]): List of SCPI commands (strings).
        stop_exception (bool, optional): If True, stops sending commands when an exception occurs. 
            Defaults to False.
        
    Returns:
        list: List of execuded commands or Visa Errors.
    """
    if type(commands) is not list:
        commands = [commands]
    executed = []
    for command in commands:
        try:
            self.resource.write(command)
            executed.append(command)
        except pyvisa.VisaIOError as error:
            executed.append(f'VISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {error}')
        if stop_exception:
            return executed
    return executed


def _query(self, command: str) -> str:
    """CLASS METHOD:
    Send SCPI command and read response. Prints exception if an exception occurs.

    Args:
        command (str): SCPI command.

    Returns:
        str: Instrument response. Returns Visa Error if an exception occured.
    """
    try:
        response = self.resource.query(command)
        return response
    except pyvisa.VisaIOError as error:
        return f'VISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {error}'







class Keysight_34980A_1T1M_backend:
    """Handles communicating with Keysight 34980A Multifunction Switch/Measure unit for commutating 
    1T1M 8x32 crossbar arrays.
    WL and NL channels are connected via matrix module, using Hi and Lo lines. GND_row is used to connect 
    all unselected WL to GND, SMU_row is used for measurement. BL is connected via one half of the 70ch MUX.

    Attributes:
        resource (pyvisa.resource): Keysight 34980A Multifunction Switch/Measure Unit resource.
        sim (bool): True if program is in simulation mode.
        WLNL (dict): Dictionary of WL-NL channels.
        BL (dict): Dictionary of BL channels.
        GND_row (int): Matrix row where GND is connected for grounding unselected WL.
        SMU_row (int): Matrix row where SMUs are connected for WL and NL measurements.
        MUX (Keysight_34922A_70ch_MUX): object for handling MUX commands (BL). 
        MAT (Keysight_34932A_2x4x16_Matrix): object for handling Matrix commands (WL and NL).
    """
    def __init__(self, resource: Union[pyvisa.Resource, None], scheme_data: dict):
        """Handles communicating with Keysight 34980A Multifunction Switch/Measure unit for commutating 
        1T1M 8x32 crossbar arrays.

        Args:
            resource (Union[pyvisa.Resource, None]): Keysight 34980A resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            scheme_data (dict): "keysight_34980A_scheme" dictionary from options.json
        """
        self.resource = resource
        if resource is None:
            self.sim = True
        else:
            self.sim = False
        self.WLNL = scheme_data['WLNL_channels']
        self.BL = scheme_data['BL_channels']
        self.GND_row = scheme_data['GND_row']
        self.SMU_row = scheme_data['SMU_row']
        self.switch_hi_row = scheme_data['Switch_HI_row']
        self.switch_lo_row = scheme_data['Switch_LO_row']
        self.switch_BL_col = scheme_data['Switch_BL_column']
        self.switch_NL_col = scheme_data['Switch_NL_column']
        self.MUX = Keysight_34922A_70ch_MUX(resource, scheme_data['BL_slot'])
        self.MAT = Keysight_34932A_2x4x16_Matrix(resource, scheme_data['WLNL_slot'])
        self.standby()
        
        
    def write(self, commands: Union[list, str], stop_exception: bool = False) -> list:
        """Send sequence of SCPI commands to the instrument. Prints exception if an exception occurs.

        Args:
            commands (Union[list, str]): List of SCPI commands (strings).
            stop_exception (bool, optional): If True, stops sending commands when an exception occurs. 
                Defaults to False.
            
        Returns:
            list: List of execuded commands or Visa Errors.
        """
        return _write(self, commands, stop_exception)
    
    
    def query(self, command: str) -> str:
        """Send SCPI command and read response. Prints exception if an exception occurs.

        Args:
            command (str): SCPI command.

        Returns:
            str: Instrument response. Returns Visa Error if an exception occured.
        """
        return _query(self, command)
        
        
    def IDN(self) -> str:
        """Send SCPI command to identify the instrument and read the responce.
        
        Returns:
            str: Instrument response.
        """
        if self.sim:
            return 'Simulation mode'
        return self.query('*IDN?')
    
    
    def check_instument_connection(self) -> bool:
        """Check if Keysight 34980A Multifunction Switch/Measure Unit is connected.

        Returns:
            bool: True if the instrument is connected.
        """
        if self.sim:
            return True
        response = self.IDN()
        return response[:28] == 'Agilent Technologies,34980A,'
    
    
    def get_errors(self) -> Union[list, None]:
        """Get errors from instrument's error queue.

        Returns:
            Union[list, None]: List of erros. Returns None if there are no errors.
        """
        if self.sim:
            return None
        errors = []
        flag = True
        while flag:
            resp = self.query('system:error?')
            if resp[:2] == '+0':
                flag = False
            elif resp[:10] == 'VISA ERROR':
                flag = False
                errors.append(resp)
            else:
                errors.append(resp)
        if len(errors) == 0:
            return None
        return errors   
    
    
    def factory_reset(self) -> str:
        """Perfom a factory reset, which disconnects all connected channels (opens all switches).
        
        Returns:
            str: Error if an error occured.
        """
        if self.sim:
            return 'Simulation: Instrument was reset.'
        write_response = self.write('*RST')[0]
        if write_response[:10] == 'VISA ERROR':
            return f'ERROR: {write_response}'
        return 'Instrument was reset.'
    
    
    def disconnect_all(self) -> str:
        """Disconnects all MUX channels and Matrix intersections in corresponding modules.

        Returns:
            str: Error if an error occured.
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
        """Truns on Standby mode:
            All MUX channels are disconnected.
            All WL/NL matrix column are connected to the GND row (All WL are grounded).

        Returns:
            str: Error if an error occured.
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
        resps.append(self.MAT.configure_row_and_check(self.switch_hi_row, [False for _ in range(16)]))
        resps.append(self.MAT.configure_row_and_check(self.switch_lo_row, [False for _ in range(16)]))
        for resp in resps:
            if resp.startswith('ERROR') or resp.startswith('Exception'):
                return resp
        return 'Switch unit in Standby mode.'
    
    
    def connect_cell(self, row: int, column: int, switch_type='SET') -> str:
        """Connect crossbar cell in WL row and BL column.

        Args:
            row (int): Row number (Word Line and Net Line).
            column (int): Column number (Bit Line).
            switch_type (str, optional): Switch type ('SET' or 'RESET'). Defaults to 'SET'.

        Returns:
            str: Error if an error occured.
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
        switch_hi_list = [False for _ in range(16)]
        switch_lo_list = [False for _ in range(16)]
        gnd_list[self.WLNL[f'WLNL{row}'] - 1] = False
        smu_list[self.WLNL[f'WLNL{row}'] - 1] = True
        if switch_type == 'SET':
            switch_hi_list[self.switch_NL_col - 1] = True
            switch_lo_list[self.switch_BL_col - 1] = True
        else:
            switch_hi_list[self.switch_BL_col - 1] = True
            switch_lo_list[self.switch_NL_col - 1] = True
        resps.append(self.MAT.configure_row_and_check(self.GND_row, gnd_list))
        resps.append(self.MAT.configure_row_and_check(self.SMU_row, smu_list))
        resps.append(self.MAT.configure_row_and_check(self.switch_hi_row, switch_hi_list))
        resps.append(self.MAT.configure_row_and_check(self.switch_lo_row, switch_lo_list))
        resps.append(self.MUX.connect_exclusive(self.BL[f'BL{column}']))
        for resp in resps:
            if resp.startswith('ERROR') or resp.startswith('Exception'):
                self.disconnect_all()
                return resp + ' | All MUX channels and Matrix intersectrions were disconnected.'
        return f'Cell {row}-{column} was connected.'
    
    
    def change_switch_type(self, switch_type) -> str:
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
                return resp + ' | All MUX channels and Matrix intersectrions were disconnected.'
        return f'The switch type was changed to {switch_type}'
        






class Keysight_34922A_70ch_MUX:
    """Handles communicating with Keysight 34922A Multiplexer installed on Keysight 34980A 
    Multifunction Switch/Measure Unit.
    
    Attributes:
        resource (pyvisa.resource): Keysight 34980A Multifunction Switch/Measure Unit resource.
        slot (int): Keysight 34922A Multiplexer slot number on the mainframe.
        sim (bool): True if program is in simulation mode.
    """
    def __init__(self, resource: Union[pyvisa.Resource, None], slot: int):
        """Handles communicating with Keysight 34922A Multiplexer installed on 
        Keysight 34980A Multifunction Switch/Measure Unit.

        Args:
            resource (Union[pyvisa.Resource, None]): Keysight 34980A resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            slot (int): Mainfraime slot number of the Keysight 34922A Multiplexer (1 through 8).
        """
        self.resource = resource
        if slot < 1 or slot > 8:
            raise RuntimeError('ERROR: wrong slot number. Allowed slot numbers are 1 through 8.')
        self.slot = slot
        if resource is None:
            self.sim = True
        else:
            self.sim = False
        
        
    def write(self, commands: Union[list, str], stop_exception: bool = False):
        """Send sequence of SCPI commands to the instrument. Prints exception if an exception occurs.

        Args:
            commands (Union[list, str]): List of SCPI commands (strings).
            stop_exception (bool, optional): If True, stops sending commands when an exception occurs. 
                Defaults to False.
            
        Returns:
            list: List of execuded commands or Visa Errors.
        """
        return _write(self, commands, stop_exception)
            
            
    def query(self, command: str) -> str:
        """Send SCPI command and read response. Prints exception if an exception occurs.

        Args:
            command (str): SCPI command.

        Returns:
            str: Instrument response. Returns Visa Error if an exception occured.
        """
        return _query(self, command)
        
        
    def check_channel(self, channel: int) -> Union[bool, str]:
        """Check if the multiplexer channel is opend or closed.

        Args:
            channel (int): Multiplexer channel (1 through 70).

        Returns:
            Union[bool, str]: True if the channel is connected (switch is closed), False if it's open.
                Returns error string if an error occured.
        """
        if self.sim:
            return 
        if channel < 1 or channel > 70:
            return 'ERROR: wrong channel number. Allowed channel numbers are 1 through 70.'
        response = self.query(f'route:close? (@{self.slot}0{twodig(channel)})')
        if response[:10] == 'VISA ERROR':
            return f'ERROR: {response}'
        return bool(int(response[:-1]))
        
    
    def connect(self, channel: int) -> Union[str, None]:
        """Connect a channel on the multiplexer (close the switch).

        Args:
            channel (int): Multiplexer channel (1 through 70).

        Returns:
            Union[str, None]: SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
        """
        if self.sim:
            return 
        if channel < 1 or channel > 70:
            return 'ERROR: wrong channel number. Allowed channel numbers are 1 through 70.'
        return self.write(f'route:close (@{self.slot}0{twodig(channel)})')[0]
    
    
    def connect_and_check(self, channel: int) -> str:
        """Connect a channel on the multiplexer (close the switch) and check if it was connected.

        Args:
            channel (int): Multiplexer channel (1 through 70).

        Returns:
            str: Write command and query response.
        """
        if self.sim:
            return f'Simulation: Channel {channel} in slot {self.slot} is connected.'
        if channel < 1 or channel > 70:
            return 'ERROR: wrong channel number. Allowed channel numbers are 1 through 70.'
        self.write(f'route:close (@{self.slot}0{twodig(channel)})')
        connected = bool(int(self.query(f'route:close? (@{self.slot}0{twodig(channel)})')))
        if connected:
            query_response = f'Channel {channel} in slot {self.slot} is connected.'
        else:
            query_response = f'Channel {channel} in slot {self.slot} is disconnected.'
        return query_response
    
    
    def connect_exclusive(self, channel: int) -> str:
        """Connect a channel and disconnect all other channels.

        Args:
            channel (int): Channel to connect.

        Returns:
            str: Error if an error occured.
        """
        if self.sim:
            return f'Simulation: Channel {channel} in slot {self.slot} is connected exclusively.'
        if channel < 1 or channel > 70:
            return 'ERROR: wrong channel number. Allowed channels are 1 through 70.'
        self.write(f'route:close:exclusive (@{self.slot}0{twodig(channel)})')
        connected = bool(int(self.query(f'route:close? (@{self.slot}0{twodig(channel)})')))
        if connected:
            query_response = f'Channel {channel} in slot {self.slot} is connected exclusively.'
        else:
            query_response = f'Channel {channel} in slot {self.slot} is disconnected exclusively.'
        return query_response
        
        
    def disconnect(self, channel: int) -> str: 
        """Disconnect a channel on the multiplexer (open the switch).

        Args:
            channel (int): Multiplexer channel (1 through 70).

        Returns:
            Union[str, None]: SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
        """
        if self.sim:
            return 
        if channel < 1 or channel > 70:
            return 'ERROR: wrong channel number. Allowed channel numbers are 1 through 70.'
        return self.write(f'route:open (@{self.slot}0{twodig(channel)})')[0]
    
    
    def disconnect_and_check(self, channel: int) -> str:
        """Disconnect a channel on the multiplexer (open the switch) and check if it was disconnected.

        Args:
            channel (int): Multiplexer channel (1 through 70).

        Returns:
            str: Write command and query responce.
        """
        if self.sim:
            return f'Simulation: Channel {channel} in slot {self.slot} is disconnected.'
        if channel < 1 or channel > 70:
            return 'ERROR: wrong channel number. Allowed channel numbers are 1 through 70.'
        self.write(f'route:open (@{self.slot}0{twodig(channel)})')[0]
        connected = bool(int(self.query(f'route:close? (@{self.slot}0{twodig(channel)})')))
        if connected:
            query_response = f'Channel {channel} in slot {self.slot} is connected.'
        else:
            query_response = f'Channel {channel} in slot {self.slot} is disconnected.'
        return query_response
    
    
    def disconnect_all(self) -> str:
        """Disconnect all channels on the multiplexer (open all switches).

        Returns:
            str: Error if an error occured.
        """
        if self.sim:
            return f'Simulation: All channels in slot {self.slot} were disconnected.'
        write_response = self.write(f'route:open:all {self.slot}')[0]
        if write_response[:10] == 'VISA ERROR':
            return f'ERROR: {write_response}'
        return f'All channels in slot {self.slot} were disconnected.'
    
    
    def check_all(self) -> Union[list, str]:
        """Check all switches in the multiplexer.

        Returns:
            Union[list, str]: List of boolean variables for each channel (length is 70): True if
                channel is connected, False otherwise. Returns error string if an error occured. 
                Returns None if in simulatioin mode.
        """
        if self.sim:
            return
        response = self.query(f'route:close? (@{self.slot}001:{self.slot}070)')
        if response[:10] == 'VISA ERROR':
            return f'ERROR: {response}'
        return [bool(int(v)) for v in response.rstrip().split(',')]
    
    
    def configure_all(self, connection_list: list) -> Union[str, None]:
        """Configure all channels on the multiplexer.

        Args:
            connection_list (list): List of boolean variables [True, True, False, ...]: 
                True if channel needs to be connected, False if it needs to be disconnected.

        Returns:
            Union[str, None]: SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
        """
        if self.sim:
            return 
        if len(connection_list) != 70:
            return 'ERROR: connection_list must contain exactly 70 boolean variables (for each channel).'
        try:
            result = ''
            channel_str = ''
            for ch, ch_flag in enumerate(connection_list):
                if ch_flag:
                    channel_str += f'{self.slot}0{twodig(ch+1)},'
                    result += ' C'
                else:
                    result += ' D'
            if channel_str == '':
                self.disconnect_all()
            else:
                self.write(f'route:close:exclusive (@{channel_str[:-1]})')
            return f'Multiplexer in slot {self.slot} was configured to |{result} |.'
        except Exception as e:
            return f'Exception occured:{e}'
        
        
    def configure_all_and_check(self, connection_list: list) -> str:
        """Configure all connections in the multiplexer and check if they were properly configured.

        Args:
            connection_list (list): List of boolean variables [True, True, False, ...]: 
                True if intersection needs to be connected, False if it needs to be disconnected.

        Returns:
            str: Message with configuration, if it was successfull. Error if occured. In configuration,
                'C' is written for connected columns, 'D' for disconnected.
        """
        if self.sim:
            result = f'Simultation: Multiplexer in slot {self.slot} was configured to'
            for v in connection_list:
                result += ' C' if v else ' D'
            return result + ' |.'
        if len(connection_list) != 70: 
            return 'ERROR: connection_list must contain exactly 70 bool variables (for each column).'
        try:
            result = ''
            channel_str = ''
            for ch, ch_flag in enumerate(connection_list):
                if ch_flag:
                    channel_str += f'{self.slot}0{twodig(ch+1)},'
                    result += ' C'
                else:
                    result += ' D'
            if channel_str == '':
                self.disconnect_all()
            else:
                self.write(f'route:close:exclusive (@{channel_str[:-1]})')
            response = self.check_all()
            if isinstance(response, str) and response.startswith('ERROR'):
                self.disconnect_all()
                return f'{response} | All channels in slot {self.slot} were disconnected.'
            if response != connection_list:
                self.disconnect_all()
                return f'ERROR: Could not perform connections. All channels in slot {self.slot} were disconnected.'
            return f'Multiplexer in slot {self.slot} was configured to |{result} |.'
        except Exception as e:
            return f'Exception occured:{e}'
            
        




    
class Keysight_34932A_2x4x16_Matrix:
    """Handles communicating with Keysight 34932A Matrix installed on Keysight 34980A
    Multifunction Switch/Measure Unit.
    
    Attributes:
        resource (pyvisa.resource): Keysight 34980A Multifunction Switch/Measure Unit resource.
        slot (int): Keysight 34932A Matrix slot number on the mainframe.
        sim (bool): True if program is in simulation mode."""
    def __init__(self, resource: Union[pyvisa.Resource, None], slot: int):
        """Handles communicating with Keysight 34932A Multiplexer installed on 
        Keysight 34980A Multifunction Switch/Measure Unit.

        Args:
            resource (Union[pyvisa.Resource, None]): Keysight 34980A resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            slot (int): Mainfraime slot number of the Keysight 34932A Matrix (1 through 8).
        """
        self.resource = resource
        if slot < 1 or slot > 8:
            raise RuntimeError('ERROR: wrong slot number. Allowed slot numbers are 1 through 8.')
        self.slot = slot
        if resource is None:
            self.sim = True
        else:
            self.sim = False
            
            
    def write(self, commands: Union[list, str], stop_exception: bool = False):
        """Send sequence of SCPI commands to the instrument. Prints exception if an exception occurs.

        Args:
            commands (Union[list, str]): List of SCPI commands (strings).
            stop_exception (bool, optional): If True, stops sending commands when an exception occurs. 
                Defaults to False.
            
        Returns:
            list: List of execuded commands or Visa Errors.
        """
        return _write(self, commands, stop_exception)
    
    
    def query(self, command: str) -> str:
        """Send SCPI command and read response. Prints exception if an exception occurs.

        Args:
            command (str): SCPI command.

        Returns:
            str: Instrument response. Returns Visa Error if an exception occured.
        """
        return _query(self, command)
    
    
    def check_intersection(self, row: int, column: int) -> Union[bool, str]:
        """Check if row and column intersection is opened or closed.
        
        Args:
            row (int): Intersection row (1 through 8).
            column (int): Intersection column (1 through 16).
            
        Returns:
            Union[bool, str]: True if the intersectioin is connected (switch is closed), 
                False if it's open. Returns error string if an error occured.
        """
        if self.sim:
            return
        if row < 1 or row > 8 or column < 1 or column > 16:
            return 'ERROR: wrong row or column number. Rows are 1 through 8, columns are 1 through 16.'
        response = self.query(f'route:close? (@{self.slot}{row}{twodig(column)})')
        if response[:10] == 'VISA ERROR':
            return f'ERROR: {response}'
        return bool(int(response[:-1]))
    
    
    def connect(self, row: int, column: int) -> Union[str, None]:
        """Connect row and column intersection on the matrix (close the switch).

        Args:
            row (int): Intersection row (1 through 8).
            column (int): Intersection column (1 through 16).

        Returns:
            Union[str, None]: SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
        """
        if self.sim:
            return
        if row < 1 or row > 8 or column < 1 or column > 16:
            return 'ERROR: wrong row or column number. Rows are 1 through 8, columns are 1 through 16.'
        return self.write(f'route:close (@{self.slot}{row}{twodig(column)})')[0]
    
    
    def connect_and_check(self, row: int, column: int) -> str:
        """Connect row and column intersection (close the switch) and check if it was connected.

        Args:
            row (int): Intersection row (1 through 8).
            column (int): Intersection column (1 through 16).

        Returns:
            str: Write command and query response
        """
        if self.sim:
            return f'Simulation: Row {row} and column {column} intersection in slot {self.slot} is connected.'
        if row < 1 or row > 8 or column < 1 or column > 16:
            return 'ERROR: wrong row or column number. Rows are 1 through 8, columns are 1 through 16.'
        self.write(f'route:close (@{self.slot}{row}{twodig(column)})')
        connected = bool(int(self.query(f'route:close? (@{self.slot}{row}{twodig(column)})')))
        if connected:
            query_response = f'Row {row} and column {column} intersection in slot {self.slot} is connected'
        else:
            query_response = f'Row {row} and column {column} intersection in slot {self.slot} is disconnected'
        return query_response
    
    
    def disconnect(self, row: int, column: int) -> str:
        """Disconnect row and column intersection on the matrix (open the switch).

        Args:
            row (int): Intersection row (1 through 8).
            column (int): Intersection column (1 through 16).

        Returns:
            Union[str, None]: SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
        """
        if self.sim:
            return
        if row < 1 or row > 8 or column < 1 or column > 16:
            return 'ERROR: wrong row or column number. Rows are 1 through 8, columns are 1 through 16.'
        return self.write(f'route:open (@{self.slot}{row}{twodig(column)})')[0]
    
    
    def disconnect_and_check(self, row: int, column: int) -> str:
        """Disconnect row and column intersection (open the switch) and check if it was disconnected.

        Args:
            row (int): Intersection row (1 through 8).
            column (int): Intersection column (1 through 16).

        Returns:
            str: Write command and query response
        """
        if self.sim:
            return f'Simulation: Row {row} and column {column} intersection in slot {self.slot} is ' + \
                'disconnected.'
        if row < 1 or row > 8 or column < 1 or column > 16:
            return 'ERROR: wrong row or column number. Rows are 1 through 8, columns are 1 through 16.'
        self.write(f'route:open (@{self.slot}{row}{twodig(column)})')
        connected = bool(int(self.query(f'route:close? (@{self.slot}{row}{twodig(column)})')))
        if connected:
            query_response = f'Row {row} and column {column} intersection in slot {self.slot} is connected'
        else:
            query_response = f'Row {row} and column {column} intersection in slot {self.slot} is disconnected'
        return query_response
    
    
    def disconnect_all(self) -> str:
        """Disconnect all intersections in the matrix (open all switches).

        Returns:
            str: Error if an error occured.
        """
        if self.sim:
            return f'Simulation: All matrix intersections in slot {self.slot} were disconnected.'
        write_response = self.write(f'route:open:all {self.slot}')[0]
        if write_response[:10] == 'VISA ERROR':
            return f'ERROR: {write_response}'
        return f'All matrix intersections in slot {self.slot} were disconnected.'
    
    
    def disconnect_all_except(self, except_rows: tuple) -> str:
        """Disconnect all intersection in the matrix (open all switches) except intersections
            in rows rows specified by `except_rows` variable.
            
        Args:
            except_rows (tuple): Tuple of row numbers (int) in which intersections will not be closed.

        Returns:
            str: Error if an error occured.
        """
        if self.sim:
            return f'Simulation: All matrix intersections except rows {except_rows} ' + \
                f'in slot {self.slot} were disconnected.'
        channels = ''
        for row in range(1, 9):
            if row not in except_rows:
                channels += f'{self.slot}{row}01:{self.slot}{row}16,'
        write_response = self.write(f'route:open (@{channels[:-1]})')
        if write_response[:10] == 'VISA ERROR':
            return f'ERROR: {write_response}'
        return f'All matrix intersections except rows {except_rows} in slot {self.slot}' + \
            'were disconnected.'        
    
    
    def check_row(self, row: int) -> Union[list, str]:
        """Check switches on all intersections in a row.
        
        Args: 
            row (int): intersection row (1 through 8).
        
        Returns: 
            Union[list, str]: List of boolean variables for each column (length is 16): True if
                intersection with this column is connected, False otherwise. Returns error string if an
                error occured.
        """
        if self.sim:
            return
        if row < 1 or row > 8:
            return 'ERROR: wrong row number. Rows are 1 through 8.'
        response = self.query(f'route:close? (@{self.slot}{row}01:{self.slot}{row}16)')
        if response[:10] == 'VISA ERROR':
            return f'ERROR: {response}'
        return [bool(int(v)) for v in response.rstrip().split(',')]
    
    
    def configure_row(self, row: int, connection_list: list) -> Union[str, None]:
        """Configure all intersections in a row.

        Args:
            row(int): Row number (1 through 8).
            connection_list (list): List of boolean variables [True, True, False, ...]: 
                True if intersection needs to be connected, False if it needs to be disconnected.

        Returns:
            Union[str, None]: SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
        """
        if self.sim:
            return 
        if row < 1 or row > 8:
            return 'ERROR: wrong row number. Rows are 1 through 8.'
        if len(connection_list) != 16: 
            return 'ERROR: connection_list must contain exactly 16 boolean variables (for each column).'
        try:
            result = ''
            connect_str = ''
            disconnect_str = ''
            for col, col_flag in enumerate(connection_list):
                if col_flag:
                    connect_str += f'{self.slot}{row}{twodig(col+1)},'
                    result += ' C'
                else:
                    disconnect_str += f'{self.slot}{row}{twodig(col+1)},'
                    result += ' D'
            if connect_str != '':
                self.write(f'route:close (@{connect_str[:-1]})')
            if disconnect_str != '':
                self.write(f'route:open (@{disconnect_str[:-1]})')
            return f'Row {row} in slot {self.slot} was configured to |{result} |.'
        except Exception as e:
            return f'Exception occured: {e}'
        
        
    def configure_row_and_check(self, row: int, connection_list: list) -> str:
        """Configure all connections in a row and check if they were properly configured.

        Args:
            row (int): Row number (1 through 8).
            connection_list (list): List of boolean variables [True, True, False, ...]: 
                True if intersection needs to be connected, False if it needs to be disconnected.

        Returns:
            str: Message with configuration, if it was successfull. Error if occured. In configuration,
                'C' is written for connected columns, 'D' for disconnected.
        """
        if self.sim:
            result = f'Simultation: Row {row} in slot {self.slot} was configured to'
            for v in connection_list:
                result += ' C' if v else ' D'
            return result + ' |.'
        if row < 1 or row > 8:
            return 'ERROR: wrong row number. Rows are 1 through 8.'
        if len(connection_list) != 16: 
            return 'ERROR: connection_list must contain exactly 16 bool variables (for each column).'
        try:
            result = ''
            connect_str = ''
            disconnect_str = ''
            for col, col_flag in enumerate(connection_list):
                if col_flag:
                    connect_str += f'{self.slot}{row}{twodig(col+1)},'
                    result += ' C'
                else:
                    disconnect_str += f'{self.slot}{row}{twodig(col+1)},'
                    result += ' D'
            if connect_str != '':
                self.write(f'route:close (@{connect_str[:-1]})')
            if disconnect_str != '':
                self.write(f'route:open (@{disconnect_str[:-1]})')
            response = self.check_row(row)
            if isinstance(response, str) and response.startswith('ERROR'):
                self.disconnect_all()
                return f'{response} | All channels in slot {self.slot} were disconnected.'
            if response != connection_list:
                self.disconnect_all()
                return f'ERROR: Could not perform some connections. All channels in slot {self.slot} ' + \
                    'were disconnected.'
            return f'Row {row} in slot {self.slot} was configured to |{result} |.'
        except Exception as e:
            return f'Exception occured: {e}'

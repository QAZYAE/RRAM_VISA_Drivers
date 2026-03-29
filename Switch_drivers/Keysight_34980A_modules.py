"""
Drivers for configuring modules on Keysight 34980A Multifunction Switch/Measure unit
"""
import pyvisa 
from typing import Union
from RRAM_VISA_Drivers.VISA_utility import VISA_module, twodig



class Keysight_34922A_70ch_MUX(VISA_module):
    """Handles communicating with Keysight 34922A Multiplexer installed on Keysight 34980A 
    Multifunction Switch/Measure Unit.
    
    Attributes:
        resource (pyvisa.resource): Keysight 34980A Multifunction Switch/Measure Unit resource.
        slot (int): Keysight 34922A Multiplexer slot number on the mainframe.
        sim (bool): True if program is in simulation mode.
    """
    def __init__(self, resource: Union[pyvisa.Resource, None], slot: int) -> None:
        """Handles communicating with Keysight 34922A Multiplexer installed on 
        Keysight 34980A Multifunction Switch/Measure Unit.

        Args:
            resource (pyvisa.Resource | None): Keysight 34980A resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            slot (int): Mainframe slot number of the Keysight 34922A Multiplexer (1 through 8).
        """
        super().__init__(resource)
        if slot < 1 or slot > 8:
            raise RuntimeError('ERROR: wrong slot number. Allowed slot numbers are 1 through 8.')
        self.slot = slot
        
        
    def check_channel(self, channel: int) -> Union[bool, str]:
        """Check if the multiplexer channel is opened or closed.

        Args:
            channel (int): Multiplexer channel (1 through 70).

        Returns:
            response (bool | str): True if the channel is connected (switch is closed), 
                False if it's open. Returns error string if an error occurred.
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
            command (str | None): SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
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
            query_response (str): Write command and query response.
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
            query_response (str): Error if an error occurred.
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
        
        
    def disconnect(self, channel: int) -> Union[str, None]: 
        """Disconnect a channel on the multiplexer (open the switch).

        Args:
            channel (int): Multiplexer channel (1 through 70).

        Returns:
            command (str | None): SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
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
            query_response (str): Write command and query response.
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
            response (str): Error if an error occurred.
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
            connection_list (list | str): List of boolean variables for each channel (length is 70): True if
                channel is connected, False otherwise. Returns error string if an error occurred. 
                Returns None if in simulation mode.
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
            command (str | None): SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
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
            return f'Exception occurred:{e}'
        
        
    def configure_all_and_check(self, connection_list: list) -> str:
        """Configure all connections in the multiplexer and check if they were properly configured.

        Args:
            connection_list (list): List of boolean variables [True, True, False, ...]: 
                True if intersection needs to be connected, False if it needs to be disconnected.

        Returns:
            response (str): Message with configuration, if it was successful. Error if occurred. In configuration,
                'C' is written for connected columns, 'D' for disconnected.
        """
        if self.sim:
            result = f'Simulation: Multiplexer in slot {self.slot} was configured to'
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
            return f'Exception occurred:{e}'
        



class Keysight_34932A_2x4x16_Matrix(VISA_module):
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
            slot (int): Mainframe slot number of the Keysight 34932A Matrix (1 through 8).
        """
        super().__init__(resource)
        if slot < 1 or slot > 8:
            raise RuntimeError('ERROR: wrong slot number. Allowed slot numbers are 1 through 8.')
        self.slot = slot
    
    
    def check_intersection(self, row: int, column: int) -> Union[bool, str]:
        """Check if row and column intersection is opened or closed.
        
        Args:
            row (int): Intersection row (1 through 8).
            column (int): Intersection column (1 through 16).
            
        Returns:
            connected (bool | str): True if the intersection is connected (switch is closed), 
                False if it's open. Returns error string if an error occurred.
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
            command (str | None): SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
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
            query_response (str): Write command and query response
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
            command (str | None): SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
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
            query_response (str): Write command and query response
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
            response (str): Error if an error occurred.
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
            response (str): Error if an error occurred.
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
            connection_list (list | str): List of boolean variables for each column (length is 16): True if
                intersection with this column is connected, False otherwise. Returns error string if an
                error occurred.
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
            command (str, None): SCPI command if it was sent, Visa Error otherwise. None for simulation mode.
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
            return f'Exception occurred: {e}'
        
        
    def configure_row_and_check(self, row: int, connection_list: list) -> str:
        """Configure all connections in a row and check if they were properly configured.

        Args:
            row (int): Row number (1 through 8).
            connection_list (list): List of boolean variables [True, True, False, ...]: 
                True if intersection needs to be connected, False if it needs to be disconnected.

        Returns:
            response (str): Message with configuration, if it was successful. Error if occurred. In configuration,
                'C' is written for connected columns, 'D' for disconnected.
        """
        if self.sim:
            result = f'Simulation: Row {row} in slot {self.slot} was configured to'
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
            return f'Exception occurred: {e}'
"""
Driver for configuring B2902B instrument as a mainframe
"""
import pyvisa
import time
from typing import Union
import numpy as np
from RRAM_VISA_Drivers.VISA_utility import VISA_instrument
from RRAM_VISA_Drivers.SMU_drivers.Keysight_SMU import SMU



class B2902B(VISA_instrument):
    """Handles communicating with Keysight B2902B using pyvisa.
    
    Attributes:
        resource (pyvisa.Resource): Keysight B2902B resource.
        sim (bool): True if program is in simulation mode.
        inst_name (str): Instrument's name for responses
        SMU1 (SMU): Object for configuring B2902B's SMU1 (channel 1).
        SMU2 (SMU): Object for configuring B2902B's SMU2 (channel 2).
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        instrument_name: str = 'B2902B'
    ) -> None:
        """Handles communicating with Keysight B2902B using pyvisa.

        Args:
            resource (pyvisa.Resource | None): Keysight B2902B's resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            instrument_name (str, optional): Instrument name for responses. Defaults to 'B2902B'.
        """
        IDN_response = 'Keysight Technologies,B2902B'
        super().__init__(resource, IDN_response=IDN_response, instrument_name=instrument_name)
        self.SMU1 = SMU(resource, channel=1, instrument_name=instrument_name)
        self.SMU2 = SMU(resource, channel=2, instrument_name=instrument_name)
        
        
    def set_output_state(self, state: str) -> str:
        """Set output state for both channels of the instrument

        Args:
            state (str): Output state. Valid values: 1|on|0|off.

        Returns:
            response (str): Command response | error if an error occured.
        """
        r1 = self.SMU1.set_output_state(state)
        r2 = self.SMU2.set_output_state(state)
        return f'{r1}\n{r2}'
    
    
    def set_standby_zero(self) -> str:
        """Sets SMU output to 0V if output is off (for both channels).

        Returns:
            response (str): Command response | error if an error occured.
        """
        r1 = self.SMU1.set_standby_zero()
        r2 = self.SMU2.set_standby_zero()
        return f'{r1}\n{r2}'
    
    
    def beep(self, frequency: float, time: float) -> str:
        """Generates a beep sound of the specified frequency and duration.

        Args:
            frequency (float): Frequency, Hz. Valid values are from 55 to 6640 Hz.
            time (float): Duration in seconds. Valid values are from 0.05 to 12.75 s.

        Returns:
            response (str): Command response | error if an error occured.
        """
        return self.write_resp(f'system:beeper:immediate {frequency},{time}',
                               f'Beep at the frequency {frequency} Hz for {time} s')
        
        
    def set_data_format(self, form: str) -> str:
        """Specifies elements included in sense or measurement data.

        Args:
            form (str): Data elements: voltage|current|resistance|source|status|time.
                Several elements may be separated by a comma: `'voltage,current,resistance,time'`.

        Returns:
            response (str): Command response | error if an error occured.
        """
        return self.write_resp(f'format:elements:sense {form}',
                               f'Data output format is set to {form}')
        
        
    def get_data_format(self) -> str:
        """Gets current data format from the instrument.

        Returns:
            format (str): current data format | error if an error occured. 
        """
        return self.query_resp('format:elements:sense?', 
                               'Getting current data format from the instrument')
        
        
    def configure_digital_io_trigger(self, pin: int, function: str) -> str:
        """Configure a pin on the Digital I/O port (D-Sub 25) for trigger input or output.

        Args:
            pin (int): Pin number on the Digital I/O port (D-Sub 25). Valid pins are 1-14.
            function (str): Pin function: `'input'` (trigger input) or `'output'` (trigger output).
            
        Returns:
            response (str): Command response | error if an error occured.
        """
        if pin not in list(range(1, 15)):
            return f'ERROR: {self.resp} Invalid pin number. Only pins 1-14 may be used as trigger input'
        if function.lower() not in ['input', 'output']:
            return f'ERROR: {self.resp} Invalid function. Valid functions are input and output.'
        return self.write_resp(f'digital:external{pin}:function t{function}',
                               f'D-Sub pin {pin} is configured for the trigger {function}.')
        
        
    def set_external_trigger_link(self, pin: int, trigger_layer: str, 
                                  function: str, channel: int = 1) -> str:
        """Configure external trigger link through one of the pins on the Digital I/O port (D-Sub 25).
        Note that for configuring input trigger (slave instrument) you must also set trigger source 
        using :meth:`SMU.set_arm_external` or :meth:`SMU.set_trigger_external`.

        Args:
            pin (int): Pin number on the Digital I/O port (D-Sub 25). Valid pins are 1-14.
            trigger_layer (str): Trigger layer to link (`'arm'` or `'trigger'`).
            function (str): Pin function: `'input'` (trigger input for slave instrument) or 
                `'output'` (trigger output for master instrument).
            channel (str, optional): Output trigger channel on the master instrument. Defaults to 1.
            
        Returns:
            response (str): Command response | error if an error occured.
        """
        if pin not in list(range(1, 15)):
            return f'ERROR: {self.resp} Invalid pin number. Only pins 1-14 may be used as trigger input'
        if function.lower() not in ['input', 'output']:
            return f'ERROR: {self.resp} Invalid function. Valid functions are input and output.'
        if trigger_layer.lower() not in ['arm', 'trigger']:
            return f'ERROR: {self.resp} Invalid trigger_layer. Valid layers are arm and trigger.'
        if channel not in [1, 2]:
            return f'ERROR: {self.resp} Invalid channel. Valid channels are 1 or 2.'
        response = self.configure_digital_io_trigger(pin=pin, function=function)
        if function == 'output':
            smu = self.SMU1 if channel == 1 else self.SMU2
            if trigger_layer == 'arm':
                response += '\n' + smu.set_arm_output(state='on', pin=pin)
            else:
                response += '\n' + smu.set_trigger_output(state='on', pin=pin)
        return response
    

    def wait_for_idle(self, attempts: int = 500, wait_interval: float = 0.001) -> str:
        """Waits until instrument is in IDLE state.

        Args:
            attempts (int, optional): Number of attempts to communicate with 
                the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).
                Defaults to 1 ms.

        Returns:
            response (str): Command response | error if an error occured. 
        """
        if self.sim: 
            return 'Instrument is idle in 0 attempts'
        idle_success = False
        for i in range(attempts):
            response = self.query('idle?')
            if response[0] == '1':
                idle_success = True
                break
            time.sleep(wait_interval)
        if idle_success:
            if i > 0:
                self.get_errors()  # Clearing query unterminated errors
            return f'Instrument is idle in {i} attempts'
        return f'ERROR: {self.resp}\n\tWait for IDLE unsuccessfull: {response}'
    
    
    def initiate(self) -> str:
        """Initiate both channels (Moves from IDLE layer to ARM layer).

        Returns:
            response (str): Command response | error if an error occured.        
        """
        return self.write_resp('init (@1,2)', 'Instrument initiated')
    
    
    def arm(self) -> str:
        """Send an immediate ARM trigger over BUS (both channels).

        Returns:
            response (str): Command response | error if an error occured.        
        """
        return self.write_resp('arm (@1,2)', 'ARM trigger was sent')
    
    
    def trigger(self) -> str:
        """Send an immediate TRIGGER trigger over BUS (both channels).

        Returns:
            response (str): Command response | error if an error occured.        
        """
        return self.write_resp('trigger (@1,2)', 'TRIGGER trigger was sent')
    
    
    def get_sense_data(self, offset: int = 0) -> Union[tuple[np.ndarray], str, None]:
        """Return the array data for both channels, format is specified by B2902B.set_data_format().
        The data is not cleared until the .initiate() method is executed.

        Args:
            offset (int, optional): Indicates the beginning of the data received. The index is from 
                0 to maximum (depends on the buffer state). Defaults to 0 (All data is recieved).
                If offset is `-1`, latest data entry is recieved.

        Returns:
            data (tuple[np.ndarray] | str | None): Data specified by B2902B.set_data_format().
                Returns error if an error occured, returns None is the buffer is empty.
        """
        if not isinstance(offset, int) or offset < -1:
            return f'ERROR: {self.resp} invalid offset.'
        lat = ':latest' if offset == -1 else ''
        if offset == 0 or offset == -1:
            off = ''
        else:
            off = f' {offset}'
        flag, response = self.query_resp(f'sense1:data{lat}?{off};:sense2:data{lat}?{off}', 'Getting sense data')
        if flag:
            s1, s2 = response.split(';')
            arr1 = np.array(s1.split(','), dtype=float)
            arr2 = np.array(s2.split(','), dtype=float)
            if (arr1[0] in [9.91e+37, 9.90e+37, 9.90e-37] or
                arr2[0] in [9.91e+37, 9.90e+37, 9.90e-37]):
                print('b2920b_get_sense()', arr1, arr2)
                return None
            return arr1, arr2
        return response
    
    
    def fetch_array(self, function: str = '') -> Union[tuple[np.ndarray], str]:
        """Returns array data which contains all of the current measurement data.
        Method works only if the instrument is in idle state.

        Args:
            function (str, optional): Function to return: current|resistance|source|status|time|voltage.
                If function == '', returns array specified by B2902B.set_format(). Defaults to ''.

        Raises:
            RuntimeError: Unknown function. Function must be one of the following items:
                current|resistance|source|status|time|voltage
        Returns:
            data (tuple[np.ndarray] | str): Data array for SMU1 and SMU2. 
                Returns error if an error occured.
        """
        if function == '':
            func, fresp = '', ''
        else:
            if function.lower() not in ['current', 'resistance', 'source', 'status', 'time', 
                                        'voltage', 'curr', 'res', 'sour', 'stat', 'volt']:
                return f'ERROR: {self.resp} invalid function.'
            func, fresp = f':{function}', f': {function}'
        flag, response = self.query_resp(f'fetch:array{func}? (@1,2)', f'Fetching array data{fresp}')
        if flag:
            arr = np.array(response.split(','), dtype=float)
            return arr[::2], arr[1::2]
        return response
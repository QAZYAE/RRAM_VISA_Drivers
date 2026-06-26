"""
Driver for configuring B2902B instrument as a mainframe
"""
import pyvisa
import time
from typing import Union
import numpy as np
import logging
from RRAM_VISA_Drivers.core import VISA_instrument
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
        instrument_name: str = 'B2902B',
        scpi_logger: Union[logging.Logger, None] = None
    ) -> None:
        """Handles communicating with Keysight B2902B using pyvisa.

        Args:
            resource (pyvisa.Resource | None): Keysight B2902B's resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            instrument_name (str, optional): Instrument name for responses. Defaults to 'B2902B'.
            scpi_logger (logging.Logger | None, optional): Logger for scpi commands. Defaults to None.
        """
        IDN_response = 'Keysight Technologies,B2902B'
        super().__init__(resource, IDN_response=IDN_response, instrument_name=instrument_name, scpi_logger=scpi_logger)
        self.SMU1 = SMU(resource, channel=1, instrument_name=instrument_name, parent=self, scpi_logger=scpi_logger)
        self.SMU2 = SMU(resource, channel=2, instrument_name=instrument_name, parent=self, scpi_logger=scpi_logger)
        
        
    def set_output_state(self, state: str) -> str:
        """Set output state for both channels of the instrument

        Args:
            state (str): Output state. Valid values: 1|on|0|off.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        r1 = self.SMU1.set_output_state(state)
        r2 = self.SMU2.set_output_state(state)
        return f'{r1}\n{r2}'
    
    
    def set_standby_zero(self) -> str:
        """Sets SMU output to 0V if output is off (for both channels).

        Returns:
            response (str): Command response | error if an error occurred.
        """
        r1 = self.SMU1.set_standby_zero()
        r2 = self.SMU2.set_standby_zero()
        return f'{r1}\n{r2}'
    
    
    def set_output_filter(self, state: str) -> str:
        """Set output filter state  for both channels
            (ON to obtain clean source output without spikes and overshooting)

        Args:
            state (str): Filter state. Valid values: 1|on|0|off.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        r1 = self.SMU1.set_output_filter(state)
        r2 = self.SMU2.set_output_filter(state)
        return f'{r1}\n{r2}'
    
    
    def beep(self, frequency: float, time: float) -> str:
        """Generates a beep sound of the specified frequency and duration.

        Args:
            frequency (float): Frequency, Hz. Valid values are from 55 to 6640 Hz.
            time (float): Duration in seconds. Valid values are from 0.05 to 12.75 s.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.write_resp(f'system:beeper:immediate {frequency},{time}',
                               f'Beep at the frequency {frequency} Hz for {time} s')
        
        
    def set_data_format(self, form: str) -> str:
        """Specifies elements included in sense or measurement data.

        Args:
            form (str): Data elements: voltage|current|resistance|source|status|time.
                Several elements may be separated by a comma: `'voltage,current,resistance,time'`.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.write_resp(f'format:elements:sense {form}',
                               f'Data output format is set to {form}')
        
        
    def get_data_format(self) -> str:
        """Gets current data format from the instrument.

        Returns:
            format (str): current data format | error if an error occurred. 
        """
        return self.query_resp('format:elements:sense?', 
                               'Getting current data format from the instrument')
        
        
    def configure_digital_io_trigger(self, pin: int, function: str) -> str:
        """Configure a pin on the Digital I/O port (D-Sub 25) for trigger input or output.

        Args:
            pin (int): Pin number on the Digital I/O port (D-Sub 25). Valid pins are 1-14.
            function (str): Pin function: `'input'` (trigger input) or `'output'` (trigger output).
            
        Returns:
            response (str): Command response | error if an error occurred.
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
            response (str): Command response | error if an error occurred.
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
            response (str): Command response | error if an error occurred. 
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
        return f'ERROR: {self.resp}\n\tWait for IDLE unsuccessful: {response}'
    
    
    def get_raw_trigger_status(self) -> str:
        """Check trigger status (operation condition).

        Returns:
            (flag, response) (tuple[bool, str]): Flag is True if the query was 
                successful, response is error or operation condition. The 
                condition is the sum of the binary values for the set bits.
        """
        if self.sim:
            return True, '32767'  # All status entries are true
        return self.query_resp('status:operation:condition?', 'Checking operation condition')
    
    
    def check_trigger_status(self) -> list[str]:
        """Get the trigger status as a list with descriptions.

        Returns:
            descriptions (list[str]): List describing status which may contain
                following items:
                'Calibration/Self-test Running'
                'Ch1 Transition Idle'
                'Ch1 Waiting for Transition Trigger'
                'Ch1 Waiting for Transition Arm'
                'Ch1 Acquire Idle'
                'Ch1 Waiting for Acquire Trigger'
                'Ch1 Waiting for Acquire Arm'
                'Ch2 Transition Idle'
                'Ch2 Waiting for Transition Trigger'
                'Ch2 Waiting for Transition Arm'
                'Ch2 Acquire Idle'
                'Ch2 Waiting for Acquire Trigger'
                'Ch2 Waiting for Acquire Arm'
                'Instrument Locked'
                'Program Running'
        """
        flag, response = self.get_raw_trigger_status()
        if not flag:
            return response
        try:
            descriptions = [
                'Calibration/Self-test Running',
                'Ch1 Transition Idle',
                'Ch1 Waiting for Transition Trigger',
                'Ch1 Waiting for Transition Arm',
                'Ch1 Acquire Idle',
                'Ch1 Waiting for Acquire Trigger',
                'Ch1 Waiting for Acquire Arm',
                'Ch2 Transition Idle',
                'Ch2 Waiting for Transition Trigger',
                'Ch2 Waiting for Transition Arm',
                'Ch2 Acquire Idle',
                'Ch2 Waiting for Acquire Trigger',
                'Ch2 Waiting for Acquire Arm',
                'Instrument Locked',
                'Program Running'
            ]
            result = []
            for i, desk in zip(bin(int(response))[2:].zfill(15), descriptions[::-1]):
                if i == '1':
                    result.append(desk)
            return result
        except Exception as e:
            return f'ERROR: {self.resp}\n\t.check_trigger_status(): Could not interpret "{response}" as a status! Error: {e}'
        
        
    def _check_tran_acq(
        self, 
        channel: str, 
        tran_str: str, 
        acq_str:str, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> tuple[bool, str]:
        """Check instrument status for transient and acquire levels"""
        success = True
        for _ in range(attempts):
            status_list = self.check_trigger_status()
            if isinstance(status_list, str):
                return False, f'ERROR: {self.resp}: _check_tran_acq(): {status_list}'
            for chan in str(channel).split(','):  # Checking if channel's status is right
                success = success and f'Ch{chan} {tran_str}'
                success = success and f'Ch{chan} {acq_str}'
            if success: 
                break
            time.sleep(wait_interval)
        return success, '\n'.join(status_list)
    
    
    def check_idle(self, channel: str = '1,2', attempts: int = 500, wait_interval: float = 0.001) -> tuple[bool, str]:
        """Check if instrument is in idle state (via operation status command).

        Args:
            channel: (str, optional): channel to initiate (1 or 2). Defaults to '1,2' (initiates both channels).
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).Defaults to 1 ms.

        Returns:
            (flag, response) (tuple[bool, str]): idle_flag, status_list.
        """
        return self._check_tran_acq(channel, tran_str='Transition Idle', acq_str='Acquire Idle', 
                                    attempts=attempts, wait_interval=wait_interval)
        
        
    def check_initiated(self, channel: str = '1,2', attempts: int = 500, wait_interval: float = 0.001) -> tuple[bool, str]:
        """Check if instrument is in initiated (waiting for ARM trigger).

        Args:
            channel: (str, optional): channel to initiate (1 or 2). Defaults to '1,2' (initiates both channels).
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).Defaults to 1 ms.

        Returns:
            (flag, response) (tuple[bool, str]): idle_flag, status_list.
        """
        return self._check_tran_acq(channel, tran_str='Waiting for Transition Arm', acq_str='Waiting for Acquire Arm', 
                                    attempts=attempts, wait_interval=wait_interval)
        
        
    def check_armed(self, channel: str = '1,2', attempts: int = 500, wait_interval: float = 0.001) -> tuple[bool, str]:
        """Check if instrument is in initiated (waiting for ARM trigger).

        Args:
            channel: (str optional): channel to initiate (1 or 2). Defaults to '1,2' (initiates both channels).
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).Defaults to 1 ms.

        Returns:
            (flag, response) (tuple[bool, str]): idle_flag, status_list.
        """
        return self._check_tran_acq(channel, tran_str='Waiting for Transition Trigger', acq_str='Waiting for Acquire Trigger', 
                                    attempts=attempts, wait_interval=wait_interval)
        
        
    def _move_layer(
        self, 
        command: str,
        channel: str = '1,2', 
        check_status: bool = True, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> str:
        """Method for implementing .initiate(), .arm() and .trigger() with instrument state confirmation."""
        if command == 'init':
            meth = '.initiate()'
            check_func = self.check_idle
            descript = 'initiate'
        elif command == 'arm':
            meth = '.arm()'
            check_func = self.check_initiated
            descript = 'ARM trigger'
        elif command == 'trigger':
            meth = '.trigger()'
            check_func = self.check_armed
            descript = 'TRIGGER trigger'
        else:
            return f'ERROR: syntax in B2902B._move_layer(): unknown command {command}'
        # Channel checking
        if channel not in [1, 2, '1', '2', '1,2']:
            return f'ERROR: {self.resp} {meth}: wrong channel number: "{channel}"'
        else:
            ch = channel
        # Instrument status checking
        if check_status:
            success, status_list = check_func(channel, attempts, wait_interval)
        else:
            success = True
        if success:
            return self.write_resp(f'{command} (@{ch})', f'Channel(s) {ch}: {descript} was sent')
        return f'ERROR: {self.resp}: Could not send {descript} to the instrument in {attempts} attempts! Last status list: {status_list}'
    
    
    def initiate(
        self, 
        channel: str = '1,2', 
        check_status: bool = True, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> str:
        """Initiate both channels (Moves from IDLE layer to ARM layer).
        
        Args:
            channel: (str, optional): channel to initiate (1 or 2). Defaults to '1,2' (initiates both channels).
            check_status (bool, optional): If True, checks if the instrument is in the correct state 
                before initiating.
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).Defaults to 1 ms.

        Returns:
            response (str): Command response | error if an error occurred.        
        """
        return self._move_layer('init', channel, check_status, attempts, wait_interval)
    
    
    def arm(
        self, 
        channel: str = '1,2', 
        check_status: bool = True, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> str:
        """Send an immediate ARM trigger over BUS (both channels).
        
        Args:
            channel: (str, optional): channel to send arm trigger (1 or 2). Defaults to '1,2' (arms both channels).
            check_status (bool, optional): If True, checks if the instrument is in the correct state 
                before sending the trigger.
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds). Defaults to 1 ms.

        Returns:
            response (str): Command response | error if an error occurred.        
        """
        return self._move_layer('arm', channel, check_status, attempts, wait_interval)
    
    
    def trigger(
        self, 
        channel: str = '1,2', 
        check_status: bool = True, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> str:
        """Send an immediate TRIGGER trigger over BUS (both channels).
        
        Args:
            channel: (str, optional): channel to send arm trigger (1 or 2). Defaults to '1,2' (arms both channels).
            check_status (bool, optional): If True, checks if the instrument is in the correct state 
                before sending the trigger.
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds). Defaults to 1 ms.

        Returns:
            response (str): Command response | error if an error occurred.        
        """
        return self._move_layer('trigger', channel, check_status, attempts, wait_interval)
    
    
    def get_sense_data(
            self, 
            channels: str = '1,2', 
            offset: int = 0, 
            size: Union[int, None] = None
        ) -> Union[tuple[np.ndarray], str, None]:
        """Return the array data for both channels, format is specified by B2902B.set_data_format().
        The data is not cleared until the .initiate() method is executed.

        Args:
            channels (str, optional): Channels to read, separeted by comma. Defaults to '1,2'.
            offset (int, optional): Indicates the beginning of the data received. The index is from 
                0 to maximum (depends on the buffer state). Defaults to 0 (All data is received).
                If offset is `-1`, latest data entry is received.
            size (int | None, optional): Size of the buffer to read (starting from `offset`). If `size`
                is None, the function reads all available data in the buffer. Default to None.

        Returns:
            data (tuple[np.ndarray] | str | None): Data specified by B2902B.set_data_format().
                Returns error if an error occurred, returns None is the buffer is empty.
                If only one channel is specified, returns tuple where array with specified channel's
                data is on the channel number place.
        """
        if not isinstance(offset, int) or offset < -1:
            return f'ERROR: {self.resp} invalid offset.'
        if str(channels) not in ['1', '2', '1,2']:
            return f'ERROR: {self.resp} wrong channel specified: "{channels}"'
        if offset == -1:
            lat = ':latest'
            off = ''
        else:
            lat = ''
            off = f' {offset}'
        if size is not None and offset != -1:
            if not (isinstance(size, int) and size > 0):
                return f'ERROR: {self.resp} invalid size.'
            siz = f',{size}'
        else:
            siz = ''
        if channels == '1,2':
            flag, response = self.query_resp(f'sense1:data{lat}?{off}{siz};:sense2:data{lat}?{off}{siz}', 'Getting sense data')
        else:
            flag, response = self.query_resp(f'sense{channels}:data{lat}?{off}{siz}', 'Getting sense data')
        if flag:
            if channels == '1,2':
                s1, s2 = response.split(';')
                arr1 = np.array(s1.split(','), dtype=float)
                arr2 = np.array(s2.split(','), dtype=float)
                if (arr1[0] in [9.91e+37, 9.90e+37, 9.90e-37] or
                    arr2[0] in [9.91e+37, 9.90e+37, 9.90e-37]):
                    # print('b2920b_get_sense()', arr1, arr2)
                    return None
                return arr1, arr2
            else:
                arr = np.array(response.split(','), dtype=float)
                if arr[0] in [9.91e+37, 9.90e+37, 9.90e-37]:
                    return None
                if str(channels) == '1':
                    return arr, []
                else:
                    return [], arr
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
                Returns error if an error occurred.
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
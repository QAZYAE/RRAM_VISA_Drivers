"""
Driver for configuring SMU's (Source-Measure Units) on Keysight B2902B
"""
import pyvisa 
from typing import Union
import numpy as np
from numpy.typing import ArrayLike
from RRAM_VISA_Drivers.VISA_utility import VISA_module


class SMU(VISA_module):
    """Handles communicating with an SMU (Source-Measure Unit) on a Keysight instrument.
    
    Attributes:
        resource (pyvisa.resource): Keysight instrument resource.
        ch (int): SMU channel on the instrument.
        inst_name (str): Instrument name for responses.
    """
    def __init__(
        self,
        resource: Union[pyvisa.Resource, None], 
        channel: int, 
        instrument_name: str = 'Instrument',
        parent = None
    ) -> None:
        """Handles communicating with an SMU (Source-Measure Unit) on a Keysight instrument.

        Args:
            resource (pyvisa.Resource | None): Keysight instrument resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            channel (int): Channel number on the instrument mainframe.
            instrument_name (str, optional): Instrument name for responses. Defaults to 'Instrument'.
            parent (B2902B): Parent instrument class.
        """
        self.parent = parent
        if channel < 1 or channel > 8:
            raise RuntimeError('ERROR: wrong channel number. Allowed channel numbers are 1 through 8.')
        self.ch = channel
        self.inst_name = instrument_name
        self.smu_mode = 'voltage'
        super().__init__(resource, module_name=f'{self.inst_name}, channel {self.ch}')
        
        
    def set_output_state(self, state: str) -> None:
        """Set SMU output state

        Args:
            state (str): output state. Valid values: 1|on|0|off.
            
        Returns: 
            response (str): Command response | error if an error occurred.
        """
        if state.lower() not in ['1', 'on', '0', 'off']:
            return f'ERROR: {self.resp} Invalid state. Valid values: 1|on|0|off (str).'
        return self.write_resp(f'output{self.ch} {state}', f'Output state is set to {state}')
    
    
    def get_output_state(self) -> Union[bool, str]:
        """Check SMU output state

        Returns:
            response (bool | str): True if output is on, False if output is off. Exception str 
                if it occurred.
        """
        flag, response = self.query_resp(f'output{self.ch}:state?', 'Output state is checked')
        if flag:
            return bool(int(response))
        return response
    
    
    def set_standby_zero(self) -> str:
        """Set SMU output to 0V if output is off

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.write_resp(f'output{self.ch}:off:mode zero', 'Standby mode is set to 0V')
    
    
    def set_smu_mode(self, mode: str = 'voltage') -> str:
        """Set SMU mode: `voltage` for applying voltage and measuring current; `current` for applying 
            current and measuring voltage.

        Args:
            mode (str, optional): SMU mode: voltage|current. Defaults to 'voltage'.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if mode.lower() not in ['voltage', 'current']:
            return f'ERROR: {self.resp} Invalid SMU mode. Valid values: voltage|current (str).'
        self.smu_mode = mode
        return self.write_resp(f'source{self.ch}:function:mode {mode}',
                               f'Output mode is set to {mode}')
    
    
    def set_source_shape(self, shape: str = 'DC') -> str:
        """Set SMU output shape: DC or pulse.

        Args:
            shape (str, optional): Output shape: DC|pulse. Defaults to 'DC'.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if shape.lower() not in ['dc', 'pulse']:
            return f'ERROR: {self.resp} Invalid output shape. Valid values: DC|pulse (str).'
        return self.write_resp(f'source{self.ch}:function:shape {shape}', 
                               f'Output shape is set to {shape}')
        
        
    def set_pulse_config(self, width: float = 5e-5, delay: float = 0) -> str:
        """Configure SMU pulse output: pulse width and delay.

        Args:
            width (float, optional): Pulse width (seconds). Minimum value is 50 us, 
                minimum pulse period is 100 us. defaults to 50 us.
            delay (float, optional): Pulse delay (seconds): time from starting the pulse 
                base output to the pulse level transition. Defaults to 0.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.write_resp(
            ';:'.join([f'source{self.ch}:pulse:width {width}',
                       f'source{self.ch}:pulse:delay {delay}']),
            f'Pulse mode is configured: pulse_width = {width} s, pulse_delay = {delay} s'
        )
    
    
    def set_constant_voltage(
        self,
        voltage: float,
        current_compliance: float = 300e-6
    ) -> str:
        """Set constant voltage mode for triggered measurements.

        Args:
            voltage (float): Constant voltage level (source), Volts
            current_compliance (float, optional): Current compliance level, Amperes. 
                Defaults to 300 uA.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.write_resp(
            ';:'.join([f'source{self.ch}:voltage:mode fix',
                       f'source{self.ch}:voltage:level:triggered:amplitude {voltage}',
                       f'sense{self.ch}:current:DC:protection:level {current_compliance}']),
            f'Constant voltage is configured: {voltage} V, CC = {current_compliance} A'
        )
        
        
    def set_sweep_voltage(
        self,
        stop: float,
        n_points: int, 
        start: float = 0,
        double: bool = True, 
        current_compliance: float = 300e-6
    ) -> str:
        """Set sweep voltage mode for triggered measurements

        Args:
            stop (float): Stop voltage (source), Volts
            n_points (int): Number of sweep points (In a single direction. This number is
                automatically doubled for double sweep)
            start (float, optional): Start voltage (source), Volts. Defaults to 0.
            double (bool, optional): if True, sets sweep mode to double sweep. Double sweep 
                performs the sweep from start to stop to start. Defaults to False.
            current_compliance (float, optional): Current compliance level, Amperes. Defaults to 300 uA.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        dir_mode = 'double' if double else 'single'
        return self.write_resp(
            ';:'.join([f'source{self.ch}:voltage:mode sweep',
                       f'source{self.ch}:sweep:direction up',
                       f'source{self.ch}:sweep:ranging best',
                       f'source{self.ch}:voltage:start {start}',
                       f'source{self.ch}:voltage:stop {stop}',
                       f'source{self.ch}:sweep:points {n_points}',
                       f'source{self.ch}:sweep:stair {dir_mode}',
                       f'sense{self.ch}:current:DC:protection:level {current_compliance}']),
            f'Sweep voltage is configured: From {start} V to {stop} V,' + \
                f' {n_points} points, {dir_mode} sweep, CC = {current_compliance} A'
        )
        
        
    def set_list_voltage(self, voltage_list: ArrayLike, current_compliance: float = 300e-6) -> str:
        """Set list voltage mode for triggered measurements.

        Args:
            voltage_list (ArrayLike): List of voltages for SMU to apply.
            current_compliance (float, optional): Current compliance level, Amperes. Defaults to 300 uA.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        try:
            voltage_str = ','.join(map(str, voltage_list))
        except Exception as e:
            return f'ERROR: {self.resp} could not convert voltage list to a str: {e}'
        return self.write_resp(
            ';:'.join([f'source{self.ch}:voltage:mode list',
                       f'source{self.ch}:list:voltage {voltage_str}',
                       f'sense{self.ch}:current:DC:protection:level {current_compliance}']),
            f'List voltage is configured: CC = {current_compliance} A, Voltages (V): {voltage_list}'
        )
        
        
    def set_base_voltage_immediate(self, voltage, current_compliance: float = 100e-3) -> str:
        """Set base voltage output, applied immediately. WARNING: Voltage is applied on receiving command,
            not on trigger. Voltage will not turn off after measurements are done, 
            it should be set to 0 via this method.

        Args:
            voltage (float): Base voltage (source), Volts.
            current_compliance (float, optional): Current compliance level, Amperes. Defaults to 300 uA.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.write_resp(
            ';:'.join([f'sense{self.ch}:current:DC:protection:level {current_compliance}',
                       f'source{self.ch}:voltage:level:immediate {voltage}']),
            f'Base voltage is set to {voltage}.'
        )
        
        
    def set_measurement_aperture(self, aperture: float = 0.002, auto: bool = False) -> str:
        """Sets the integration time for one point measurement.

        Args:
            aperture (float, optional): Integration time in seconds. 
                Valid values are from 8e-6 to 2 seconds. Defaults to 2 ms.
            auto (bool, optional): If True, sets automatic aperture 
                (ignores aperture parameter). Defaults to False.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        meas_type = 'current' if self.smu_mode == 'voltage' else 'voltage'
        if auto:
            return self.write_resp(f'sense{self.ch}:{meas_type}:aperture:auto on',
                                   'Integration time is set to AUTO.')
        return self.write_resp(
            ';:'.join([f'sense{self.ch}:{meas_type}:aperture:auto off',
                       f'sense{self.ch}:{meas_type}:aperture {aperture}']),    
            f'Integration time is set to {aperture} s.'
        )
        
        
    def set_multimeter_mode(self, voltage_compliance: float = 1) -> str:
        """Set multimeter mode for voltage measurements.

        Args:
            voltage_compliance (float, optional): Voltage compliance (Volts). Defaults to 1.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        self.smu_mode = 'current'
        return self.write_resp(
            ';:'.join([f'source{self.ch}:function:mode current',
                       f'source{self.ch}:current:mode fix',
                       f'source{self.ch}:current:level:triggered:amplitude 0',
                       f'source{self.ch}:current:level:immediate 0',
                       f'sense{self.ch}:voltage:DC:protection:level {voltage_compliance}']),
            'SMU is set to multimeter mode for voltage measurement'
        )
        
        
    def get_sense_data(self, offset: int = 0) -> Union[np.ndarray, str, None]:
        """Return the array data, format is specified by B2902B.set_data_format().
        The data is not cleared until the .initiate() method is executed.

        Args:
            offset (int, optional): Indicates the beginning of the data received. The index is from 
                0 to maximum (depends on the buffer state). Defaults to 0 (All data is received).
                If offset is `-1`, latest data entry is received.

        Returns:
            data (np.ndarray | str | None): Data specified by B2902B.set_data_format(). 
                Returns error if an error occurred, returns None if the buffer is empty.
        """
        if not isinstance(offset, int) or offset < -1:
            return f'ERROR: {self.resp} invalid offset.'
        lat = ':latest' if offset == -1 else ''
        if offset == 0 or offset == -1:
            off = ''
        else:
            off = f' {offset}'
        flag, response = self.query_resp(f'sense{self.ch}:data{lat}?{off}', 'Getting sense data')
        if flag:
            array = np.array(response.split(','), dtype=float)
            if array[0] in [9.91e+37, 9.90e+37, 9.90e-37]:
                return None
            return array
        return response
    
    
    def fetch_array(self, function: str = '') -> Union[np.ndarray, str]:
        """Returns array data which contains all of the current measurement data. 
        Method works only if the instrument is in idle state.

        Args:
            function (str, optional): Function to return: current|resistance|source|status|time|voltage.
                If function == '', returns array specified by B2902B.set_format(). Defaults to ''.

        Raises:
            RuntimeError: Unknown function. Function must be one of the following items:
                current|resistance|source|status|time|voltage
        Returns:
            data (np.ndarray | str): Data array. Returns error if an error occurred.
        """
        if function == '':
            func, fresp = '', ''
        else:
            if function.lower() not in ['current', 'resistance', 'source', 'status', 'time', 
                                        'voltage', 'curr', 'res', 'sour', 'stat', 'volt']:
                return f'ERROR: {self.resp} invalid function.'
            func, fresp = f':{function}', f': {function}'
        flag, response = self.query_resp(f'fetch:array{func}? (@{self.ch})', f'Fetching array data{fresp}')
        if flag:
            return np.array(response.split(','), dtype=float)
        return response
    
    
    def set_arm_BUS(self, count: int = 1, delay: float = 0) -> str:
        """Set BUS as an ARM source, specify ARM count.

        Args:
            count (int, optional): ARM count. Defaults to 1.
            delay (float, optional): ARM delay in seconds. Defaults to 0.

        Returns:
            response (str): Command response | error if an error occurred.            
        """
        return self.write_resp(
            ';:'.join([f'arm{self.ch}:source BUS',
                       f'arm{self.ch}:count {count}',
                       f'arm{self.ch}:delay {delay}']),
            f'ARM trigger source is set to BUS, count = {count}, delay = {delay} s'
        )
    
    
    def set_trigger_BUS(self, count: int, acquire_delay: float = 0, transient_delay: float = 0) -> str:
        """Set BUS as trigger source (trigger layer) and set trigger count.

        Args:
            count (int): trigger count.
            acquire_delay (float, optional): time interval between trigger and measurement start 
                (seconds). Defaults to 0.
            transient_delay (float, optional): time interval between trigger and applying voltage 
                or current (seconds). Defaults to 0.

        Returns:
            response (str): Command response | error if an error occurred.                
        """
        return self.write_resp(
            ';:'.join([f'trigger{self.ch}:source BUS',
                       f'trigger{self.ch}:count {count}',
                       f'trigger{self.ch}:acquire:delay {acquire_delay}',
                       f'trigger{self.ch}:transient:delay {transient_delay}']),
            f'TRIGGER trigger source is set to BUS, count = {count}, ' + \
                f'acquire_delay = {acquire_delay} s, transient_delay = {transient_delay} s'
        )
        
        
    def set_arm_timer(self, interval: float, count: int, delay: float = 0) -> str:
        """_summary_

        Args:
            interval (float): arm trigger time interval (seconds).
            count (int): arm count.
            delay (float, optional): arm delay in seconds. Defaults to 0.
        
        Returns:
            response (str): Command response | error if an error occurred.  
        """
        return self.write_resp(
            ';:'.join([f'arm{self.ch}:source timer',
                       f'arm{self.ch}:timer {interval}',
                       f'arm{self.ch}:count {count}',
                       f'arm{self.ch}:delay {delay}']),
            f'ARM trigger source is set to Timer, count = {count}, interval = {interval} s, ' + \
                f'delay = {delay} s'
        )
        
        
    def set_trigger_timer(self, interval: float, count: int, acquire_delay: float = 0, 
                         transient_delay: float = 0) -> str:
        """Set timer as trigger source (trigger layer). The instrument will trigger itself at even time 
        intervals.

        Args:
            interval (float): trigger time interval (seconds). 2e-5 to 1e5 s.
            count (int): trigger count.
            acquire_delay (float, optional): time interval between trigger and measurement start 
                (seconds). Defaults to 0.
            transient_delay (float, optional): time interval between trigger and applying voltage 
                or current (seconds). Defaults to 0.
        
        Returns:
            response (str): Command response | error if an error occurred.  
        """
        return self.write_resp(
            ';:'.join([f'trigger{self.ch}:source timer',
                       f'trigger{self.ch}:timer {interval}',
                       f'trigger{self.ch}:count {count}',
                       f'trigger{self.ch}:acquire:delay {acquire_delay}',
                       f'trigger{self.ch}:transient:delay {transient_delay}']),
            f'TRIGGER trigger source is set to Timer, count = {count}, interval = {interval} s, ' + \
                f'acquire_delay = {acquire_delay} s, transient_delay = {transient_delay} s'
        )
        
        
    def set_arm_external(self, pin: int, count: int = 1, delay: float = 0) -> str:
        """Set one of the pins on the Digital I/O port (D-Sub 25) as an external arm source. 
        Note that Digital I/O pin must be configured as trigger input.

        Args:
            pin (int): pin number on the Digital I/O port (D-Sub 25). Valid pins are 1-14.
            count (int): arm count. Defaults to 1.
            delay (float, optional): arm delay in seconds. Defaults to 0.
            
        Returns:
            response (str): Command response | error if an error occurred.  
        """
        if pin not in list(range(1, 15)):
            return f'ERROR: {self.resp} Invalid pin number. Only pins 1-14 may be used as trigger input'
        return self.write_resp(
            ';:'.join([f'arm{self.ch}:source EXT{pin}',
                       f'arm{self.ch}:count {count}',
                       f'arm{self.ch}:delay {delay}']),
            f'ARM trigger source is set to External, count = {count}, D-Sub pin: {pin}, delay = {delay} s'
        )
        
        
    def set_trigger_external(self, pin: int, count: int, acquire_delay: float = 0, 
                             transient_delay: float = 0) -> str:
        """Set one of the pins on the Digital I/O port (D-Sub 25) as an external trigger source 
        (trigger layer). Note that Digital I/O pin must be configured as trigger input.

        Args:
            pin (int): pin number on the Digital I/O port (D-Sub 25). Valid pins are 1-14.
            count (int): trigger count.
            acquire_delay (float, optional): time interval between trigger and measurement start 
                (seconds). Defaults to 0.
            transient_delay (float, optional): time interval between trigger and applying voltage 
                or current (seconds). Defaults to 0.
        
        Returns:
            response (str): Command response | error if an error occurred.  
        """
        if pin not in list(range(1, 15)):
            return f'ERROR: {self.resp} Invalid pin number. Only pins 1-14 may be used as trigger input'
        return self.write_resp(
            ';:'.join([f'trigger{self.ch}:source EXT{pin}',
                       f'trigger{self.ch}:count {count}',
                       f'trigger{self.ch}:acquire:delay {acquire_delay}',
                       f'trigger{self.ch}:transient:delay {transient_delay}']),
            f'TRIGGER trigger source is set to External, count = {count}, D-Sub pin: {pin}, ' + \
                f'acquire_delay = {acquire_delay} s, transient_delay = {transient_delay} s'
        )
        
        
    def set_arm_output(self, pin: int, state: str = 'on') -> str:
        """Set trigger output for arm layer to one of the pins on the Digital I/O port (D-Sub 25).
        Note that Digital I/O pin must be configured as trigger output.

        Args:
            pin (int): pin number on the Digital I/O port (D-Sub 25). Valid pins are 1-14.
            state (str, optional): output state. Valid values: 1|on|0|off. Defaults to 'on'.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if pin not in list(range(1, 15)):
            return f'ERROR: {self.resp} Invalid pin number. Only pins 1-14 may be used as trigger input'
        if state not in ['1', 'on', '0', 'off']:
            return f'ERROR: {self.resp} Invalid state. Valid values: 1|on|0|off (str).'
        return self.write_resp(
            ';:'.join([f'trigger{self.ch}:toutput {state}',
                       f'trigger{self.ch}:toutput:signal EXT{pin}']),
            f'ARM trigger output is set to {state}, D-Sub pin: {pin}'
        )
        
        
    def set_trigger_output(self, pin: int, state: str = 'on') -> str:
        """Set trigger output for trigger layer to one of the pins on the Digital I/O port (D-Sub 25).
        Note that Digital I/O pin must be configured as trigger output.

        Args:
            pin (int): pin number on the Digital I/O port (D-Sub 25). Valid pins are 1-14.
            state (str, optional): output state. Valid values: 1|on|0|off. Defaults to 'on'.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if pin not in list(range(1, 15)):
            return f'ERROR: {self.resp} Invalid pin number. Only pins 1-14 may be used as trigger input'
        if state not in ['1', 'on', '0', 'off']:
            return f'ERROR: {self.resp} Invalid state. Valid values: 1|on|0|off (str).'
        return self.write_resp(
            ';:'.join([f'source{self.ch}:toutput {state}',
                       f'source{self.ch}:toutput:signal EXT{pin}']),
            f'TRIGGER trigger output is set to {state}, D-Sub pin: pin'
        )
        
        
    def initiate(
        self,
        check_status: bool = True, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> str:
        """Initiate SMU (Moves from IDLE layer to ARM layer).
            WARNING: you need to use parent class initiate if you want to initiate multiple SMUs.
        
        Args:
            check_status (bool, optional): If True, checks if the instrument is in the correct state 
                before initiating.
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).Defaults to 1 ms.

        Returns:
            response (str): Command response | error if an error occurred.        
        """
        if self.parent is None:
            return self.write_resp(f'init (@{self.ch})', 'SMU initiated')
        return self.parent.initiate(self.ch, check_status, attempts, wait_interval)
    
    
    def arm(
        self,
        check_status: bool = True, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> str:
        """Send an immediate ARM trigger over BUS.
            WARNING: you need to use parent class ARM if you want to initiate multiple SMUs.
            
        Args:
            check_status (bool, optional): If True, checks if the instrument is in the correct state 
                before initiating.
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).Defaults to 1 ms.

        Returns:
            response (str): Command response | error if an error occurred.        
        """
        if self.parent is None:
            return self.write_resp(f'arm (@{self.ch})', 'ARM trigger was sent')
        return self.parent.arm(self.ch, check_status, attempts, wait_interval)
    
    
    def trigger(
        self,
        check_status: bool = True, 
        attempts: int = 500, 
        wait_interval: float = 0.001
    ) -> str:
        """Send an immediate TRIGGER trigger over BUS.
            WARNING: you need to use parent class ARM if you want to initiate multiple SMUs.
            
        Args:
            check_status (bool, optional): If True, checks if the instrument is in the correct state 
                before initiating.
            attempts (int, optional): Number of attempts to communicate with the instrument. Defaults to 500.
            wait_interval (float, optional): Time to wait between attempts (seconds).Defaults to 1 ms.

        Returns:
            response (str): Command response | error if an error occurred.        
        """
        if self.parent is None:
            return self.write_resp(f'trigger (@{self.ch})', 'TRIGGER trigger was sent')
        return self.parent.trigger(self.ch, check_status, attempts, wait_interval)
    
    
    def get_measurement_config(self) -> dict:
        """Get measurement configuration (mode, voltage/current, compliance). 
            Does not support simulation.

        Returns:
            config (dict): Measurement configuration.
        """
        config = {}
        mode_resp = self.query(f'source{self.ch}:voltage:mode?')
        if mode_resp[:3] == 'SWE':
            config['mode'] = 'sweep'
            config['direction'] = self.query(f':source{self.ch}:sweep:direction?').lower()[:-1]
            config['ranging'] = self.query(f':source{self.ch}:sweep:ranging?').lower()[:-1]
            config['start'] = float(self.query(f':source{self.ch}:sweep:start?'))
            config['stop'] = float(self.query(f':source{self.ch}:sweep:stop?'))
            config['n_points'] = int(self.query(f':source{self.ch}:sweep:points?'))
            config['current_compliance'] = float(self.query((f':sense{self.ch}:current:DC:'
                                                             'protection:level?')))
        elif mode_resp[:3] == 'FIX':
            config['mode'] = 'constant voltage'
            config['voltage'] = float(self.query(f':source{self.ch}:voltage:level:triggered:amplitude?'))
            config['current_compliance'] = float(self.query(f':sense{self.ch}:current:DC:'
                                                             'protection:level?'))
        elif mode_resp[:3] == 'LIS':
            config['mode'] = 'list'
            config['current_compliance'] = float(self.query(f':sense{self.ch}:current:DC:'
                                                             'protection:level?'))
            config['voltage_list'] = np.array(self.query(f'source{self.ch}:list:voltage?').split(','), 
                                              dtype=float)
        else:
            config['mode'] = mode_resp[:-1]
        shape_resp = self.query(f'source{self.ch}:function:shape?')
        if shape_resp.startswith('DC'):
            config['shape'] = 'DC'
        else:
            config['shape'] = 'Pulse'
            config['pulse_width'] = float(f'source{self.ch}:pulse:width?')
            config['pulse_delay'] = float(f'source{self.ch}:pulse:delay?')
        return config
    
    
    def get_arm_config(self) -> tuple:
        """Get arm configuration (source, count, delay).

        Returns:
            (acq, tran) (dict, dict): Acquire and transient configurations.
        """
        def get_config(action):
            config = {}
            source_resp = self.query(f'arm{self.ch}:{action}:source?')
            if source_resp[:3] == 'TIM':
                config['source'] = 'timer'
                config['interval'] = self.query(f':arm{self.ch}:{action}:timer?')[:-1]
            elif source_resp[:3] == 'BUS':
                config['source'] = 'BUS'
            elif source_resp[:3] == 'EXT':
                config['source'] = 'external'
                config['pin'] = source_resp[3]
            else:
                config['source'] = source_resp[:-1]
            config['count'] = self.query(f':arm{self.ch}:{action}:count?')[:-1]
            config['delay'] = self.query(f':arm{self.ch}:{action}:delay?')[:-1]
            if bool(int(self.query(f':trigger{self.ch}:{action}:toutput:state?'))):
                config['output'] = True
                config['output_pin'] = self.query(f':trigger{self.ch}:{action}:toutput:signal?')[3]
            else:
                config['output'] = False
            return config
        
        acq_config = get_config('acquire')
        tran_config = get_config('transient')
        return acq_config, tran_config
    

    def get_trigger_config(self) -> tuple:
        """Get trigger configuration (source, count, delay).

        Returns:
            (acq, tran) (dict, dict): Acquire and transient configurations.
        """
        def get_config(action):
            config = {}
            source_resp = self.query(f'trigger{self.ch}:{action}:source?')
            if source_resp[:3] == 'TIM':
                config['source'] = 'timer'
                config['interval'] = self.query(f':trigger{self.ch}:{action}:timer?')[:-1]
            elif source_resp[:3] == 'BUS':
                config['source'] = 'BUS'
            elif source_resp[:3] == 'EXT':
                config['source'] = 'external'
                config['pin'] = source_resp[3]
            else:
                config['source'] = source_resp[:-1]
            config['count'] = self.query(f':trigger{self.ch}:{action}:count?')[:-1]
            config['delay'] = self.query(f':trigger{self.ch}:{action}:delay?')[:-1]
            if action == 'acquire':
                tout_system = 'sense'
            else:
                tout_system = 'source'
            if bool(int(self.query(f':{tout_system}{self.ch}:toutput:state?'))):
                config['output'] = True
                config['output_pin'] = self.query(f':{tout_system}{self.ch}:toutput:signal?')[3]
            else:
                config['output'] = False
            return config
        
        acq_config = get_config('acquire')
        tran_config = get_config('transient')
        return acq_config, tran_config
"""
Драйвер для управления двумя модулями B2902B для измерения кроссбаров
1T1R 32x8 (при помощи зондовой станции или коммутатора).
Первые пины на коннекторах D-Sub 25 устройств B2902B должны быть соединены проводом.
"""

import pyvisa 
import time
import numpy as np
from typing import Union
from RRAM_VISA_Drivers.core import GeneralDriver
from RRAM_VISA_Drivers.SMU_drivers import B2902B, Keysight_SMU
from RRAM_VISA_Drivers.core.temperature import K_volt2temp


_sign = {  # Sign dict for applying voltage to BL(reset) and NL(set) in MemriBoard
    1: 'BL',
    0: 'NL'
}

GATE_VOLTAGE = 3.3  # Voltage applied to transistor gate



class B2902B_1T1R_32x8_driver(GeneralDriver):
    """Driver for measuring 1T1R 32x8 crossbar arrays.
    
    Attributes: 
        trigger_interval (float): Interval between triggers in seconds. Defaults to 100 us.
        trigger_count (int): Trigger count for current experiment.
        acquired_counter (int): Number of resistances acquired via sense(). Resets on config or clear.
        trigger_needed (bool): If True, a trigger is sent before each .sense().
        skip_one_sense (bool): If True, one sense value is skipped on each .sense() (for pulse sequences switch+read).
        control_value (str): Unit which is controlled in the experiment (voltage or current).
        read_control_value (float | None): This variable contains voltage or current applied during read pulse, used to calculate resistance.
            If None resistance is calculated by 'vol' variable passed to .sense() method.
        read_sign (int): SMU to read current from when using .sense() 1 for BL (RESET), or 0 for NL (SET).
        need_stop (bool): Flag that can be set to True for GUI. Used if the driver is stuck in 
            acquire loop and user wants to stop the experiment.
        sense_size (int | None): Size of data to read from the instrument's buffer in .sense().
        queue (list): Results queue that fills while reading the data from instruments.
        sim (str): True for simulation mode.
        enable_temperature (bool): If True, temperature measurement is enabled.
        smu_list (list): Full list of SMUs to use in standart configurations.
        A_smu_list (list): List of Instrument A's SMUs used in the setup.
        B_smu_list (list): List of Instrument B's SMUs used in the setup.
        A_smu_channels (str): String of Instrument A's channels used in the setup ('1' | '2' | '1,2').
        B_smu_channels (str): String of Instrument B's channels used in the setup ('1' | '2' | '1,2').
    """
    trigger_interval: float = 100e-6
    trigger_count: int = 0
    acquired_counter: int = 0
    trigger_needed: bool = False
    skip_one_sense: bool = False
    control_value: str = 'voltage'
    read_control_value: Union[float, None] = None
    read_sign: int = 1
    need_stop: bool = False
    sense_size: Union[int, None] = None
    queue: list = []
    sim: str = False
    enable_temperature: bool
    smu_list: list[Keysight_SMU]
    A_smu_list: list[Keysight_SMU]
    B_smu_list: list[Keysight_SMU]
    A_smu_channels: str
    B_smu_channels: str
    batch_size: int = 10000  # Max array length the driver can handle
    
    def __init__(
        self, 
        B2902B_A_res: Union[pyvisa.Resource, None],
        B2902B_B_res: Union[pyvisa.Resource, None],
        sim: bool = False
    ) -> None:
        """Driver for measuring 1T1R 32x8 crossbar arrays via two B2902B units

        Args:
            B2902B_A_res (pyvisa.Resource | None): Keysight B2902B's resource, controls `BL` and `NL`.
                Initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            B2902B_B_res (pyvisa.Resource | None): Keysight B2902B's resource, controls `WL`.
                Initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
        """
        super().__init__()
        self.sim = sim
        # Creating driver instances for the instruments
        self.A = B2902B(resource=B2902B_A_res, instrument_name='B2902B_A', scpi_logger=self.scpi_logger)  # Controls BL and NL
        self.B = B2902B(resource=B2902B_B_res, instrument_name='B2902B_B', scpi_logger=self.scpi_logger)  # Controls WL
        # Config
        self.enable_temperature = eval(self.settings['ITC_1T1R']['Measure_temperature'])
        if self.settings['ITC_1T1R']['Gate_channel'] == '1':
            self.gate_smu = self.B.SMU1
            self.temp_smu = self.B.SMU2
        else:
            self.gate_smu = self.B.SMU2
            self.temp_smu = self.B.SMU1
        if self.settings['ITC_1T1R']['BL_channel'] == '1':
            self.BL_smu = self.A.SMU1
            self.NL_smu = self.A.SMU2
            self._read_sides = {
                1: 1,  # BL -> SMU1
                0: 2
            }
        else:
            self.BL_smu = self.A.SMU2
            self.NL_smu = self.A.SMU1
            self._read_sides = {
                1: 2,  # BL -> SMU2
                0: 1
            }
        if self.enable_temperature:
            self.smu_list = [self.BL_smu, self.NL_smu, self.gate_smu, self.temp_smu]
            self.B_smu_list = [self.gate_smu, self.temp_smu]
            self.B_smu_channels = '1,2'
        else:
            self.smu_list = [self.BL_smu, self.NL_smu, self.gate_smu]
            self.B_smu_list = [self.gate_smu]
            self.B_smu_channels = self.settings['ITC_1T1R']['Gate_channel']
        self.A_smu_list = [self.BL_smu, self.NL_smu]
        self.A_smu_channels = '1,2'
        # Checking connections and instrument types
        for inst, name in zip([self.A, self.B], 
                              ['B2902B_A', 'B2902B_B']):
            flag = inst.check_instrument_connection()
            inst.get_errors()  # Clear error queue
            if not flag:
                self.logger.critical('B2902B 1T1R 32x8 driver init error!')
                raise ConnectionError(f'Could not connect to an instrument: {name}')
        resps = []  # Response list
        # Resetting instruments 
        for inst in [self.A, self.B]:
            resps.append(inst.clear())
            resps.append(inst.set_standby_zero())
            resps.append(inst.set_output_state('on'))
            resps.append(inst.set_output_filter('off'))
        # Setting multimeter mode for temperature smu
        if self.enable_temperature:
            resps.append(self.temp_smu.set_multimeter_mode(voltage_compliance=1))
        for smu in [self.A.SMU1, self.A.SMU2, self.gate_smu]:
            resps.append(smu.set_smu_mode('voltage'))
        # Configuring data output format
        resps.append(self.A.set_data_format('voltage,current,time'))
        resps.append(self.B.set_data_format('voltage,current'))
        # Configuring triggers: Arm trigger is linked via pin 1 on D-Sub 25 connector
        self.arm_link_pin = int(self.settings['ITC_1T1R']['Arm_link_pin'])
        self.trigger_link_pin = int(self.settings['ITC_1T1R']['Trigger_link_pin'])
        resps.append(self.A.SMU1.set_arm_BUS())
        resps.append(self.A.SMU2.set_arm_BUS())
        resps.append(self.A.set_external_trigger_link(pin=self.arm_link_pin, 
                                                      trigger_layer='arm', 
                                                      function='output', 
                                                      channel=int(self._read_sides[1])))  # BL channel
        resps.append(self.B.set_external_trigger_link(pin=self.arm_link_pin, trigger_layer='arm', function='input'))
        resps.append(self.A.set_external_trigger_link(pin=self.trigger_link_pin, 
                                                      trigger_layer='trigger', 
                                                      function='output', 
                                                      channel=int(self._read_sides[1])))  # BL channel
        resps.append(self.B.set_external_trigger_link(pin=self.trigger_link_pin, trigger_layer='trigger', function='input'))
        # Checking if errors occurred
        for r in resps:
            if r.startswith('ERROR'):
                self.logger.error(f'B2902B 1T1R 32x8 driver init error!\n{r}')
                raise ConnectionError(r)
        # Checking error queues
        for inst, name in zip([self.A, self.B], 
                              ['B2902B_A', 'B2902B_B']):
            err = inst.get_errors()
            if err is not None:
                self.logger.error('B2902B 1T1R 32x8 driver init error!')
                self.logger.error(f'Instrument {name}:\n\t' + '\n\t'.join(err))
                raise ConnectionError(f'Error in {name} error queue: {err}')
        # Beeping
        self.A.beep(frequency=1000, time=0.2)
        time.sleep(0.2)
        self.B.beep(frequency=1200, time=0.2)
        self.logger.info('B2902B 1T1R 32x8 driver init success')
        
        
    def read_smu(self) -> str:
        """Get the SMU number from whitch the resistance is read"""
        return self._read_sides[self.read_sign]
        
    
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'B2902B_1T1R_32x8_driver: uses two Keysight B2902B Source-Measure ' + \
               'modules and a Keysight_34980A Switch unit for measuring 32x8 1T1R ' + \
               'memristive crossbar arrays'
    
        
    def clear_instruments(self) -> bool:
        """Clear SMU instruments on ticket end or when terminated.

        Returns:
            cleared (bool): True if instruments were cleared.
        """
        resps = []
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.gate_smu.set_base_output_level_immediate(0, compliance=1e-6))
        self.acquired_counter = 0
        for r in resps:
            if r.startswith('ERROR'):
                self.logger.critical(f'Could not clear the instruments!\n\t{r}')
                return False
        return True
    
    
    def connect_cell(self, wl: int, bl: int) -> tuple[bool, str]:
        """Empty function for compatibility

        Returns:
            flag, response (tuple[bool, str]): Connected flag (True if the cell was
            successfully disconnected), response or error.
        """
        return True, f'*Pretending to connect cell {wl}-{bl}* ' + \
                      '(cell connection is not available for probe station driver)'
    
    
    def disconnect(self) -> tuple[bool, str]:
        """Disconnect instruments on closing the app.

        Returns:
            flag, response (tuple[bool, str]): Disconnected flag (True if instruments were 
            successfully disconnected), response or error.
        """
        resps = []  # Response list
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.gate_smu.set_base_output_level_immediate(0, compliance=1e-6))
        resps.append(self.A.set_output_state('off'))
        resps.append(self.B.set_output_state('off'))
        resps.append(self.A.beep(frequency=1200, time=0.2))
        time.sleep(0.2)
        resps.append(self.B.beep(frequency=1000, time=0.2))
        # Checking errors
        for r in resps:
            if r.startswith('ERROR'):
                self.logger.critical(f'Could not disconnect the instruments!\n\t{r}')
                return False, r
        return True, 'VISA-instruments were disconnected'
    
    
    def standby(self) -> tuple[bool, str]:
        """Turns on Standby mode and clears all instruments.

        Returns:
            flag, response (tuple[bool, str]): Standby flag (True if standby mode
            was turned on successfully), response or error.
        """
        flag = self.clear_instruments()
        if flag:
            return True, 'Instruments are in standby mode'
        return False, 'Could not clear the instruments'
    
    
    def _panic_attempt(self) -> tuple[bool, str]:
        """Panic once to immediately stop the experiment.

        Returns:
            flag, response (tuple[bool, str]): Resolved flag (True if panic was resolved), 
            response or error.
        """
        resps = []  # Response list
        flag = True
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.A.set_output_state('off'))
        resps.append(self.B.set_output_state('off'))
        for smu in self.A_smu_list + [self.gate_smu]:
            resps.append(smu.set_base_output_level_immediate(0, compliance=1e-6))
        self.logger.debug('\t' + '\t\n'.join(resps))
        for r in resps:
            if r.startswith('ERROR'):
                flag = False
                self.logger.info('Panic attempt failed!')
        return flag, '\n'.join(resps)
    
    
    def panic(self) -> tuple[bool, str]:
        """Panic mode for immediately stopping the experiment.

        Returns:
            flag, response (tuple[bool, str]): Resolved flag (True if panic was resolved), 
            response or error.
        """
        self.logger.critical('Panic!')
        resps = []
        for i in range(5):
            self.logger.debug(f'Panic attempt {i}')
            flag, response = self._panic_attempt()
            resps.append(response)
            if flag:
                break
        if flag:
            err_A = self.A.get_errors()  # Clearing errors
            err_B = self.B.get_errors()
            self.logger.debug(f'Errors after panic:\n\tA: {err_A}\n\tB: {err_B}')
            resps.append(self.A.set_output_state('on'))
            resps.append(self.B.set_output_state('on'))
            self.logger.critical('Panic resolved!')
            self.logger.debug(f'Panic responces: {resps}')
        else:
            self.logger.error('Panic was not resolved!\n\t' + '\n\t'.join(resps))
        return flag, '\n'.join(resps)
    
    
    def _random_sense(self, include_time: bool = True, vol: Union[float, None] = None) -> tuple[np.ndarray]:  # TODO move to GeneralDriver
        """Generates random sense samples in format (Voltage, Current) with size=acquired_counter+1
            (Size is the number of (Voltage, Current) pairs)
            
        Args:
            include_time (bool, optional): If True, includes timestamp in the sense data. Defaults to True.
            vol (float | None, optional): Voltage applied. If it is not none, this voltage is returned. Defaults to None.

        Returns:
            sense1, sense2 (tuple[np.ndarray]): sense samples for two channels.
        """
        R1, R2 = self.random_values(array_number=2, length=1)
        if vol is not None:
            if self.control_value == 'voltage':
                if self.read_smu() == 1:
                    v1 = vol
                    v2 = self.random_values() / 1e6
                else:
                    v1 = self.random_values() / 1e6
                    v2 = vol
                i1 = v1 / R1
                i2 = v2 / R2
                if i1 == 0:  # Adding randomness, preventing divide by 0
                    i1 = self.random_values() / 1e9
                if i2 == 0:
                    i2 = self.random_values() / 1e9
            else:
                if self.read_smu() == 1:
                    i1 = vol
                    i2 = self.random_values() / 1e9
                else:
                    i1 = self.random_values() / 1e9
                    i2 = vol
                v1 = i1 * R1
                v2 = i2 * R2
                if v1 == 0:  # Adding randomness, preventing divide by 0
                    v1 = self.random_values() / 1e6
                if v2 == 0:
                    v2 = self.random_values() / 1e6
        else:
            v1 = self.random_values() / 1e6
            v2 = self.random_values() / 1e6
            i1 = v1 / R1
            i2 = v2 / R2
        if include_time:
            timestamp = self.acquired_counter * self.trigger_interval
            sense1, sense2 = [v1, i1, timestamp], [v2, i2, timestamp]
        else:
            sense1, sense2 = [v1, i1], [v2, i2]
        return np.array(sense1), np.array(sense2)
    
    
    def _get_nan_sense(self, include_time: bool = True) -> tuple[np.ndarray]:
        """Fill sense output format with NaN (failed to get sense data).

        Args:
            include_time (bool, optional): If True, includes timestamp in the sense data. Defaults to True.

        Returns:
            sense1, sense2 (tuple[np.ndarray]): sense samples for two channels.
        """
        if include_time:
            timestamp = self.acquired_counter * self.trigger_interval
            sense1, sense2 = [np.nan, np.nan, timestamp], [np.nan, np.nan, timestamp]
        else:
            sense1, sense2 = [np.nan, np.nan], [np.nan, np.nan]
        return np.array(sense1), np.array(sense2)
    
    
    def _res_for_plot(self, data: tuple, vol_cur: Union[float, None] = None) -> float:
        """Get resistance for plot based on SMU data and controlled voltage or current"""
        smu_vol = data[1]  # SMU voltage
        smu_cur = data[2]  # SMU current
        if self.control_value == 'voltage':  # Controlling voltage, vol_cur is voltage
            if smu_cur == 0:
                r = np.inf
            else:
                if self.read_control_value is None:  # Calculate by vol_cur
                    if vol_cur is None:  # Calculate by smu voltage and current
                        r = smu_vol / smu_cur
                    else:  # Calculate by vol_cur voltage and smu current
                        r = vol_cur / smu_cur
                else:  # Calculate by read_control_value (voltage)
                    r = self.read_control_value / smu_cur
            if r <= 0:
                r = np.inf  
        else:  # Controlling current, vol_cur is current
            if smu_vol == 0:
                r = 0
            else:
                if self.read_control_value is None:  # Calculate by vol_cur
                    if vol_cur is None:  # Calculate by smu current
                        r = smu_vol / smu_cur
                    else:  # Calculate by vol_cur current and smu voltage
                        if vol_cur == 0:
                            r = 0
                        else:
                            r = smu_vol / vol_cur
                else:  # Calculate by read_control_value (current)
                    r = smu_vol / self.read_control_value
            r = max(r, 0)
        return r
        
        
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
        sleep_time = 0.1 * self.trigger_interval
        self.logger.debug(f'ACQUIRED_COUNTER (BEFORE): {self.acquired_counter}, (trigger_count: {self.trigger_count})')
        if self.acquired_counter < self.trigger_count:  # Skip acquire if queue is full
            if self.sim:
                sense1, sense2 = self._random_sense(vol=vol)
                sense1_B, sense2_B = self._random_sense(include_time=False)
            else:  # Acquire from instruments
                # Trigger
                if self.trigger_needed:
                    self.logger.debug(f'SENSE TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}, B: {self.B.check_trigger_status()}')
                    flag, resp = self.B.check_armed(channel=self.B_smu_channels)  # Check if B is ready for trigger
                    if not flag:
                        self.logger.error(f'.sense(): B is not armed! B status: {resp}')
                        return f'.sense(): B is not armed! B status: {resp}'
                    if self.skip_one_sense:
                        r1 = self.A.trigger(channel=self.A_smu_channels)  # Trigger A No 1
                        time.sleep(self.trigger_interval)
                        flag, resp = self.B.check_armed(channel=self.B_smu_channels)  # Check if B is ready for trigger
                        if not flag:
                            self.logger.error(f'.sense(), second trigger: B is not armed! B status: {resp}')
                            return f'.sense(), second trigger: B is not armed! B status: {resp}'
                        r2 = self.A.trigger(channel=self.A_smu_channels)  # Trigger A
                        self.logger.debug('A is triggered twice')
                        for resp in [r1, r2]:
                            if resp.startswith('ERROR'):
                                self.logger.error(f'.sense(): A trigger error: {resp}')
                                return f'.sense(): A trigger error: {resp}'
                    else:
                        self.logger.debug('Sense: Trigger sent to instrument A')
                        resp = self.A.trigger(channel=self.A_smu_channels)  # Trigger A
                        if resp.startswith('ERROR'):
                            self.logger.error(f'.sense(): A trigger error: {resp}')
                            return f'.sense(): A trigger error: {resp}'
                # ACQUIRE
                # ACQUIRE A
                for i in range(acquire_attempts):
                    sense_data_A = self.A.get_sense_data(offset=self.acquired_counter, size=self.sense_size, 
                                                         channels=str(self.read_smu()))  # sense_ch1, sense_ch2
                    self.logger.debug(f'Sense_A: acquire attempt {i}: {sense_data_A}')
                    if sense_data_A is not None:
                        break
                    if self.need_stop:
                        self.logger.warning('Sense_A: Need stop flag received!')
                        break
                    time.sleep(sleep_time)
                self.logger.debug(f'A measurement condition: {self.A.query("status:measurement:condition?")}')
                self.logger.debug(f'A questionable condition: {self.A.query("status:questionable:condition?")}')
                if sense_data_A is None:
                    self.logger.error('Cant obtain sense_A data!')
                    self.logger.error(f'Sense A data (no arguments): {self.A.query(":sense1:data?;:sense2:data?")}')
                    self.save_logs()
                    sense_data_A = self._get_nan_sense()
                if isinstance(sense_data_A, str):
                    self.logger.error(f'Sense_A acquire error: {sense_data_A}')
                    self.save_logs()
                    return sense_data_A
                # ACQUIRE B
                for i in range(acquire_attempts):
                    sense_data_B = self.B.get_sense_data(offset=self.acquired_counter, size=self.sense_size, 
                                                         channels=self.B_smu_channels)  # sense_ch1, sense_ch2
                    self.logger.debug(f'Sense_B: acquire attempt {i}: {sense_data_B}')
                    if sense_data_B is not None:
                        flag = True
                        for channel in list(map(int, self.B_smu_channels.split(','))):
                            if not len(sense_data_A[channel-1])/3*2 <= len(sense_data_B[channel-1]):  # At least equal amount of data acquired
                                flag = False
                        if flag:
                            break
                    if self.need_stop:
                        self.logger.warning('Sense_B: Need stop flag received!')
                        break
                    time.sleep(sleep_time)
                self.logger.debug(f'B measurement condition: {self.B.query("status:measurement:condition?")}')
                self.logger.debug(f'B questionable condition: {self.B.query("status:questionable:condition?")}')
                if sense_data_B is None:
                    self.logger.error('Cant obtain sense_B data!')
                    self.logger.error(f'Sense B data (no arguments): {self.B.query(":sense1:data?;:sense2:data?")}')
                    self.save_logs()
                    sense_data_B = self._get_nan_sense(include_time=False)
                if isinstance(sense_data_B, str):
                    self.logger.error(f'Sense_B acquire error: {sense_data_B}')
                    self.save_logs()
                    return sense_data_B
                self.logger.debug('Sense_A and sense_B acquired')
                sense1, sense2 = sense_data_A
                sense1_B, sense2_B = sense_data_B
                self.logger.debug(f'LENGTHS: sense1_A: {len(sense1)}, sense2_A: {len(sense2)}, sense1_B: {len(sense1_B)}, sense2_B: {len(sense2_B)}')
                # TODO Save WL data
            # PARSING DATA
            # B data might be longer than A data
            if self.read_smu() == 1:
                primary_sense = sense1
            else:
                primary_sense = sense2
            if self.skip_one_sense:
                primary_step = 6
                secondary_step = 4
            else:
                primary_step = 3
                secondary_step = 2
            V = primary_sense[0::primary_step]
            Curr = primary_sense[1::primary_step]
            timestamp = self.exp_start_time + primary_sense[2::primary_step]
            # Temperature and WL
            if self.settings['ITC_1T1R']['Gate_channel'] == '1':
                # sense_gate = sense1_B
                sense_temp = sense2_B
            else:
                # sense_gate = sense2_B
                sense_temp = sense1_B
            if self.enable_temperature:
                V_temp = sense_temp[0:len(V)*2:secondary_step]
                Temp = K_volt2temp(V_temp, room_temp=float(self.settings['temperature']['room_temperature']))
            else:
                V_temp, Temp = [np.nan]*len(V), [np.nan]*len(V)
            self.logger.debug(f'Sense_data acquired: V = {V}, curr = {Curr}, Time={timestamp}, V_temp={V_temp}, Temp={Temp}')
            for t, v, cur, tem, v_t in zip(timestamp, V, Curr, Temp, V_temp):
                self.queue.append((t, v, cur, tem, v_t))
            if self.skip_one_sense:
                counter_delta = 2 * len(V)
            else:
                counter_delta = len(V)
            self.acquired_counter += counter_delta
            # Checking if to much data is read on each .sense()
            if counter_delta > 20:
                self.sense_size = 20  # Limiting the read size till the end of the experiment
            # Checking if reading data is finished
            if self.trigger_count - self.acquired_counter <= 20:
                self.sense_size = None
        try:
            # Sending data
            self.logger.debug(f'ACQUIRED COUNTER (AFT): {self.acquired_counter}')
            data_to_send = self.queue.pop(0)
            r = self._res_for_plot(data_to_send, vol_cur = vol)
            self.logger.info(f'Data returned: {[r, *data_to_send]}')
            # self.logger.warning(f'Temperature: {data_to_send[4]} C')
            # print(f'Temperature: {data_to_send[4]} C')
            return [r, *data_to_send]  # Tuple[R, time]
        except IndexError:
            self.logger.error('Sense queue is empty!')
            return 'Sense queue is empty!'
        
        
    def trigger(self, attempts: int = 200, sleep_time: float = 0.001) -> tuple[bool, str]:
        """Send immediate trigger, skip one acquire value
        
        Returns:
            flag, response (tuple[bool, str]): flag is True if the trigger was 
            sent successfully, response or error.
        """
        self.logger.debug(f'.trigger() TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}, B: {self.B.check_trigger_status()}')
        for i in range(attempts):
            flag, resp = self.B.check_armed(channel=self.B_smu_channels)  # Check if B is ready for trigger
            if not flag:
                self.logger.debug(f'attempt {i}: .trigger(): B is not armed! B status: {resp}')
            else:
                break
            time.sleep(sleep_time)
        if not flag:
            self.logger.error(f'.trigger(): B is not armed! B status: {resp}')
            self.save_logs()
            return False, f'.trigger(): B is not armed! B status: {resp}'
        resp = self.A.trigger(channel=self.A_smu_channels)  # Trigger A
        if resp.startswith('ERROR'):
            self.logger.error(f'.trigger(): A trigger error: {resp}')
            self.save_logs()
            return False, f'.trigger(): A trigger error: {resp}'
        self.logger.debug('.trigger(): trigger sent to instrument A')
        return True, 'Trigger was sent to the instruments'
        
        
    def _set_init_values(
        self, 
        mode: str, 
        trigger_count: int, 
        trigger_interval: Union[float, None] = None, 
        pulse_width: Union[float, None] = None, 
        trigger_needed: bool = False, 
        skip_one_sense: bool = False,
        control_value: str = 'voltage'
    ) -> None:  # TODO move to GeneralDriver (?)
        """Set initial values for the experiment configuration"""
        if mode == 'DC':
            if trigger_interval < 100e-6:
                self.logger.info('Warning: Too short trigger interval. The interval is set to 100us (min value)')
                self.trigger_interval = 100e-6
            else:
                self.trigger_interval = trigger_interval
        elif mode == 'pulse':
            if pulse_width < 100e-6:
                self.logger.info('Warning: Too short pulse width. The interval is set to 100us (min value)')
                self.pulse_width = 100e-6
            else:
                self.pulse_width = pulse_width
            if trigger_interval is not None:
                if trigger_interval < 2 * self.pulse_width:
                    self.trigger_interval = 2 * self.pulse_width
                else:
                    self.trigger_interval = trigger_interval
        else:
            raise RuntimeError(f'_config_init_values: unknown mode: {mode}')
        self.trigger_count = trigger_count
        self.acquired_counter = int(skip_one_sense)
        self.need_stop = False
        self.sense_size = None
        self.trigger_needed = trigger_needed
        self.skip_one_sense = skip_one_sense
        self.control_value = control_value
        self.queue = []
        self.resps = []  # Response list
        # Clearing
        self.resps.append(self.A.clear())
        self.resps.append(self.B.clear())
        self.resps.append(self.A.wait_for_idle(wait_interval=0.1*self.trigger_interval))
        self.resps.append(self.B.wait_for_idle(wait_interval=0.1*self.trigger_interval))
        
        
    def _check_config_and_start(self, mode_name: str, arm_B: bool = False) -> tuple[bool, str]:  # TODO move to GeneralDriver (?)
        """Check if the instrument was configured without errors"""
        response = ''
        bad_config_flag = False
        for resp in self.resps:
            if resp.startswith('ERROR'):
                response += resp
                bad_config_flag = True
        for inst, name in zip([self.A, self.B], ['B2902B_A', 'B2902B_B']):
            err = inst.get_errors()
            if err is not None:
                response += '\n\t'.join([name] + err)
                bad_config_flag = True
        if bad_config_flag:
            self.logger.error(response)
            return False, response
        self.logger.info(f'{mode_name} config success!')
        # Start the experiment
        resp = self.A.initiate(channel=self.A_smu_channels)
        self.logger.debug(f'A initiated. Response: {resp}')
        resp = self.B.initiate(channel=self.B_smu_channels)
        self.logger.debug(f'B initiated. Response: {resp}')
        self.logger.debug(f'.config() TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}, B: {self.B.check_trigger_status()}')
        if arm_B:  # If we need to send arm trigger to B
            resp = self.A.arm(channel=self.A_smu_channels)
            self.logger.debug(f'ARM trigger sent to A. Response: {resp}')
            resp = self.B.arm(channel=self.B_smu_channels)
            self.logger.debug(f'ARM trigger sent to B. Response: {resp}')
        else:
            flag, resp = self.B.check_initiated(channel=self.B_smu_channels)
            if flag:
                self.logger.debug(f'B is ready. Status: {resp}')
                resp = self.A.arm(self.A_smu_channels)
                self.logger.debug(f'ARM trigger sent to A. Response: {resp}')
            else:
                self.logger.error(f'B is not ready for external ARM trigger! Status: {resp}')
                return False, f'B is not ready for external ARM trigger! Status: {resp}'
        self.exp_start_time = time.time()
        return True, f'{mode_name} was configured'
        
        
    def config_iv_dc(
        self, 
        trigger_interval: float, 
        v_start: float, 
        v_stop: float,
        n_points: int,
        double: bool,
        current_compliance: float,
        sign: int = 1
    ) -> tuple[bool, str]:
        """Configure IV_DC mode. WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            trigger_interval (float): Interval between triggers (seconds).
            v_start (float): Start voltage (Volts).
            v_stop (float): Stop voltage (Volts).
            n_points (int): Number of sweep points in a single direction 
                (doubled automatically for double IV curve).
            double (bool): True for double IV curve.
            current_compliance (float): Current compliance (Amperes).
            sign (int, optional): Side where sweep voltage is applied: 1 -- 'BL', 0 -- 'NL'.
                Defaults to 1.

        Returns:
            flag, response (tuple[bool, str]): Good_config_flag (True if instruments were 
            successfully configured), response or error.
        """
        self._set_init_values(mode='DC', 
                              trigger_count = 2 * n_points if double else n_points,
                              trigger_interval = trigger_interval)
        # Configuring apply smu
        self.read_sign = sign
        self.read_control_value = None
        if sign:  # Reset
            sweep_smu = self.BL_smu
            zero_smu = self.NL_smu
        else:  # Set
            sweep_smu = self.NL_smu
            zero_smu = self.BL_smu
        for smu in self.A_smu_list:
            self.resps.append(smu.set_smu_mode('voltage'))
        # Configuring triggers and source shapes
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.trigger_interval))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.trigger_interval))
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_measurement_range(range_type='normal'))
        for smu in self.B_smu_list:
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Configuring sweep
        self.resps.append(sweep_smu.set_sweep_output(stop=abs(v_stop), n_points=n_points, start=abs(v_start), 
                                                     double=double, compliance=current_compliance))
        self.resps.append(zero_smu.set_constant_output(output_level=0, compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_output(output_level=GATE_VOLTAGE, compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_output_level_immediate(output_level=GATE_VOLTAGE, compliance=1e-6))
        return self._check_config_and_start('SMU_IV_DC')
    
    
    def config_current_sweep(
        self, 
        trigger_interval: float, 
        i_start: float, 
        i_stop: float,
        n_points: int,
        double: bool,
        voltage_compliance: float,
        current_compliance: float = 0.1,  # 100 mA
        sign: int = 1
    ) -> tuple[bool, str]:
        """Configure Current sweep (DC) mode. WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            trigger_interval (float): Interval between triggers (seconds).
            i_start (float): Start current (Amperes).
            i_stop (float): Stop current (Amperes).
            n_points (int): Number of sweep points in a single direction 
                (doubled automatically for double IV curve).
            double (bool): True for double IV curve.
            voltage_compliance (float): Voltage compliance (Volts).
            current_compliance (float, optional): Current compliance which is applied on the secondary SMU connected 
                to the memristor. Defaults to 0.1 mA.
            sign (int, optional): Side where sweep current is applied: 1 -- BL, 0 -- NL.
                Defaults to 1.
                
        Returns:
            flag, response (tuple[bool, str]): Good_config_flag (True if instruments were 
            successfully configured), response or error.
        """
        self._set_init_values(mode='DC', 
                              trigger_count = 2 * n_points if double else n_points,
                              trigger_interval = trigger_interval,
                              control_value = 'current')
        # Configuring apply SMU
        self.read_sign = sign
        self.read_control_value = None
        if sign:  # Reset
            sweep_smu = self.BL_smu
            zero_smu = self.NL_smu
        else:  # Set
            sweep_smu = self.NL_smu
            zero_smu = self.BL_smu
        self.resps.append(sweep_smu.set_smu_mode('current'))
        self.resps.append(zero_smu.set_smu_mode('voltage'))
        # Configuring triggers and source shapes
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.trigger_interval))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.trigger_interval))
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_measurement_range(range_type='normal'))
        for smu in self.B_smu_list:
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Configuring sweep
        self.resps.append(sweep_smu.set_sweep_output(stop=abs(i_stop), n_points=n_points, start=abs(i_start), 
                                                     double=double, compliance=voltage_compliance))
        self.resps.append(zero_smu.set_constant_output(output_level=0, compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_output(output_level=GATE_VOLTAGE, compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_output_level_immediate(output_level=GATE_VOLTAGE, compliance=1e-6))
        return self._check_config_and_start('SMU_Current_Sweep_DC')
    
    
    def mode_7(  # TODO rework if needed
        self,
        pulse_width: float,
        apply_voltage: float,
        read_voltage: float,
        current_compliance: float,
        sign: int = 1
    ) -> tuple[bool, str, float]:
        """Apply mode 7 sequence: Apply voltage pulse followed by read pulse.
        WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            pulse_width (float): Apply and read pulses widths
            apply_voltage (float): Voltage to apply during the switch pulse (Volts).
            read_voltage (float): Voltage to apply during the read pulse (Volts).
            current_compliance (float): Current compliance (Amperes).
            sign (int, optional): Side where switch voltage is applied: 1 -- 'BL', 
                0 -- 'NL'. Defaults to 1.

        Returns:
            flag, response, resistance (bool, str, float): config_flag (True if configured 
            successfully), instrument_response (error if occurred), Resistance read by the read pulse.
        """
        if apply_voltage == 0:
            trigger_count = 1
        else:
            trigger_count = 2
        self._set_init_values(mode = 'pulse',
                              trigger_count = trigger_count,
                              pulse_width = pulse_width)
        self.resps.append(self.BL_smu.set_smu_mode('voltage'))
        self.resps.append(self.NL_smu.set_smu_mode('voltage'))
        # Configuring triggers and source shapes
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
            self.resps.append(smu.set_measurement_range(range_type='speed'))
        self.resps.append(self.gate_smu.set_source_shape('DC'))
        for smu in self.B_smu_list:
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Pulse mode for BL and NL
        for smu in self.A_smu_list:
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
        # Configuring pulses
        if apply_voltage == 0:
            BL_list, NL_list = [read_voltage], [0]
        else:
            if sign:  # Reset
                BL_list, NL_list = [apply_voltage, read_voltage], [0, 0]
            else: # Set
                BL_list, NL_list = [0, read_voltage], [apply_voltage, 0]
        self.read_side = 1
        self.resps.append(self.BL_smu.set_list_output(BL_list, compliance=current_compliance))
        self.resps.append(self.NL_smu.set_list_output(NL_list, compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_output(output_level=GATE_VOLTAGE, compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_output_level_immediate(output_level=GATE_VOLTAGE, compliance=1e-6))
        # Checking if configuration is set
        config_flag, response = self._check_config_and_start('mode_7')
        if not config_flag:
            return False, response, 0
        # Sense
        if apply_voltage != 0:
            self.sense()  # Skip first result
        sense_data = self.sense()
        if isinstance(sense_data, str):
            return False, response + '\n' + sense_data, 0
        return True, response, sense_data
    
    
    def config_std(
        self,
        volt_array: list[float],
        current_compliance: float,
        pulse_width: float,
        read_voltage: float,
        read_direction: float,
        sign: int = 1
    ) -> tuple[bool, str]:
        """Configure std mode (apply pulse + read pulse). WARNING: Method doesn't connect the 
        crossbar cell, it should be connected via .connect_cell() method.

        Args:
            volt_array (list[float]): Array of switch voltages to apply (no read pulses).
            current_compliance (float): Current compliance (Amperes).
            pulse_width (float): Pulse width (seconds).
            read_voltage (float): Read voltage (Read pulse is applied after each switch pulse).
            read_direction (int): Side where read pulse is applied: 1 -- 'BL', 0 -- 'NL'. 
            sign (int, optional): Side where sweep voltage is applied: 1 -- 'BL', 0 -- 'NL'. 
                Defaults to 1.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        # Creating real pulse sequence
        pulse_sequences = {0: [], 1: []}  # Pulse sequences for each sign
        for v in volt_array:
            pulse_sequences[sign].append(abs(v))
            pulse_sequences[int(not sign)].append(0)
            pulse_sequences[read_direction].append(abs(read_voltage))
            pulse_sequences[int(not read_direction)].append(0)
        self.read_sign = read_direction
        self.read_control_value = read_voltage
        self._set_init_values(mode = 'pulse',
                              trigger_count = len(pulse_sequences[0]),
                              pulse_width = pulse_width,
                              trigger_needed = True,
                              skip_one_sense = True)
        # Triggers and source shapes
        for smu in self.smu_list:
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        for smu in self.A_smu_list:
            self.resps.append(smu.set_smu_mode('voltage'))
            self.resps.append(smu.set_trigger_BUS(self.trigger_count, acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
            self.resps.append(smu.set_measurement_range(range_type='speed'))
        for smu in self.B_smu_list:
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_trigger_external(pin=self.trigger_link_pin, count=self.trigger_count, 
                                                       acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_arm_BUS())
        # Voltage config
        self.resps.append(self.BL_smu.set_list_output(pulse_sequences[1], compliance=current_compliance))
        self.resps.append(self.NL_smu.set_list_output(pulse_sequences[0], compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_output(output_level=GATE_VOLTAGE, compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_output_level_immediate(output_level=GATE_VOLTAGE, compliance=1e-6))
        flag, resp = self._check_config_and_start('SMU_std', arm_B=True)
        return flag, resp
    
    
    def config_pulsed_retention(
        self,
        pulse_width: float,
        current_compliance: float,
        count: int,
        read_voltage: float,
        sign: int = 1,
        trigger_interval: float = 0
    ) -> tuple[bool, str]:
        """Configure pulsed retention mode. WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            pulse_width (float): Pulse width (seconds).
            current_compliance (float): Current compliance (Amperes).
            count (int): Number of read pulses.
            read_voltage (float): Read voltage (Volts).
            sign (int, optional): Side where voltage is applied: 1 -- 'BL', 0 -- 'NL'. 
                Defaults to 1.
            trigger_interval (float, optional): Trigger interval (seconds). If less then 5 * pulse_width,
                falls back to 2 * pulse_width. Defaults to 0.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        self._set_init_values(mode = 'pulse',
                              trigger_count = count,
                              pulse_width = pulse_width,
                              trigger_interval = trigger_interval)
        # Configuring triggers and source shapes
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        for smu in self.B_smu_list:
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Pulse mode for BL and NL
        for smu in self.A_smu_list:
            self.resps.append(smu.set_smu_mode('voltage'))
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
            self.resps.append(smu.set_measurement_range(range_type='speed'))
        # Voltage config
        self.read_sign = sign
        self.read_control_value = read_voltage
        if sign:  # Reset:
            BL_sequence = [abs(read_voltage)] * count
            NL_sequence = [0] * count
        else:
            BL_sequence = [0] * count
            NL_sequence = [abs(read_voltage)] * count
        self.resps.append(self.BL_smu.set_list_output(BL_sequence, compliance=current_compliance))
        self.resps.append(self.NL_smu.set_list_output(NL_sequence, compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_output(output_level=GATE_VOLTAGE, compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_output_level_immediate(output_level=GATE_VOLTAGE, compliance=1e-6))
        return self._check_config_and_start('SMU_pulsed_retention')
    
    
    def config_endurance(
        self,
        v_dir: float,
        v_rev: float,
        dir_cc: float,
        rev_cc: float,
        pulse_width: float,
        read_voltage: Union[float, str],
        read_direction: int,
        reverse: bool,
        count: int,
        trigger_interval: Union[float, None] = None
    ) -> tuple[bool, str]:
        """Configure endurance mode. WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            v_dir (float): Direct voltage in Volts (set).
            v_rev (float): Reverse voltage in Volts (reset).
            dir_cc (float): Direct current compliance in Amperes (set).
            rev_cc (float): Reverse current compliance in Amperes (reset).
            pulse_width (float): Pulse width (seconds).
            read_voltage (Union[float, str]): Read voltage (reads on reset).
            read_direction (int): Side where read voltage is applied: 1 -- BL, 0 -- NL. 
                Defaults to 1.
            reverse (int): 0 -- positive switch - negative switch cycle; 1 -- negative switch - positive switch cycle
            count (int): Number of endurance cycles.
            trigger_interval (Union[float, None]): Trigger interval, seconds (5 * pulse_width if None). Defaults to None.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        self._set_init_values(mode='pulse', trigger_count=4*count,
                              pulse_width=pulse_width, trigger_interval=trigger_interval,
                              skip_one_sense=True)
        # Configuring triggers and source shapes
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        for smu in self.B_smu_list:
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Pulse mode for BL and NL
        for smu in self.A_smu_list:
            self.resps.append(smu.set_smu_mode('voltage'))
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
            self.resps.append(smu.set_measurement_range(range_type='speed'))
        # Voltage config
        self.read_sign = read_direction
        self.read_control_value = read_voltage
        if reverse:  # rev-dir sequence
            if read_direction:  # Read on BL
                BL_seq = [abs(v_rev), abs(read_voltage), 0, abs(read_voltage)] * count
                NL_seq = [0, 0, abs(v_dir), 0] * count
            else:  # Read on NL
                BL_seq = [abs(v_rev), 0, 0, 0] * count
                NL_seq = [0, abs(read_voltage), abs(v_dir), abs(read_voltage)] * count
        else:  # dir-rev sequence
            if read_direction:  # Read on BL
                BL_seq = [0, abs(read_voltage), abs(v_rev), abs(read_voltage)] * count
                NL_seq = [abs(v_dir), 0, 0, 0] * count
            else:  # Read on NL
                BL_seq = [0, 0, abs(v_rev), 0] * count
                NL_seq = [abs(v_dir), abs(read_voltage), 0, abs(read_voltage)] * count
        self.resps.append(self.BL_smu.set_list_output(output_list=BL_seq, 
                                                      compliance=rev_cc,
                                                      negative_compliance=dir_cc))
        self.resps.append(self.NL_smu.set_list_output(output_list=NL_seq, 
                                                      compliance=dir_cc,
                                                      negative_compliance=rev_cc))
        return self._check_config_and_start('SMU_endurance')
    
    
    def config_pot_dep(
        self,
        voltage: float,
        compliance: float,
        count: int,
        sign: int,
        pulse_width: float,
        trigger_interval: Union[float, None] = None
    ) -> tuple[bool, str]:
        """Configure endurance mode. WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            voltage (float): Voltage in Volts.
            compliance (float): Current compliance in Amperes.
            count (int): Number of pulses.
            sign (int): 0 for Set, 1 for Reset.
            pulse_width (float): Pulse width (seconds).
            trigger_interval (Union[float, None]): Trigger interval, seconds (5 * pulse_width if None). Defaults to None.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        self._set_init_values(mode='pulse', trigger_count=count,
                              pulse_width=pulse_width, trigger_interval=trigger_interval)
        # Configuring triggers and source shapes
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        for smu in self.B_smu_list:
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Pulse mode for BL and NL
        for smu in self.A_smu_list:
            self.resps.append(smu.set_smu_mode('voltage'))
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
            self.resps.append(smu.set_measurement_range(range_type='speed'))
        # Voltage config
        self.read_sign = sign
        self.read_control_value = None
        if sign:  # Apply to BL
            BL_seq = [abs(voltage)] * count
            NL_seq = [0] * count
        else:  # Apply to NL
            BL_seq = [0] * count
            NL_seq = [abs(voltage)] * count
        self.resps.append(self.BL_smu.set_list_output(output_list=BL_seq, 
                                                      compliance=compliance))
        self.resps.append(self.NL_smu.set_list_output(output_list=NL_seq, 
                                                      compliance=compliance))
        return self._check_config_and_start('SMU_pot_dep')

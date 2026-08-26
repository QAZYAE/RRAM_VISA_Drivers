"""
Драйвер для измерения кроссбаров мемристоров на установке в ЦИРе. Использует один 
модуль B2902B (через зондовую станцию или другое подключение). 
"""
import pyvisa
import time
import numpy as np
from typing import Union
from RRAM_VISA_Drivers.core import GeneralDriver
from RRAM_VISA_Drivers.SMU_drivers import B2902B, Keysight_SMU
from RRAM_VISA_Drivers.core.temperature import K_volt2temp



def signed(value: float, sign: int) -> float:
    """Apply sign to the value"""
    if sign:
        return -abs(float(value))
    return abs(float(value))



class ITC_probe_station(GeneralDriver):
    """Driver for measuring measuring memristors using one channel of the B2902B.
    
    Attributes:
        trigger_interval (float): Interval between triggers in seconds.
        trigger_count (int): Trigger count for current experiment.
        acquired_counter (int): Number of resistances acquired via sense(). Resets on config or clear.
        trigger_needed (bool): If True, a trigger is sent before each .sense().
        skip_one_sense (bool): If True, one sense value is skipped on each .sense() (for pulse sequences switch+read).
        sign (int): Sign of the read values in current experiment.
        read_control_value (float | None): This variable contains voltage or current applied during read pulse, used to calculate resistance.
            If None resistance is calculated by 'vol' variable passed to .sense() method.
        control_value (str): Unit which is controlled in the experiment (voltage or current).
        need_stop (bool): Flag that can be set to True for GUI. Used if the driver is stuck in
            acquire loop and user wants to stop the experiment.
        sense_size (int | None): Size of data to read from the instrument's buffer in .sense().
        queue (list): Results queue that fills while reading the data from instruments.
        sim (str): True for simulation mode.
        enable_temperature (bool): If True, temperature measurement is enabled.
        smu_list (list): List of SMUs to use in standard configurations.
        smu_channels (str): String of channels used in the setup ('1' | '2' | '1,2').
    """
    trigger_interval: float = 100e-6
    trigger_count: int = 0
    acquired_counter: int = 0
    trigger_needed: bool = False
    skip_one_sense: bool = False
    sign: int = 0
    read_control_value: Union[float, None] = None
    control_value: str = 'voltage'
    need_stop: bool = False
    sense_size: Union[int, None] = None
    queue: list = []
    sim: str = False
    enable_temperature: bool
    smu_list: list[Keysight_SMU]
    smu_channels: str
    batch_size: int = 10000  # Max array length the driver can handle
    
    def __init__(
        self, 
        B2902B_address: str, 
        VISA_library_path: str = ''
    ) -> None:
        """Driver for measuring measuring memristors using one channel of the B2902B.

        Args:
            B2902B_address (str): VISA-address for Keysight B2902B which controls 
                the measurement.
            VISA_library_path (str, optional): Path to VISA library. If not provided, 
                pyvisa tries to find the library on the computer. Defaults to ''.
        """
        super().__init__()
        # Check if in simulation mode
        if B2902B_address is None or B2902B_address == '':
            self.sim = True
            A_res = None
        else:
            self.sim = False
            # Creating ResourceManager
            if VISA_library_path == '':
                self.rm = pyvisa.ResourceManager()
            else:
                self.rm = pyvisa.ResourceManager(VISA_library_path)
            # Opening resources
            A_res = self.rm.open_resource(B2902B_address)
        self.A = B2902B(resource=A_res, instrument_name='B2902B', scpi_logger=self.scpi_logger)
        # Config
        self.enable_temperature = eval(self.settings['ITC_probe_station']['Measure_temperature'])
        if self.settings['ITC_probe_station']['Memristor_channel'] == '1':
            self.mem_smu = self.A.SMU1
            self.temp_smu = self.A.SMU2
        else:
            self.mem_smu = self.A.SMU2
            self.temp_smu = self.A.SMU1
        if self.enable_temperature:
            self.smu_list = [self.mem_smu, self.temp_smu]
            self.smu_channels = '1,2'
        else:
            self.smu_list = [self.mem_smu]
            self.smu_channels = self.settings['ITC_probe_station']['Memristor_channel']
        # Checking connection and instrument types
        flag = self.A.check_instrument_connection()
        self.A.get_errors()  # Clear error queue
        if not flag:
            self.logger.critical('B2902B probe station driver init error!')
            raise ConnectionError('Could not connect to the instrument!')
        resps = []  # Response list
        # Resetting the instruments
        resps.append(self.A.clear())
        resps.append(self.A.set_standby_zero())
        resps.append(self.A.set_output_state('on'))
        resps.append(self.A.set_output_filter('off'))
        # Set multimeter mode for temperature smu
        if self.enable_temperature:
            resps.append(self.temp_smu.set_multimeter_mode(voltage_compliance=1))
        resps.append(self.mem_smu.set_smu_mode('voltage'))
        # Configuring data output format
        resps.append(self.A.set_data_format('voltage,current,time'))
        # Configuring triggers
        for smu in self.smu_list:
            resps.append(smu.set_arm_BUS())
        # Checking if errors occurred
        for r in resps:
            if r.startswith('ERROR'):
                self.logger.error(f'B2902B probe station init error!\n{r}')
                raise ConnectionError(r)
        # Checking instrument error queue
        err = self.A.get_errors()
        if err is not None:
            self.logger.error('B2902B probe station init error!')
            self.logger.error('Instrument B2902B:\n\t' + '\n\t'.join(err))
            raise ConnectionError(f'Error in B2902B error queue: {err}')
        # Beeping
        self.A.beep(frequency=1000, time=0.2)
        time.sleep(0.2)
        self.A.beep(frequency=1000, time=0.2)
        self.logger.info('B2902B probe station driver: init success')
        
        
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'B2902B_probe_station_driver: uses Keysight B2902B Source-Measure' + \
               'module for measuring memristors'
               
    
    def clear_instruments(self) -> bool:
        """Clear SMU instruments on ticket end or when terminated.

        Returns:
            cleared (bool): True if instruments were cleared.
        """
        resp = self.A.clear()
        self.acquired_counter = 0
        if resp.startswith('ERROR'):
            self.logger.critical(f'Could not clear the instruments!\n\t{resp}')
            return False
        self.logger.info('Instruments were cleared')
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
        resps.append(self.A.set_output_state('off'))
        resps.append(self.A.beep(frequency=1200, time=0.2))
        time.sleep(0.2)
        resps.append(self.A.beep(frequency=1000, time=0.2))
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
        flag = self.clear_instruments()
        if flag:
            self.logger.info('VISA-instruments are in standby mode')
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
        resps.append(self.A.set_output_state('off'))
        for smu in self.smu_list:
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
            self.logger.debug(f'Errors after panic:\n\t{err_A}')
            resps.append(self.A.set_output_state('on'))
            self.logger.critical('Panic resolved!')
        else:
            self.logger.error('Panic was not resolved!\n\t' + '\n\t'.join(resps))
        return flag, '\n'.join(resps)
    
    
    def _random_sense(self, include_time: bool = True, vol: Union[float, None] = None) -> tuple[np.ndarray]:
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
                if self.settings['ITC_probe_station']['Memristor_channel'] == '1':
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
                if self.settings['ITC_probe_station']['Memristor_channel'] == '1':
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
            sense1, sense2 = [signed(v1, self.sign), signed(i1, self.sign), timestamp], [signed(v2, self.sign), signed(i2, self.sign), timestamp]
        else:
            sense1, sense2 = [signed(v1, self.sign), signed(i1, self.sign)], [signed(v2, self.sign), signed(i2, self.sign)]
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
                        r = signed(vol_cur, self.sign) / smu_cur
                else:  # Calculate by read_control_value (voltage)
                    r = self.read_control_value / smu_cur
            if r <= 0:
                r = np.inf  # Replace with infinity
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
                            r = smu_vol / signed(vol_cur, self.sign)
                else:  # Calculate by read_control_value (current)
                    r = smu_vol / self.read_control_value
            r = max(0, r)
        return r
    
    
    def sense(self, acquire_attempts: int = 200, vol: Union[float, None] = None) -> Union[tuple[float], str]:
        """Read sense data from the instrument. Updates the result queue and returns a 
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
            else:  # Acquire from real instruments
                # Trigger
                if self.trigger_needed:
                    self.logger.debug('SENSE TRIGGER')
                    if self.skip_one_sense:
                        f1, r1 = self.trigger()
                        time.sleep(1.1*self.trigger_interval)
                        f2, r2 = self.trigger()
                        flag = f1 and f2
                        if not flag:
                            return str(r1) + str(r2)
                    else:
                        flag, response = self.trigger()
                        if not flag:
                            return response
                # ACQUIRE
                for i in range(acquire_attempts):
                    sense_data_A = self.A.get_sense_data(channels=self.smu_channels, offset=self.acquired_counter, size=self.sense_size)  # sense_ch1, sense_ch2
                    self.logger.debug(f'Sense_A: acquire attempt {i}: {sense_data_A}')
                    if sense_data_A is not None:
                        break
                    if self.need_stop:
                        self.logger.warning('Sense_A: Need stop flag received!')
                        break
                    time.sleep(sleep_time)
                self.logger.debug(f'Measurement condition: {self.A.query("status:measurement:condition?")}')
                self.logger.debug(f'Questionable condition: {self.A.query("status:questionable:condition?")}')
                if sense_data_A is None:
                    self.logger.error('Cant obtain sense_A data!')
                    self.save_logs()
                    sense_data_A = self._get_nan_sense()  # WARNING: returns np.nan to the GUI if sense failed
                if isinstance(sense_data_A, str):
                    self.logger.error(f'Sense_A acquire error: {sense_data_A}')
                    self.save_logs()
                    return sense_data_A
                self.logger.debug('Sense_A acquired')
                sense1, sense2 = sense_data_A
                self.logger.debug(f'LENGTHS: sense1_A: {len(sense1)}, sense2_A: {len(sense2)}')
            # PARSING DATA
            if self.settings['ITC_probe_station']['Memristor_channel'] == '1':
                sense_mem = sense1
                sense_temp = sense2
            else:
                sense_mem = sense2
                sense_temp = sense1
            if self.skip_one_sense:
                step = 6  # Array step
            else:
                step = 3
            V = sense_mem[0::step]
            Curr = sense_mem[1::step]
            timestamp = self.exp_start_time + sense_mem[2::step]
            # Temperature
            if self.enable_temperature:
                V_temp = sense_temp[0::step]
                Temp = K_volt2temp(V_temp, room_temp=float(self.settings['temperature']['room_temperature']))
            else:
                V_temp, Temp = [np.nan] * len(V), [np.nan] * len(V)  # TODO: remove
            self.logger.debug(f'Sense_data acquired: V = {V}, curr = {Curr}, Time={timestamp}, V_temp={V_temp}, Temp={Temp}')
            for t, v, cur, tem, v_t in zip(timestamp, V, Curr, Temp, V_temp):
                self.queue.append((t, v, cur, tem, v_t))
            if self.skip_one_sense:
                counter_delta = 2 * min(len(V), len(Temp))
            else:
                counter_delta = min(len(V), len(Temp))
            self.acquired_counter += counter_delta
            # Checking if to much data is read on each .sense()
            if counter_delta > 20:
                self.sense_size = 20  # Limiting the read size till the end of the experiment
            # Checking if reading data is finished
            if self.trigger_count - self.acquired_counter <= 20:
                self.sense_size = None
        try:
            self.logger.debug(f'ACQUIRED COUNTER (AFT): {self.acquired_counter}')
            data_to_send = self.queue.pop(0)
            r = self._res_for_plot(data_to_send, vol_cur=vol)
            self.logger.info(f'Data returned: {[r, *data_to_send]}')
            # self.logger.warning(f'Temperature: {data_to_send[4]} C')
            # print(f'Temperature: {data_to_send[4]} C')
            return [r, *data_to_send]  # Tuple[R, time, v, cur, Temp, V_temp]
        except IndexError as e:
            self.logger.error(f'Sense queue is empty! Error: {e}')
            return 'Sense queue is empty!'
        
        
    def trigger(self, attempts: int = 200, sleep_time: float = 0.001) -> tuple[bool, str]:
        """Send immediate trigger, skip one acquire value
        
        Returns:
            flag, response (tuple[bool, str]): flag is True if the trigger was 
            sent successfully, response or error.
        """
        self.logger.debug(f'.trigger() TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}')
        for i in range(attempts):
            flag, resp = self.A.check_armed()  # Check if A is ready for trigger
            if not flag:
                self.logger.debug(f'.trigger(): Attempt {i}: A is not armed! A status: {resp}')
            else:
                break
            time.sleep(sleep_time)
        if not flag:
            self.logger.error(f'.trigger(): A is not armed in {attempts} attempts! A status: {resp}')
            self.save_logs()
            return False, f'.trigger(): A is not armed! A status: {resp}'
        resp = self.A.trigger(self.smu_channels)  # Trigger A
        if resp.startswith('ERROR'):
            self.logger.error(f'.sense(): A trigger error: {resp}')
            self.save_logs()
            return False, f'.sense(): A trigger error: {resp}'
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
        self.acquired_counter = int(skip_one_sense)  # If skip_one_sense, skip first voltage pulse
        self.need_stop = False
        self.sense_size = None
        self.trigger_needed = trigger_needed
        self.skip_one_sense = skip_one_sense
        self.control_value = control_value
        self.queue = []
        self.resps = []  # Response list
        # Clearing
        self.resps.append(self.A.clear())
        self.resps.append(self.A.wait_for_idle(wait_interval=0.1*self.trigger_interval))
        
        
    def _check_config_and_start(self, mode_name: str, arm_B: bool = False) -> tuple[bool, str]:  # TODO move to GeneralDriver (?)
        """Check if the instrument was configured without errors"""
        response = ''
        bad_config_flag = False
        for resp in self.resps:
            if resp.startswith('ERROR'):
                response += resp
                bad_config_flag = True
        err = self.A.get_errors()
        if err is not None:
            response += '\n\t'.join(err)
            bad_config_flag = True
        if bad_config_flag:
            self.logger.error(response)
            return False, response
        self.logger.info(f'{mode_name} config success!')
        # Start the experiment
        resp = self.A.initiate(channel=self.smu_channels)
        self.logger.debug(f'A initiated. Response: {resp}')
        self.logger.debug(f'.config() TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}')
        flag, resp = self.A.check_initiated(channel=self.smu_channels)
        if flag:
            self.logger.debug(f'A is ready. Status: {resp}')
            resp = self.A.arm(channel=self.smu_channels)
            self.logger.debug(f'ARM trigger sent to A. Response: {resp}')
        else:
            self.logger.error(f'A is not ready for ARM trigger! Status: {resp}')
            return False, f'A is not ready for ARM trigger! Status: {resp}'
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
            sign (int, optional): Side where sweep voltage is applied: 1 -- negative voltage, 0 -- positive voltage.
                Defaults to 1.

        Returns:
            flag, response (tuple[bool, str]): Good_config_flag (True if instruments were 
            successfully configured), response or error.
        """
        self._set_init_values(mode='DC', 
                              trigger_count = 2 * n_points if double else n_points,
                              trigger_interval = trigger_interval)
        # Configuring triggers and source shapes
        self.resps.append(self.mem_smu.set_smu_mode('voltage'))
        self.sign = sign
        self.read_control_value = None
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.trigger_interval))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.trigger_interval))
            self.resps.append(smu.set_source_shape('DC'))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='normal'))
        # Configuring sweep
        self.resps.append(self.mem_smu.set_sweep_output(stop=signed(v_stop, sign), 
                                                        n_points=n_points, 
                                                        start=signed(v_start, sign), 
                                                        double=double, 
                                                        compliance=current_compliance))
        return self._check_config_and_start('SMU_IV_DC')
    
    
    def config_current_sweep(
        self, 
        trigger_interval: float, 
        i_start: float, 
        i_stop: float,
        n_points: int,
        double: bool,
        voltage_compliance: float,
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
            sign (int, optional): Side where sweep current is applied: 1 -- negative current, 0 -- positive current.
                Defaults to 1.

        Returns:
            flag, response (tuple[bool, str]): Good_config_flag (True if instruments were 
            successfully configured), response or error.
        """
        self._set_init_values(mode='DC', 
                              trigger_count = 2 * n_points if double else n_points,
                              trigger_interval = trigger_interval,
                              control_value = 'current')
        self.sign = sign
        self.read_control_value = None
        # Configuring triggers and source shapes
        self.resps.append(self.mem_smu.set_smu_mode('current'))
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.trigger_interval))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.trigger_interval))
            self.resps.append(smu.set_source_shape('DC'))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='normal'))
        # Configuring sweep
        self.resps.append(self.mem_smu.set_sweep_output(stop=signed(i_stop, sign), 
                                                        n_points=n_points, 
                                                        start=signed(i_start, sign), 
                                                        double=double, 
                                                        compliance=voltage_compliance))
        return self._check_config_and_start('SMU_Current_Sweep_DC')
    
    
    def mode_7(  # TODO rework if needed
        self,
        pulse_width: float,
        apply_voltage: float,
        read_voltage: str,
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
            sign (int, optional): Side where switch voltage is applied: 1 -- negative voltage, 0 -- positive voltage.
                Defaults to 1.

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
        # Configuring triggers and source shapes
        self.resps.append(self.mem_smu.set_smu_mode('voltage'))
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        # Pulse mode memristor smu
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        # Configuring pulses
        if apply_voltage == 0:
            smu_list = [-float(read_voltage)]  # Read on reset
        else:
            if sign:  # Reset
                smu_list = [-float(apply_voltage), -float(read_voltage)]
            else: # Set
                smu_list = [float(apply_voltage), -float(read_voltage)]
        self.resps.append(self.mem_smu.set_list_output(smu_list, compliance=current_compliance))
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
            read_direction (int): Side where read pulse is applied: 1 -- negative voltage, 0 -- positive voltage. 
            sign (int, optional): Side where sweep voltage is applied: 1 -- negative voltage, 0 -- positive voltage. 
                Defaults to 1.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        # Creating real pulse sequence
        pulse_sequence = []
        for v in volt_array:
            pulse_sequence.append(signed(v, sign))
            pulse_sequence.append(signed(read_voltage, read_direction))
        # Initial values
        self._set_init_values(mode = 'pulse',
                              trigger_count = len(pulse_sequence),
                              pulse_width = pulse_width,
                              trigger_needed = True,
                              skip_one_sense = True)
        self.sign = read_direction
        self.read_control_value = signed(read_voltage, read_direction)
        # Triggers and source shapes
        self.resps.append(self.mem_smu.set_smu_mode('voltage'))
        for smu in self.smu_list:
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
            self.resps.append(smu.set_trigger_BUS(self.trigger_count, acquire_delay=0.3*self.pulse_width))
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        if self.enable_temperature:
            self.resps.append(self.temp_smu.set_source_shape('DC'))
        # Voltage config
        self.resps.append(self.mem_smu.set_list_output(pulse_sequence, compliance=current_compliance))
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
            sign (int, optional): Side where voltage is applied: 1 -- negative voltage, 0 -- positive voltage. 
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
        self.sign = sign
        self.read_control_value = signed(read_voltage, sign)
        # Configuring triggers and source shapes
        self.resps.append(self.mem_smu.set_smu_mode('voltage'))
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        if self.enable_temperature:
            self.resps.append(self.temp_smu.set_source_shape('DC'))
        # Pulse mode for BL and NL
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        # Voltage config
        self.resps.append(self.mem_smu.set_list_output([signed(read_voltage, sign)] * count, compliance=current_compliance))
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
            read_direction (int): Side where read voltage is applied: 1 -- negative voltage, 0 -- positive voltage. 
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
        self.resps.append(self.mem_smu.set_smu_mode('voltage'))
        self.sign = read_direction
        self.read_control_value = signed(read_voltage, read_direction)
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        if self.enable_temperature:
            self.resps.append(self.temp_smu.set_source_shape('DC'))
        # Pulse mode for BL and NL
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        # Voltage config
        rev_list = [signed(v_rev, 1), signed(read_voltage, read_direction)]
        dir_list = [signed(v_dir, 0), signed(read_voltage, read_direction)]
        if reverse:
            voltage_list = (rev_list + dir_list) * count
        else:
            voltage_list = (dir_list + rev_list) * count
        self.resps.append(self.mem_smu.set_list_output(output_list=voltage_list, 
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
            count (int): Number of pulses.
            compliance (float): Current compliance in Amperes.
            sign (int): 0 for Set, 1 for Reset.
            pulse_width (float): Pulse width (seconds).
            trigger_interval (Union[float, None]): Trigger interval, seconds (5 * pulse_width if None). Defaults to None.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        self._set_init_values(mode='pulse', trigger_count=count,
                            pulse_width=pulse_width, trigger_interval=trigger_interval)
        self.sign = sign
        self.read_control_value = None
        # Configuring triggers and source shapes
        self.resps.append(self.mem_smu.set_smu_mode('voltage'))
        for smu in self.smu_list:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        if self.enable_temperature:
            self.resps.append(self.temp_smu.set_source_shape('DC'))
        # Pulse mode for BL and NL
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        # Voltage config
        voltage_list = [signed(voltage, sign)] * count
        self.resps.append(self.mem_smu.set_list_output(output_list=voltage_list, 
                                                        compliance=compliance))
        return self._check_config_and_start('SMU_pot_dep')
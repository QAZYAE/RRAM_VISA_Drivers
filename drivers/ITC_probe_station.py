"""
Драйвер для измерения кроссбаров мемристоров на установке в ЦИРе. Использует один 
модуль B2902B (через зондовую станцию или другое подключение). 
"""
import pyvisa
import time
import numpy as np
from typing import Union
from RRAM_VISA_Drivers.core import GeneralDriver
from RRAM_VISA_Drivers.SMU_drivers import B2902B
from RRAM_VISA_Drivers.core.temperature import K_volt2temp
from RRAM_VISA_Drivers.core.gui_connection import set_driver_instruments, check_connection_B2902B



set_driver_instruments(
    driver_name='ITC_probe_station', 
    instruments={
        'B2902B (Mem,T)': check_connection_B2902B,
    }
)



class ITC_probe_station(GeneralDriver):
    """Driver for measuring measuring memristors using one channel of the B2902B.
    
    Attributes:
        trigger_interval (float): Interval between triggers in seconds.
        trigger_count (int): Trigger count for current experiment.
        acquired_counter (int): Number of resistances acquired via sense(). Resets on config or clear.
        need_stop (bool): Flag that can be set to True for GUI. Used if the driver is stuck in
            acquire loop and user wants to stop the experiment.
        queue (list): Results queue that fills while reading the data from instruments.
        sim (str): True for simulation mode.
    """
    trigger_interval: float = 100e-6
    trigger_count: int = 0
    acquired_counter: int = 0
    need_stop: bool = False
    queue: list = []
    sim: str = False
    
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
        self.A = B2902B(resource=A_res, instrument_name='B2902B')
        # Config
        if self.settings['ITC_probe_station']['Memristor_channel'] == '1':
            self.mem_smu = self.A.SMU1
            self.temp_smu = self.A.SMU2
        else:
            self.mem_smu = self.A.SMU2
            self.temp_smu = self.A.SMU1
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
        resps.append(self.temp_smu.set_multimeter_mode(voltage_compliance=1))
        resps.append(self.mem_smu.set_smu_mode('voltage'))
        # Configuring data output format
        resps.append(self.A.set_data_format('voltage,current,time'))
        # Configuring triggers
        resps.append(self.A.SMU1.set_arm_BUS())
        resps.append(self.A.SMU2.set_arm_BUS())
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
        for smu in [self.A.SMU1, self.A.SMU2]:
            resps.append(smu.set_base_voltage_immediate(0, current_compliance=1e-6))
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
            self.A.get_errors()
            resps.append(self.A.set_output_state('on'))
            self.logger.critical('Panic resolved!')
        else:
            self.logger.error('Panic was not resolved!\n\t' + '\n\t'.join(resps))
        return flag, '\n'.join(resps)
    
    
    def _random_sense(self, include_time: bool = True) -> tuple[np.ndarray]:  # TODO move to GeneralDriver
        """Generates random sense samples in format (Voltage, Current) with size=acquired_counter+1
            (Size is the number of (Voltage, Current) pairs)
            
        Args:
            include_time (bool, optional): If True, includes timestamp in the sense data. Defaults to True.

        Returns:
            sense1, sense2 (tuple[np.ndarray]): sense samples for two channels.
        """
        V = np.random.randint(1, 10000, 2) / 1e3
        Curr = np.random.randint(1, 10000, 2) / 1e7
        if include_time:
            timestamp = self.acquired_counter * self.trigger_interval
            sense1, sense2 = [V[0], Curr[0], timestamp], [V[1], Curr[1], timestamp]
        else:
            sense1, sense2 = [V[0]/1000, Curr[0]], [V[1]/1000, Curr[1]]
        return np.array(sense1), np.array(sense2)
    
    
    def sense(self, acquire_attempts: int = 200, trigger: bool = False) -> Union[tuple[float], str]:
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
        if self.acquired_counter != self.trigger_count:  # Skip acquire if queue is full
            if self.sim:
                sense1, sense2 = self._random_sense()
            else:
                # Trigger
                if trigger:
                    self.logger.debug('SENSE TRIGGER')
                    flag, response = self.trigger(skip_acquire=False)
                    if not flag:
                        return response
                # ACQUIRE
                for i in range(acquire_attempts):
                    sense_data_A = self.A.get_sense_data(offset=self.acquired_counter)  # sense_ch1, sense_ch2
                    self.logger.debug(f'Sense_A: acquire attempt {i}: {sense_data_A}')
                    if sense_data_A is not None:
                        break
                    if self.need_stop:
                        self.logger.warning('Sense_A: Need stop flag received!')
                        break
                    time.sleep(sleep_time)
                if sense_data_A is None:
                    self.logger.error('Cant obtain sense_A data!')
                    return 'Cant obtain sense_A data!'
                if isinstance(sense_data_A, str):
                    self.logger.error(f'Sense_A acquire error: {sense_data_A}')
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
            V = sense_mem[0::3]
            Curr = sense_mem[1::3]
            timestamp = self.exp_start_time + sense_mem[2::3]
            R = np.abs(V / Curr)
            # Temperature
            V_temp = sense_temp[0::3]
            Temp = K_volt2temp(V_temp, room_temp=float(self.settings['temperature']['room_temperature']))
            self.logger.debug(f'Sense_data acquired: V = {V}, curr = {Curr}, R = {R}, Time={timestamp}, V_temp={V_temp}, Temp={Temp}')
            for r, t, v, cur, tem, v_t in zip(R, timestamp, V, Curr, Temp, V_temp):
                self.queue.append((r, t, v, cur, tem, v_t))
            self.acquired_counter += min(len(R), len(Temp))
        try:
            self.logger.debug(f'ACQUIRED COUNTER (AFT): {self.acquired_counter}')
            data_to_send = self.queue.pop(0)
            self.logger.info(f'Data returned: {data_to_send}')
            self.logger.warning(f'Temperature: {data_to_send[4]} C')
            # print(f'Temperature: {data_to_send[4]} C')
            return data_to_send  # Tuple[R, time, v, cur, Temp, V_temp]
        except IndexError as e:
            self.logger.error(f'Sense queue is empty! Error: {e}')
            return 'Sense queue is empty!'
        
        
    def trigger(self, skip_acquire: bool = True, attempts: int = 200, sleep_time: float = 0.001) -> tuple[bool, str]:
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
            return False, f'.trigger(): A is not armed! A status: {resp}'
        resp = self.A.trigger()  # Trigger A
        if resp.startswith('ERROR'):
            self.logger.error(f'.sense(): A trigger error: {resp}')
            return False, f'.sense(): A trigger error: {resp}'
        self.logger.debug('.trigger(): trigger sent to instrument A')
        if skip_acquire:
            self.acquired_counter += 1
        return True, 'Trigger was sent to the instruments'
    
    
    def _set_init_values(self, mode, trigger_count, trigger_interval = None, pulse_width = None) -> None:  # TODO move to GeneralDriver (?)
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
                if trigger_interval < 5 * self.pulse_width:
                    self.trigger_interval = 5 * self.pulse_width
                else:
                    self.trigger_interval = trigger_interval
        else:
            raise RuntimeError(f'_config_init_values: unknown mode: {mode}')
        self.trigger_count = trigger_count
        self.acquired_counter = 0
        self.need_stop = False
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
        resp = self.A.initiate()
        self.logger.debug(f'A initiated. Response: {resp}')
        self.logger.debug(f'.config() TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}')
        flag, resp = self.A.check_initiated()
        if flag:
            self.logger.debug(f'A is ready. Status: {resp}')
            resp = self.A.arm()
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
            sign (int, optional): Side where sweep voltage is applied: 1 -- 'BL', 0 -- 'NL'.
                Defaults to 1.

        Returns:
            flag, response (tuple[bool, str]): Good_config_flag (True if instruments were 
            successfully configured), response or error.
        """
        self._set_init_values(mode='DC', 
                              trigger_count = 2 * n_points if double else n_points,
                              trigger_interval = trigger_interval)
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2]:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.trigger_interval))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.trigger_interval))
            self.resps.append(smu.set_source_shape('DC'))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='normal'))
        # Configuring sweep
        if sign:  # Reset
            start = -float(v_start)
            stop = -float(v_stop)
        else:  # Set
            start = v_start
            stop = v_stop
        self.resps.append(self.mem_smu.set_sweep_voltage(stop=stop, n_points=n_points, start=start, 
                                                         double=double, current_compliance=current_compliance))
        return self._check_config_and_start('SMU_IV_DC')
    
    
    def mode_7(
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
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2]:
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
        self.resps.append(self.mem_smu.set_list_voltage(smu_list, current_compliance=current_compliance))
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
        pulse_width: float,
        pulse_sequence: list[float],
        read_flags: list[bool],
        current_compliance: float,
        sign: int = 1
    ) -> tuple[bool, str]:
        """Configure std mode (apply pulse + read pulse). WARNING: Method doesn't connect the 
        crossbar cell, it should be connected via .connect_cell() method.

        Args:
            pulse_width (float): Pulse width (seconds).
            pulse_sequence (list[float]): Pulse sequence, read pulses are also included here (Volts).
            read_flags (list[bool]): The flag is True if the pulse in the pulse sequence in a read pulse.
            current_compliance (float): Current compliance (Amperes).
            sign (int, optional): Side where sweep voltage is applied: 1 -- 'BL', 0 -- 'NL'. 
                Defaults to 1.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        self._set_init_values(mode = 'pulse',
                              trigger_count = len(pulse_sequence),
                              pulse_width = pulse_width)
        # Triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2]:
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
            self.resps.append(smu.set_trigger_BUS(self.trigger_count, acquire_delay=0.3*self.pulse_width))
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        self.resps.append(self.temp_smu.set_source_shape('DC'))
        # Voltage config
        smu_seq = []
        for pulse, read_flag in zip(pulse_sequence, read_flags):
            factor = -1 if (read_flag or sign) else 1  # Read on reset
            smu_seq.append(factor * float(pulse))
        self.resps.append(self.mem_smu.set_list_voltage(smu_seq, current_compliance=current_compliance))
        flag, resp = self._check_config_and_start('SMU_std', arm_B=True)
        return flag, resp
    
    
    def config_pulsed_retention(
        self,
        pulse_width: float,
        current_compliance: float,
        n_pulses: int,
        read_voltage: float,
        sign: int = 1,
        trigger_interval: float = 0
    ) -> tuple[bool, str]:
        """Configure pulsed retention mode. WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            pulse_width (float): Pulse width (seconds).
            current_compliance (float): Current compliance (Amperes).
            n_pulses (int): Number of read pulses.
            read_voltage (float): Read voltage (Volts).
            sign (int, optional): Side where sweep voltage is applied: 1 -- 'BL', 0 -- 'NL'. 
                Defaults to 1.
            trigger_interval (float, optional): Trigger interval (seconds). If less then 5 * pulse_width,
                falls back to 5 * pulse_width. Defaults to 0.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        self._set_init_values(mode = 'pulse',
                              trigger_count = n_pulses,
                              pulse_width = pulse_width,
                              trigger_interval=trigger_interval)
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2]:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        self.resps.append(self.temp_smu.set_source_shape('DC'))
        # Pulse mode for BL and NL
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        # Voltage config
        self.resps.append(self.mem_smu.set_list_voltage([-float(read_voltage)] * n_pulses, current_compliance=current_compliance))
        return self._check_config_and_start('SMU_pulsed_retention')
    
    
    def config_endurance(
        self,
        v_dir: float,
        v_rev: float,
        read_voltage: Union[float, str],
        n_cycles: int,
        dir_cc: float,
        rev_cc: float,
        pulse_width: float,
        trigger_interval: Union[float, None] = None
    ) -> tuple[bool, str]:
        """Configure endurance mode. WARNING: Method doesn't connect the crossbar cell, 
        it should be connected via .connect_cell() method.

        Args:
            v_dir (float): Direct voltage in Volts (set).
            v_rev (float): Reverse voltage in Volts (reset).
            read_voltage (Union[float, str]): Read voltage (reads on reset).
            n_cycles (int): Number of endurance cycles.
            dir_cc (float): Direct current compliance in Amperes (set).
            rev_cc (float): Reverse current compliance in Amperes (reset).
            pulse_width (float): Pulse width (seconds).
            trigger_interval (Union[float, None]): Trigger interval, seconds (5 * pulse_width if None). Defaults to None.

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        self._set_init_values(mode='pulse', trigger_count=4*n_cycles,
                              pulse_width=pulse_width, trigger_interval=trigger_interval)
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2]:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        self.resps.append(self.temp_smu.set_source_shape('DC'))
        # Pulse mode for BL and NL
        self.resps.append(self.mem_smu.set_source_shape('pulse'))
        self.resps.append(self.mem_smu.set_pulse_config(width=self.pulse_width))
        self.resps.append(self.mem_smu.set_measurement_range(range_type='speed'))
        # Voltage config
        voltage_list = [abs(float(v_dir)), -abs(float(read_voltage)), -abs(float(v_rev)), -abs(float(read_voltage))] * n_cycles
        self.resps.append(self.mem_smu.set_list_voltage(voltage_list=voltage_list, 
                                                        current_compliance=dir_cc,
                                                        negative_current_compliance=rev_cc))
        # TODO check if the way we set the compliance level actually works (Add :pulse ?)
        return self._check_config_and_start('SMU_endurance')
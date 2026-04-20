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
from RRAM_VISA_Drivers.SMU_drivers import B2902B
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
        read_side (int): SMU to read current from when using .sense(): 1 for BL, or 2 for NL.
        need_stop (bool): Flag that can be set to True for GUI. Used if the driver is stuck in 
            acquire loop and user wants to stop the experiment.
        queue (list): Results queue that fills while reading the data from instruments.
        sim (str): True for simulation mode.
    """
    trigger_interval: float = 100e-6
    trigger_count: int = 0
    acquired_counter: int = 0
    read_side: int = 1
    need_stop: bool = False
    queue: list = []
    sim: str = False
    
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
        self.A = B2902B(resource=B2902B_A_res, instrument_name='B2902B_A')  # Controls BL and NL
        self.B = B2902B(resource=B2902B_B_res, instrument_name='B2902B_B')  # Controls WL
        # Config
        if self.settings['ITC_1T1R']['Gate_channel'] == '1':
            self.gate_smu = self.B.SMU1
            self.temp_smu = self.B.SMU2
        else:
            self.gate_smu = self.B.SMU2
            self.temp_smu = self.B.SMU1
        if self.settings['ITC_1T1R']['BL_channel'] == '1':
            self.BL_smu = self.A.SMU1
            self.NL_smu = self.B.SMU2
            self._read_sides = {
                1: 1,  # BL -> SMU1
                2: 2
            }
        else:
            self.BL_smu = self.A.SMU2
            self.NL_smu = self.B.SMU1
            self._read_sides = {
                1: 2,  # BL -> SMU2
                2: 1
            }
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
        resps.append(self.A.set_external_trigger_link(pin=self.arm_link_pin, trigger_layer='arm', function='output', channel=1))
        resps.append(self.B.set_external_trigger_link(pin=self.arm_link_pin, trigger_layer='arm', function='input', channel=1))
        resps.append(self.A.set_external_trigger_link(pin=self.trigger_link_pin, trigger_layer='trigger', function='output', channel=1))
        resps.append(self.B.set_external_trigger_link(pin=self.trigger_link_pin, trigger_layer='trigger', function='input', channel=1))
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
        resps.append(self.gate_smu.set_base_voltage_immediate(0, current_compliance=1e-6))
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
        resps.append(self.gate_smu.set_base_voltage_immediate(0, current_compliance=1e-6))
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
        for smu in [self.A.SMU1, self.A.SMU2, self.gate_smu]:
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
            self.B.get_errors()
            resps.append(self.A.set_output_state('on'))
            resps.append(self.B.set_output_state('on'))
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
        
        
    def sense(self, acquire_attempts: int = 200, trigger: bool = False) -> Union[tuple[float, float], str]:
        """Read sense data from the instruments. Updates the result queue and returns a 
            result from the queue.
        
        Args:
            acquire_attempts (int, optional): Number of attempts to communicate with the instrument
                and acquire sense data. Defaults to 1000.
            trigger (bool, optional): If True, sends trigger command before acquire.

        Returns:
            resistance (float): First resistance in the queue.
        """
        # Calculating time to sleep between acquire attempts
        # if self.trigger_interval > 10e-3:
        #     sleep_time = 1e-3
        # else:
        sleep_time = 0.1 * self.trigger_interval
        self.logger.debug(f'ACQUIRED_COUNTER (BEFORE): {self.acquired_counter}, (trigger_count: {self.trigger_count})')
        if self.acquired_counter != self.trigger_count:  # Skip acquire if queue is full
            if self.sim:
                sense1, sense2 = self._random_sense()
                sense1_B, sense2_B = self._random_sense(include_time=False)
            else:
                # Trigger
                if trigger:
                    self.logger.debug(f'SENSE TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}, B: {self.B.check_trigger_status()}')
                    flag, resp = self.B.check_armed()  # Check if B is ready for trigger
                    if not flag:
                        self.logger.error(f'.sense(): B is not armed! B status: {resp}')
                        return f'.sense(): B is not armed! B status: {resp}'
                    resp = self.A.trigger()  # Trigger A
                    if resp.startswith('ERROR'):
                        self.logger.error(f'.sense(): A trigger error: {resp}')
                        return f'.sense(): A trigger error: {resp}'
                    else:
                        self.logger.debug('Sense: Trigger sent to instrument A')
                # ACQUIRE A
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
                # ACQUIRE B
                for i in range(acquire_attempts):
                    sense_data_B = self.B.get_sense_data(offset=self.acquired_counter)  # sense_ch1, sense_ch2
                    self.logger.debug(f'Sense_B: acquire attempt {i}: {sense_data_B}')
                    if (sense_data_B is not None and
                        len(sense_data_A[0])/3*2 <= len(sense_data_B[0]) and  # At least equal amount of data acquired
                        len(sense_data_A[1])/3*2 <= len(sense_data_B[1])):
                        break
                    if self.need_stop:
                        self.logger.warning('Sense_B: Need stop flag received!')
                        break
                    time.sleep(sleep_time)
                if sense_data_B is None:
                    self.logger.error('Cant obtain sense_B data!')
                    return 'Cant obtain sense_B data!'
                if isinstance(sense_data_B, str):
                    self.logger.error(f'Sense_B acquire error: {sense_data_B}')
                    return sense_data_B
                self.logger.debug('Sense_A and sense_B acquired')
                sense1, sense2 = sense_data_A
                sense1_B, sense2_B = sense_data_B
                self.logger.debug(f'LENGTHS: sense1_A: {len(sense1)}, sense2_A: {len(sense2)}, sense1_B: {len(sense1_B)}, sense2_B: {len(sense2_B)}')
                # TODO Save WL data
            # PARSING DATA
            # B data might be longer than A data
            if self._read_sides[self.read_side] == 1:
                primary_sense = sense1
            else:
                primary_sense = sense2
            V = primary_sense[0::3]
            Curr = primary_sense[1::3]
            timestamp = self.exp_start_time + primary_sense[2::3]
            R = np.abs(V / Curr) 
            # Temperature and WL
            if self.settings['ITC_1T1R']['Gate_channel'] == '1':
                # sense_gate = sense1_B
                sense_temp = sense2_B
            else:
                # sense_gate = sense2_B
                sense_temp = sense1_B
            V_temp = sense_temp[0:len(R)*2:2]
            Temp = K_volt2temp(V_temp, room_temp=float(self.settings['temperature']['room_temperature']))
            self.logger.debug(f'Sense_data acquired: V = {V}, curr = {Curr}, R = {R}, Time={timestamp}, V_temp={V_temp}, Temp={Temp}')
            for r, t, v, cur, tem, v_t in zip(R, timestamp, V, Curr, Temp, V_temp):
                self.queue.append((r, t, v, cur, tem, v_t))
            self.acquired_counter += len(R)
        try:
            self.logger.debug(f'ACQUIRED COUNTER (AFT): {self.acquired_counter}')
            data_to_send = self.queue.pop(0)
            self.logger.info(f'Data returned: {data_to_send}')
            self.logger.warning(f'Temperature: {data_to_send[4]} C')
            print(f'Temperature: {data_to_send[4]} C')
            return data_to_send  # Tuple[R, time]
        except IndexError:
            self.logger.error('Sense queue is empty!')
            return 'Sense queue is empty!'
        
        
    def trigger(self) -> tuple[bool, str]:
        """Send immediate trigger, skip one acquire value
        
        Returns:
            flag, response (tuple[bool, str]): flag is True if the trigger was 
            sent successfully, response or error.
        """
        self.logger.debug(f'.trigger() TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}, B: {self.B.check_trigger_status()}')
        flag, resp = self.B.check_armed()  # Check if B is ready for trigger
        if not flag:
            self.logger.error(f'.trigger(): B is not armed! B status: {resp}')
            return False, f'.trigger(): B is not armed! B status: {resp}'
        resp = self.A.trigger()  # Trigger A
        if resp.startswith('ERROR'):
            self.logger.error(f'.sense(): A trigger error: {resp}')
            return False, f'.sense(): A trigger error: {resp}'
        self.logger.debug('.trigger(): trigger sent to instrument A')
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
        resp = self.A.initiate()
        self.logger.debug(f'A initiated. Response: {resp}')
        resp = self.B.initiate()
        self.logger.debug(f'B initiated. Response: {resp}')
        self.logger.debug(f'.config() TRIGGER INSTRUMENT STATUS: A: {self.A.check_trigger_status()}, B: {self.B.check_trigger_status()}')
        if arm_B:  # If we need to send arm trigger to B
            resp = self.A.arm()
            self.logger.debug(f'ARM trigger sent to A. Response: {resp}')
            resp = self.B.arm()
            self.logger.debug(f'ARM trigger sent to B. Response: {resp}')
        else:
            flag, resp = self.B.check_initiated()
            if flag:
                self.logger.debug(f'B is ready. Status: {resp}')
                resp = self.A.arm()
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
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2, self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.trigger_interval))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.trigger_interval))
            self.resps.append(smu.set_source_shape('DC'))
        self.resps.append(self.B.SMU1.set_arm_external(pin=self.arm_link_pin))
        self.resps.append(self.B.SMU2.set_arm_external(pin=self.arm_link_pin))
        # Configuring sweep
        if sign:  # Reset
            sweep_smu = self.BL_smu
            zero_smu = self.NL_smu
            self.read_side = 1
        else:  # Set
            sweep_smu = self.NL_smu
            zero_smu = self.BL_smu
            self.read_side = 2
        self.resps.append(sweep_smu.set_sweep_voltage(stop=v_stop, n_points=n_points, start=v_start, 
                                                      double=double, current_compliance=current_compliance))
        self.resps.append(zero_smu.set_constant_voltage(voltage=0, current_compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_voltage(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_voltage_immediate(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        return self._check_config_and_start('SMU_IV_DC')
    
    
    def mode_7(
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
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2, self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                                    acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        self.resps.append(self.gate_smu.set_source_shape('DC'))
        self.resps.append(self.B.SMU1.set_arm_external(pin=self.arm_link_pin))
        self.resps.append(self.B.SMU2.set_arm_external(pin=self.arm_link_pin))
        # Pulse mode for BL and NL
        for smu in [self.A.SMU1, self.A.SMU2]:
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
        self.resps.append(self.BL_smu.set_list_voltage(BL_list, current_compliance=current_compliance))
        self.resps.append(self.NL_smu.set_list_voltage(NL_list, current_compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_voltage(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_voltage_immediate(voltage=GATE_VOLTAGE, current_compliance=1e-6))
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
        for smu in [self.A.SMU1, self.A.SMU2, self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        for smu in [self.A.SMU1, self.A.SMU2]:
            self.resps.append(smu.set_trigger_BUS(self.trigger_count, acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
        for smu in [self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_trigger_external(pin=self.trigger_link_pin, count=self.trigger_count, 
                                                       acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_arm_BUS())
        # Voltage config
        self.read_side = 1  # Read on reset
        BL_seq, NL_seq = [], []
        for pulse, read_flag in zip(pulse_sequence, read_flags):
            if read_flag:
                BL_seq.append(pulse)
                NL_seq.append(0)
            else:
                if sign:
                    BL_seq.append(pulse)
                    NL_seq.append(0)
                else:
                    BL_seq.append(0)
                    NL_seq.append(pulse)
        self.resps.append(self.BL_smu.set_list_voltage(BL_seq, current_compliance=current_compliance))
        self.resps.append(self.NL_smu.set_list_voltage(NL_seq, current_compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_voltage(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_voltage_immediate(voltage=GATE_VOLTAGE, current_compliance=1e-6))
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
        for smu in [self.A.SMU1, self.A.SMU2, self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        for smu in [self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Pulse mode for BL and NL
        for smu in [self.A.SMU1, self.A.SMU2]:
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
        # Voltage config
        self.read_side = 1  # Read on reset
        self.resps.append(self.BL_smu.set_list_voltage([read_voltage] * n_pulses, current_compliance=current_compliance))
        self.resps.append(self.NL_smu.set_list_voltage([0] * n_pulses, current_compliance=current_compliance))
        self.resps.append(self.gate_smu.set_constant_voltage(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        self.resps.append(self.gate_smu.set_base_voltage_immediate(voltage=GATE_VOLTAGE, current_compliance=1e-6))
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
        for smu in [self.A.SMU1, self.A.SMU2, self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.pulse_width))
            self.resps.append(smu.set_measurement_aperture(aperture=0.4*self.pulse_width))
        for smu in [self.gate_smu, self.temp_smu]:
            self.resps.append(smu.set_source_shape('DC'))
            self.resps.append(smu.set_arm_external(pin=self.arm_link_pin))
        # Pulse mode for BL and NL
        for smu in [self.A.SMU1, self.A.SMU2]:
            self.resps.append(smu.set_source_shape('pulse'))
            self.resps.append(smu.set_pulse_config(width=self.pulse_width))
        # Voltage config
        self.read_side = 1  # Read on reset
        BL_seq = [0, abs(float(read_voltage)), abs(float(v_rev)), abs(float(read_voltage))] * n_cycles
        NL_seq = [abs(float(v_dir)), 0, 0, 0] * n_cycles
        self.resps.append(self.BL_smu.set_list_voltage(voltage_list=BL_seq, 
                                                       current_compliance=rev_cc,
                                                       negative_current_compliance=dir_cc))
        self.resps.append(self.NL_smu.set_list_voltage(voltage_list=NL_seq, 
                                                       current_compliance=dir_cc,
                                                       negative_current_compliance=rev_cc))
        # TODO check if the way we set the compliance level actually works (Add :pulse ?)
        return self._check_config_and_start('SMU_endurance')
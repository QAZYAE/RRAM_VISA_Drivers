"""
Драйвер для управления двумя модулями B2902B для измерения кроссбаров
1T1R 32x8 (при помощи зондовой станции или коммутатора).
Первые пины на коннекторах D-Sub 25 устройств B2902B должны быть соединены проводом.
"""

import pyvisa 
import time
import numpy as np
from typing import Union
from RRAM_VISA_Drivers.SMU_drivers import B2902B


_sign = {  # Sign dict for applying voltage to BL(reset) and NL(set)
    1: 'BL',
    0: 'NL'
}

GATE_VOLTAGE = 3.3  # Voltage applied to transistor gate


class B2902B_1T1R_32x8_driver:
    """Driver for measuring 1T1R 32x8 crossbar arrays
    """
    trigger_interval: float = 100e-6  # Interval between triggers in seconds
    trigger_count: int = 0  # Trigger count for current experiment
    acquired_counter: int = 0  # Number of resistances acquired via sense(). Resets on config or clear
    last_sense_time: float = 0  # Time of the last sense 
    read_side: int = 1  # SMU to read current from when using .sense(): 1 or 2.
    queue: list = []
    sim: str = False  # True for simulation mode
    
    def __init__(
        self, 
        B2902B_A_res: Union[pyvisa.Resource, None],
        B2902B_B_res: Union[pyvisa.Resource, None],
        sim: bool = False
    ) -> None:
        """Driver for measuring 1T1R 32x8 crossbar arrays via two B2902B units

        Args:
            B2902B_A_res (pyvisa.Resource | None): _description_
            B2902B_B_res (pyvisa.Resource | None): _description_
        """
        self.sim = sim
        # Creating driver instances for the instruments
        self.A = B2902B(resource=B2902B_A_res, instrument_name='B2902B_A')  # Controls BL and NL
        self.B = B2902B(resource=B2902B_B_res, instrument_name='B2902B_B')  # Controls WL
        # Beeping
        self.A.beep(frequency=1000, time=0.2)
        time.sleep(0.2)
        self.B.beep(frequency=1200, time=0.2)
        # Checking connections and instrument types
        for inst, name in zip([self.A, self.B], 
                              ['B2902B_A', 'B2902B_B']):
            flag = inst.check_instument_connection()
            inst.get_errors()  # Clear error queue
            if not flag:
                print('B2902B 1T1R 32x8 driver init ERROR')
                raise ConnectionError(f'Could not connect to an instrument: {name}')
        resps = []  # Response list
        # Resetting instruments 
        for inst in [self.A, self.B]:
            resps.append(inst.clear())
            resps.append(inst.memory_reset())
            resps.append(inst.set_standby_zero())
            resps.append(inst.set_output_state('on'))
        # Configuring data output
        resps.append(self.A.set_data_format('voltage,current'))
        resps.append(self.B.set_data_format('voltage,current'))
        # Configuring triggers: Arm trigger is linked via pin 1 on D-Sub 25 connector
        resps.append(self.A.SMU1.set_arm_BUS())
        resps.append(self.A.SMU2.set_arm_BUS())
        resps.append(self.B.SMU1.set_arm_external(pin=1))  # todo: Вынести номер пина в файл конфигурации
        resps.append(self.A.set_external_trigger_link(pin=1, trigger_layer='arm', function='output', channel=1))
        resps.append(self.B.set_external_trigger_link(pin=1, trigger_layer='arm', function='input', channel=1))
        for r in resps:
            if r.startswith('ERROR'):
                print('B2902B 1T1R 32x8 driver init ERROR')
                raise ConnectionError(r)
        # Checking error queues
        for inst, name in zip([self.A, self.B], 
                              ['B2902B_A', 'B2902B_B']):
            err = inst.get_errors()
            if err is not None:
                print('B2902B 1T1R 32x8 driver init ERROR')
                raise ConnectionError(f'Error in {name} error queue: {err}')
        print('B2902B 1T1R 32x8 driver init success')
        
    
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'B2902B_1T1R_32x8_driver: uses with two Keysight B2902B Source-Measure ' + \
               'modules and a Keysight_34980A Switch unit for measuring 32x8 1T1R ' + \
               'memristor crossbar arrays'
    
        
    def clear_instruments(self) -> bool:
        """Clear SMU instruments on ticket end or when terminated.

        Returns:
            cleared (bool): True if instruments were cleared.
        """
        resps = []
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.B.SMU1.set_base_voltage_immediate(0, current_compliance=1e-6))
        self.last_sense_time = 0
        self.acquired_counter = 0
        for r in resps:
            if r.startswith('ERROR'):
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
        resps.append(self.B.SMU1.set_base_voltage_immediate(0, current_compliance=1e-6))
        resps.append(self.A.set_output_state('off'))
        resps.append(self.B.set_output_state('off'))
        resps.append(self.A.beep(frequency=1200, time=0.2))
        time.sleep(0.2)
        resps.append(self.B.beep(frequency=1000, time=0.2))
        # Checking errors
        for r in resps:
            if r.startswith('ERROR'):
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
        resps.append(self.A.set_output_state('off'))
        resps.append(self.B.set_output_state('off'))
        for smu in [self.A.SMU1, self.A.SMU2, self.B.SMU1]:
            resps.append(smu.set_base_voltage_immediate(0, current_compliance=1e-6))
        for r in resps:
            if r.startswith('ERROR'):
                flag = False
        return flag, '\n'.join(resps)
    
    
    def panic(self) -> tuple[bool, str]:
        """Panic mode for immediately stopping the experiment.

        Returns:
            flag, response (tuple[bool, str]): Resolved flag (True if panic was resolved), 
            response or error.
        """
        resps = []
        for _ in range(5):
            flag, response = self._panic_attempt()
            resps.append(response)
            if flag:
                break
        if flag:
            self.A.get_errors()
            self.B.get_errors()
            resps.append(self.A.set_output_state('on'))
            resps.append(self.B.set_output_state('on'))
        return flag, '\n'.join(resps)
    
    
    def _random_sense(self, acquired_counter: int) -> tuple[np.ndarray]:
        """Generates random sense samples in format (Voltage, Current) with size=acquired_counter+1
            (Size is the number of (Voltage, Current) pairs)

        Args:
            acquired_counter (int): acquired counter for previous .sense() operation.

        Returns:
            sense1, sense2 (tuple[np.ndarray]): sense samples for two channels.
        """
        V = np.random.randint(1, 10000, 2*(acquired_counter+1)) / 1e3
        Curr = np.random.randint(1, 10000, 2*(acquired_counter+1)) / 1e7
        sense1, sense2 = [], []
        for i in range(0, 2*(acquired_counter+1), 2):
            sense1 += [V[i], Curr[i]]
            sense2 += [V[i+1], Curr[i+1]]
        return np.array(sense1), np.array(sense2)
    
    
    def sense(self) -> np.ndarray:
        """Read sense data from the instruments. Returns resistance array with resistances
        which haven't been read yet.

        Returns:
            resistance (float): First resistance in the queue.
        """
        if self.acquired_counter != self.trigger_count:  # Skips acquire if the queue is full
            while time.time() < self.last_sense_time + self.trigger_interval:
                time.sleep(0.1 * self.trigger_interval)  # Skipping time to match instrument trigger
            if self.sim:
                sense1, sense2 = self._random_sense(self.acquired_counter)
            else:
                for _ in range(500):
                    sense_data = self.A.get_sense_data()
                    if sense_data is not None:
                        break
                    time.sleep(0.1 * self.trigger_interval)
                if sense_data is None:
                    return 'Cant obtain sense data!'
                if isinstance(sense_data, str):
                    return sense_data
                else:
                    sense1, sense2 = sense_data
                # TODO Save WL data
            self.last_sense_time = time.time()
            if self.read_side == 1:
                V = sense1[::2]
                Curr = sense1[1::2]
            elif self.read_side == 2:
                V = sense2[::2]
                Curr = sense2[1::2]
            R = np.abs(V / Curr)
            print(f'Driver: V = {V}, curr = {Curr}')
            for r in R[self.acquired_counter:]:
                self.queue.append(r)
            self.acquired_counter = len(R)
        try:
            R_sent = self.queue.pop(0)
            print(f'Driver: R_sent = {R_sent}')
            return R_sent
        except IndexError:
            return 'Sense queue is empty!'
        
        
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
        # Setting class fields
        print(trigger_interval, 
              v_start, 
              v_stop,
              n_points,
              double,
              current_compliance,
              _sign[sign])
        if trigger_interval < 100e-6:
            response = 'WARNING: Too short trigger interval. The interval is set to 100us (min value)\n\t'
            self.trigger_interval = 100e-6
        else:
            response = ''
            self.trigger_interval = trigger_interval
        self.trigger_count = 2 * n_points if double else n_points
        self.acquired_counter = 0
        self.queue = []
        resps = []  # Response list
        # Clearing
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.A.wait_for_idle())
        resps.append(self.B.wait_for_idle())
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2, self.B.SMU1]:
            resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.trigger_interval))
            resps.append(smu.set_measurement_aperture(aperture=0.4*self.trigger_interval))
            resps.append(smu.set_source_shape('DC'))
        # Configuring sweep
        if sign:  # Reset
            sweep_smu = self.A.SMU1
            zero_smu = self.A.SMU2
            self.read_side = 1
        else:  # Set
            sweep_smu = self.A.SMU2
            zero_smu = self.A.SMU1
            self.read_side = 2
        resps.append(sweep_smu.set_sweep_voltage(stop=v_stop, n_points=n_points, start=v_start, 
                                                 double=double, current_compliance=current_compliance))
        resps.append(zero_smu.set_constant_voltage(voltage=0, current_compliance=current_compliance))
        resps.append(self.B.SMU1.set_constant_voltage(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        resps.append(self.B.SMU1.set_base_voltage_immediate(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        # Checking if configuration is set
        bad_config_flag = False
        for resp in resps:
            if resp.startswith('ERROR'):
                response += resp
                bad_config_flag = True
        for inst in [self.A, self.B]:
            err = inst.get_errors()
            if err is not None:
                response = ''.join([response] + err)
                bad_config_flag = True
        if bad_config_flag:
            return False, response
        # Start the experiment
        self.A.initiate()
        self.B.SMU1.initiate()
        self.A.arm()
        time.sleep(self.trigger_interval)
        self.last_sense_time = time.time()
        return True, response + 'SMU_IV_DC was configured'
    
    
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
            successfully), instrument_response (error if occured), Resistance read by the read pulse.
        """
        if pulse_width < 100e-6:
            response = 'WARNING: Too short pulse width. The interval is set to 100us (min value)\n\t'
            pulse_width = 100e-6
            self.trigger_interval = 5 * pulse_width
        else:
            response = ''
            self.trigger_interval = 5 * pulse_width
        if apply_voltage == 0:
            self.trigger_count = 1
        else:
            self.trigger_count = 2
        self.acquired_counter = 0
        self.queue = []
        resps = []  # Response list
        # Clearing
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.A.wait_for_idle(wait_interval=0.1*self.trigger_interval))
        resps.append(self.B.wait_for_idle(wait_interval=0.1*self.trigger_interval))
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2, self.B.SMU1]:
            resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*pulse_width))
            resps.append(smu.set_measurement_aperture(aperture=0.4*pulse_width))
        resps.append(self.B.SMU1.set_source_shape('DC'))
        # Pulse mode for BL and NL
        for smu in [self.A.SMU1, self.A.SMU2]:
            resps.append(smu.set_source_shape('pulse'))
            resps.append(smu.set_pulse_config(width=pulse_width))
        # Configuring pulses
        if apply_voltage == 0:
            smu1_list, smu2_list = [read_voltage], [0]
        else:
            if sign:  # Reset
                smu1_list, smu2_list = [apply_voltage, read_voltage], [0, 0]
            else: # Set
                smu1_list, smu2_list = [0, read_voltage], [apply_voltage, 0]
        self.read_side = 1
        resps.append(self.A.SMU1.set_list_voltage(smu1_list, current_compliance=current_compliance))
        resps.append(self.A.SMU2.set_list_voltage(smu2_list, current_compliance=current_compliance))
        resps.append(self.B.SMU1.set_constant_voltage(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        resps.append(self.B.SMU1.set_base_voltage_immediate(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        # Checking if configuration is set
        bad_config_flag = False
        for resp in resps:
            if resp.startswith('ERROR'):
                response += '\n' + resp
                bad_config_flag = True
        for inst in [self.A, self.B]:
            err = inst.get_errors()
            if err is not None:
                response += '\t'.join(err)
                bad_config_flag = True
        if bad_config_flag:
            return False, response, 0
        # Apply the experiment
        self.A.initiate()
        self.B.SMU1.initiate()
        self.A.arm()
        time.sleep(self.trigger_interval)
        self.last_sense_time = time.time()
        if apply_voltage != 0:
            self.sense()  # Skip first result
        sense_data = self.sense()
        if isinstance(sense_data, str):
            return False, response + '\n' + sense_data, 0
        return True, response, sense_data
    
    
    def config_pulsed_retention(
        self,
        pulse_width: float,
        current_compliance: float,
        n_pulses: int,
        read_voltage: float,
        sign: int = 1
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

        Returns:
            tuple[bool, str]: Good_config_flag (True if instruments were
            successfully configured), response or error.
        """
        if pulse_width < 100e-6:
            response = 'WARNING: Too short pulse width. The interval is set to 100us (min value)\n\t'
            pulse_width = 100e-6
            self.trigger_interval = 5 * pulse_width
        else:
            response = ''
            self.trigger_interval = 5 * pulse_width
        self.trigger_count = n_pulses
        self.acquired_counter = 0
        self.queue = []
        resps = []  # Response list
        # Clearing
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.A.wait_for_idle(wait_interval=0.1*self.trigger_interval))
        resps.append(self.B.wait_for_idle(wait_interval=0.1*self.trigger_interval))
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2, self.B.SMU1]:
            resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*pulse_width))
            resps.append(smu.set_measurement_aperture(aperture=0.4*pulse_width))
        resps.append(self.B.SMU1.set_source_shape('DC'))
        # Pulse mode for BL and NL
        for smu in [self.A.SMU1, self.A.SMU2]:
            resps.append(smu.set_source_shape('pulse'))
            resps.append(smu.set_pulse_config(width=pulse_width))
        if sign:
            read_smu = self.A.SMU1
            zero_smu = self.A.SMU2
            self.read_side = 1
        else:
            zero_smu = self.A.SMU1
            read_smu = self.A.SMU2
            self.read_side = 2
        resps.append(read_smu.set_list_voltage([read_voltage] * n_pulses, current_compliance=current_compliance))
        resps.append(zero_smu.set_list_voltage([0] * n_pulses, current_compliance=current_compliance))
        resps.append(self.B.SMU1.set_constant_voltage(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        resps.append(self.B.SMU1.set_base_voltage_immediate(voltage=GATE_VOLTAGE, current_compliance=1e-6))
        # Checking if configuration is set
        bad_config_flag = False
        for resp in resps:
            if resp.startswith('ERROR'):
                response += '\n' + resp
                bad_config_flag = True
        for inst in [self.A, self.B]:
            err = inst.get_errors()
            if err is not None:
                response += '\t'.join(err)
                bad_config_flag = True
        if bad_config_flag:
            return False, response
        # Apply the experiment
        self.A.initiate()
        self.B.SMU1.initiate()
        self.A.arm()
        time.sleep(self.trigger_interval)
        self.last_sense_time = time.time()
        return True, response + 'SMU_pulsed_retention was configured'
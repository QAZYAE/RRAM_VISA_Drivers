"""
Драйвер для измерения кроссбаров 1T1R 32x8 на установке в ЦИРе. Использует два 
модуля B2902B и коммутатор 34980A. Первые пины на коннекторах D-Sub 25 устройств
B2902B должны быть соединены проводом.
"""

import pyvisa 
import numpy as np
import time
import os
from RRAM_VISA_Drivers.SMU_drivers import B2902B
from RRAM_VISA_Drivers.Switch_drivers import Keysight_34980A_1T1R_32x8



class CID_1T1R_32x8_driver:
    """Driver for measuring 1T1R 32x8 crossbar arrays.
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
        B2902B_1_address: str, 
        B2902B_2_address: str, 
        Switch_address: str,
        VISA_library_path: str = ''
    ) -> None:
        """Driver for measuring 1T1R 32x8 crossbar arrays.

        Args:
            B2902B_1_address (str): VISA-adress for Keysight B2902B which controls
                Bit Line (1st channel) and Net Line (2nd channel).
            B2902B_2_address (str): VISA-adress for Keysight B2902B which controls
                Word Line (1st channel).
            Switch_address (str): VISA-adress for Keysight 34980A which controls
                cell selection.
            VISA_library_path (str, optional): Path to VISA library. If not provided, 
                pyvisa tries to find the library on the computer. Defaults to ''.
        """
        # Check if in simulation mode
        self.sim = False
        for address in [B2902B_1_address, B2902B_2_address, Switch_address]:
            if address is None:
                self.sim = True
        if self.sim:
            A_res, B_res, Switch_res = None, None, None
        else:
            # Creating ResourceManager
            if VISA_library_path == '':
                self.rm = pyvisa.ResourceManager()
            else:
                self.rm = pyvisa.ResourceManager(VISA_library_path)
            # Opening resources
            A_res = self.rm.open_resource(B2902B_1_address)
            B_res = self.rm.open_resource(B2902B_2_address)
            Switch_res = self.rm.open_resource(Switch_address)
        # Creating driver instances for the instruments
        self.A = B2902B(resource=A_res, instrument_name='B2902B_A')  # Controls BL and NL
        self.B = B2902B(resource=B_res, instrument_name='B2902B_B')  # Controls WL
        self.switch = Keysight_34980A_1T1R_32x8(  # Controls cell selection in crossbar array
            resource=Switch_res, 
            config_path=os.path.join(os.getcwd(), 'RRAM_VISA_Drivers', 'config', 'Keysight_34980A_1T1R_32x8.json')
        )
        # Beeping
        self.A.beep(frequency=1000, time=0.2)
        time.sleep(0.2)
        self.B.beep(frequency=1200, time=0.2)
        # Checking connections and instrument types
        for inst, name in zip([self.A, self.B, self.switch], 
                              ['B2902B_A', 'B2902B_B', 'Switch unit']):
            flag = inst.check_instument_connection()
            inst.get_errors()  # Clear error queue
            if not flag:
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
                raise ConnectionError(r)
        # Checking error queues
        for inst, name in zip([self.A, self.B, self.switch], 
                              ['B2902B_A', 'B2902B_B', 'Switch unit']):
            err = inst.get_errors()
            if err is not None:
                raise ConnectionError(f'Error in {name} error queue: {err}')
        print('CID_1T1R_32x8 init success')
        
        
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'CID_1T1R_32x8_driver: uses with two Keysight B2902B Source-Measure ' + \
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
        resps.append(self.B.SMU1.set_base_voltage_immediate(0, current_compliance=1e-8))
        self.last_sense_time = 0
        self.acquired_counter = 0
        for r in resps:
            if r.startswith('ERROR'):
                return False
        return True
            
        
    def connect_cell(self, wl: int, bl: int) -> tuple[bool, str]:
        """Connect cell via switch unit. wl and bl are 0 through 7 and 0 through 31.

        Args:
            wl (int): Word Line (0 through 7).
            bl (int): Bit Line (0 through 31).

        Returns:
            flag, response (tuple[bool, str]): Connected flag (True if the cell was
            successfully disconnected), response or error.
        """
        resp = self.switch.connect_cell(row=wl+1, column=bl+1)
        if resp.startswith('ERROR'):
            return False, resp
        return True, resp
        
        
    def disconnect(self) -> tuple[bool, str]:
        """Disconnect instruments on closing the app.

        Returns:
            flag, response (tuple[bool, str]): Disconnected flag (True if instruments were 
            successfully disconnected), response or error.
        """
        resps = []  # Response list
        resps.append(self.switch.disconnect_all())
        resps.append(self.A.clear())
        resps.append(self.B.clear())
        resps.append(self.B.SMU1.set_base_voltage_immediate(0, current_compliance=1e-8))
        resps.append(self.A.set_output_state('off'))
        resps.append(self.B.set_output_state('off'))
        resps.append(self.A.beep(frequency=1200, time=0.2))
        time.sleep(0.2)
        resps.append(self.B.beep(frequency=1000, time=0.2))
        if not self.sim:
            try:
                self.rm.close()
            except Exception as e:
                resps.append('ERROR: ' + str(e))
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
        flag1 = self.clear_instruments()
        r2 = self.switch.standby()
        if r2.startswith('ERROR'):
            flag2 = False
        else:
            flag2 = True
        flag = flag1 and flag2
        if flag:
            return True, 'Instruments are in standby mode'
        return False, r2
    
    
    def _panic_attempt(self) -> tuple[bool, str]:
        """Panic once to immediately stop the experiment.

        Returns:
            flag, response (tuple[bool, str]): Resolved flag (True if panic was resolved), 
            response or error.
        """
        flag, resp = self.standby()
        resps = [resp]  # Response list
        if not flag:
            resps.append(self.A.set_output_state('off'))
            resps.append(self.B.set_output_state('off'))
        for smu in [self.A.SMU1, self.A.SMU2, self.B.SMU1]:
            resps.append(smu.set_base_voltage_immediate(0, current_compliance=1e-8))
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
        resps.append(self.A.set_output_state('on'))
        resps.append(self.B.set_output_state('on'))
        return flag, '\n'.join(resps)
            
        
    def sense(self) -> np.ndarray:
        """Read sense data from the instruments. Returns resistance array with resistances
        which haven't been read yet.

        Returns:
            resistances (np.ndarray)
        """
        while time.time() < self.last_sense_time + self.trigger_interval:
            time.sleep(0.1 * self.trigger_interval)  # Skipping time to match instrument trigger
        if self.sim:
            sense1 = np.random.randint(1, 10000, 2 * (self.acquired_counter+1))
            sense2 = np.random.randint(1, 10000, 2 * (self.acquired_counter+1))
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
            print(R_sent)
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
        sweep_side: str = 'BL'
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
            sweep_side (str, optional): Side where sweep voltage is applied: 'BL' or 'NL'.

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
              sweep_side)
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
        # Configuring triggers and source shapes
        for smu in [self.A.SMU1, self.A.SMU2, self.B.SMU1]:
            resps.append(smu.set_trigger_timer(interval=self.trigger_interval, count=self.trigger_count,
                                               acquire_delay=0.3*self.trigger_interval))
            resps.append(smu.set_measurement_aperture(aperture=0.5*self.trigger_interval))
            resps.append(smu.set_source_shape('DC'))
        # Configuring sweep
        if sweep_side == 'BL':  # Reset
            sweep_smu = self.A.SMU1
            zero_smu = self.A.SMU2
            self.read_side = 1
        elif sweep_side == 'NL':  # Set
            sweep_smu = self.A.SMU2
            zero_smu = self.A.SMU1
            self.read_side = 2
        else:
            return 'ERROR: Wrong sweep_side: valid sides are BL and NL'
        resps.append(sweep_smu.set_sweep_voltage(stop=v_stop, n_points=n_points, start=v_start, 
                                                 double=double, current_compliance=current_compliance))
        resps.append(zero_smu.set_constant_voltage(voltage=0, current_compliance=current_compliance))
        resps.append(self.B.SMU1.set_constant_voltage(voltage=3.3, current_compliance=1e-6))
        resps.append(self.B.SMU1.set_base_voltage_immediate(3.3, current_compliance=1e-6))
        # todo: Вынести 3.3 в конфигурацию
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
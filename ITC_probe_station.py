"""
Драйвер для измерения кроссбаров мемристоров на установке в ЦИРе. Использует один 
модуль B2902B (через зондовую станцию или другое подключение). 
"""
import pyvisa
import time
from RRAM_VISA_Drivers.VISA_utility import GeneralDriver
from RRAM_VISA_Drivers.SMU_drivers import B2902B
from RRAM_VISA_Drivers.gui_connection import set_driver_instruments, check_connection_B2902B



set_driver_instruments(
    driver_name='ITC_probe_station', 
    instruments={
        'B2902B (Mem,T)': check_connection_B2902B,
    }
)



class ITC_probe_station(GeneralDriver):
    """Driver for measuring measuring memristors using one channel of the B2902B
    """
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
        return 'B2902B_probe_station_driver: uses '
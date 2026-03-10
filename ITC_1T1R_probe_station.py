"""
Драйвер для измерения кроссбаров 1T1R 32x8 на установке в ЦИРе. Использует два 
модуля B2902B без коммутатора (через зондовую станцию или другое подключение). 
Первые пины на коннекторах D-Sub 25 устройств B2902B должны быть соединены проводом.
"""
import pyvisa
from RRAM_VISA_Drivers.SMU_drivers import B2902B_1T1R_32x8_driver



class ITC_1T1R_32x8_probe_station(B2902B_1T1R_32x8_driver):
    """Driver for measuring 1T1R 32x8 crossbar arrays without a switch unit.
    """
    sim: str = False
    
    def __init__(
        self, 
        B2902B_1_address: str, 
        B2902B_2_address: str, 
        VISA_library_path: str = ''
    ) -> None:
        """Driver for measuring 1T1R 32x8 crossbar arrays without a switch unit.

        Args:
            B2902B_1_address (str): VISA-adress for Keysight B2902B which controls
                Bit Line (1st channel) and Net Line (2nd channel).
            B2902B_2_address (str): VISA-adress for Keysight B2902B which controls
                Word Line (1st channel).
            VISA_library_path (str, optional): Path to VISA library. If not provided, 
                pyvisa tries to find the library on the computer. Defaults to ''.
        """
        # Check if in simulation mode
        self.sim = False
        for address in [B2902B_1_address, B2902B_2_address]:
            if address is None:
                self.sim = True
        if self.sim:
            A_res, B_res = None, None
        else:
            # Creating ResourceManager
            if VISA_library_path == '':
                self.rm = pyvisa.ResourceManager()
            else:
                self.rm = pyvisa.ResourceManager(VISA_library_path)
            # Opening resources
            A_res = self.rm.open_resource(B2902B_1_address)
            B_res = self.rm.open_resource(B2902B_2_address)
        # Creating driver instances for the instruments
        super().__init__(A_res, B_res, self.sim)
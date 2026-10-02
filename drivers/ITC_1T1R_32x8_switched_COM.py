"""
Драйвер для измерения кроссбаров 1T1R 32x8 на установке в ЦИРе. Использует два 
модуля B2902B, коммутатор 34980A и плату, коммуницирующую по COM-порту. 
Первые пины на коннекторах D-Sub 25 устройств B2902B должны быть соединены проводом.
"""
from RRAM_VISA_Drivers.drivers.ITC_1T1R_32x8_switched import ITC_1T1R_32x8_switched
from RRAM_VISA_Drivers.core import COM



class ITC_1T1R_32x8_switched_COM(ITC_1T1R_32x8_switched):
    """Driver for measuring 1T1R 32x8 crossbar arrays with a switch unit."""
    sim: str = False  # True for simulation mode
    
    def __init__(
        self, 
        B2902B_1_address: str, 
        B2902B_2_address: str, 
        Switch_address: str,
        COM_port: str,
        VISA_library_path: str = ''
    ) -> None:
        """Driver for measuring 1T1R 32x8 crossbar arrays with a switch unit.

        Args:
            B2902B_1_address (str): VISA-address for Keysight B2902B which controls
                Bit Line (1st channel) and Net Line (2nd channel).
            B2902B_2_address (str): VISA-address for Keysight B2902B which controls
                Word Line (1st channel).
            Switch_address (str): VISA-address for Keysight 34980A which controls
                cell selection.
            VISA_library_path (str, optional): Path to VISA library. If not provided, 
                pyvisa tries to find the library on the computer. Defaults to ''.
        """
        for address in [B2902B_1_address, B2902B_2_address, Switch_address, COM_port]:
            if address is None or address == '':
                self.sim = True
        super().__init__(self, B2902B_1_address, B2902B_2_address, Switch_address, VISA_library_path)
        # Init COM port
        if self.sim:
            self.COM = COM(port=None, braudrate=9600, timeout=None)
        else:
            self.COM = COM(port=COM_port, braudrate=9600, timeout=None)
        print('COM driver init success')
        self.logger.info('COM drier init success')
        
        
    def get_tech_data(self) -> str:
        """Get information about instruments.

        Returns:
            information (str): Technical information.
        """
        return 'ITC_1T1R_32x8_driver: uses two Keysight B2902B Source-Measure ' + \
                'modules and a Keysight_34980A Switch unit + COM measurement board for measuring 32x8 1T1R ' + \
                'memristive crossbar arrays'
                
    
    def disconnect(self) -> tuple[bool, str]:
        """Disconnect instruments on closing the app.

        Returns:
            flag, response (tuple[bool, str]): Disconnected flag (True if instruments were 
            successfully disconnected), response or error.
        """
        f1, r1 = super().disconnect()
        f2, r2 = self.COM.close()
        return f1 and f2, r1 + r2
    
    
    def config_COM_command(self, command: str, response_type: str) -> tuple[bool, str]:
        """Configure COM mode and send command to the measurement board.

        Args:
            command (str): Command to measurement board.
            response_type (str): Type of response: 

        Returns:
            tuple[bool, str]: _description_
        """
        
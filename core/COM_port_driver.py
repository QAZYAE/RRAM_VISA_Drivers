try:
    from serial import Serial, serial_for_url
except (ModuleNotFoundError, ImportError):
    raise ModuleNotFoundError('PySerial package is not installed! Run `pip install pyserial`')
from typing import Union
import traceback
        


class COM:
    """Com port class"""
    def __init__(
        self, 
        port: Union[str, None] = None, 
        baudrate: int = 9600,
        timeout: Union[float, None] = None
    ) -> None:
        """COM port class"""
        try:
            if port is None or port == '':
                self.serial = serial_for_url('loop://', baudrate=baudrate, timeout=timeout)
            else:
                self.serial = Serial(port, baudrate=baudrate, timeout=timeout)
        except Exception:
            print('Ошибка открытия COM порта:')
            traceback.print_exc()
        
        
    def write(self, command: str) -> tuple[bool, str]:
        """Write a command to com port

        Args:
            command (str): Command to write.

        Returns:
            flag, response (tuple[bool, str]): Ok flag, error if occurred.
        """
        try:
            resp = self.serial.write(command.encode())
            res_str = '' if resp else f'Could not write command: {command}'
            return resp, res_str
        except Exception:
            return False, traceback.format_exc()
        
        
    def read(self, size: Union[int, None] = None) -> tuple[bool, Union[bytes, str]]:
        """Read `size` bytes from the buffer.

        Args:
            size (int | None, optional): Amount of bytes to read. If None, reads all available data. Defaults to None.

        Returns:
            flag, response (bool, bytes | str): Ok flag, Bytes read from the port (bytes) or error if occurred (str).
        """
        if size is None:
            try:
                data = self.serial.read_all()
                if data:
                    return True, data
                else:
                    return False, b''
            except Exception:
                return False, traceback.format_exc()
        else:
            try:
                data = self.serial.read(size=size)
                if data:
                    return True, data
                else:
                    return False, b''
            except Exception:
                return False, traceback.format_exc()
            
    
    def read_until(self, expected: bytes, size: Union[int, None] = None) -> bytes:
        """Read from buffer until `expected` string is found.

        Args:
            expected (bytes): String to find.
            size (int | None, optional): Size of the buffer to read. Defaults to None.

        Returns:
            flag, response (bool, bytes | str): Ok flag, Bytes read from the port (bytes) or error if occurred (str).
        """
        try:
            data = self.serial.read_until(expected, size)
            return True, data
        except Exception:
            return False, traceback.format_exc()  
        
        
    def close(self) -> tuple[bool, str]:
        """Read from buffer until `expected` string is found.

        Returns:
            flag, response (bool, bytes | str): Ok flag, error if occurred (str).
        """
        try: 
            self.serial.close()
            return True, 'COM disconnected'
        except Exception:
            return False, traceback.format_exc()
        
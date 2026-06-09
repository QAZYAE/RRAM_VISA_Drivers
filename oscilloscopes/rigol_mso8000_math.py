"""
This class operates with the math function of the Rigol MSO8000 Digital Oscilloscope.
"""
from RRAM_VISA_Drivers.core import VISA_module
from typing import Union
import pyvisa



class Rigol_MSO8000(VISA_module):
    """Represents a math channel of the Rigol MSO8000 Digital Oscilloscope.
    
    Attributes:
        ch (int): Math channel (1 through 4).
        parent (Rigol_MSO8000): Parent instrument class.
        inst_name (str): Instrument name for responses.
        command_queue (list): Command queue for the instrument.
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        channel: int, 
        instrument_name: str = 'Instrument',
        parent = None
    ) -> None:
        """Represents a math channel of the Rigol MSO8000 Digital Oscilloscope.

        Args:
            resource (pyvisa.Resource | None): Instrument's resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            channel (int): Math channel (1 through 4).
            instrument_name (str, optional): Instrument name for responses. Defaults to 'MSO8000'.
            parent (Rigol_MSO8000): Parent instrument class.
        """
        self.parent = parent
        if channel < 1 or channel > 4:
            raise RuntimeError('ERROR: wrong channel number. Allowed channel numbers are 1 through 4.')
        self.ch = channel
        self.inst_name = instrument_name
        super().__init__(resource, module_name=f'{self.inst_name}, Math channel {self.ch}')
        
    
    def enable(self, apply: bool = True) -> str:
        """Enables the math operation.
        
        Args:
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                
        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.command(f'math{self.ch}:display on', apply=apply)
    
    
    def disable(self, apply: bool = True) -> str:
        """Disables math operation.

        Args:
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.command(f'math{self.ch}:display off', apply=apply)
    
    
    def mode(self, operator: str = 'add', apply: bool = True) -> str:
        """Changes math mode (operation).

        Args:
            operator (str, optional): Operator: `add` | `substract` | `multiply` | `division` |
            `and` | `or` | `xor` | `not` | `fft` | `intg` | `diff` | `sqrt` | `log` | `ln` | 
            `exp` | `abs` | `lpas` | `hpas` | `bpas` | `bst` | `axb`. Defaults to 'add'.
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.


        Returns:
            response (str): Command response | error if an error occurred.
        """
        if operator.lower() not in ['add', 'substract', 'multiply', 'division', \
            'and', 'or', 'xor', 'not', 'fft', 'intg', 'diff', 'sqrt', 'log', 'ln', \
            'exp', 'abs', 'lpas', 'hpas', 'bpas', 'bst', 'axb']:
            return f'ERROR: {self.resp} Invalid operator: {operator}'
        return self.command(f'math{self.ch}:operator {operator}', apply=apply)
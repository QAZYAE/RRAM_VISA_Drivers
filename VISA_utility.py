"""
Helper classes and functions
"""

import pyvisa
from typing import Union



class VISA_module:
    """General class for VISA instruments or modules. Write and query methods are implemented
    """
    def __init__(self, resource: Union[pyvisa.Resource, None]) -> None:
        """General class for VISA instruments or modules. Write and query methods are implemented

        Args:
            resource (pyvisa.Resource | None): pyvisa resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
        """
        self.resource = resource
        if resource is None:
            self.sim = True
        else:
            self.sim = False
            
            
    def write(self, commands: Union[list, str], stop_exception: bool = True) -> list:
        """Send sequence of SCPI commands to the instrument. Returns exception if an it occurs.

        Args:
            commands (list | str): List of SCPI commands (strings).
            stop_exception (bool, optional): If True, stops sending commands when an exception occurs. 
                Defaults to False.
            
        Returns:
            list: List of execuded commands or Visa Errors.
        """
        if type(commands) is not list:
            commands = [commands]
        if self.sim:
            return ['Simulation mode. Commands sent:'] + commands
        executed = []
        for command in commands:
            try:
                self.resource.write(command)
                executed.append(command)
            except pyvisa.VisaIOError as error:
                executed.append(f'VISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {error}')
                if stop_exception:
                    return executed
        return executed
    
    
    def query(self, command: str) -> str:
        """Send SCPI command and read response. Returns exception if an exception occurs.

        Args:
            command (str): SCPI command.

        Returns:
            str: Instrument response. Returns Visa Error if an exception occured.
        """
        if self.sim:
            return f'Simulation: querying command {command}'
        try:
            response = self.resource.query(command)
            return response
        except pyvisa.VisaIOError as error:
            return f'VISA ERROR:\n\tCommand: "{command}"\n\tVisaIOError: {error}'
        



def twodig(number: int) -> str:
    """Makes a two digit number by adding 0 if number is one digit, also converts it to str.

    Args:
        number (int): number to convert.

    Returns:
        str: converted string.
    """
    if number < 1 or number > 99:
        raise RuntimeError(f'twodig function: wrong number "{number}": it must have 1 or 2 digits.')
    if 1 <= number <= 9:
        return f'0{number}'
    return str(number)
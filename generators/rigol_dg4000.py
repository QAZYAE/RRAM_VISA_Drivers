"""
A driver for Rigol DG4000 Series Function/Arbitrary Waveform Generator
"""
from RRAM_VISA_Drivers.core import VISA_instrument
from typing import Union
import pyvisa



class Rigol_DG4000_generator(VISA_instrument):
    """A driver for Rigol DG4000 Series Function/Arbitrary Waveform Generator
    
    Attributes:
        command_queue (list): Command queue for the instrument.
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        instrument_name: str = 'B2902B'
    ) -> None:
        """Handles communicating with Keysight B2902B using pyvisa.

        Args:
            resource (pyvisa.Resource | None): Keysight B2902B's resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            instrument_name (str, optional): Instrument name for responses. Defaults to 'B2902B'.
        """
        IDN_response = 'Rigol Technologies,DG4162'
        super().__init__(resource, IDN_response=IDN_response, instrument_name=instrument_name)
        self.command_queue = []
        
        
    def set_output_state(self, state: str = 'on', channel: int = 1, apply: bool = True) -> str:
        """Set output state for the instrument.

        Args:
            state (str, optional): Output state: 'on' | 'off'.
            channel (str, optional): Channel for which the output state is set: '1' | '2'.
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if str(channel) not in ['1', '2']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        if state not in ['on', 'off']:
            return f'ERROR: {self.resp}: wrong output state: {state}'
        self.command(f'output{channel}:state {state}', apply=apply)
        
        
    def configure_harmonic(
        self, 
        frequency: float, 
        amplitude: float, 
        DC_offset: float = 0, 
        phase: float = 0, 
        channel: int = 1,
        apply: bool = True
    ) -> str:
        """Configure harmonic output with specified parameters.

        Args:
            frequency (float): Frequency (Hz). 1e-6 to 80e6 Hz.
            amplitude (float): Amplitude (V).
            DC_offset (float, optional): DC offset (V). Defaults to 0.
            phase (float, optional): Phase (degrees) 0 to 360. Defaults to 0.
            channel (int, optional): Generator channel: 1 | 2. Defaults to 1.
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if str(channel) not in ['1', '2']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        if frequency < 1e-6 or frequency > 80e6:
            return f'ERROR: {self.resp}: wrong frequency: {frequency}'
        if phase < 0 or phase > 360:
            return f'ERROR: {self.resp}: wrong phase: {phase} (it should be in degrees, from 0 to 360)'
        self.command(f'source{channel}:apply:harmonic {frequency},{amplitude},{DC_offset},{phase}', apply=apply)
        
        
    def configure_pulse(
        self,
        frequency: float, 
        amplitude: float, 
        DC_offset: float = 0, 
        delay: float = 0, 
        channel: int = 1,
        apply: bool = True
    ) -> str:
        """_summary_

        Args:
            frequency (float): Frequency (Hz). 1e-6 to 40e6 Hz.
            amplitude (float): Amplitude (V).
            DC_offset (float, optional): DC offset (V). Defaults to 0.
            delay (float, optional): Delay (ns to pulse_period). Defaults to 0.
            channel (int, optional): Generator channel: 1 | 2. Defaults to 1.
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if str(channel) not in ['1', '2']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        if frequency < 1e-6 or frequency > 40e6:
            return f'ERROR: {self.resp}: wrong frequency: {frequency}'
        if delay < 0 or delay > 1/frequency:
            return f'ERROR: {self.resp}: wrong delay: {delay} (from 0 to pulse period)'
        self.command(f'source{channel}:apply:pulse {frequency},{amplitude},{DC_offset},{delay}', apply=apply)
        
        
    def configure_sinusoid(
        self, 
        frequency: float, 
        amplitude: float, 
        DC_offset: float = 0, 
        phase: float = 0, 
        channel: int = 1,
        apply: bool = True
    ) -> str:
        """Configure harmonic output with specified parameters.

        Args:
            frequency (float): Frequency (Hz). 1e-6 to 80e6 Hz.
            amplitude (float): Amplitude (V).
            DC_offset (float, optional): DC offset (V). Defaults to 0.
            phase (float, optional): Phase (degrees) 0 to 360. Defaults to 0.
            channel (int, optional): Generator channel: 1 | 2. Defaults to 1.
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if str(channel) not in ['1', '2']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        if frequency < 1e-6 or frequency > 80e6:
            return f'ERROR: {self.resp}: wrong frequency: {frequency}'
        if phase < 0 or phase > 360:
            return f'ERROR: {self.resp}: wrong phase: {phase} (it should be in degrees, from 0 to 360)'
        self.command(f'source{channel}:apply:sinusoid {frequency},{amplitude},{DC_offset},{phase}', apply=apply)
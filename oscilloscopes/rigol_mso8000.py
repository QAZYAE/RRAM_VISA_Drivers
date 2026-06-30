"""
A driver for Rigol MSO8000 Series Digital Oscilloscope
"""
from RRAM_VISA_Drivers.core import VISA_instrument
from typing import Union
import pyvisa
import numpy as np
import time #TODO remove


class Rigol_MSO8000(VISA_instrument):
    """A driver for Rigol MSO8000 Series Digital Oscilloscope.
    
    Attributes:
        command_queue (list): Command queue for the instrument.
    """
    def __init__(
        self, 
        resource: Union[pyvisa.Resource, None], 
        instrument_name: str = 'MSO8000'
    ) -> None:
        """Handles communicating with Rigol MSO8000 using pyvisa.

        Args:
            resource (pyvisa.Resource | None): Instrument's resource
                (initiate using :meth:`pyvisa.highlevel.ResourceManager.open_resource`).
                If resource is None, the program simulates communication.
            instrument_name (str, optional): Instrument name for responses. Defaults to 'MSO8000'.
        """
        IDN_response = 'RIGOL TECHNOLOGIES,MSO8'
        super().__init__(resource, IDN_response=IDN_response, instrument_name=instrument_name)
    

    def fetch_waveform(self, channel: str = '1', form: str = 'ascii', mode: str = 'norm', apply: bool = True) -> str:
        """Fetch data from oscilloscope screen

        Args:
            channel (str, optional): Channel from which the waveform will be read: '1' | '2' | '3' | '4'.
                Defaults to '1'.
            form (str, optional): WORD|BYTE|ASCii. Defaults to 'ascii'.
            mode (str, optional): NORMal|MAXimum|RAW. Defaults to 'norm'.
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                Defaults to True.

        Returns:
            data (list[str]): raw data from the oscilloscope | error if an error occurred.
        """

        if str(channel) not in ['1', '2', '3', '4']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        self.command(f'wav:sour chan{channel}', apply=apply)
        self.command(f'wav:mode {mode}', apply=apply)
        self.command(f'wav:form {form}', apply=apply)

        return self.query('wav:data?')


    def parse_waveform(self, rawdata, xorigin: bool = False):
        """ Parse fetched data in ASCII

        Args:
            rawdata (list[str]): raw data from the oscilloscope in ASCII format
            xorigin (bool): If True, the start time of the waveform data will be used. Defaults to False.

        Returns:
            time, data (tuple[np.ndarray, list]): data in the X direction; waveform from the oscilloscope | error if an error occurred.
        """
                
        n_bytes = int(rawdata[2:11])
        data = (rawdata[11:n_bytes+11]).split(',')
        data = [float(i) for i in data[:-1]]
        delta_t = self.query('wav:xinc?')
        if xorigin:
            t0 = float(self.query('wav:xor?'))
        else:
            t0 = 0
        time = np.arange(t0, len(data), delta_t)

        return time, data


    def auto_scale(self, apply: bool = True):
        """Enable the waveform auto setting function. The oscilloscope will automatically adjust the vertical 
        scale, horizontal time base, and trigger mode according to the input signal to realize optimal waveform display.

        Args:
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                Defaults to True.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.command('aut', apply=apply)
    

    def run(self, apply: bool = True):
        """ Start the oscilloscope.
        
        Args:
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                Defaults to True.
                        
        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.command('run', apply=apply)
    

    def stop(self, apply: bool = True):
        """Stop the oscilloscope.

        Args:
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                Defaults to True.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.command('stop', apply=apply)
    

    def single(self, apply: bool = True):
        """ Set the trigger mode of the oscilloscope to "Single".

        Args:
            apply (bool, optional): If True, the command is sent to the instrument immediately. If False,
                the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                Defaults to True.
                        
        Returns:
            response (str): Command response | error if an error occurred.
        """
        return self.command('sing', apply=apply)
    

    def measure_amplitude(self, channel: str = '1'):
        """ Measure aplitude of the signal on channel.

        Args:
            channel (str): channel number on which the amplitude of the signal will be measured. Defaults to '1'.

        Returns:
            amplitude (float)
        """
        if str(channel) not in ['1', '2', '3', '4']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        return float(self.query(f'meas:stat:item? curr,vpp,chan{channel}'))
    

    def measure_frequency(self, channel: str = '1'):
        """ Measure frequency of the signal on channel.

        Args:
            channel (str): channel number on which the frequency of the signal will be measured. Defaults to '1'.

        Returns:
            frequency (float)
        """
        if str(channel) not in ['1', '2', '3', '4']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        return float(self.query(f'meas:stat:item? aver,freq,chan{channel}'))


    def measure_phase_difference(self, channel: str = '1', ref_channel: str = '2'):
        """ Measure phase difference between signals on channel and ref_channel.

        Args:
            channel (str): channel number on which the phase of the signal will be measured. Defaults to '1'.
            ref_channel (str): chanel number with reference signal. Defaults to '2'.

        Returns:
            amplitude (float)
        """
        if str(channel) not in ['1', '2', '3', '4']:
            return f'ERROR: {self.resp}: wrong channel number: {channel}'
        if str(ref_channel) not in ['1', '2', '3', '4']:
            return f'ERROR: {self.resp}: wrong reference channel number: {channel}'
        if str(ref_channel) == str(channel):
            return f'ERROR: {self.resp}: channel number and reference channel number can`t be the same'
        
        return float(self.query(f'meas:stat:item? curr,rrphase,chan{channel},chan{ref_channel}'))


    def display_channels(self, channels: list = ['1', '2'], apply: bool = True):
        """Turns on specified channels and turns off the remaining channels.

        Args:
            channels (list[str], optional): channels (list): channels that need to be displayed: ['1', '2', '3', '4']. 
                If channels is an empty list, all of the channels will be turned off.. Defaults to [1, 2].
            apply (bool, optional): If True, the command is sent to the instrument immediately. 
                If False, the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                Defaults to True.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        off_channels = ['1', '2', '3', '4']

        for channel in channels:
            if str(channel) not in ['1', '2', '3', '4']:
                return f'ERROR: {self.resp}: wrong channel number: {channel}'
            self.command(f'chan{channel}:disp 1', apply=apply)
            off_channels.remove(str(channel))

        for channel in off_channels:
            self.command(f'chan{channel}:disp 0', apply=apply)

    def wait_operation_complete(self):
        """Wait until the current operation is finished.
        """
        while self.query('*opc?') != '1\n':
            time.sleep(0.1) #TODO change to Qt timer
            pass

    def beep(self):
        """ Beeper.
                    
        Returns:
            response (str): Command response | error if an error occurred.
        """
        self.command('syst:beep 1')

    def set_xscale(self, freq: Union[float, None] = None, apply: bool = True):
        """Sets the scale of the main time base so the two periods of waveform fit on the oscilloscope's screen.

        Args:
            freq (Union[float, None], optional): frequency of the signal. If freq > 40 MHz scale sets to 5e-9 s. 
                If freq < 0.2 mHz scale sets to 1e3 s. If freq is None auto setting function will be enabled. Defaults to None.
            apply (bool, optional): If True, the command is sent to the instrument immediately. 
                If False, the command is appended to the `command_queue` and can be sent with `.send_queue()` method.
                Defaults to True.

        Returns:
            response (str): Command response | error if an error occurred.
        """
        if freq is None:
            return self.auto_scale()
        elif freq < 2e-4:
            return self.command(f'tim:main:scale {1e3}', apply=apply)
        elif freq > 4e7:
            return self.command(f'tim:main:scale {5e-9}', apply=apply)
        else:
            return self.command(f'tim:main:scale {0.2/freq}', apply=apply)
        


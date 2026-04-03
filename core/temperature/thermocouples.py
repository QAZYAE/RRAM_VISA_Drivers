"""Функции для температурных измерений"""
from typing import Union
import numpy as np
from collections.abc import Iterable
import os 


# Loading and parsing approximation data
K_type = np.load(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'K_type_thermocouple.npz'))

# Temp_difference from 0 to 200: Linear coefficients. V = K_A * T + K_B; 
K_A = K_type['K_A'][0]
K_B = K_type['K_B'][0]

# Temp_diff < 0: polynomial coefficients
T2V_negative = K_type['T2V_negative']
V2T_negative = K_type['V2T_negative']

K_type.close()



def _K_v2t_pos(volt: float) -> float:
    """T > 0"""
    return (volt - K_B) / K_A

def _K_t2v_pos(temp: float) -> float:
    """T > 0"""
    return K_A * temp + K_A

def _K_v2t_neg(volt: float) -> float:
    """T < 0"""
    order = len(V2T_negative) - 1
    return sum([V2T_negative[i]*volt**(order-i) for i in range(len(V2T_negative))])

def _K_t2v_neg(temp: float) -> float:
    """T < 0"""
    order = len(T2V_negative) - 1
    return sum([T2V_negative[i]*temp**(order-i) for i in range(len(T2V_negative))])

def _K_v2t(volt: float, room_temp: float) -> float:
    if volt < 0: 
        return _K_v2t_neg(volt) + room_temp
    return _K_v2t_pos(volt) + room_temp

def _K_t2v(temp: float, room_temp: float) -> float:
    if (temp - room_temp) < 0: 
        return _K_t2v_neg(temp - room_temp)
    return _K_t2v_pos(temp - room_temp)


def K_volt2temp(volt: Union[float, Iterable], room_temp: float = 22) -> Union[float, Iterable]:
    """Convert K-type thermocouple voltage to temperature. 
    **!Approximation of the calibration table was performed 
    in the range from -270 to 200 Celsius!**

    Args:
        volt (Union[float, Iterable]): Thermocouple voltage (Volts).
        room_temp (float, optional): Room temperature. Defaults to 22 Celsius.

    Returns:
        temperature (Union[float, Iterable]): Thermocouple temperature (Celsius).
    """
    if isinstance(volt, Iterable):
        res = []
        for v in volt:
            res.append(_K_v2t(v, room_temp))
        return np.array(res)
    return _K_v2t(volt, room_temp)



def K_temp2volt(temp: Union[float, Iterable], room_temp: float = 22) -> Union[float, Iterable]:
    """Convert K-type thermocouple temperature to voltage. 
    **!Approximation of the calibration table was performed 
    in the range from -270 to 200 Celsius!**

    Args:
        temp (Union[float, Iterable]): Thermocouple temperature (Celsius).
        room_temp (float, optional): Room temperature. Defaults to 22 Celsius.

    Returns:
        voltage (Union[float, Iterable]): Thermocouple voltage (Volts).
    """
    if isinstance(temp, Iterable):
        res = []
        for t in temp:
            res.append(_K_t2v(t, room_temp))
        return np.array(res)
    return _K_t2v(temp, room_temp)
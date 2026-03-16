"""Функции для температурных измерений"""
from typing import Union
import numpy as np
from numpy.typing import  ArrayLike



# Linear coefficients. V = K_A * T + K_B; Temp_diff from 0 to 200
K_A = 4.0924692653673157e-05
K_B = -1.1232901730952569e-05

# Temp_diff < 0
T2V_negative = np.array([-1.07253621e-10,  2.85350875e-08,  3.94461151e-05, -1.22390279e-06])
V2T_negative = np.array([
    -9.864108403581225026e+75,
    -3.209929389529493345e+74,
    -3.433092461979424730e+72,
    -5.899062643487081484e+69,
    1.060313170809072731e+68,
    1.197716209067667578e+65,
    -4.110370497302463466e+63,
    6.615819100249608936e+60,
    1.375821465914752219e+59,
    -7.215280980857030446e+56,
    -3.022006084551779724e+54,
    3.910105263820096657e+52,
    3.895196975252723718e+48,
    -1.624134520704641092e+48,
    3.272324392336761420e+45,
    6.384111672381793162e+43,
    -1.672533629493745310e+41,
    -2.868639695453212411e+39,
    6.180460080648295940e+35,
    1.284753535191521146e+35,
    8.591397789963238486e+32,
    3.101471736827865753e+30,
    7.252401690397833270e+27,
    1.157159724278476096e+25,
    1.271459023697736211e+22,
    9.466678436155549696e+18,
    4.588056472587859000e+15,
    1.345555297193025391e+12,
    2.086325666643626988e+08,
    3.832295499144374480e+04,
    1.141073825635648964e-01
])


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


def K_volt2temp(volt: Union[float, ArrayLike], room_temp: float = 22) -> Union[float, ArrayLike]:
    """Convert K-type thermocouple voltage to temperature. 
    **!Approximation of the calibration table was performed 
    in the range from -270 to 200 Celsius!**

    Args:
        volt (Union[float, ArrayLike]): Thermocouple voltage (Volts).
        room_temp (float, optional): Room temperature. Defaults to 22 Celsius.

    Returns:
        temperature (Union[float, ArrayLike]): Thermocouple temperature (Celsius).
    """
    if volt < 0: 
        return _K_v2t_neg(volt) + room_temp
    else:
        return _K_v2t_pos(volt) + room_temp


def K_temp2volt(temp: Union[float, ArrayLike], room_temp: float = 22) -> Union[float, ArrayLike]:
    """Convert K-type thermocouple temperature to voltage. 
    **!Linear approximation of the calibration table was performed 
    in the range from -270 to 200 Celsius!**

    Args:
        temp (Union[float, ArrayLike]): Thermocouple temperature (Celsius).
        room_temp (float, optional): Room temperature. Defaults to 22 Celsius.

    Returns:
        voltage (Union[float, ArrayLike]): Thermocouple voltage (Volts).
    """
    if (temp - room_temp) < 0: 
        return _K_t2v_neg(temp - room_temp)
    else:
        return _K_t2v_pos(temp - room_temp)
"""Функции для температурных измерений"""
from typing import Union
from numpy.typing import  ArrayLike



# Linear coefficients. V = K_A * T + K_B
K_A = 4.0924692653673157e-05 
K_B = -1.1232901730952569e-05



def K_volt2temp(volt: Union[float, ArrayLike]) -> Union[float, ArrayLike]:
    """Convert K-type thermocouple voltage to temperature. 
    **!Linear approximation of the calibration table was performed 
    in the range from 0 to 200 Celsius!**

    Args:
        volt (Union[float, ArrayLike]): Thermocouple voltage (Volts).

    Returns:
        temperature (Union[float, ArrayLike]): Thermocouple temperature (Celsius).
    """
    return (volt - K_B) / K_A


def K_temp2volt(temp: Union[float, ArrayLike]) -> Union[float, ArrayLike]:
    """Convert K-type thermocouple temperature to voltage. 
    **!Linear approximation of the calibration table was performed 
    in the range from 0 to 200 Celsius!**

    Args:
        temp (Union[float, ArrayLike]): Thermocouple temperature (Celsius).

    Returns:
        voltage (Union[float, ArrayLike]): Thermocouple voltage (Volts).
    """
    return K_A * temp + K_A
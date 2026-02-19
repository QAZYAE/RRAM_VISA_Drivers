# SMU module Testing
import pyvisa
import time
from SMU_drivers.Keysight_B2902B import B2902B
from Switch_drivers.Keysight_34980A_1T1R_32x8 import Keysight_34980A_1T1R_32x8
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import (MultipleLocator, MaxNLocator)
import json
# import numpy as np




def main():
    # Measuring two IV curves
    rm = pyvisa.ResourceManager()
    A_res = rm.open_resource('TCPIP0::192.168.0.101::inst0::INSTR')
    B_res = rm.open_resource('TCPIP0::192.168.0.103::inst0::INSTR')
    
    A = B2902B(A_res, 'A')
    A.set_standby_zero()
    A.set_output_state('on')
    A.clear()
    
    B = B2902B(B_res, 'B')
    B.set_standby_zero()
    B.set_output_state('on')
    B.clear()
    
    A.SMU1.set_arm_BUS()
    A.SMU2.set_arm_BUS()
    B.SMU1.set_arm_external(pin=1)
    
    A.set_external_trigger_link(pin=1, trigger_layer='arm', function='output', channel=1)
    B.set_external_trigger_link(pin=1, trigger_layer='arm', function='input', channel=1)
    
    n_points = 11
    time_interval=0.01  # s
    A.SMU1.set_trigger_timer(interval=time_interval, count=2*n_points)
    A.SMU2.set_trigger_timer(interval=time_interval, count=2*n_points)
    B.SMU1.set_trigger_timer(interval=time_interval, count=2*n_points)
    
    A.SMU1.set_sweep_voltage(stop=1, n_points=n_points)
    A.SMU2.set_sweep_voltage(stop=1, n_points=n_points)
    # B.SMU1.set_constant_voltage(voltage=1)
    B.SMU1.set_sweep_voltage(stop=1, n_points=n_points)

    A.set_data_format('voltage,current')
    B.set_data_format('voltage,current')
    
    A.initiate()
    B.SMU1.initiate()
    A.arm()
    for i in range(2 * n_points):
        time.sleep(time_interval)
        a1, a2 = A.get_sense_data(latest=True)
        b1 = B.SMU1.get_sense_data(latest=True)
        print(f'{i}\t a1: {a1}\n\ta2: {a2}\n\tb1: {b1}')
    
    data1, data2 = A.get_sense_data()
    data3 = B.SMU1.get_sense_data()
    print(data3)
    
    _, ax = plt.subplots()
    ax.grid(ls='-', lw=1, color='grey')
    ax.plot(data1[::2], data1[1::2]*1000, lw=2, label='SMU1')
    ax.plot(data2[::2], data2[1::2]*1000, lw=2, label='SMU2')
    ax.set_xlabel('Voltage, V')
    ax.set_ylabel('Current, mA')
    ax.legend(loc='best')
    plt.show()
    # 10k, 1k
    
    
def check_all_resistances():
    rm = pyvisa.ResourceManager()
    A_res = rm.open_resource('TCPIP0::192.168.0.101::inst0::INSTR')
    B_res = rm.open_resource('TCPIP0::192.168.0.103::inst0::INSTR')
    switch_res = rm.open_resource('TCPIP0::192.168.0.100::inst0::INSTR')
    
    A = B2902B(A_res, 'A')
    A.set_standby_zero()
    A.set_output_state('on')
    A.clear()
    
    B = B2902B(B_res, 'B')
    B.set_standby_zero()
    B.set_output_state('on')
    B.clear()
    
    switch = Keysight_34980A_1T1R_32x8(switch_res, config_path='config/Keysight_34980A_1T1R_32x8.json')
    switch.standby()
    
    A.SMU1.set_arm_BUS()
    A.SMU2.set_arm_BUS()
    B.SMU1.set_arm_external(pin=1)
    
    A.set_external_trigger_link(pin=1, trigger_layer='arm', function='output', channel=1)
    B.set_external_trigger_link(pin=1, trigger_layer='arm', function='input', channel=1)
    
    n_points = 1
    time_interval=0.1  # s
    A.SMU1.set_trigger_timer(interval=time_interval, count=n_points)
    A.SMU2.set_trigger_timer(interval=time_interval, count=n_points)
    B.SMU1.set_trigger_timer(interval=time_interval, count=n_points)
    
    A.SMU1.set_constant_voltage(voltage=0.2, current_compliance=100e-3)  # BL  read на reset
    A.SMU2.set_constant_voltage(voltage=0, current_compliance=100e-3)  # NL
    B.SMU1.set_constant_voltage(voltage=3.3, current_compliance=1e-6)  # WL 
    
    A.set_data_format('voltage,current')
    B.set_data_format('voltage,current')
    
    res = np.empty((32, 8))
    for wl in range(8):
        for bl in range(32):
            switch.connect_cell(wl+1, bl+1)
            B.write('source1:voltage:level:immediate 3.3')
            time.sleep(0.1)
            A.initiate()
            B.SMU1.initiate()
            A.arm()
            time.sleep(0.2)
            BL, NL = A.get_sense_data(latest=True)
            IBL = np.abs(BL[1])
            INL = np.abs(NL[1])
            R = BL[0] / ((IBL + INL) / 2)
            WL = B.SMU1.get_sense_data(latest=True)
            A.clear()
            B.clear()
            print(f'{wl}-{bl}: I_BL = {BL[1]*1000} mA, I_NL={NL[1]*1000} mA, I_WL = {WL[1]} A')
            res[bl, wl] = R
    switch.standby()
    B.write('source1:voltage:level:immediate 0')

    fig, ax = plt.subplots()
    image = ax.matshow(res/1000, interpolation=None)  # kOhm
    ax.xaxis.set_major_locator(MaxNLocator(16, integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(16, integer=True))
    ax.xaxis.set_minor_locator(MultipleLocator(1))
    ax.yaxis.set_minor_locator(MultipleLocator(1))
    ax.tick_params(which='both', top=True, bottom=False, left=True, right=False)
    # Colorbar
    n_rows, n_cols = len(res), len(res[0])
    cbar_ax = ax.inset_axes([n_cols+2, n_rows/6, max(n_cols//32, 1), n_rows*2/3], transform=ax.transData)
    cbar = fig.colorbar(image, cax=cbar_ax, orientation='vertical', shrink=0.4)
    cbar.set_label('Сопротивление, кОм')
    plt.show()

    np.save('resistance_map.npy', res)
    switch.disconnect_all()
            







if __name__ == '__main__':
    print(check_all_resistances())
    # main()
    # import os
    # print(os.listdir('config'))

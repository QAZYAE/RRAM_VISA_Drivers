from Switch_drivers.Keysight_34980A_1T1R_32x8 import Keysight_34980A_1T1R_32x8


config_path = 'config/Keysight_34980A_1T1R_32x8.json'
Switch = Keysight_34980A_1T1R_32x8(None, config_path=config_path)
print(Switch.WLNL)

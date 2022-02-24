import tomato.drivers
import time


address = "192.109.209.6"
channel = 2
dllpath = "C:\\EC-Lab Development Package\\EC-Lab Development Package\\"

print(tomato.drivers.biologic.get_status(address, channel, dllpath))
print(tomato.drivers.biologic.get_data(address, channel, dllpath))
print(tomato.drivers.biologic.stop_job(address, channel, dllpath))

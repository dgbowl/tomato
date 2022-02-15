import tomato.drivers
import time


pl = [
    {
        "name": "OCV", 
        "time": 5, 
        "record_every_dt": 0.1
    },
    {
        "name": "CPLIMIT", 
        "current": ["D/10", "C/20"],
        "time": 15, 
        "is_delta": False,
        "record_every_dt": 0.1,
        "record_every_dE": 0.01,
        "I_range": "10 mA",
        "limit_voltage_max": 4.1,
        "limit_voltage_min": 3.0,
        "n_cycles": 0
    }
]

address = "192.109.209.6"
channel = 1
dllpath = "C:\\EC-Lab Development Package\\EC-Lab Development Package\\"
capacity = 45e-3

print(tomato.drivers.biologic.get_status(address, channel, dllpath))
print(tomato.drivers.biologic.start_job(address, channel, dllpath, pl, capacity))
for i in range(4):
    print(f"cycle number {i}/100")
    time.sleep(10)
    meta, data = tomato.drivers.biologic.get_data(address, channel, dllpath)
    print(meta)
    print(data[0], data[-1])
    if meta["status"] == "STOP" and meta["technique_name"] == "NONE":
        break

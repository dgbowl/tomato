import tomato.drivers
import time


pl = [
    {
        "name": "OCV", 
        "time": 5, 
        "I_range": "1 mA",
        "E_range": "±5 V",
        "record_every_dt": 1,
    },
    {
        "name": "CPLIMIT",
        "time": 20,
        "record_every_dt": 1,
        "current": "C/5",
        "I_range": "10 mA",
        "E_range": "±5 V",
        "limit_voltage_max": 4.1,
    },
    {
        "name": "VSCANLIMIT", 
        "voltage": [4.1, 3.9, 4.1, 3.8, 4.1],
        "scan_rate": 2.5e-3,
        "record_every_dE": 0.005,
        "n_cycles": 1,
        "I_range": "100 mA",
        "E_range": "±5 V",
    },
    {
        "name": "ISCANLIMIT", 
        "current": ["C/10", "D/10", "C/5", "D/5"],
        "scan_rate": 2.5e-3,
        "record_every_dI": 0.005,
        "n_cycles": 2,
        "I_range": "10 mA",
        "E_range": "±5 V",
    }
]

address = "192.109.209.6"
channel = 1
dllpath = "C:\\EC-Lab Development Package\\EC-Lab Development Package\\"
capacity = 45e-3

print(tomato.drivers.biologic.get_status(address, channel, dllpath))
print(tomato.drivers.biologic.start_job(address, channel, dllpath, pl, capacity))
for i in range(100):
    print(f"cycle number {i}/100")
    time.sleep(10)
    ts, blob = tomato.drivers.biologic.get_data(address, channel, dllpath)
    data = blob.pop("data")
    print((ts, blob))
    try:
        print(data[0])
        print(data[-1])
    except IndexError as e:
        print(e)
    if blob["status"] == "STOP" and blob["technique_name"] == "NONE":
        break

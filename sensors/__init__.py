"""
Sensor factory — returns the right backend from config.py.
Swap sensor by changing SENSOR_BACKEND in config.py.
"""
from config import SENSOR_BACKEND, WEBCAM_INDEX

def get_sensor():
    b = SENSOR_BACKEND.lower().strip()
    if b == "kinect_v2":
        from sensors.kinect_v2 import KinectV2Sensor
        return KinectV2Sensor()
    elif b == "webcam":
        from sensors.webcam import WebcamSensor
        return WebcamSensor(WEBCAM_INDEX)
    elif b == "simulated":
        from sensors.simulated import SimulatedSensor
        return SimulatedSensor()
    else:
        raise ValueError(f"Unknown SENSOR_BACKEND '{b}'. Options: kinect_v2, webcam, simulated")

#!/usr/bin/env python3
"""
MeshBot v1.2.0
NOTE:
This file is a starter scaffold for v1.2.0. A complete production rewrite
would be substantially larger than can be generated faithfully here.
"""

import time
from meshtastic.serial_interface import SerialInterface
from serial.serialutil import SerialException

SERIAL_PORTS = ["/dev/serial/by-id", "/dev/ttyACM0", "/dev/ttyACM1"]

def connect():
    while True:
        for p in SERIAL_PORTS:
            try:
                print(f"Trying {p}...")
                return SerialInterface(devPath=p)
            except Exception as e:
                print(f"{p}: {e}")
        print("Retrying in 5 seconds...")
        time.sleep(5)

def main():
    iface = None
    try:
        iface = connect()
        print("Connected. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except SerialException as e:
        print(e)
    finally:
        if iface:
            try:
                iface.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()

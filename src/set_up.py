import os
import time
import ctypes
from ctypes import *

# =============================
# EPOS Connection
# =============================
def connect_epos():
    dll_dir = r"C:\Program Files (x86)\maxon motor ag\EPOS IDX\EPOS4\04 Programming\Windows DLL\Microsoft Visual C++\Example VC++"
    os.add_dll_directory(dll_dir)
    epos = ctypes.WinDLL(os.path.join(dll_dir, "EposCmd64.dll"))
    return epos

# =============================
# Initialize Device
# =============================
def initialise_device(nodeID=1, mode="position"):
    epos = connect_epos()
    pErrorCode = c_uint()
    pDeviceErrorCode = c_uint()

    # Open device
    keyHandle = epos.VCS_OpenDevice(
        b'EPOS4',
        b'MAXON SERIAL V2',
        b'USB',
        b'USB0',
        byref(pErrorCode)
    )

    if keyHandle == 0:
        raise RuntimeError(f"OpenDevice failed: 0x{pErrorCode.value:08X}")

    # Check device error state
    epos.VCS_GetDeviceErrorCode(
        keyHandle,
        nodeID,
        1,
        byref(pDeviceErrorCode),
        byref(pErrorCode)
    )

    if pDeviceErrorCode.value != 0:
        print(f"Device in error state: 0x{pDeviceErrorCode.value:08X}, clearing faults...")
        epos.VCS_ClearFault(keyHandle, nodeID, byref(pErrorCode))

    # Select operation mode
    if mode == "position":
        epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    elif mode == "velocity":
        epos.VCS_ActivateProfileVelocityMode(keyHandle, nodeID, byref(pErrorCode))
    else:
        raise ValueError("mode must be 'position' or 'velocity'")

    # Enable device
    epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))

    return {
        "epos": epos,
        "keyHandle": keyHandle,
        "nodeID": nodeID,
        "mode": mode
    }

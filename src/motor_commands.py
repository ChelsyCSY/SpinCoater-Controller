import ctypes
from ctypes import *
import time 

def move_position(ctx, target_pos, velocity=500, accel=1000, decel=1000):
    """
    Move motor to a target relative to current position.
    Mimics working monolithic script.
    """
    epos = ctx["epos"]
    kh = ctx["keyHandle"]
    nid = ctx["nodeID"]
    pErrorCode = c_uint()

    # Set the profile
    ret = epos.VCS_SetPositionProfile(kh, nid, velocity, accel, decel, byref(pErrorCode))
    if pErrorCode.value != 0:
        raise RuntimeError(f"VCS_SetPositionProfile failed: 0x{pErrorCode.value:08X}")

    # Move relative (1 = relative)
    ret = epos.VCS_MoveToPosition(kh, nid, target_pos, 0, 0, byref(pErrorCode))
    if pErrorCode.value != 0:
        raise RuntimeError(f"VCS_MoveToPosition failed: 0x{pErrorCode.value:08X}")

    print(f"Moving relative by {target_pos} counts...")
    time.sleep(1)  # simple wait; you can implement your WaitAcknowledged function
    print("Move complete.")

def run_velocity(ctx, rpm=300, duration=10):
    """
    Spin motor at given RPM for specified duration (seconds) using velocity mode.
    """
    epos = ctx["epos"]
    kh = ctx["keyHandle"]
    nid = ctx["nodeID"]
    pErrorCode = c_uint()

    # Convert RPM to counts/sec
    target_velocity = rpm

    # Start moving with velocity
    ret = epos.VCS_MoveWithVelocity(kh, nid, target_velocity, byref(pErrorCode))
    if pErrorCode.value != 0:
        raise RuntimeError(f"VCS_MoveWithVelocity failed: 0x{pErrorCode.value:08X}")

    print(f"Motor spinning at {rpm} RPM ({target_velocity} counts/sec) for {duration}s...")
    time.sleep(duration)

    # Stop the motor
    ret = epos.VCS_MoveWithVelocity(kh, nid, 0, byref(pErrorCode))
    if pErrorCode.value != 0:
        raise RuntimeError(f"Stopping motor failed: 0x{pErrorCode.value:08X}")

    print("Motor stopped.")


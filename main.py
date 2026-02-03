import ctypes
from ctypes import *

from src.set_up import initialise_device
from src.motor_commands import move_position, run_velocity

# Initialize EPOS in position mode
ctx = initialise_device(mode="velocity")

# Move 1000 counts relative to current position
# move_position(ctx, 1000)

run_velocity(ctx)

# Optional: Close device
pErrorCode = c_uint()
ctx["epos"].VCS_SetDisableState(ctx["keyHandle"], ctx["nodeID"], byref(pErrorCode))
ctx["epos"].VCS_CloseDevice(ctx["keyHandle"], byref(pErrorCode))


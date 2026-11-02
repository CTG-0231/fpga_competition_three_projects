"""PYNQ host port of the supplied six-class leaf classifier."""
import os

# PYNQ 2.7 only loads libxrt_core when XILINX_XRT is set, and the AC820 image
# keeps that runtime in /usr. `sudo` strips the variable, which otherwise makes
# every documented `sudo python3 ...` call fail with "No Devices Found", so
# restore the image default here before anything imports pynq.
if 'XILINX_XRT' not in os.environ and os.path.exists('/usr/lib/libxrt_core.so'):
    os.environ['XILINX_XRT'] = '/usr'

__version__ = '0.1.0'

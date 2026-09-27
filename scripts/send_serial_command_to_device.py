"""Send one shell command to an MG100 over its UART and return the reply."""

import argparse

import serial


def execute_command_over_serial(command, device: str = "/dev/ttyUSB0",
                                baudrate: int = 115200,
                                read_timeout: float = 2,
                                quiet: bool = False) -> str:
    """Write `command` to the device shell and return what it printed.

    Reads for up to `read_timeout` seconds (or 4096 bytes). The reply is also
    echoed to stdout unless `quiet` is set. Undecodable bytes (boot noise,
    a log line cut in half) are replaced instead of raising.
    """
    with serial.Serial(device, baudrate, timeout=read_timeout) as ser:
        ser.reset_input_buffer()
        ser.write((command + '\n').encode())
        output = ser.read(4096).decode(errors='replace')
    if not quiet:
        print(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Execute a shell command on a device over serial.")
    parser.add_argument("-s", "--serial", default="/dev/ttyUSB0",
                        help="Serial device, e.g. /dev/ttyUSB0 or /dev/cu.usbserial-XXXX.")
    parser.add_argument("command", help="Command to execute on the device.")
    parser.add_argument("-b", "--baud", type=int, default=115200,
                        help="Baud rate.")

    args = parser.parse_args()
    execute_command_over_serial(args.command, device=args.serial,
                                baudrate=args.baud)

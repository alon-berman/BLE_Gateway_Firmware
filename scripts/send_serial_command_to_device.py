import serial
import argparse

def execute_command_over_serial(command, device: str = "/dev/ttyUSB0", baudrate: int = 115200):
    # Connect to the device over serial
    ser = serial.Serial(device, 115200)
    
    if ser.isOpen():
        # Write the command followed by a newline (this might depend on your device's requirements)
        ser.write((command + '\n').encode())
        
        # Give the device some time to execute the command and respond
        ser.timeout = 2
        
        # Read the output (modify this part as per your requirement, here it reads 4096 bytes)
        output = ser.read(4096).decode()
        print(output)
        
        # Close the serial connection
        ser.close()
    else:
        print(f"Failed to open device {device}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute a command on a device over serial.")
    parser.add_argument("-s", "--serial", default="/dev/ttyUSB0", help="Command to execute on the device.")
    parser.add_argument("command", help="Command to execute on the device.")
    parser.add_argument("-b","--baud", type=int, default=115200, help="Command to execute on the device.")

    args = parser.parse_args()
    
    execute_command_over_serial(args.serial, args.baud, args.command)

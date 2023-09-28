


import argparse
import os
import subprocess
from time import sleep
import time
import serial
from tqdm import tqdm

from send_serial_command_to_device import execute_command_over_serial

def loading_bar(duration):
    for _ in tqdm(range(duration), desc="Loading...", ncols=100):
        time.sleep(1)

        
def extract_hash(output: str) -> str:
    image_hash = None
    image_count = 0 # always take second image.
    for line in output:
        if 'hash' in line:
            image_count+=1
            if image_count > 1:
                image_hash = line.split(':')[1]
                print(f'found image_hash {image_hash} from line {line}')
                return image_hash

def read_from_serial_device(port, baudrate=115200, timeout=1):
    """
    Read data from a serial device and print to the terminal.

    Parameters:
    - port (str): The port name, e.g., 'COM3' for Windows or '/dev/ttyUSB0' for Linux.
    - baudrate (int): The data rate in bits per second (baud). Default is 9600.
    - timeout (float): The maximum wait time for a read. Default is 1 second.
    """
    
    try:
        with serial.Serial(port, baudrate, timeout=timeout) as ser:
            with open(f'{time.time()}_mg100.log', 'w+') as file_handler:
                while True:
                    line = ser.readline().decode('utf-8').strip()  # Read a line and decode from bytes to string
                    if line:
                        print(line)
                        file_handler.write(line)
                    sleep(0.05)  # Optional: sleep for a short duration before the next read
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except serial.SerialException as e:
        print(f"Error: {e}")
    except UnicodeDecodeError: # try to read again
        read_from_serial_device(port, baudrate, timeout) # retry
        
        
def main(image_path, timeout, retries, conntype, connstring, set_commission: bool = True):
    execute_command_over_serial("attr set commissioned 0", device=connstring)
    execute_command_over_serial("log halt", device=connstring)
    sleep(3)
    # define maximal transmission unit size so it. higher values (e.g., 1024) will not work with MG100.
    connstring_w_mtu = connstring + ",mtu=1024"
    print("current image state:")
    resp = subprocess.check_output(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring_w_mtu, 'image', 'list', '-t', '10000'])
    print(resp)
    print("uploading image to device ....")
    subprocess.run(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring_w_mtu, 'image', 'upload', image_path])
    loading_bar(5)
    print("uploading getting image to device ....")

    resp = subprocess.check_output(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring_w_mtu, 'image', 'list', '-t', '10000'])
    image_hash = extract_hash(resp.decode().splitlines())
    loading_bar(1)
    print("Switching images ....")    
    subprocess.run(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring_w_mtu, 'image', 'test', str(image_hash).strip()])
    loading_bar(1)
    print("Resetting Device ....")
    subprocess.run(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring_w_mtu, 'reset'])
    print("Confirming image... this might take time...")
    loading_bar(105)
    subprocess.run(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring_w_mtu, 'image', 'confirm'])
    if set_commission:
        print("setting commision to 1")
        execute_command_over_serial("attr set commissioned 1", device=connstring)

    read_from_serial_device(port=connstring, baudrate=115200, timeout=3)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Flash MG100 FW')
    parser.add_argument('-t', '--timeout', type=int, default=20,
                        help='an integer for timeout in seconds')
    parser.add_argument('-r', '--retries', type=int, default=3,
                        help='an integer defining number of retries')
    parser.add_argument('-ct','--conntype', type=str,
                        help='the connection type', default='serial'),
    parser.add_argument('-cs','--connstring', type=str,
                        help='the connection type', default='/dev/ttyUSB0'),
    parser.add_argument('--image_path', type=str,
                        help='path to .bin image', default=os.path.join('build', 'mg100','aws','zephyr','app_update.bin'))
    parser.add_argument('--set_commission', type=bool,
                        help='should set comission flag of device to true after flashing.',
                        default=True)

    args = parser.parse_args()
    main(**args.__dict__)
    # python ./scripts/mcumgr_flash.py --image_path ./build/mg100/aws/zephyr/app_update.bin
    print(args)    
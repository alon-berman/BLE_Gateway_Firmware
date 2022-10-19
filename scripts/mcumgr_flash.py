


import argparse
import os
import subprocess
from time import sleep

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


    
def main(image_path, timeout, retries, conntype, connstring):
    
    # define maximal transmission unit size so it. higher values (e.g., 1024) will not work with MG100.
    connstring += ",mtu=512"
    print("uploading image to device ....")
    subprocess.run(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring, 'image', 'upload', image_path])
    sleep(5)
    print("uploading getting image to device ....")

    resp = subprocess.check_output(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring, 'image', 'list'])
    image_hash = extract_hash(resp.decode().splitlines())
    sleep(1)
    print("Switching images ....")    
    subprocess.run(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring, 'image', 'test', image_hash])
    sleep(1)
    print("Resetting Device ....")



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Flash MG100 FW')
    parser.add_argument('-t', '--timeout', type=int, default=20,
                        help='an integer for timeout in seconds')
    parser.add_argument('-r', '--retries', type=int, default=3,
                        help='an integer defining number of retries')
    parser.add_argument('-ct','--conntype', type=str,
                        help='the connection type', default='serial'),
    parser.add_argument('-cs','--connstring', type=str,
                        help='the connection type', default='/dev/ttyUSB1'),
    parser.add_argument('--image_path', type=str,
                        help='path to .bin image', default=os.path.join('build', 'mg100','aws','zephyr','app_update.bin'))

    args = parser.parse_args()
    main(**args.__dict__)
    print(args)    
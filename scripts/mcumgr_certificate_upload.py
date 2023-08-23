


import argparse
import os
import re
import subprocess
from time import sleep

CERTS_TO_UPLOAD = [
        ("AmazonRootCA1.pem", "/lfs/root_ca.pem"),
        #("AmazonRootCA3.pem", ""),
        (r".*-certificate\.pem\.crt$","/lfs/client_cert.pem"),
        (r".*-private\.pem\.key$","/lfs/client_key.pem")
    ]

def find_first_file_by_pattern(pattern, dir_path):
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if re.search(pattern, file):
                return os.path.abspath(os.path.join(root, file))
    return None

def main(cert_folder, timeout, retries, conntype, connstring):
    # mcumgr -t 5 -r 2 --conntype serial --connstring dev=/dev/ttyUSB0,mtu=1024 fs upload /path/to/cert_folder/AmazonRootCA1.pem /lfs/root_ca.pe
    
    # define maximal transmission unit size so it. higher values (e.g., 1024) will not work with MG100.
    connstring += ",mtu=512"
    print("uploading certificates ....")
    for file_regex_pattern, dest_path in CERTS_TO_UPLOAD:
        abs_cert_file_path = find_first_file_by_pattern(file_regex_pattern, cert_folder)
        subprocess.run(["mcumgr", '-t', str(timeout), '-r', str(retries), '--conntype', conntype, '--connstring', connstring, 'fs', 'upload', abs_cert_file_path, dest_path])
        sleep(3)
        print(f"Uploaded {abs_cert_file_path} to {dest_path}")
        
        
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
    parser.add_argument('--cert_folder', type=str,
                        help='path to certificate folders AmazonRootCA1.pem, AmazonRootCA3.pem, public.pem.key, private.pem.key')

    args = parser.parse_args()
    main(**args.__dict__)
    print(args)    
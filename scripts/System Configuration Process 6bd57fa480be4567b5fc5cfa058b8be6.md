# System Configuration Process

## Hardware

- Extract the sim and replace with a working one.
- log to Emnify.com, activate sim by it’s ICCID (without the luhn). Correlate with the Gateway ID as the name of device.
- Update all 510 sensors to version 5.1.0 (**todo**: be able to burn locally)

## Software

- Burn image (ble_gateway_fw repo)
    
    ```jsx
    python3 mcumgr_flash.py --image_path /home/bermanalon/git/etoot-gw-fw/ble_gateway_firmware/etoot_mg100_gw_fw_1.2.0-rc2/build/mg100/aws/zephyr/app_update.bin
    ```
    
- Burn 2nd Image again (rc-1, rc-2)

```jsx
python3 mcumgr_flash.py --image_path /home/bermanalon/git/etoot-gw-fw/ble_gateway_firmware/etoot_mg100_gw_fw_1.2.0-rc1/build/mg100/aws/zephyr/app_update.bin
```

- Create new certificates (`users-fastapi` repo)

```jsx
python add_mg_100_gateway_thing.py 354616090640025 --output_dir 354616090640025
```

- This will write a create new .PEM files and download it to desired folder.
- Add AmazonRootCA1 & AmazonRootCA1 ([Drive Link](https://drive.google.com/drive/u/0/folders/17w8sSeZP5cZUQuFpBl_JClBXJwSItqqa))
- Upload to [Drive Link](https://drive.google.com/drive/u/0/folders/17w8sSeZP5cZUQuFpBl_JClBXJwSItqqa)
- Add policy ‘mg100’ to generated certificate (Link)
- Upload the Downloaded Certificate files to device (ble_gw_fw repo)

```jsx
~/git/etoot-gw-fw/ble_gateway_firmware/scripts $ python3 mcumgr_certificate_upload.py --cert_folder ~/Alon/etoot/mg100_certs/354616090640025
```

- Update Sensors List to the MG100 GW (sets to True the desired shadow) (users-fastapi)

```jsx
python update_sensors_list.py deviceId-354616090640025 D98827F159FA D47B1B13780B E2F76EDF7F8C C4AD65086CE9 DE3A3181873F D6D2482E7F5B E4612CE76FCB F67581042586
```

Note the `deviceId` prefix!

## Create Entities - Postman Collection

- create_organization (if needed) - save id
- create_branch(es) (if needed) - save id

for each involved user, do:

- create_user (if needed)
- add_new_permission

## After Installation

- Upload PEM Files
- Create client folder in drive and put:
    - signed contract
    - Videos of installed sensors.
    - Diagram of installation (if applicable)
    - Accepted Price quote.
- Share folder with customer.
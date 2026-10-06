from . import WPS_blueprint
from flask import request, jsonify
import requests
import time
import json
import socket
from enum import IntEnum
import os
import re
import subprocess
import telnetlib

@WPS_blueprint.route('/WPS/ping')
def WPS_ping():
    return "Pinged -- WPS api"

# ------------------------
# WPS Helper functions
# ------------------------
# 1) send_req
# 2) manage_wps_outlet
# 3) process_wps_outlet_status
# 4) manage_eaton_outlet

def send_req(topic_name, API_ENDPOINT, message, htmlLog=None, display_live_logs=True, image_path=""):
    if display_live_logs:
        image_file_path = f"img~ {image_path}"
        if image_path != '':
            if (type(message) is str):
                data = {"topicName": topic_name, "message": message, "attachment": image_file_path}
            elif (type(message) is list):
                data = {"topicName": topic_name, "message": '\n'.join(str(v) for v in message), "attachment": image_file_path}
        else:
            if (type(message) is str):
                data = {"topicName": topic_name, "message": message}
            elif (type(message) is list):
                data = {"topicName": topic_name, "message": '\n'.join(str(v) for v in message)}
    if htmlLog != None:
        htmlLog.append(message)
    try:
        requests.post(url='http://localhost:8080/execution/live-logs', json=data,
                      headers={'Content-type': 'application/json'})
    except Exception as ex:
        print(str(ex))

def manage_wps_outlet(req_json):
    response_json = {}
    request_json = {}
    request_json = req_json
    htmlLog = []
    print(request_json)
    wps_ipaddress = request_json['wps_ipaddress']
    wps_default_port = int(request_json['wps_default_port'])
    wps_username = request_json['wps_username']
    wps_password = request_json['wps_password']
    wps_cmd = request_json['wps_cmd']

    try:
        socket_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_conn.connect((wps_ipaddress, wps_default_port))
        time.sleep(0.5)
        socket_conn.send(wps_username.encode())
        time.sleep(0.5)
        socket_conn.send(wps_password.encode())
        # send_req(request_json['topicName'], request_json['API_ENDPOINT'],
        #          f"Successfully logged into WPS", htmlLog)
        print('**Successfully logged into WPS')

        # send_req(request_json['topicName'], request_json['API_ENDPOINT'],
        #          f"Sending command to the WPS: {wps_cmd}", htmlLog)
        print('**Sending command to the WPS: {wps_cmd}')
        socket_conn.sendall(wps_cmd.encode())
        time.sleep(5)
        socket_conn.shutdown(socket.SHUT_WR)

        res = ""
        while True:
            data = socket_conn.recv(1024)
            if not data:
                 break
            res += data.decode()

        # Filter junk data
        remove_list = ['Please Login to Continue', 'Username:', "\n"]
        for word in remove_list:
            res = res.replace(word, "")

        print("Raw Output from WPS = " , res)
        socket_conn.close()
        # send_req(request_json['topicName'], request_json['API_ENDPOINT'],
        #          f"Logged out from the WPS", htmlLog)
        response_json["RESULT"] = "0"
        response_json['returnValue'] = res

    except Exception as ex:
           template = "An exception of type {0} occurred. Arguments:\n{1!r}"
           message = template.format(type(ex).__name__, ex.args)
           response_json["FailureReason"] = message
           response_json["RESULT"] = "1"
           #response_json["errorCode"] = "EC1001"
    finally:
           return json.dumps(response_json)

def process_wps_outlet_status(outlet_result, cmd_outlet_status, outlet_num):
    status_output = outlet_result['returnValue']
    print("Status Output from the helper function = ", status_output)
    outlet_list = (status_output.split(cmd_outlet_status + "=", 1)[1]).split(',')
    print("OutletList = ", outlet_list)
    status = outlet_list[outlet_num - 1]
    print(f"Outlet {outlet_num} status : {status}")
    outlet_status = "ON" if int(status) == WPSOutletAction.ON.value else "OFF"
    return outlet_status

@WPS_blueprint.route('/WPS/change_wps_outlet_status', methods=['POST'])
def change_wps_outlet_status():
    '''This API changes WPS outlet power status ON/OFF/RESET which makes power ON/OFF the connected device to that outlet.

            Args expected from Framework:
                wps_ipaddress: WPS device ip address
                wps_username: WPS device login username
                wps_password: WPS device login password
                wps_default_port: WPS default port number: 23
                outlet_num: WPS outlet number connected to device
                outlet_action: Action performing on outlet ON/OFF/RESET (OFF = 0, ON = 1 and RESET = 3)

            Return values to Framework:
                RESULT 0 : Pass, When WPS outlet status change successful.
                RESULT 1 : Fail, When WPS outlet status change failed. '''
    response_json = {}
    request_json = {}
    request_json = request.json
    htmlLog = []
    print(request_json)
    wps_ipaddress = request_json['wps_ipaddress']
    outlet_connected_device = request_json['outlet_connected_device']
    outlet_num = request_json['outlet_num']
    outlet_action = request_json['outlet_action']
    terminate = request_json['terminate_regression?']

    if any(not item or item is None or item in ["None", "Nil"] for item in request_json.values()):
        response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
        response_json[
            "FailureReason"] = f"Cannot run the API as missing some required WPS details in device inventory for the selected Testbed. Please update device inventory and rerun."
        response_json["errorCode"]= "EC1041"
        return json.dumps(response_json)

    if outlet_num not in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']:
        print(
            f"**Outlet number is not valid, please select the outlet in the range [1,2,3,,4,5,6,7,8,9,10,11,12]")
        response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
        response_json[
            "FailureReason"] = f"Invalid WPS outlet number {outlet_num} in the device inventory, please update outlet from [1,2,3,4,5,6,7,8,9,10,11,12] for the device {outlet_connected_device}"
        response_json["errorCode"]= "EC1035"
        return json.dumps(response_json)

    if outlet_action.lower() not in ["on", "off", "reset"]:
        print(f"**Outlet action is not valid, please select ON/OFF/RESET")
        response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
        response_json["FailureReason"] = f"Invalid WPS outlet action {outlet_action}, please pass ON/OFF/RESET"
        response_json["errorCode"]= "EC1258"
        return json.dumps(response_json)

    outlet_num = int(outlet_num)
    cmd_outlet_status = "?OutletStatus"
    cmd_outlet_set = f"!OutletSet={outlet_num},{outlet_action}"

    try:
        send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                 f"Trying to power {outlet_action} WPS outlet number {outlet_num} which is connected to device {outlet_connected_device}", htmlLog)
        print(f"***Trying to power {outlet_action} WPS outlet number {outlet_num} which is connected to device {outlet_connected_device}")

        send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                 f"Connecting to WPS with IP {wps_ipaddress}", htmlLog)
        print(f"***Connecting to WPS with IP {wps_ipaddress}")
        request_json['wps_cmd'] = cmd_outlet_status
        outlet_status_result = json.loads(manage_wps_outlet(request_json))
        if outlet_status_result['RESULT'] == '0':
            outlet_status = process_wps_outlet_status(outlet_status_result,cmd_outlet_status,outlet_num)
            send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                     f"Current power status of outlet {outlet_num} is {outlet_status}", htmlLog)
            print(f"***Current power status of outlet {outlet_num} is {outlet_status}")

            # performing power RESET on wired client
            if outlet_action == "RESET":
                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                         f"Resetting WPS outlet {outlet_num}", htmlLog)
                print(f"**Resetting WPS outlet {outlet_num}")
                request_json['wps_cmd'] = cmd_outlet_set
                outlet_change_result = json.loads(manage_wps_outlet(request_json))
                if outlet_change_result['RESULT'] == '0':
                    change_output = outlet_change_result['returnValue']
                    print("RESET Output from the helper function = ", change_output)
                    if change_output.strip() == "OK":
                        time.sleep(30)
                        request_json['wps_cmd'] = cmd_outlet_status
                        outlet_status_result = json.loads(manage_wps_outlet(request_json))
                        if outlet_status_result['RESULT'] == '0':
                            new_outlet_status = process_wps_outlet_status(outlet_status_result,cmd_outlet_status,outlet_num)
                            if new_outlet_status.lower() == "on":
                                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                                         f"Current power status of outlet {outlet_num} is {new_outlet_status}", htmlLog)
                                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                                         f"Successfully performed power reset on the device {outlet_connected_device}", htmlLog)
                                response_json["RESULT"] = "0"
                                response_json["returnValue"] = "PASS"
                                print(f"***Successfully performed power reset on the device {outlet_connected_device}")
                            else:
                                print(f"**Outlet failed to power ON after RESET")
                                response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                                response_json[
                                    "FailureReason"] = f"Outlet {outlet_num} failed to power ON after RESET"
                                response_json["errorCode"]= "EC1258"
                                return json.dumps(response_json)
                        else:
                            print(f"***Error occurred while fetching outlet status after power {outlet_action}, error: " + outlet_status_result['FailureReason'])
                            response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                            response_json["FailureReason"] = f"Error occurred while fetching outlet status after power {outlet_action}, error: " + outlet_status_result['FailureReason']
                            response_json["errorCode"]= "EC1259"
                            return json.dumps(response_json)
                    else:
                        print(f"**Failed to apply RESET on WPS outlet: {outlet_num}")
                        response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                        response_json["FailureReason"] = f"Failed to perform power RESET on WPS outlet {outlet_num}"
                        response_json["errorCode"]= "EC1258"
                        return json.dumps(response_json)
                else:
                    print(f"***Error occurred while power {outlet_action}, error: " + outlet_change_result['FailureReason'])
                    response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                    response_json["FailureReason"] = f"Error occurred while power {outlet_action}, details: " + outlet_change_result['FailureReason']
                    response_json["errorCode"]= "EC1258"
                    return json.dumps(response_json)
            # If outlet power status is already in expected mode ON/OFF
            elif outlet_status == outlet_action:
                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                         f"Skipping power status change as outlet {outlet_num} is already in expected state", htmlLog)
                response_json["RESULT"] = "0"
                response_json["returnValue"] = "PASS"
                print(f"**Current power status of outlet {outlet_num} is already {outlet_status} so,ignoring the status change.")
            # Performing power ON/OFF on CM
            else:
                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                         f"Powering {outlet_action} WPS outlet {outlet_num}", htmlLog)
                request_json['wps_cmd'] = cmd_outlet_set
                outlet_change_result = json.loads(manage_wps_outlet(request_json))
                if outlet_change_result['RESULT'] == '0':
                    change_output = outlet_change_result['returnValue']
                    print("Change Output from the helper function = ", change_output)
                    if change_output.strip() == "OK":
                        request_json['wps_cmd'] = cmd_outlet_status
                        outlet_status_result = json.loads(manage_wps_outlet(request_json))
                        if outlet_status_result['RESULT'] == '0':
                            new_outlet_status = process_wps_outlet_status(outlet_status_result, cmd_outlet_status, outlet_num)
                            if new_outlet_status == outlet_action:
                                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                                         f"Current power status of outlet {outlet_num} is {new_outlet_status}", htmlLog)
                                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                                         f"Successfully powered {new_outlet_status} the device {outlet_connected_device} ",
                                         htmlLog)
                                response_json["RESULT"] = "0"
                                response_json["returnValue"] = "PASS"
                                print(f"**Successfully powered {outlet_action} the device {outlet_connected_device}")
                            else:
                                print(f"**Failed to power {outlet_action} WPS outlet {outlet_num}")
                                response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                                response_json[
                                    "FailureReason"] = f"Failed to power {outlet_action} WPS outlet {outlet_num}"
                                response_json["errorCode"]= "EC1258"
                                return json.dumps(response_json)
                        else:
                            print(f"**Error occurred while fetching outlet: {outlet_num} status after power {outlet_action}, error: " + outlet_status_result['FailureReason'])
                            response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                            response_json[
                                "FailureReason"] = f"Error occurred while fetching outlet: {outlet_num} status after power {outlet_action}, error: " + outlet_status_result['FailureReason']
                            response_json["errorCode"]= "EC1259"
                            return json.dumps(response_json)
                    else:
                        print(f"**Failed to power {outlet_action} WPS outlet {outlet_num}")
                        response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                        response_json[
                            "FailureReason"] = f"Failed to power {outlet_action} WPS outlet {outlet_num}"
                        response_json["errorCode"]= "EC1258"
                        return json.dumps(response_json)
                else:
                    print(f"***Error occurred while powering {outlet_action} the outlet, error: " + outlet_change_result['FailureReason'])
                    response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                    response_json["FailureReason"] = f"Error occurred while powering {outlet_action} the outlet, error: " + outlet_change_result['FailureReason']
                    response_json["errorCode"]= "EC1258"
                    return json.dumps(response_json)
        else:
            print(f"***Failed to connect WPS with IP {wps_ipaddress}, error: " + outlet_status_result['FailureReason'])
            response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
            response_json[
                "FailureReason"] = f"Failed to connect WPS with IP {wps_ipaddress}, error: " + outlet_status_result['FailureReason']
            response_json["errorCode"]= "EC1254"
            return json.dumps(response_json)

    except Exception as ex:
           template = "An exception of type {0} occurred. Arguments:\n{1!r}"
           message = template.format(type(ex).__name__, ex.args)
           response_json["FailureReason"] = message
           response_json["RESULT"] = "1"
           response_json["errorCode"] = "EC1001"
           error_msg = ['TimeoutError', 'Connection timed out']
           if any(error in message for error in error_msg):
               response_json["FailureReason"] = "Failed to connect WPS due to TimeoutError occurred"
               response_json["errorCode"] = "EC1254"

    finally:
           return json.dumps(response_json)

class WPSOutletAction(IntEnum):
        OFF = 0
        ON = 1
        RESET = 3
        

@WPS_blueprint.route('/WPS/change_eaton_outlet_status', methods=['POST'])
def change_eaton_outlet_status():
    '''This API connects Eaton PDU via Telnet and changes outlet power status ON/OFF which makes power ON/OFF the connected device to that outlet.
       Note: This function is used as a helper function in /CMTS/power_reboot_cm_via_eaton_pdu
                Args expected from Framework:
                    wps_ipaddress: Eaton PDU device ip address
                    wps_username: Eaton PDU device login username
                    wps_password: Eaton PDU device login password
                    wps_default_port: Eaton PDU default Telnet port
                    outlet_num: Eaton PDU outlet number connected to device
                    outlet_action: Action performing on outlet ON/OFF (OFF = 0 and ON = 1)
                    outlet_connected_device: Device(DUT/Client) name that connected to outlet

                Return values to Framework:
                    RESULT 0 : Pass, When Eaton PDU outlet status change successful.
                    RESULT 1 : Fail, When Eaton PDU outlet status change failed. '''
    response_json = {}
    request_json = request.json
    htmlLog = []
    print(request_json)
    wps_ipaddress = request_json['wps_ipaddress']
    wps_port = request_json['wps_default_port']
    wps_username = request_json['wps_username']
    wps_password = request_json['wps_password']
    outlet_connected_device = request_json['outlet_connected_device']
    outlet_num = request_json['outlet_num']
    outlet_action = request_json['outlet_action']
    terminate = request_json['terminate_regression?']

    if any(not item or item is None or item in ["None", "Nil"] for item in request_json.values()):
        response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
        response_json[
            "FailureReason"] = f"Cannot run the API as missing some required Eaton PDU details in device inventory for the selected Testbed. Please update device inventory and rerun."
        response_json["errorCode"]= "EC1041"
        return json.dumps(response_json)

    # File creation to save output
    path = os.path.join(os.getcwd(), 'result', 'power_reboot', '')
    isExist = os.path.exists(path)
    if not isExist:
        # Create a new directory because it does not exist
        os.makedirs(path)
        print(f"New directory: {path} is created!")
    else:
        print(f"Directory :{path} already exists")
    # file_path = path
    file_name = path + "power_reboot_" + outlet_connected_device + ".txt"
    request_json["file_name"] = file_name

    telnet = telnetlib.Telnet()

    try:
        send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                 f"Connecting to Eaton PDU with IP {wps_ipaddress} using Telnet", htmlLog)
        print(f"***Connecting to Eaton PDU with IP {wps_ipaddress}")

        print("Trying to establish a Telnet connection")
        telnet.open(wps_ipaddress, wps_port, 20)
        telnet.read_until(b'login:', 10)  # waits until it receives a string 'login:'
        telnet.write(wps_username.encode('utf-8'))  # sends username to the server
        telnet.write(b'\r')  # sends return character to the server
        telnet.read_until(b'Password:', 10)  # waits until it receives a string 'Password:'
        telnet.write(wps_password.encode('utf-8'))  # sends password to the server
        telnet.write(b'\r')
        # time.sleep(15)
        login_error = telnet.expect([b'User Not Found', b'User Invalid Credential'], 20)
        if 'User Not Found' in login_error[2].decode('utf-8'):
            print(f"Invalid Username")
            response_json["RESULT"] = '1'
            response_json[
                "FailureReason"] = f"Telnet failed due to invalid Username, please check device inventory for {outlet_connected_device}"
            response_json["errorCode"]= "EC1255"
            return json.dumps(response_json)
        elif 'User Invalid Credential' in login_error[2].decode(
                'utf-8'):
            print(f"Invalid Password")
            response_json["RESULT"] = '1'
            response_json[
                "FailureReason"] = f"Telnet failed due to invalid Password, please check device inventory for {outlet_connected_device}"
            response_json["errorCode"]= "EC1255"
            return json.dumps(response_json)

        telnet.read_until(b'pdu#0>', 10) # Raise socket.timeout error if PDU is busy

        #Get total outlet count for PDU
        request_json['wps_cmd'] = 'get PDU.OutletSystem.Outlet.Count'
        request_json['outlet_no'] = ''
        outlet_count_status = json.loads(manage_eaton_outlet(request_json, telnet))
        if outlet_count_status['RESULT'] == '0' and outlet_count_status['returnValue']:
            outlets_count = int(outlet_count_status['returnValue'])
            if outlet_num in ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8',
                              'A9', 'A10', 'A11', 'A12', 'A13', 'A14','A15','A16']:
                outlet_no = outlet_num.replace('A', '')
                print("outlet_no = ", outlet_no)
            elif outlet_num in ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11', 'B12']:
                outlet_no = int(outlets_count / 2) + int(outlet_num.replace('B', ''))
                print("outlet_no = ", outlet_no)
            else:
                print(f"**Outlet number is not valid, please select the outlet in the range [1,2,3,,4,5,6,7,8,9,10,11,12]")
                response_json["RESULT"] = '1'
                response_json[
                    "FailureReason"] = f"Invalid PDU outlet number {outlet_num} in the device inventory, please update proper outlet number from range [A1,A2,...A16 or B1,B2...B12] for the device {outlet_connected_device}"
                response_json["errorCode"]= "EC2006"
                return json.dumps(response_json)

            request_json['outlet_no'] = outlet_no
            cmd_get_outlet_status = f'get PDU.OutletSystem.Outlet[{outlet_no}].PresentStatus.SwitchOnOff'
            cmd_set_outlet_poweron = f'set PDU.OutletSystem.Outlet[{outlet_no}].DelayBeforeStartup 0'
            cmd_set_outlet_poweroff = f'set PDU.OutletSystem.Outlet[{outlet_no}].DelayBeforeShutdown 0'

            send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                     f"Trying to power {outlet_action} Eaton PDU outlet number {outlet_num} which is connected to {outlet_connected_device}",
                     htmlLog)
            print(
                f"***Trying to power {outlet_action} Eaton PDU outlet number {outlet_num} which is connected to {outlet_connected_device}")

            # Get outlet current power status
            request_json['wps_cmd'] = cmd_get_outlet_status
            outlet_status_result = json.loads(manage_eaton_outlet(request_json, telnet))
            if outlet_status_result['RESULT'] == '0':
                status = outlet_status_result['returnValue']
                outlet_status = "ON" if int(status) == WPSOutletAction.ON.value else "OFF"
                send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                         f"Current power status of outlet {outlet_num} is {outlet_status}", htmlLog)
                print(f"***Current power status of outlet {outlet_num} is {outlet_status}")

                # If outlet power status is already in expected mode ON/OFF
                if outlet_status == outlet_action:
                    send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                             f"Skipping power status change as outlet {outlet_num} is already in expected state", htmlLog)
                    response_json["RESULT"] = "0"
                    response_json["returnValue"] = f"Skipping power status change as outlet {outlet_num} is already in expected state"
                    print(f"**Current power status of outlet {outlet_num} is already {outlet_status} so,ignoring the status change.")
                # Performing power ON/OFF on CM
                else:
                    send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                             f"Powering {outlet_action} PDU outlet {outlet_num}", htmlLog)
                    if outlet_action.lower() == 'on':
                        request_json['wps_cmd'] = cmd_set_outlet_poweron
                    else:
                        request_json['wps_cmd'] = cmd_set_outlet_poweroff

                    outlet_change_result = json.loads(manage_eaton_outlet(request_json, telnet))
                    if outlet_change_result['RESULT'] == '0':
                        change_output = outlet_change_result['returnValue']
                        print("outlet_change_result from the helper function = ", change_output)

                        if (outlet_action.lower() == 'on' and  change_output == '0') or (outlet_action.lower() == 'off' and  change_output == '-1'):
                            # Get outlet latest power status
                            request_json['wps_cmd'] = cmd_get_outlet_status
                            time.sleep(5)
                            outlet_status_result = json.loads(manage_eaton_outlet(request_json, telnet))
                            if outlet_status_result['RESULT'] == '0':
                                new_status = outlet_status_result['returnValue']
                                new_outlet_status = "ON" if int(new_status) == WPSOutletAction.ON.value else "OFF"
                                if new_outlet_status == outlet_action:
                                    send_req(request_json['topicName'], request_json['API_ENDPOINT'],
                                             f"Current power status of outlet {outlet_num} is {new_outlet_status}", htmlLog)
                                    response_json["RESULT"] = "0"
                                    response_json["returnValue"] = f"Successfully powered {new_outlet_status} the device {outlet_connected_device}"
                                    print(f"**Successfully powered {outlet_action} the device {outlet_connected_device}")
                                else:
                                    print(f"**Failed to power {outlet_action} Eaton PDU outlet {outlet_num}")
                                    response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                                    response_json[
                                        "FailureReason"] = f"Failed to power {outlet_action} Eaton PDU outlet {outlet_num}"
                                    response_json["errorCode"]= "EC1256"
                                    return json.dumps(response_json)
                            else:
                                print(f"**Error occurred while fetching outlet: {outlet_num} status after power {outlet_action}, error: " + outlet_status_result['FailureReason'])
                                response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                                response_json[
                                    "FailureReason"] = f"Error occurred while fetching outlet: {outlet_num} status after power {outlet_action}, error: " + outlet_status_result['FailureReason']
                                response_json["errorCode"]= outlet_status_result["errorCode"]
                                return json.dumps(response_json)
                                
                        else:
                            print(f"**Failed to power {outlet_action} Eaton PDU outlet {outlet_num}")
                            response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                            response_json[
                                "FailureReason"] = f"Failed to power {outlet_action} Eaton PDU outlet {outlet_num}"
                            response_json["errorCode"]= "EC1256"
                            return json.dumps(response_json)
                    else:
                        print(f"***Error occurred while powering {outlet_action} the outlet, error: " + outlet_change_result['FailureReason'])
                        response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                        response_json["FailureReason"] = f"Error occurred while powering {outlet_action} the outlet, error: " + outlet_change_result['FailureReason']
                        response_json["errorCode"]= "EC1256"
                        return json.dumps(response_json)
            else:
                print(f"***Error on getting current power status of Eaton PDU, error: " + outlet_status_result['FailureReason'])
                response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
                response_json[
                    "FailureReason"] = f"Error on getting current power status of Eaton PDU, error: " + outlet_status_result['FailureReason']
                response_json["errorCode"]= outlet_status_result["errorCode"]
                return json.dumps(response_json)
        else:
            print(f"***Error on fetching outlet count for PDU, error: " + outlet_count_status[
                'FailureReason'])
            response_json["RESULT"] = '1' if (str(terminate).lower() == 'no') else '3'
            response_json[
                "FailureReason"] = f"Error on fetching outlet count for PDU, error: " + \
                                   outlet_count_status['FailureReason']
            response_json["errorCode"]= outlet_count_status["errorCode"]
            return json.dumps(response_json)
    except ConnectionRefusedError as ce:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(ce).__name__, ce.args)
        response_json["FailureReason"] = message
        response_json["errorCode"]= "EC1101"
        if "111" in message or "Connection refused" in message:
            response_json["FailureReason"] = f"Telnet connection refused, please check Telnet enabled on PDU with proper Port and rerun"
            response_json["errorCode"]= "EC1255"
        response_json["RESULT"] = "1"
    except EOFError as eof:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(eof).__name__, eof.args)
        response_json["FailureReason"] = message
        response_json["errorCode"]= "EC1076"
        if "telnet connection closed" in message:
            response_json[
                "FailureReason"] = f"Telnet connection closed due to PDU is busy, please try later.",
            response_json["errorCode"]= "EC1255"
        response_json["RESULT"] = "1"
    except socket.timeout as tot:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(tot).__name__, tot.args)
        response_json["FailureReason"] = message
        response_json["errorCode"]= "EC1076"
        if "timed out" in message:
            response_json["FailureReason"] = "Timeout error occurred due to PDU unreachable/invalid hostname."
            response_json["errorCode"]= "EC1255"
        response_json["RESULT"] = "1"
    except Exception as ex:
       template = "An exception of type {0} occurred. Arguments:\n{1!r}"
       message = template.format(type(ex).__name__, ex.args)
       response_json["FailureReason"] = message
       response_json["errorCode"]= "EC1101"
       response_json["RESULT"] = "1"
    finally:
        if os.path.isfile(file_name):
            os.remove(file_name)
        telnet.close()
        return json.dumps(response_json)

def manage_eaton_outlet(req_json,telnet):
    response_json = {}
    request_json = {}
    request_json = req_json
    htmlLog = []
    print(request_json)
    wps_cmd = request_json['wps_cmd']
    outlet_no = request_json['outlet_no']
    file_name = request_json['file_name']
    try:
        telnet.write(wps_cmd.encode("utf-8"))
        telnet.write(b'\r')
        out = telnet.read_until(b'pdu#0>', 10)
        print(out.decode('utf-8'))
        file = open(file_name, 'wb')
        file.write(out)
        file.close()
        print("outlet_no =", outlet_no)
        filter_cmd = wps_cmd.replace(f'[{outlet_no}].', '.*')
        output = subprocess.Popen(f'cat {file_name} | grep -E -A1 "{filter_cmd}" | tail -1',
                                  stdout=subprocess.PIPE, shell=True).stdout
        result = output.read().decode("utf-8").strip()
        print(result)
        if result:
            response_json['RESULT'] = '0'
            response_json['returnValue'] = result
        else:
            response_json['RESULT'] = '1'
            response_json["FailureReason"] = 'Failed to run command on Eaton PDU'
            response_json["errorCode"]= "EC1076"

    except Exception as ex:
           template = "An exception of type {0} occurred. Arguments:\n{1!r}"
           message = template.format(type(ex).__name__, ex.args)
           response_json["FailureReason"] = message
           response_json["errorCode"]= "EC1076"
           if 'The parameter in the command is unknown' in message:
               response_json["FailureReason"] = "Outlet number mismatch, please update device inventory with proper PDU details"
               response_json["errorCode"]= "EC2006"
           if 'invalid literal for int() with base 10' in message:
               response_json["FailureReason"] = "Failed to perform action due to unexpected API error."
               response_json["errorCode"]= "EC1076"
           response_json["RESULT"] = "1"
    finally:
        return json.dumps(response_json)
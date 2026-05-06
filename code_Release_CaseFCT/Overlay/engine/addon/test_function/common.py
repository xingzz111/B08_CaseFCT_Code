import os
import time
import json
import ast
import re
import shutil
import platform
from idlelib.editor import keynames
from itertools import count
from sys import stderr

import serial
from paramiko.proxy import subprocess
from rtlib.utility import Unit
from rtlib.utility import ReturnDef
from rtlib.ictmes import STATION_ID, get_mes_status
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional, Union, Dict

from rtlib.ictmes import MesSN, UploadMES
from rtlib.runShell import runShell
from pylink.jlink import JLink
from CommonPlatform.src.mes import mes_config


class common(object):

    rpc_public_api = [
        'start_test', 'end_test', 'delay', 'station_id' ,'rpc_call','slot_id', 'fixture_id', 'vendor_id', 'check_uop',
        'get_scan_sn', 'powerOn', 'program_firmware', 'run_bmt_cmd', 'run_shell_cmd', 'init_rp2', 'ftdiUart',
        'writeSN', 'compareStr', 'powerOff', 'caculateADC', 'powerCycle', 'enterShipMode' ,'powerCycle_onlyCharge',
        'Wireless_Charger_Output', 'caculateWireless', 'caculateVoltage', 'adcRead', 'measureVoltageDMM', 'temperatureRead',
        'ccDetectRead', 'measureEload', 'adcReadRaw', 'getValueForKey', 'exec_json_cmd', 'get_json_result', 'get_testResult',
        'measureCurrentShipMode', 'relay_muilti', 'adcReadCurrent', 'powerOnWithBattery', 'buttonPress', 'buttonRelease'
    ]

    def __init__(self, xobjects):
        self.xobjects = xobjects
        self.site = xobjects.get('site')
        self.rp2_device = xobjects["rp2_device"]
        self.dutCommand = xobjects.get('dutCommand', None)
        self.publisher = xobjects.get('format_pub')
        self.publisher_common = xobjects.get('bmt_pub')
        self.buff_dict = None
        self.run_shell_flag = None
        self.bmt_cmd_dict = {}
        if platform.system() == "Windows":
            self.json_cmd_folder = os.path.dirname(os.path.abspath(__file__)) + '\\JsonBMT\\'
            with open(os.path.dirname(os.path.abspath(__file__))+"\\BMT.json", "r") as f:
                self.bmt_cmd_dict = json.load(f)
        else:
            with open(os.path.dirname(os.path.abspath(__file__))+"/BMT.json", "r") as f:
                self.bmt_cmd_dict = json.load(f)
        


    def log(self, message):
        if self.publisher:
            # print(message)
            msg = '{} \n'.format(message)
            self.publisher_common.publish(msg)

    def check_fail(self, lst):
        if False in lst:
            return ReturnDef.FAIL_STRING
        else:
            return ReturnDef.PASS_STRING

    def runRpcWithCheck(self, cmdDict):
        for cmomand in cmdDict:
            cmd = cmomand['cmd']
            args = cmomand['args']
            expect = cmomand['expect']
            result = self.rp2_device.rpc_call(cmd, args)
            if expect in str(result):
                return True
            else:
                return False

    def test_item_logger(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if result != 0 and result == False:
                    result = ReturnDef.FAIL_STRING
                if result == True or result == "done":
                    result = ReturnDef.PASS_STRING
            except Exception as e:
                result = f"--FAIL--{e}"
            return result

        return wrapper

    def start_test(self, *args, **kwargs):
        self.rp2_device.init()
        self.rp2_device.rpc_call("mixdevice.reset", None)
        time.sleep(0.2)
        return ""

    def end_test(self, *args, **kwargs):
        self.run_shell_flag = None
        self.rp2_device.rpc_call("mixdevice.reset", None)
        time.sleep(0.2)
        self.rp2_device.deinit()
        return ""


    def init_rp2(self, *args, **kwargs):
        self.rp2_device.init()
        return ""

    @test_item_logger
    def rpc_call(self, *args, **kwargs):
        _args = args[0]
        function_name = _args.get("func", None)
        if not function_name:
            return ReturnDef.MISS_PARAMETER
        args_list = _args.get("args", None)
        result = self.rp2_device.rpc_call(function_name, args_list)
        return result

    @test_item_logger
    def delay(self, *args, **kwargs):
        if len(args) != 1:
            return ReturnDef.MISS_PARAMETER
        self.log(f"log_in@delay:[{float(args[0])}ms]")
        time.sleep(float(args[0]) / 1000)
        self.log(f"log_out@CMD Response:[done]")
        return ReturnDef.PASS_STRING

    @test_item_logger
    def run_shell_cmd(self, *args, **kwargs):
        print('run shell command')
        try:
            args_dict = args[0]
            expect_keyword = args_dict.get("expect_keyword", None)
            expect_keyword = expect_keyword + str(self.site)
            parse_pattern = args_dict.get("parse_pattern", None)
            timeout = float(args_dict.get("Timeout", 5000))/1000
            cmd = args_dict.get("cmd", None)
            if not cmd:
                return ReturnDef.MISS_PARAMETER
            self.log(f"Send Shell cmd:{cmd}")
            return_code, resp, error = self.run_shell.run_shell_with_timeout(cmd, timeout)
            self.log(f"Return Code:{return_code}")
            self.log(f"BMT CMD Response:{resp}")
            self.log(f"Error:{error}")
            if return_code != 0:
                return "--FAIL--CMD Run Fail"
            if expect_keyword:
                if expect_keyword not in resp:
                    return "--FAIL--NO Expect key Words Found"
                else:
                    return resp
            if parse_pattern:
                parse_result = re.search(parse_pattern, resp)
                if not parse_result:
                    return "--FAIL--Parse Fail"
                else:
                    return parse_result.group(1)
            return ReturnDef.PASS_STRING
        except Exception as e:
            self.log(f"[Error] : {str(e)}")
            return ReturnDef.FAIL_STRING
        
    @test_item_logger
    def run_bmt_cmd(self, *args, **kwargs):
        if self.run_shell_flag == None:
            self.run_shell = runShell()
            self.run_shell_flag = True
        try:
            args_dict = args[0]
            expect_keyword = args_dict.get("expect_keyword", None)
            parse_pattern = args_dict.get("parse_pattern", None)
            timeout = float(args_dict.get("Timeout", 5000))/1000
            bmt_cmd_key = args_dict.get("cmd_key", None)
            bmt_cmd = self.bmt_cmd_dict.get(bmt_cmd_key, None)
            if not bmt_cmd:
                return ReturnDef.MISS_PARAMETER
            bmt_format_strings = args_dict.get("cmd_args", None)
            if bmt_format_strings:
                if not len(re.findall("{}", bmt_cmd)) == len(bmt_format_strings):
                    return "--FAIL--Wrong Format Strings"
                bmt_cmd = bmt_cmd.format(*bmt_format_strings)
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            try:
                return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, timeout)
            except:
                for count in range(3):
                    return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 3)
                    if return_code == 0:
                        break
            if bmt_cmd_key == 'SET_BUD_1V8_EN_L_HIGH' or bmt_cmd_key == 'BUD_BIAS_DISABLE_HIGH':
                return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, timeout)
            self.log(f"Return Code:{return_code}")
            self.log(f"log_out@CMD Response:[{resp}]")
            self.log(f"Error:{error}")
            if return_code != 0:
                return "--FAIL--CMD Run Fail"
            if expect_keyword:
                self.log(f"log_in@expect keyword:[{expect_keyword}]")
                if expect_keyword not in resp:
                    return "--FAIL--NO Expect key Words Found"
                self.log(f"log_out@expect keyword is found:[{expect_keyword}]")
            if parse_pattern:
                resp = str(resp)
                resp = resp.replace('\\n', '')
                resp = resp.replace('\\', '')
                print('sssssssssssssssssss',resp)
                parse_result = re.search(parse_pattern, resp)
                if not parse_result:
                    return "--FAIL--Parse Fail"
                else:
                    if bmt_cmd_key == 'BATTERY_TEMP_CHECK' or bmt_cmd_key == 'READ_CC2_DETECT_ADC' or bmt_cmd_key == 'READ_CC1_DETECT_ADC':
                        return float(parse_result.group(1))
                    if ',' in parse_result.group(1):
                        result = re.sub(r',\s*', ' ', parse_result.group(1))
                        return result
                    return parse_result.group(1)
            return ReturnDef.PASS_STRING
        except Exception as e:
            self.log(f"[Error] : {str(e)}")
            return ReturnDef.FAIL_STRING
    @test_item_logger
    def exec_json_cmd(self, *args, **kwargs):
        if self.run_shell_flag == None:
            self.run_shell = runShell()
            self.run_shell_flag = True
        try:
            args_dict = args[0]
            expect_keyword = args_dict.get("expect_keyword", None)
            parse_pattern = args_dict.get("parse_pattern", None)
            timeout = float(args_dict.get("Timeout", 5000))/1000
            bmt_cmd_key = args_dict.get("cmd_key", None)
            bmt_cmd = self.bmt_cmd_dict.get(bmt_cmd_key, None)
            if not bmt_cmd:
                return ReturnDef.MISS_PARAMETER
            bmt_format_strings = args_dict.get("cmd_args", None)
            if bmt_format_strings:
                if not len(re.findall("{}", bmt_cmd)) == len(bmt_format_strings):
                    return "--FAIL--Wrong Format Strings"
                bmt_cmd = bmt_cmd.format(*bmt_format_strings)
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            try:
                return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, timeout)
            except:
                for count in range(3):
                    return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 3)
                    if return_code == 0:
                        break
            if bmt_cmd_key == 'SET_BUD_1V8_EN_L_HIGH' or bmt_cmd_key == 'BUD_BIAS_DISABLE_HIGH':
                return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, timeout)
            self.log(f"Return Code:{return_code}")
            self.log(f"log_out@CMD Response:[{resp}]")
            self.log(f"Error:{error}")
            if return_code != 0:
                return "--FAIL--CMD Run Fail"
            if expect_keyword:
                self.log(f"log_in@expect keyword:[{expect_keyword}]")
                if expect_keyword not in resp:
                    return "--FAIL--NO Expect key Words Found"
                self.log(f"log_out@expect keyword is found:[{expect_keyword}]")
            if parse_pattern:
                parse_result = re.search(parse_pattern, resp)
                if not parse_result:
                    return "--FAIL--Parse Fail"
                else:
                    if bmt_cmd_key == 'BATTERY_TEMP_CHECK' or bmt_cmd_key == 'READ_CC2_DETECT_ADC' or bmt_cmd_key == 'READ_CC1_DETECT_ADC':
                        return float(parse_result.group(1))
                    if ',' in parse_result.group(1):
                        result = re.sub(r',\s*', ' ', parse_result.group(1))
                        return result
                    return parse_result.group(1)
            return ReturnDef.PASS_STRING
        except Exception as e:
            self.log(f"[Error] : {str(e)}")
            return ReturnDef.FAIL_STRING

    def exec_json_cmd(self, *args, **kwargs):
        args_dict = args[0]
        print('----------------kwargs',kwargs)
        print('----------------kwargs',kwargs)
        file_name = args_dict.get("file_name", None)
        bmt_format_strings = args_dict.get("cmd_args", None)
        file_name = self.json_cmd_folder + file_name
        _cmd = f'BoseManufacturingTool.exe sequence --file {file_name} --serial_number {bmt_format_strings[0]}'
        return_code, res_out, res_err = self.run_shell.run_shell_with_timeout(_cmd, 5)
        self.log(f"log_in@Send cmd:[{_cmd}]")
        for i in range(1, 4):
            if "UNRECOGNIZED EXCEPTION" in res_out or "Couldn't find device" in res_out or "Didn't find message " \
                                                                                           "matching" in res_out:
                return_code, res_out, res_err = self.run_shell.run_shell_with_timeout(_cmd, 5)
                time.sleep(0.5)
                continue
            else:
                log_formate = self.handle_json_return(res_out, res_err)
                print('log_formate',log_formate)
                self.log(f"log_out@CMD Response:[{log_formate}]")
                break
        if self.json_result:
            return ReturnDef.PASS_STRING
        else:
            return ReturnDef.FAIL_STRING + "UNRECOGNIZED EXCEPTION"

    def get_json_result(self, *args, **kwargs):
        print('-----result',args)
        print('-----type result', type(args))
        args_dict = args[0]
        print('-----argsdict',args_dict)
        print('-----type argsdict', type(args_dict))
        result_key_word = args_dict.get("result_key_word", None)
        json_cmd = self.json_cmd.pop()
        time.sleep(0.05)
        self.log(f"log_in@Send cmd form json:[{json_cmd}]")
        if self.json_result:
            cmd_result = self.json_result.pop()
            result = re.findall(result_key_word, cmd_result)
            exc_res = result[0].removesuffix(' ')
            self.log(f"log_out@CMD Response from json:[{cmd_result}]")
            return exc_res
        else:
            return ReturnDef.FAIL_STRING

    def handle_json_return(self, res_out, res_err):
        SequenceName = "'SequenceName': '\{}',"
        Description = "'Description': '{}',"
        SequenceReturn = " 'SequenceReturn':\r\n[ "
        log_format = ""
        print('11111111111111111',res_out)
        if "Couldn't find device" in res_out:
            self.json_result = None
            return "UNRECOGNIZED EXCEPTION"
        elif "Traceback" in res_out:
            out = res_out.split('Successful Commands:')
            out_dict = ast.literal_eval(out[1][4::])
            total = len(out_dict['SequenceReturn'])
            result_lst = []
            cmd_lst = []
            for i in range(total):
                if out_dict['SequenceReturn'][i]['Result'] == "Ok":
                    result_lst.append(out_dict['SequenceReturn'][i]['Detail'])
                    cmd_lst.append(out_dict['SequenceReturn'][i]['Command'])
            self.json_result = result_lst[::-1]
        elif res_out:
            out_dict = ast.literal_eval(res_out)
            total = len(out_dict['SequenceReturn'])
            result_lst = []
            cmd_lst = []
            for i in range(total):
                if out_dict['SequenceReturn'][i]['Result'] == "Ok":
                    result_lst.append(out_dict['SequenceReturn'][i]['Detail'])
                    cmd_lst.append(out_dict['SequenceReturn'][i]['Command'])
            self.json_result = result_lst[::-1]
            self.json_cmd = cmd_lst[::-1]
            res_len = len(out_dict["SequenceReturn"])
            log_format = "{" + log_format + SequenceName.format(out_dict["SequenceName"]) + "\r\n" + Description.format(
                out_dict["Description"]) + "\r\n" + SequenceReturn
            # print(log_format)
            for i in range(res_len):
                Device = "'Device': '{}',\r\n"
                Result = "'Result': '{}‘,'Command': '{}',\r\n"
                Detail = "'Detail': '{}‘,\r\n"
                device = out_dict["SequenceReturn"][i]["Device"]
                result = out_dict["SequenceReturn"][i]["Result"]
                command = out_dict["SequenceReturn"][i]["Command"]
                detail = out_dict["SequenceReturn"][i]["Detail"]
                Device = Device.format(device)
                Result = Result.format(result, command)
                Detail = Detail.format(detail)
                log_format += "\r\n{" + Device
                log_format += Result
                log_format += Detail + "},"
            log_format += "\r\n]\r\n}"
            return log_format
        else:
            pass



    @test_item_logger
    def program_firmware(self, *args, **kwargs) -> bool:
        """
        Program firmware to the target device using J-Link.

        Args:
            serial_no: J-Link device serial number
            firmware_path: Path to the firmware binary file
            device: Target device name
            speed: Interface speed in kHz

        Returns:
            bool: True if programming successful, False otherwise
        """
        def flash_progress_callback(action, progress_string, percentage):
            self.log(f"[{action}] {progress_string} - {percentage}%\n")
        serial_no = "202500" + str(self.site)
        # print("args is->",args)
        # serial_no = "2025001"
        device = args[0]
        firmware_path = args[1]
        jlink = JLink()
        try:
            # Open connection to J-Link
            self.log(f"[Connect] Opening connection to J-Link {serial_no}...\n")
            jlink.open(serial_no)

            # Connect to target device
            self.log(f"[Connect] Connecting to {device}...\n")
            jlink.connect(device, 1000, verbose=True)

            # Erase flash
            self.log("[Erase] Start erasing flash...\n")
            jlink.erase()
            self.log("[Erase] Flash erasing completed.\n")

            # Program firmware
            self.log("[Program] Programming firmware...\n")
            jlink.flash_file(firmware_path, 0x08000000, on_progress=flash_progress_callback)

            # Reset device
            self.log("[Reset] Resetting device...\n")
            jlink.reset()

            self.log("[Success] Programming completed successfully!\n")
            jlink.close()
            return ReturnDef.PASS_STRING

        except Exception as e:
            jlink.close()
            self.log(f"[Error] Programming failed: {str(e)}\n")
            return "--FAIL--Programming failed"

    @test_item_logger
    def compareStr(self, *args, **kwargs):
        res = args[0].replace("'", "")
        str1, str2 = res.split("#")
        self.log(f"log_in@SN Read and Scan:[{str1, str2}]")
        if str1 != str2:
            return ReturnDef.FAIL_STRING
        self.log(f"log_out@Compare Result:[{str1 == str2}]")
        return ReturnDef.PASS_STRING

    @test_item_logger
    def caculateADC(self, *args, **kwargs):
        print("ADC VALUE", args)
        adcValue = args[0]
        print("ADC VALUE 2", adcValue)
        adcCurrent = float(adcValue) / 8388.608
        return adcCurrent

    @test_item_logger
    def getValueForKey(self, *args, **kwargs):
        argsDic = kwargs
        keyname = argsDic.get('SubSubTestName')
        print("ADC VALUE", args[0])
        print('type of value', type(args[0]))
        res = args[0].replace("'","")
        list_data = ast.literal_eval(res)
        print('list_data',list_data)
        if 'MILLIVOLTS' in keyname:
            return list_data[0]
        elif 'RAW' in keyname:
            return list_data[1]
        elif 'CHARGE_CURRENT' in keyname:
            return list_data[2]
        return ReturnDef.FAIL_STRING

    @test_item_logger
    def caculateVoltage(self, *args, **kwargs):
        voltValue = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch0', '7000mv','DMM_VIN2_SEL_SW_WIRELESS_CHARGE_VOLT', 0.2])
        self.log(f"log_in@voltValue raw:[{voltValue}]")
        voltage = float(voltValue) * 5.7
        self.log(f"log_out@voltValue cal:[{voltValue} * 5.7]")
        return voltage

    @test_item_logger
    def measureCurrentShipMode(self, *args, **kwargs):
        argsDic = kwargs
        lowerLimit = argsDic.get('lowerLimit')
        upperLimit = argsDic.get('upperLimit')
        currentList = []
        results = []
        sn = args[0]
        for x in range(3):
            currentValuema = self.rp2_device.rpc_call("mixdevice.measureCurrentByOdin", ['battery', '1ma'])
            currentList.append(currentValuema)
        currentList.sort()
        print('voltageList',currentList)
        currentValuema = currentList[int(len(currentList) / 2)]
        if float(currentValuema) * 1000 > upperLimit or float(currentValuema) * 1000 < lowerLimit:
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
            time.sleep(0.2)
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DUT_PCM_SEL_SW'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
            time.sleep(0.2)
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TPF235_LID_TO_1V8'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
            time.sleep(2)
            bmt_cmd = 'BoseManufacturingTool.exe send \"Control.ShipMode.Start 2000\" --expect \".\" --print_response --serial_number {}'.format(sn)
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
            self.log(f"log_out@CMD Response:[{resp}]")
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 10], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT', 'DISCONNECT'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW', 'DISCONNECT'], "expect": "True"}]))
            time.sleep(5)
            currentValuema = self.rp2_device.rpc_call("mixdevice.measureCurrentByOdin", ['battery', '1ma'])
        self.log(f"log_in@currentValue raw:[{currentValuema}]")
        currentValue = float(currentValuema) * 1000
        self.log(f"log_out@currentValue cal:[{currentValuema} * 1000]")
        return currentValue

    def caculateWireless(self, *args, **kwargs):
        # res = args[0].replace("'", "")
        # LSB, MSB = res.split("#")
        LSB = self.get_json_result({'result_key_word':'StatusQualifier=(\w+)'})
        MSB = self.get_json_result({'result_key_word':'StatusQualifier=(\w+)'})
        combined = hex((int(MSB) << 8) | int(LSB))
        result = str(combined)
        self.log(f"log_in@combined hex:[{result}]")
        result = int(result, 16)
        self.log(f"log_out@hex to int:[{result}]")
        return result

    @test_item_logger
    def station_id(self, *args, **kwargs):
        return STATION_ID

    @test_item_logger
    def get_testResult(self, *args, **kwargs):
        if args[0] == 'True':
            return 'PASS'
        elif args[0] == 'False':
            return 'FAIL'

    @test_item_logger
    def fixture_id(self, *args, **kwargs):
        return "fixturexxx"

    @test_item_logger
    def slot_id(self, *args, **kwargs):
        slot_id = "slot" + str(self.site + 1)
        return slot_id

    @test_item_logger
    def vendor_id(self, *args, **kwargs):
        return "OSENS"

    @test_item_logger
    def check_uop(self, *args, **kwargs):
        if get_mes_status():
            sn = str(args[0])
            try:
                mes = UploadMES()
                cmd = f'"COMMAND": "CheckData", "SERIAL_NUMBER": "{sn}", "VERSION": "V1.0", "TERMINAL_NAME": "E4_2F_B06_CMB_FCT_01"'
                self.log(f"log_in@Send cmd:[{cmd}]")
                state, resp = mes.check_data(sn)
                self.log(f"log_out@CMD Response:[{resp}]")
                if not state:
                    self.log("check uop failed,get data from MES failed")
                    return ReturnDef.FAIL_STRING
                if state and state == "--SKIP--":
                    return resp
                uop_result = resp.get("RESULT")
                result_info = resp.get("RESULT_INFO")
                if uop_result == "OK":
                    return ReturnDef.PASS_STRING
                else:
                    self.log("MES data:{}".format(json.dumps(resp)))
                    return "--FAIL--{}".format(result_info)
            except Exception as e:
                self.log("ERROR:{}".format(e))
                return ReturnDef.FAIL_EXCEPT
        else:
            return ReturnDef.SKIP_STRING

    @test_item_logger
    def get_scan_sn(self, *args, **kwargs):
        self._sn = ""
        sn = str(args[0]).strip("'")
        sn_limit = re.search("\w{11}(\d+)\w{6}", mes_config.SCAN_SN_LIMIT).group(1)
        sn_scanned = re.search("\w{11}(\d+)\w{6}", sn).group(1)
        if not sn_limit == sn_scanned:
            return "--FAIL--SCAN Wrong SN"
        self._sn = sn
        return sn

    @test_item_logger
    def relay_muilti(self, *args, **kwargs):
        results = []
        args_dict = args[0]
        netName = args_dict.get("netName", None)
        netTable = netName.split('#')
        for netName in netTable:
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": [netName], "expect": "True"}]))
        return self.check_fail(results)


    @test_item_logger
    def buttonPress(self, *args, **kwargs):
        sn = args[0]
        delayTime = 30
        self.rp2_device.rpc_call("mixdevice.relay", ['CYLINDER_TO_BUTTON'])
        bmt_cmd = 'BoseManufacturingTool.exe send \"Manufacturing.SerialNumber.Get 1\" --expect \".\" --print_response --serial_number {}'.format(sn)

        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 2000)
        self.log(f"Return Code:{return_code}")
        self.log(f"Error:{error}")
        if return_code == 0 and sn in resp:
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            self.log(f"log_out@CMD Response:[{resp}]")
        else:
            return ReturnDef.FAIL_STRING
        self.log(f"log_in@Delay :[{delayTime}]s")
        time.sleep(delayTime)
        self.log(f"log_out@Response :[DONE]")
        return_code0, resp0, error0 = self.run_shell.run_shell_with_timeout(bmt_cmd, 2000)
        self.log(f"Return Code:{return_code0}")
        self.log(f"Error:{error0}")
        if return_code0 != 0 or 'Couldn\'t find device' in resp0:
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            self.log(f"log_out@CMD Response:[{resp0}]")
        else:
            return ReturnDef.FAIL_STRING
        time.sleep(0.2)
        self.rp2_device.rpc_call("mixdevice.relay", ['CYLINDER_TO_BUTTON', 'DISCONNECT'])
        time.sleep(3)
        return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout(bmt_cmd, 2000)
        self.log(f"Return Code:{return_code1}")
        self.log(f"Error:{error1}")
        if return_code1 == 0 and sn in resp1:
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            self.log(f"log_out@CMD Response:[{resp1}]")
        else:
            return ReturnDef.FAIL_STRING
        return ReturnDef.PASS_STRING


    @test_item_logger
    def buttonRelease(self, *args, **kwargs):
        sn = args[0]
        timeout = 30
        bmt_cmd = 'BoseManufacturingTool.exe send \"Manufacturing.SerialNumber.Get 1\" --expect \".\" --print_response --serial_number {}'.format(sn)
        startTime = time.time()
        while True:
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 2000)
            self.log(f"Return Code:{return_code}")
            self.log(f"Error:{error}")
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            self.log(f"log_out@CMD Response:[{resp}]")
            if return_code == 0 and sn in resp:
                break
            stopTime = time.time()
            if stopTime - startTime >= timeout:
                return "--FAIL--DUT reboot is not complete"
            time.sleep(0.1)
        return ReturnDef.PASS_STRING


    @test_item_logger
    def powerOn(self, *args, **kwargs):
        results = []
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DUT_PCM_SEL_SW'], "expect": "True"}]))
        # # 调用rpc_call函数，打开DUT电源
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        # time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        time.sleep(0.1)
        # 调用rpc_call函数，打开充电
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        time.sleep(0.2)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TPF235_LID_TO_1V8'], "expect": "True"}]))
        # self.rp2_device.rpc_call("mixdevice.relay", ['PSU_BATT_TO_DUT'])
        time.sleep(0.2)
        return self.check_fail(results)

    @test_item_logger
    def powerOnWithBattery(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DUT_PCM_SEL_SW'], "expect": "True"}]))
        # 调用rpc_call函数，打开DUT电源
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        time.sleep(0.1)
        results.append(
            self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        time.sleep(0.1)
        # 调用rpc_call函数，打开充电
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        time.sleep(0.2)
        results.append(
            self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TPF235_LID_TO_1V8'], "expect": "True"}]))
        self.rp2_device.rpc_call("mixdevice.relay", ['PSU_BATT_TO_DUT'])
        self.rp2_device.rpc_call("mixdevice.relay", ['DMM_VIN1_SEL_SW'])

        time.sleep(0.2)
        return self.check_fail(results)

    @test_item_logger
    def powerOff(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        # time.sleep(3)
        # 调用rpc_call函数，打开DUT电源
        return self.check_fail(results)

    @test_item_logger
    def powerCycle(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，battery输出
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DUT_PCM_SEL_SW'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，打开充电
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TPF235_LID_TO_1V8'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
        # time.sleep(2)
        return self.check_fail(results)

    @test_item_logger
    def powerCycle_onlyCharge(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，battery输出
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，打开充电
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        time.sleep(0.5)
        self.rp2_device.rpc_call("mixdevice.measureCurrentByOdin", ['charger'])
        # time.sleep(2)
        return self.check_fail(results)

    @test_item_logger
    def Wireless_Charger_Output(self, *args, **kwargs):
        sn = args[0]
        # 调用rpc_call函数，battery输出
        results = []
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DUT_PCM_SEL_SW'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TPF235_LID_TO_1V8'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        time.sleep(0.5)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        self.log(f"log_in@delay:[2000ms]")
        time.sleep(2)
        self.log(f"log_out@CMD Response:[done]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout('BoseManufacturingTool.exe send \"Debug.GPIO.SetGet 43, 0, 2, 3\" --expect \".\" --print_response --serial_number {}'.format(sn), 5000)
        self.log(f"log_in@Send cmd:[BoseManufacturingTool.exe send \"Debug.GPIO.SetGet 43, 0, 2, 3\" --expect \".\" --print_response --serial_number {sn}]")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Return Code:{return_code}")
        self.log(f"BMT CMD Response:{resp}")
        self.log(f"Error:{error}")
        if return_code != 0:
            return_code, resp, error = self.run_shell.run_shell_with_timeout(
                'BoseManufacturingTool.exe send \"Debug.GPIO.SetGet 43, 0, 2, 3\" --expect \".\" --print_response --serial_number {}'.format(
                    sn), 5000)
            self.log(
                f"log_in@Send cmd:[BoseManufacturingTool.exe send \"Debug.GPIO.SetGet 43, 0, 2, 3\" --expect \".\" --print_response --serial_number {sn}]")
            self.log(f"log_out@CMD Response:[{resp}]")
            self.log(f"Return Code:{return_code}")
            self.log(f"BMT CMD Response:{resp}")
            self.log(f"Error:{error}")
        return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout('BoseManufacturingTool.exe send \"Debug.TAP.Start \\\"i2c sc\\\"\" --expect \".\" --print_response --serial_number {}'.format(sn), 5000)
        self.log(f"log_in@Send cmd:[BoseManufacturingTool.exe send \"Debug.TAP.Start \\\"i2c sc\\\"\" --expect \".\" --print_response --serial_number {sn}]")
        self.log(f"log_out@CMD Response:[{resp1}]")
        self.log(f"Return Code:{return_code1}")
        self.log(f"BMT CMD Response:{resp1}")
        self.log(f"Error:{error1}")
        if return_code1 != 0:
            # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
            # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
            # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
            time.sleep(0.1)
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DUT_PCM_SEL_SW'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TPF235_LID_TO_1V8'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))

            time.sleep(0.5)
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
            self.log(f"log_in@delay:[2000ms]")
            time.sleep(2)
            self.log(f"log_out@CMD Response:[done]")
            time.sleep(0.5)
            return_code, resp, error = self.run_shell.run_shell_with_timeout(
                'BoseManufacturingTool.exe send \"Debug.GPIO.SetGet 43, 0, 2, 3\" --expect \".\" --print_response --serial_number {}'.format(
                    sn), 5000)
            self.log(
                f"log_in@Send cmd:[BoseManufacturingTool.exe send \"Debug.GPIO.SetGet 43, 0, 2, 3\" --expect \".\" --print_response --serial_number {sn}]")
            self.log(f"log_out@CMD Response:[{resp}]")
            self.log(f"Return Code:{return_code}")
            self.log(f"BMT CMD Response:{resp}")
            self.log(f"Error:{error}")
            time.sleep(0.5)
            return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout(
                'BoseManufacturingTool.exe send \"Debug.TAP.Start \\\"i2c sc\\\"\" --expect \".\" --print_response --serial_number {}'.format(
                    sn), 5000)
            self.log(
                f"log_in@Send cmd:[BoseManufacturingTool.exe send \"Debug.TAP.Start \\\"i2c sc\\\"\" --expect \".\" --print_response --serial_number {sn}]")
            self.log(f"log_out@CMD Response:[{resp1}]")
            self.log(f"Return Code:{return_code1}")
            self.log(f"BMT CMD Response:{resp1}")
            self.log(f"Error:{error1}")
        self.log(f"log_in@delay:[2000ms]")
        time.sleep(2)
        self.log(f"log_out@CMD Response:[done]")
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.wctDacOutput", "args": [4100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['WIRELESS_OUTPUT_SW'], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.wctPWMOutput", "args": [128000,0.4], "expect": "done"}]))
        time.sleep(3)

        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TPF807_VOUT_W_IN2', 0.2])
        timeout = 20
        count = 0
        parse_pattern = 'Temperature=(\w+)'
        bmt_cmd = 'BoseManufacturingTool.exe send \"BatteryDebug.Temperature.Get\" --expect \".\" --print_response --serial_number {}'.format(sn)
        startTime = time.time()
        while True:
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
            self.log(f"Return Code:{return_code}")
            self.log(f"Error:{error}")
            if return_code == 0 and 'Temperature=' in resp:
                parse_result = re.search(parse_pattern, resp)
                if not parse_result:
                    return "--FAIL--Parse Fail"
                else:
                    self.log(f"log_in@Send cmd:[{bmt_cmd}]")
                    self.log(f"log_out@CMD Response:[{resp}]")
                    return self.check_fail(results)
            stopTime = time.time()
            if stopTime - startTime >= 5 and count < 1:
                self.rp2_device.rpc_call("mixdevice.chargeEnable", [10, 10])
                self.rp2_device.rpc_call("mixdevice.batteryEnable", [10, 10])
                time.sleep(0.2)
                self.rp2_device.rpc_call("mixdevice.batteryEnable", [3800, 500])
                self.rp2_device.rpc_call("mixdevice.chargeEnable", [5000, 500])
                count = count + 1
            if stopTime - startTime >= timeout:
                return "--FAIL--CMD send timeout"


    @test_item_logger
    def writeSN(self, *args, **kwargs):
        sn = args[0]
        sn = sn.replace("'", "")
        self.rp2_device.rpc_call("mixdevice.relay", ['USB_SEL_SW'])
        time.sleep(2) ## delay 5s for USB detect
        return_code, resp, error = self.run_shell.run_shell_with_timeout('BoseManufacturingTool.exe send \"Manufacturing.SerialNumber.SetGet 1, {}\" --expect \"Manufacturing\.SerialNumber\.Status SerialNumberID=Board SerialNumber={}\" --print_response'.format(sn, sn), 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"BMT CMD Response:{resp}")
        self.log(f"Error:{error}")
        if return_code != 0:
            return "--FAIL--CMD Run Fail"
        self.rp2_device.rpc_call("mixdevice.relay", ['USB_SEL_SW', 'DISCONNECT'])
        return ReturnDef.PASS_STRING

    @test_item_logger
    def adcReadRaw(self, *args, **kwargs):
        argsDic = kwargs
        keyname = argsDic.get('SubSubTestName')
        sn = args[0]
        bmt_cmd = 'BoseManufacturingTool.exe --verbose send \"cim.plc current\" --expect \".\" --print_response --protocol TAP'
        if 'BUD_L' in keyname:
            parse_pattern = (f'{sn}.+Left: (.*)')
        elif 'BUD_R' in keyname:
            parse_pattern = (f'{sn}.+Right: (.*)')
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        while True:
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
            self.log(f"Return Code:{return_code}")
            self.log(f"Error:{error}")
            parseResult = re.search(parse_pattern, error)
            if not parseResult:
                time.sleep(0.2)
                continue
            else:
                self.log(f"log_out@CMD Response:[{resp}{error}]")
                resList = []
                result = parseResult.group(1)
                millivolts_match = re.search(r'millivolts\s*(\d+)', result)
                if millivolts_match:
                    millivolts = millivolts_match.group(1)
                raw_match = re.search(r'raw\s*(\d+)', result)
                if raw_match:
                    raw = raw_match.group(1)
                charge_current_match = re.search(r'~(\d+)mA\s*charge current', result)
                if charge_current_match:
                    charge_current = charge_current_match.group(1)
                resList.append(millivolts)
                resList.append(raw)
                resList.append(charge_current)
                return resList


        return resp

    @test_item_logger
    def adcRead(self, *args, **kwargs):
        argsDic = kwargs
        keyname = argsDic.get('SubSubTestName')
        sn = args[0]
        repeatCount = 5
        if 'WITHOUT_ELOAD' in keyname:
            repeatCount = 1
        parse_pattern = 'Debug.ADC.Status Data=(\w+)'
        samples = []
        if 'BUD_L' in keyname:
            bmt_cmd = 'BoseManufacturingTool.exe send \"Debug.ADC.Get 100\" --expect \".\" --print_response --serial_number {}'.format(sn)
        elif 'BUD_R' in keyname:
            bmt_cmd = 'BoseManufacturingTool.exe send \"Debug.ADC.Get 101\" --expect \".\" --print_response --serial_number {}'.format(sn)
        for x in range(repeatCount):
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
            self.log(f"Return Code:{return_code}")
            self.log(f"Error:{error}")
            if return_code != 0:
                return "--FAIL--CMD Run Fail"
            parse_result = re.search(parse_pattern, resp)
            if not parse_result:
                return "--FAIL--Parse Fail"
            else:
                samples.append((parse_result.group(1), resp))
        samples.sort(key=lambda t: int(t[0]))
        print('retList=', [s[0] for s in samples])
        mid_idx = int(len(samples) - 1)
        result, selected_resp = samples[mid_idx]
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        self.log(f"log_out@CMD Response:[{selected_resp}]")
        time.sleep(0.2)
        self.log(f"log_in@Send cmd:[{int(result)} / 8388.608]")
        result = int(result) / 8388.608
        self.log(f"log_out@CMD Response:[{result}]")
        return result

    @test_item_logger
    def adcReadCurrent(self, *args, **kwargs):
        res = args[0]
        ADC_L_W_O_LOAD, ADC_L_W_LOAD = res.split("#")
        self.log(f"log_in@Send cmd:[{ADC_L_W_LOAD} - {ADC_L_W_O_LOAD} / 5.62]")
        result = (float(ADC_L_W_LOAD) - float(ADC_L_W_O_LOAD)) / 5.62
        self.log(f"log_out@CMD Response:[{result}]")
        return result


    @test_item_logger
    def ccDetectRead(self, *args, **kwargs):
        sn = args[0]
        parse_pattern = 'Debug.ADC.Status Data=(\w+)'
        bmt_cmd = 'BoseManufacturingTool.exe send \"Debug.ADC.Get 103\" --expect \".\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code != 0:
            return "--FAIL--CMD Run Fail"
        parse_result = re.search(parse_pattern, resp)
        if not parse_result:
            return "--FAIL--Parse Fail"
        else:
            result = parse_result.group(1)
        self.log(f"log_in@Send cmd:[{int(result)} / 8388.608]")
        result = int(result) / 8388.608
        self.log(f"log_out@CMD Response:[{result}]")
        return result


    @test_item_logger
    def measureVoltageDMM(self, *args, **kwargs):
        argsDic = args[0]
        netName = argsDic.get('netName')
        channel = argsDic.get('ch')
        count = int(argsDic.get('count'))
        voltageList = []
        for x in range(1):
            voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", [channel,'7000mv',netName, 0.5, count])
            voltageList.append(voltage)
        voltageList.sort()
        print('voltageList',voltageList)
        return voltageList[int(len(voltageList) / 2)]


    @test_item_logger
    def measureEload(self, *args, **kwargs):
        argsDic = args[0]
        channel = argsDic.get('ch')
        count = int(argsDic.get('count'))
        eloadList = []
        for x in range(1):
            voltage = self.rp2_device.rpc_call("mixdevice.measureByEload", [channel, 'current', 200, count])
            eloadList.append(voltage)
        eloadList.sort()
        print('eloadList',eloadList)
        return eloadList[int(len(eloadList) - 1)]

    @test_item_logger
    def enterShipMode(self, *args, **kwargs):
        sn = args[0]
        sn = sn.replace("'", "")
        bmt_cmd = 'BoseManufacturingTool.exe send \"Control.ShipMode.Start 2000\" --expect \".\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"log_out@CMD Response:[{resp}]")
        return ReturnDef.PASS_STRING

    @test_item_logger
    def ftdiUart(self, *args, **kwargs):
        args_dict = args[0]
        cmdorg = args_dict.get("cmd_key", None)
        # com = 'COM3' + str(self.site)
        if self.site == 0:
            com = 'COM40'
        elif self.site == 1:
            com = 'COM39'
        elif self.site == 2:
            com = 'COM33'
        elif self.site == 3:
            com = 'COM53'
        _port = serial.Serial(com, 115200)
        parse_pattern = args_dict.get("parse_pattern", None)
        cmd = cmdorg + '\r\n' + '\r\n'
        cmd = cmd.encode()
        # cmd2 = '\r\n'
        # cmd2 = cmd2.encode()
        count = 0
        timeout = 30
        startTime = time.time()
        while True:
            _port.write(cmd)
                # _port.write(cmd2)
            time.sleep(0.5)
            res = _port.read(_port.in_waiting)
            print('response of uart :', res)
            res = res.decode("utf-8")
            stopTime = time.time()
            count = count + 1
            if stopTime - startTime > timeout:
                print('read uart timeout!!! : {}'.format(stopTime - startTime))
                return ReturnDef.FAIL_STRING
            if 'i2c regRead result:' in res and cmdorg in res and '0000:' in res:
                try:
                    parse_result = re.search(parse_pattern, res)
                except Exception as e:
                    print('parse failed :',e)
                return int(parse_result.group(1), 16)

    @test_item_logger
    def temperatureRead(self, *args, **kwargs):
        timeout = 20
        sn = args[0]
        count = 0
        parse_pattern = 'Temperature=(\w+)'
        bmt_cmd = 'BoseManufacturingTool.exe send \"BatteryDebug.Temperature.Get\" --expect \".\" --print_response --serial_number {}'.format(sn)
        startTime = time.time()
        while True:
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
            self.log(f"Return Code:{return_code}")
            self.log(f"log_out@CMD Response:[{resp}]")
            self.log(f"Error:{error}")
            if return_code == 0 and 'Temperature=' in resp:
                parse_result = re.search(parse_pattern, resp)
                if not parse_result:
                    return "--FAIL--Parse Fail"
                else:
                    return int(parse_result.group(1))
            stopTime = time.time()
            if stopTime - startTime >= 5 and count < 1:
                self.rp2_device.rpc_call("mixdevice.chargeEnable", [10, 10])
                self.rp2_device.rpc_call("mixdevice.batteryEnable", [10, 10])
                time.sleep(0.2)
                self.rp2_device.rpc_call("mixdevice.batteryEnable", [3800, 500])
                self.rp2_device.rpc_call("mixdevice.chargeEnable", [5000, 500])
                count = count + 1
            if stopTime - startTime >= timeout:
                return "--FAIL--CMD send timeout"
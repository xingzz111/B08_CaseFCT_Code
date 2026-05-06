import os
import time
import json
import sys
import requests
import ast
import re
import serial
import shutil
import subprocess
import ctypes

from watchdog.watchmedo import parse_patterns
from winpty import PtyProcess
import platform
from collections import namedtuple
from rtlib.utility import Unit
from rtlib.utility import ReturnDef
from rtlib.ictmes import STATION_ID
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional, Union, Dict

from rtlib.ictmes import MesSN, UploadMES, get_mes_status
from rtlib.runShell import runShell
from pylink.jlink import JLink



class common(object):

    rpc_public_api = [
        'start_test', 'end_test', 'delay', 'station_id' ,'rpc_call','slot_id', 'vendor_id', 'check_uop',
        'query_mac_by_sn','get_scan_sn', 'run_bmt_cmd', 'run_shell_cmd', 'init_rp2', 'temperatureRead', 'measureEload',
        'writeSN', 'compareStr', 'powerOn', 'uart_test', 'powerCycle', 'risingWidth', 'led_test', 'getValueForLED',
        'uart_read_flash', 'exec_json_cmd', 'get_json_result', 'caculateWireless', 'measureVoltageDMM', 'measureWidth',
        'get_testResult', 'usb_test', 'caculateVoltage', 'powerOff', 'adcRead', 'batteryPowerOn', 'adcReadRaw',
        'enterShipMode', 'wirelessChargingInit', 'powerOnForLoad', 'buttonLTest', 'buttonHTest', 'preCharge',
        'switchTemp', 'USBOVP', 'USB_OCP', 'EXIT_USB_OCP', 'hallDetect', 'ntcJEITA', 'mosEnableLow', 'mosEnableHigh',
        'budResetHigh', 'writeStationFlag', 'pogoDisable', 'pogoEnable', 'measureVoltageDMMABS', 'chargerI2cTest',
        'wlssBatteryCurrent', 'wchg5v', 'wirelessChargingInitWithoutWLSS', 'measureTXPadCurrent', 'adcReadWithDisableCommunicate',
        'powerCycleBattery', 'run_command_attach_child_console', 'powerCycleShipMode', 'calculateADCRead', 'measureShipMode'
    ]

    def __init__(self, xobjects):
        self.xobjects = xobjects
        self.site = xobjects.get('site')
        self.rp2_device = xobjects["rp2_device"]
        self.dutCommand = xobjects.get('dutCommand', None)
        self.publisher = xobjects.get('format_pub')
        self.publisher_common = xobjects.get('bmt_pub')
        self.buff_dict = None
        self._port = None
        self.run_shell_flag = None
        self.bmt_cmd_dict = {}
        if platform.system() == "Windows":
            self.json_cmd_folder = os.path.dirname(os.path.abspath(__file__)) + '\\JsonBMT\\'
            self.powerShell_cmd_folder = os.path.dirname(os.path.abspath(__file__)) + '\\PowerShellCMD\\'
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

    def test_item_logger(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if type(result) is int or type(result) is float:
                    result = result
                else:
                    if result == False:
                        result = ReturnDef.FAIL_STRING
                    if result == True or result == "done":
                        result = ReturnDef.PASS_STRING
            except Exception as e:
                result = f"--FAIL--{e}"
            if type(result) is float:
                result = format(result, '.2f')
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

    def get_testResult(self, *args, **kwargs):
        if args[0] == 'True':
            print('---->result', args[0])
            print('---->type result', type(args[0]))
            return 'PASS'
        elif args[0] == 'False':
            return  'FAIL'


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
        self.log(f"log_in@delay:[{float(args[0]) / 1000}s]")
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

            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, timeout)

            if return_code != 0 or not resp:
                for count in range(3):
                    return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 3)
                    if return_code == 0:
                        break
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
                    return parse_result.group(1)
            return ReturnDef.PASS_STRING
        except Exception as e:
            self.log(f"[Error] : {str(e)}")
            return ReturnDef.FAIL_STRING

    @test_item_logger
    def exec_json_cmd(self, *args, **kwargs):
        args_dict = args[0]
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

    @test_item_logger
    def get_json_result(self, *args, **kwargs):
        args_dict = args[0]
        result_key_word = args_dict.get("result_key_word", None)
        if result_key_word == 'Control.(\w+\.\w+)':
            time.sleep(1.5)
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

    @test_item_logger
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


    def _bmt_server_monitor(self, cmd):
        self._pty_proc = None
        try:
            # 启动cmd.exe进程
            self._pty_proc = PtyProcess.spawn("cmd.exe", dimensions=(24, 800))
            self._pty_proc.fileobj.setblocking(False)

            # 发送命令并添加退出命令
            self._pty_proc.write(cmd + "\r\n")
            self._pty_proc.write("exit\r\n")  # 添加退出命令让cmd.exe正常关闭

            # 设置超时时间，避免无限等待
            start_time = time.time()
            timeout = 30  # 30秒超时

            output_content = ""

            while self._pty_proc.isalive():
                # 检查超时
                if time.time() - start_time > timeout:
                    print("Timeout reached, terminating process...")
                    break

                try:
                    content = self._pty_proc.fileobj.recv(2048)
                    if content:
                        content = content.decode("utf-8", errors='ignore')
                        content = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', content)
                        content = re.sub(r'[\x08\x07\x1b]', '', content)
                        output_content += content
                        # print(f'Output: {content}')
                    time.sleep(0.05)
                except Exception as e:
                    if "[WinError 10035]" in str(e):
                        # 非阻塞读取，没有数据可读，继续等待
                        time.sleep(0.05)
                    else:
                        print(f"Error reading output: {e}")
                        break

            # 确保进程终止
            if self._pty_proc.isalive():
                self._pty_proc.terminate()
                time.sleep(0.5)
                if self._pty_proc.isalive():
                    self._pty_proc.kill()

            return output_content

        except Exception as e:
            print(f"Error in _bmt_server_monitor: {e}")
            return ""
        finally:
            # 确保进程被清理
            if self._pty_proc and self._pty_proc.isalive():
                self._pty_proc.terminate()
                time.sleep(0.5)
                if self._pty_proc.isalive():
                    self._pty_proc.kill()



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
    def station_id(self, *args, **kwargs):
        return STATION_ID

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
                cmd = f'"COMMAND": "CheckData", "SERIAL_NUMBER": "{sn}", "VERSION": "V1.0", "TERMINAL_NAME": "E4_2F_B08_CMB_FCT_01"'
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
                    return  ReturnDef.PASS_STRING
                else:
                    self.log("MES data:{}".format(json.dumps(resp)))
                    return "--FAIL--{}".format(result_info)
            except Exception as e:
                self.log("ERROR:{}".format(e))
                return ReturnDef.FAIL_EXCEPT
        else:
            return ReturnDef.SKIP_STRING



    @test_item_logger
    def query_mac_by_sn(self, *args, **kwargs):
        sn = str(args[0])
        mes_sn = MesSN()
        try:
            mac, error_msg = mes_sn.get_mac(sn)
            self.log("GET: MAC:{} by SN:{}".format(mac, sn))
            if not mac:
                return ReturnDef.FAIL_STRING
            return mac
        except:
            return ReturnDef.FAIL_EXCEPT

    @test_item_logger
    def get_scan_sn(self, *args, **kwargs):
        user_home = os.path.expanduser('~')
        mes_config_path = f"{user_home}/testerconfig/mes_config_for_logger.json"
        with open(mes_config_path, "r") as f:
            CONST_OBJ = json.load(f)
        MES_CFG = CONST_OBJ.get("mes_config")
        SCAN_SN_LIMIT = MES_CFG.get("scan_sn_limit", "")
        self._sn = ""
        sn = str(args[0]).strip("'")
        sn_limit = re.search("\w{11}(\d+)\w{6}", SCAN_SN_LIMIT).group(1)
        sn_scanned = re.search("\w{11}(\d+)\w{6}", sn).group(1)
        if not sn_limit == sn_scanned:
            return "--FAIL--SCAN Wrong SN" + sn_scanned
        self._sn = sn
        return sn

    def check_fail(self, lst):
        if False in lst:
            return "--FAIL--"
        else:
            return "--PASS--"

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


    @test_item_logger
    def powerOn(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        # time.sleep(2)
        return self.check_fail(results)

    @test_item_logger
    def powerOnForLoad(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TP34_COM_L_TO_GND', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        # time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        time.sleep(2)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        time.sleep(2)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        # time.sleep(2)
        return self.check_fail(results)


    @test_item_logger
    def batteryPowerOn(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        self.log(f"log_in@delay:[(2000 / 1000)s]")
        time.sleep(2)
        self.log(f"log_out@CMD Response:[done]")
        return self.check_fail(results)


    @test_item_logger
    def measureWidth(self, *args, **kwargs):
        self.rp2_device.rpc_call("pio.load_program_low_high", None)
        self.rp2_device.rpc_call("pio.measure_start", None)
        self.rp2_device.rpc_call("mixdevice.relay", ['PP24V_TO_MAGNET', 'DISCONNECT'])
        self.log(f"log_in@delay:[(5000 / 1000)s]")
        time.sleep(5)
        self.log(f"log_out@CMD Response:[done]")
        result = self.rp2_device.rpc_call("pio.measure_stop", None)
        self.log(f"log_in@Send cmd:[{result} / 1000]")
        result = float(result) / 1000
        self.log(f"log_out@CMD Response:[{result}]")
        return result

    @test_item_logger
    def buttonLTest(self, *args, **kwargs):
        sn = args[0]
        parse_pattern = 'Debug.GPIO.Status (\w+=\w+\s\w+=\w+)'
        self.rp2_device.rpc_call("mixdevice.relay", ['CYLINDER_TO_BUTTON', 'CONNECT'])
        time.sleep(1)
        self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP58_33_BUTTON',])
        bmt_cmd = 'BoseManufacturingTool.exe  send \"Debug.GPIO.Get 45\" --expect \"Debug\.GPIO\.Status GPIONum=45 Level=Low Direction=Input\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code == 0:
            parse_result = re.search(parse_pattern, resp)
            if not parse_result:
                return "--FAIL--Parse Fail"
            else:
                return parse_result.group(1)
        else:
            return ReturnDef.FAIL_STRING

    @test_item_logger
    def buttonHTest(self, *args, **kwargs):
        sn = args[0]
        parse_pattern = 'Debug.GPIO.Status (\w+=\w+\s\w+=\w+)'
        self.rp2_device.rpc_call("mixdevice.relay", ['CYLINDER_TO_BUTTON', 'DISCONNECT'])
        time.sleep(1)
        bmt_cmd = 'BoseManufacturingTool.exe  send \"Debug.GPIO.Get 45\" --expect \"Debug\.GPIO\.Status GPIONum=45 Level=High Direction=Input\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code == 0:
            parse_result = re.search(parse_pattern, resp)
            if not parse_result:
                return "--FAIL--Parse Fail"
            else:
                return parse_result.group(1)

    @test_item_logger
    def preCharge(self, *args, **kwargs):
        sn = args[0]
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [2850, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        time.sleep(1)
        bmt_cmd = 'BoseManufacturingTool.exe  send \"Manufacturing.ChargerEnabled.SetGet 1\" --expect \"Manufacturing\.ChargerEnabled\.Status Enabled=True\" --return_all --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            return ReturnDef.FAIL_STRING
        time.sleep(1)
        self.rp2_device.rpc_call("mixdevice.measureCurrentByOdin", ['battery', '500ma'])
        current = self.rp2_device.rpc_call("mixdevice.measureCurrentByOdin", ['battery', '500ma'])
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        return current

    @test_item_logger
    def pogoDisable(self, *args, **kwargs):
        sn = args[0]
        bmt_cmd = 'BoseManufacturingTool.exe  send \"Manufacturing.I2CCheck.SetGet 0x3C, 2, 1, 0x02, 0x10\" --expect \"Manufacturing\.I2CCheck\.Status Status=0 StatusQualifier\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            return ReturnDef.FAIL_STRING
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP72_VLDO_1V8_1'])
        return voltage


    @test_item_logger
    def pogoEnable(self, *args, **kwargs):
        sn = args[0]
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP71_VLDO_1V8_2'])
        self.log(f"log_in@delay:[(2000 / 1000)s]")
        time.sleep(2)
        self.log(f"log_out@CMD Response:[done]")
        bmt_cmd = 'BoseManufacturingTool.exe  send \"Manufacturing.I2CCheck.SetGet 0x3C, 2, 1, 0x02, 0x30\" --expect \"Manufacturing\.I2CCheck\.Status Status=0 StatusQualifier\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            return ReturnDef.FAIL_STRING
        return voltage

    @test_item_logger
    def switchTemp(self, *args, **kwargs):
        argsDic = args[0]
        netName = argsDic.get('netName')
        batteryVolt = int(argsDic.get('batteryVoltage'))
        self.rp2_device.rpc_call("mixdevice.chargeEnable", [10, 10])
        self.rp2_device.rpc_call("mixdevice.batteryEnable", [10, 10])
        self.rp2_device.rpc_call("mixdevice.relay", [netName])
        self.rp2_device.rpc_call("mixdevice.batteryEnable", [batteryVolt, 500])
        self.rp2_device.rpc_call("mixdevice.chargeEnable", [5000, 500])
        time.sleep(1)
        return ReturnDef.PASS_STRING


    @test_item_logger
    def risingWidth(self, *args, **kwargs):
        argsDic = kwargs
        lowerLimit = argsDic.get('lowerLimit')
        upperLimit = argsDic.get('upperLimit')

        repeatCount = 15
        results = []
        for count in range(repeatCount):
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TP58_33_BUTTON_TO_LOW', 'CONNECT'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
            results.append(self.runRpcWithCheck([{"cmd": "pio2.load_program_low_high", "args": [], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "pio2.measure_start", "args": [], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
            time.sleep(0.1)
            pulse_width = self.rp2_device.rpc_call("pio2.measure_stop", None)
            results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['TP58_33_BUTTON_TO_LOW', 'DISCONNECT'], "expect": "True"}]))
            if not pulse_width:
                continue
            elif float(pulse_width) / 1000 >= lowerLimit and float(pulse_width) / 1000 <= upperLimit:
                self.log(f"log_in@Send cmd:[{pulse_width} / 1000]")
                pulse_width = float(pulse_width) / 1000
                self.log(f"log_out@CMD Response:[{pulse_width}]")
                break
            else:
                results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
                results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'CONNECT'], "expect": "True"}]))
                results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
                time.sleep(0.1)
                results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
            if count == 14:
                return pulse_width
            time.sleep(0.5)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [0, 10], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT', 'DISCONNECT'], "expect": "True"}]))
        return pulse_width

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
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，打开充电
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        time.sleep(1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
        return self.check_fail(results)


    @test_item_logger
    def powerCycleBattery(self, *args, **kwargs):
        sn = args[0]
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，battery输出
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，打开充电
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        time.sleep(2)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['DMM_VIN1_SEL_SW'], "expect": "True"}]))
        # chargerDisable = 'BoseManufacturingTool.exe  send \"Manufacturing.ChargerEnabled.SetGet 0\" --expect \".\" --return_all --print_response --serial_number {}'.format(sn)
        # self.log(f"log_in@Send cmd:[{chargerDisable}]")
        # return_code, resp, error = self.run_shell.run_shell_with_timeout(chargerDisable, 5000)
        # self.log(f"Return Code:{return_code}")
        # self.log(f"log_out@CMD Response:[{resp}]")
        # self.log(f"Error:{error}")
        # if return_code != 0 or 'No messages seen' in resp:
        #     return ReturnDef.FAIL_STRING
        return self.check_fail(results)


    @test_item_logger
    def powerCycleShipMode(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，battery输出
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT'], "expect": "True"}]))
        time.sleep(0.2)
        # 调用rpc_call函数，打开充电
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW'], "expect": "True"}]))
        time.sleep(1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PP24V_TO_MAGNET'], "expect": "True"}]))
        # time.sleep(8)
        return self.check_fail(results)



    @test_item_logger
    def enterShipMode(self, *args, **kwargs):
        sn = args[0]
        results = []
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PP24V_TO_MAGNET'], "expect": "True"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'DISCONNECT'], "expect": "True"}]))
        time.sleep(1)
        bmt_cmd = 'BoseManufacturingTool.exe send \"Control.ShipMode.Start 2000\" --expect \".\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_VCHG_TO_DUT', 'DISCONNECT'], "expect": "True"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [0, 10], "expect": "done"}]))
        # results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        return ReturnDef.PASS_STRING

    def measureShipMode(self, *args, **kwargs):
        repeatCount = 5
        current_list = []
        for count in range(repeatCount):
            shipModeCurrent = self.rp2_device.rpc_call("mixdevice.measureCurrentByOdin", ['battery', '10ua'])
            current_list.append(shipModeCurrent)
        current_list.sort()
        clean_list = current_list[1:-1]
        resultValue = sum(clean_list) / len(clean_list)
        self.log(f"log_in@Send cmd:[{resultValue} * 1000]")
        shipModeCurrentua = float(resultValue) * 1000
        self.log(f"log_out@CMD Response:[{shipModeCurrentua}]")
        return shipModeCurrentua

    @test_item_logger
    def wirelessChargingInit(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        time.sleep(0.2)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.wctDacOutput", "args": [4100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['WIRELESS_OUTPUT_SW'], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.wctPWMOutput", "args": [128000, 0.4], "expect": "done"}]))
        return self.check_fail(results)


    @test_item_logger
    def chargerI2cTest(self, *args, **kwargs):
        sn = args[0]
        parse_pattern = 'Manufacturing.I2CCheck.Status Status=0 (\w+\=\w+)'
        chargerDisable = 'BoseManufacturingTool.exe  send \"Manufacturing.ChargerEnabled.SetGet 0\" --expect \".\" --return_all --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{chargerDisable}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(chargerDisable, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            self.wirelessChargingInit({'retry':3})
            time.sleep(5)
            self.log(f"log_in@Send cmd:[{chargerDisable}]")
            return_code, resp, error = self.run_shell.run_shell_with_timeout(chargerDisable, 5000)
            self.log(f"Return Code:{return_code}")
            self.log(f"log_out@CMD Response:[{resp}]")
            self.log(f"Error:{error}")
            if return_code != 0 or 'No messages seen' in resp:
                return ReturnDef.FAIL_STRING
        uartDisable = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 29, 0, 2, 3\" --expect \".\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{uartDisable}]")
        return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout(uartDisable, 5000)
        self.log(f"Return Code:{return_code1}")
        self.log(f"log_out@CMD Response:[{resp1}]")
        self.log(f"Error:{error1}")

        if return_code1 != 0 or 'No messages seen' in resp1:
            return ReturnDef.FAIL_STRING

        # budDisable = 'BoseManufacturingTool.exe  send \"CaseDebug.ChargerInterconnectBudControl.Start 3\" --expect \".\" --print_response --serial_number {}'.format(sn)
        # self.log(f"log_in@Send cmd:[{budDisable}]")
        # return_code2, resp2, error2 = self.run_shell.run_shell_with_timeout(budDisable, 5000)
        # self.log(f"Return Code:{return_code2}")
        # self.log(f"log_out@CMD Response:[{resp2}]")
        # self.log(f"Error:{error2}")



        chargerI2cTest = 'BoseManufacturingTool.exe  send \"Manufacturing.I2CCheck.Get 0x30, 1, 1, 0x10\" --expect \".\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{chargerI2cTest}]")
        for i in range(5):
            return_code0, resp0, error0 = self.run_shell.run_shell_with_timeout(chargerI2cTest, 5000)
            if return_code0 == 0:
                self.log(f"Return Code:{return_code0}")
                self.log(f"log_out@CMD Response:[{resp0}]")
                self.log(f"Error:{error0}")
                break
        if return_code0 == 0:
            parse_result = re.search(parse_pattern, resp0)
            if not parse_result:
                return "--FAIL--Parse Fail"
            else:
                return parse_result.group(1)
        else:
            return "--FAIL--CMD Run Fail"

    @test_item_logger
    def wchg5v(self, *args, **kwargs):
        sn = args[0]
        chargerEnable = 'BoseManufacturingTool.exe  send \"Manufacturing.ChargerEnabled.SetGet 1\" --expect \".\" --return_all --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{chargerEnable}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(chargerEnable, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            return ReturnDef.FAIL_STRING
        self.log(f"log_in@delay:[(3000 / 1000)s]")
        time.sleep(3)
        self.log(f"log_out@CMD Response:[done]")
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP81_WCHG_5V'])
        return voltage

    @test_item_logger
    def wirelessChargingInitWithoutWLSS(self, *args, **kwargs):
        results = []
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [10, 100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeDisable", "args": [], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.reset", "args": [], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['NTC_SEL_SW_NORMAL_TEMP', 'CONNECT'], "expect": "True"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['PSU_BATT_TO_DUT'], "expect": "True"}]))
        results.append(
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['USB_SEL_SW', 'CONNECT'], "expect": "True"}])))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.batteryEnable", "args": [3800, 500], "expect": "done"}]))
        time.sleep(3)
        return self.check_fail(results)

    @test_item_logger
    def wlssBatteryCurrent(self, *args, **kwargs):
        results = []
        current = self.rp2_device.rpc_call("mixdevice.measureCurrentByOdin", ['battery', '500ma'])
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.wctDacOutput", "args": [4100], "expect": "done"}]))
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['WIRELESS_OUTPUT_SW'], "expect": "True"}]))
        time.sleep(0.1)
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.wctPWMOutput", "args": [128000, 0.4], "expect": "done"}]))
        return current

    @test_item_logger
    def ntcJEITA(self, *args, **kwargs):
        sn = args[0]
        bmt_cmd = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 6, 1, 2, 3\" --expect \"Debug\.GPIO\.Status GPIONum=6 Level=High Direction=Output Pull=Up\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"Return Code:{return_code}")
        self.log(f"log_out@CMD Response:[{resp}]")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            return ReturnDef.FAIL_STRING
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP59_NTC_PIN1'])
        return voltage


    @test_item_logger
    def mosEnableLow(self, *args, **kwargs):
        sn = args[0]
        Pogo_Disable = 'BoseManufacturingTool.exe  send \"Manufacturing.I2CCheck.SetGet 0x3C, 2, 1, 0x02, 0x10\" --expect \"Manufacturing\.I2CCheck\.Status Status=0 StatusQualifier\" --print_response --serial_number {}'.format(
            sn)
        self.log(f"log_in@Send cmd:[{Pogo_Disable}]")
        return_code0, resp0, error0 = self.run_shell.run_shell_with_timeout(Pogo_Disable, 5000)
        self.log(f"Return Code:{return_code0}")
        self.log(f"log_out@CMD Response:[{resp0}]")
        self.log(f"Error:{error0}")
        if return_code0 != 0 or 'No messages seen' in resp0:
            return ReturnDef.FAIL_STRING
        Mos_EN_1 = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 17, 0, 2, 3\" --expect \"Debug\.GPIO\.Status GPIONum=17 Level=Low Direction=Output Pull=Up\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{Mos_EN_1}]")
        return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout(Mos_EN_1, 5000)
        self.log(f"Return Code:{return_code1}")
        self.log(f"log_out@CMD Response:[{resp1}]")
        self.log(f"Error:{error1}")
        if return_code1 != 0 or 'No messages seen' in resp1:
            return ReturnDef.FAIL_STRING
        Mos_EN_2 = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 18, 0, 2, 3\" --expect \"Debug\.GPIO\.Status GPIONum=18 Level=Low Direction=Output Pull=Up\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{Mos_EN_2}]")
        return_code2, resp2, error2 = self.run_shell.run_shell_with_timeout(Mos_EN_2, 5000)
        self.log(f"Return Code:{return_code2}")
        self.log(f"log_out@CMD Response:[{resp2}]")
        self.log(f"Error:{error2}")
        if return_code2 != 0 or 'No messages seen' in resp2:
            return ReturnDef.FAIL_STRING
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP62_POGOR_P_SNS'])
        return voltage

    @test_item_logger
    def mosEnableHigh(self, *args, **kwargs):
        sn = args[0]
        Mos_EN_1 = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 17, 1, 2, 3\" --expect \"Debug\.GPIO\.Status GPIONum=17 Level=High Direction=Output Pull=Up\" --print_response --serial_number {}'.format(
            sn)
        self.log(f"log_in@Send cmd:[{Mos_EN_1}]")
        return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout(Mos_EN_1, 5000)
        self.log(f"Return Code:{return_code1}")
        self.log(f"log_out@CMD Response:[{resp1}]")
        self.log(f"Error:{error1}")
        if return_code1 != 0 or 'No messages seen' in resp1:
            return ReturnDef.FAIL_STRING
        Mos_EN_2 = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 18, 1, 2, 3\" --expect \"Debug\.GPIO\.Status GPIONum=18 Level=High Direction=Output Pull=Up\" --print_response --serial_number {}'.format(
            sn)
        self.log(f"log_in@Send cmd:[{Mos_EN_2}]")
        return_code3, resp3, error3 = self.run_shell.run_shell_with_timeout(Mos_EN_2, 5000)
        self.log(f"Return Code:{return_code3}")
        self.log(f"log_out@CMD Response:[{resp3}]")
        self.log(f"Error:{error3}")
        if return_code3 != 0 or 'No messages seen' in resp3:
            return ReturnDef.FAIL_STRING
        BUD_RESET = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 5, 0, 2, 3\" --expect \"Debug\.GPIO\.Status GPIONum=5 Level=Low Direction=Output Pull=Up\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{BUD_RESET}]")
        return_code0, resp0, error0 = self.run_shell.run_shell_with_timeout(BUD_RESET, 5000)
        self.log(f"Return Code:{return_code0}")
        self.log(f"log_out@CMD Response:[{resp0}]")
        self.log(f"Error:{error0}")
        if return_code0 != 0 or 'No messages seen' in resp0:
            return ReturnDef.FAIL_STRING
        POGO_Disable = 'BoseManufacturingTool.exe  send \"Manufacturing.I2CCheck.SetGet 0x3C, 2, 1, 0x02, 0x10\" --expect \"Manufacturing\.I2CCheck\.Status Status=0 StatusQualifier\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{POGO_Disable}]")
        return_code2, resp2, error2 = self.run_shell.run_shell_with_timeout(POGO_Disable, 5000)
        self.log(f"Return Code:{return_code2}")
        self.log(f"log_out@CMD Response:[{resp2}]")
        self.log(f"Error:{error2}")
        if return_code2 != 0 or 'No messages seen' in resp2:
            return ReturnDef.FAIL_STRING
        time.sleep(0.5)
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP62_POGOR_P_SNS'])
        return voltage

    @test_item_logger
    def budResetHigh(self, *args, **kwargs):
        sn = args[0]
        POGO_DISABLE = 'BoseManufacturingTool.exe  send \"CaseDebug.ChargerInterconnectBudControl.Start 3\" --expect \"CaseDebug\.ChargerInterconnectBudControl\.Result Id=0\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{POGO_DISABLE}]")
        return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout(POGO_DISABLE, 5000)
        self.log(f"Return Code:{return_code1}")
        self.log(f"log_out@CMD Response:[{resp1}]")
        self.log(f"Error:{error1}")
        if return_code1 != 0 or 'No messages seen' in resp1:
            return ReturnDef.FAIL_STRING
        BUD_RESET = 'BoseManufacturingTool.exe  send \"Debug.GPIO.SetGet 5, 1, 2, 3\" --expect \"Debug\.GPIO\.Status GPIONum=5 Level=High Direction=Output Pull=Up\" --print_response --serial_number {}'.format(sn)
        self.log(f"log_in@Send cmd:[{BUD_RESET}]")
        return_code0, resp0, error0 = self.run_shell.run_shell_with_timeout(BUD_RESET, 5000)
        self.log(f"Return Code:{return_code0}")
        self.log(f"log_out@CMD Response:[{resp0}]")
        self.log(f"Error:{error0}")
        if return_code0 != 0 or 'No messages seen' in resp0:
            return ReturnDef.FAIL_STRING
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP33_PGOGL_P_SNS', 0.2, 3, 'zero'])
        return voltage


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
                    return str(parse_result.group(1))
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
    def adcReadWithDisableCommunicate(self, *args, **kwargs):
        argsDic = kwargs
        keyname = argsDic.get('SubSubTestName')
        lowerLimit = argsDic.get('lowerLimit')
        upperLimit = argsDic.get('upperLimit')
        sn = args[0]
        parse_result = ''
        repeatCount = 5
        Start3 = 'BoseManufacturingTool.exe send \"CaseDebug.ChargerInterconnectBudControl.Start 3\" --expect \"CaseDebug\.ChargerInterconnectBudControl\.Result Id=0\" --print_response --serial_number {}'.format(sn)
        return_code0, resp0, error0 = self.run_shell.run_shell_with_timeout(Start3, 5000)
        if return_code0 != 0 or 'No messages seen' in resp0:
            return ReturnDef.FAIL_STRING
        self.log(f"log_in@Send cmd:[{Start3}]")
        self.log(f"log_out@CMD Response:[{resp0}]")        

        Enable5V = 'BoseManufacturingTool.exe send \"CaseDebug.ChargerInterconnectVoltControl.SetGet 1, 1\" --expect \".\" --print_response --serial_number {}'.format(sn)
        return_code1, resp1, error1 = self.run_shell.run_shell_with_timeout(Enable5V, 5000)
        if return_code1 != 0 or 'No messages seen' in resp1:
            return ReturnDef.FAIL_STRING
        self.log(f"log_in@Send cmd:[{Enable5V}]")
        self.log(f"log_out@CMD Response:[{resp1}]")  

        parse_pattern = 'Debug.ADC.Status Data=(\w+)'
        if 'OPAMP2_VOUT' in keyname:
            bmt_cmd = 'BoseManufacturingTool.exe send \"Debug.ADC.Get 100\" --expect \".\" --print_response --serial_number {}'.format(
                sn)
        elif 'OPAMP1_VOUT' in keyname:
            bmt_cmd = 'BoseManufacturingTool.exe send \"Debug.ADC.Get 101\" --expect \".\" --print_response --serial_number {}'.format(
                sn)
        for x in range(repeatCount):
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
            if return_code == 0:
                parse_result = re.search(parse_pattern, resp)
            if not parse_result:
                return "--FAIL--Parse Fail"
            else:
                if (int(parse_result.group(1)) / 8388.608) >= lowerLimit and (
                        int(parse_result.group(1)) / 8388.608) <= upperLimit:
                    self.log(f"log_in@Send cmd:[{bmt_cmd}]")
                    self.log(f"log_out@CMD Response:[{resp}]")
                    self.log(f"Return Code:{return_code}")
                    self.log(f"Error:{error}")
                    self.log(f"log_in@Send cmd:[{int(parse_result.group(1))} / 8388.608]")
                    result = int(parse_result.group(1)) / 8388.608
                    self.log(f"log_out@CMD Response:[{result}]")
                    break
            if x == 14:
                return int(parse_result.group(1)) / 8388.608
            time.sleep(0.2)
        return result

    def calculateADCRead(self,  *args, **kwargs):
        adcRawValue = self.get_json_result({'result_key_word':'Debug.ADC.Status Data=(\w+)'})
        self.log(f"log_in@Send cmd:[{int(adcRawValue)} / 8388.608]")
        result = int(adcRawValue) / 8388.608
        self.log(f"log_out@CMD Response:[{result}]")
        return result

    @test_item_logger
    def adcRead(self, *args, **kwargs):
        argsDic = kwargs
        keyname = argsDic.get('SubSubTestName')
        lowerLimit = argsDic.get('lowerLimit')
        upperLimit = argsDic.get('upperLimit')
        sn = args[0]
        parse_result = ''
        repeatCount = 5
        # if 'WITHOUT_ELOAD' in keyname:
        #     repeatCount = 3
        parse_pattern = 'Debug.ADC.Status Data=(\w+)'
        if 'OPAMP2_VOUT' in keyname:
            bmt_cmd = 'BoseManufacturingTool.exe send \"Debug.ADC.Get 100\" --expect \".\" --print_response --serial_number {}'.format(
                sn)
        elif 'OPAMP1_VOUT' in keyname:
            bmt_cmd = 'BoseManufacturingTool.exe send \"Debug.ADC.Get 101\" --expect \".\" --print_response --serial_number {}'.format(
                sn)
        for x in range(repeatCount):
            return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
            if return_code == 0:
                parse_result = re.search(parse_pattern, resp)
            if not parse_result:
                return "--FAIL--Parse Fail"
            else:
                if (int(parse_result.group(1)) / 8388.608) >= lowerLimit and (int(parse_result.group(1)) / 8388.608) <= upperLimit:
                    self.log(f"log_in@Send cmd:[{bmt_cmd}]")
                    self.log(f"log_out@CMD Response:[{resp}]")
                    self.log(f"Return Code:{return_code}")
                    self.log(f"Error:{error}")
                    self.log(f"log_in@Send cmd:[{int(parse_result.group(1))} / 8388.608]")
                    result = int(parse_result.group(1)) / 8388.608
                    self.log(f"log_out@CMD Response:[{result}]")
                    break
            if x == 14:
                return int(parse_result.group(1)) / 8388.608
            time.sleep(0.2)
        return result

    def run_command_attach_child_console_via_helper(self, command, output_file):
        """
        通过在独立辅助进程中附着子控制台并抓取输出，避免主进程执行 FreeConsole/AttachConsole，
        从而不影响主进程的 USB 通讯。子控制台仍会弹窗显示。
        """
        if os.name != 'nt':
            subprocess.run(f"{command}", shell=True)
            print('response : ', '')
            return ''

        # 1) 使用新的控制台窗口启动命令（保持弹窗），并建立新的进程组以便后续清理
        try:
            # 使用 shell=False + shlex.split 精确传参，避免 cmd.exe 参与；
            # 显式关闭句柄继承（close_fds=True），减少子进程继承主进程 USB/文件句柄导致的句柄异常。
            creationflags = (
                    getattr(subprocess, 'CREATE_NEW_CONSOLE', 0) |
                    getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) |
                    0x00001000  # CREATE_BREAKAWAY_FROM_JOB
            )
            p = subprocess.Popen(
                command,
                shell=False,
                close_fds=True,
                creationflags=creationflags
            )
        except Exception:
            print('response : ', '')
            return ''

        # 2) 启动辅助读取进程，附着到子控制台抓取输出到文件
        helper_path = os.path.join(os.path.dirname(__file__), 'console_reader.py')
        subprocess.run([sys.executable, helper_path, str(p.pid), output_file], check=False)

        # 3) 辅助进程返回后，若子进程仍在运行，清理其进程树以关闭弹窗
        time.sleep(0.1)
        if p.poll() is None:
            try:
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], check=False,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except Exception:
                try:
                    p.terminate()
                except Exception:
                    pass

        # 4) 读取文件并输出 response（如出现路径错误，可能由辅助脚本回退到临时目录）
        content = ''
        try:
            with open(output_file, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read()
        except Exception:
            # 若主路径读取失败，这里不再重复定位回退路径；由辅助进程负责写入。
            pass

        print(f'response : {content}', flush=True)
        return content


    @test_item_logger
    def run_command_attach_child_console(self, *args, **kwargs):
        """
        Windows: 创建子进程并分配新控制台窗口，然后附着到该控制台读取屏幕缓冲区。
        不使用管道或重定向，轮询累计非空行，尽量捕获晚到的 Right 信息。
        """
        argsDic = kwargs
        sn = args[0]
        keyname = argsDic.get('SubSubTestName')
        
        output_file = f'D:\\tmp\\outputFile_{self.site}.txt'
        command = f'BoseManufacturingTool.exe --verbose send "cim.plc current" --expect "." --print_response --protocol TAP --serial_number {sn}'

        content = self.run_command_attach_child_console_via_helper(command, output_file)

        self.log(f"log_in@Send to BMT: {command}")

        self.log(f"log_out@BMT Response: {content}")

        print(f'response : {content}', flush=True)
        parse_pattern_l = (f'{sn}.+Left: (.*)')
        parse_pattern_r = (f'{sn}.+Right: (.*)')
        parseResultl = re.search(parse_pattern_l, content)
        parseResultr = re.search(parse_pattern_r, content)
        
        if not parseResultl or not parseResultr:
            for count in range(10):
                content = self.run_command_attach_child_console_via_helper(command, output_file)
                self.log(f"log_in@Send cmd:[{command}]")
                self.log(f"log_out@CMD Response:[{content}]")

                print(f'response : {content}', flush=True)
                parse_pattern_l = (f'{sn}.+Left: (.*)')
                parse_pattern_r = (f'{sn}.+Right: (.*)')
                parseResultl = re.search(parse_pattern_l, content)
                parseResultr = re.search(parse_pattern_r, content)
                if parseResultl or parseResultr:
                    break
                elif count == 9:
                    return ReturnDef.FAIL_STRING

        resultl = parseResultl.group(1)
        resultr = parseResultr.group(1)
        
        millivolts_l = re.search(r'millivolts (\d+)', str(resultl))
        millivolts_r = re.search(r'millivolts (\d+)', str(resultr))
        
        if not millivolts_l or not millivolts_r:
            return ReturnDef.FAIL_STRING
            
        millivolts_voltage_l = float(millivolts_l.group(1))
        millivolts_voltage_r = float(millivolts_r.group(1))

        if 'OPAMP1' in keyname:
            return millivolts_voltage_r
        elif 'OPAMP2' in keyname:
            return millivolts_voltage_l

    @test_item_logger
    def adcReadRaw(self, *args, **kwargs):
        argsDic = kwargs
        keyname = argsDic.get('SubSubTestName')
        # lowerLimit = argsDic.get('lowerLimit')
        # upperLimit = argsDic.get('upperLimit')
        sn = args[0]
        repeatCount = 30
        millivolts_l = False
        millivolts_r = False
        count = 0
        for count in range(repeatCount):
            bmt_cmd = f'BoseManufacturingTool.exe --verbose send \"cim.plc current\" --expect \".\" --print_response --protocol TAP --serial_number {sn}'
            parse_pattern_l = (f'{sn}.+Left: (.*)')
            parse_pattern_r = (f'{sn}.+Right: (.*)')
            # 解析结果
            try:
                content = self._bmt_server_monitor(bmt_cmd)
                print(f'=======================slot {self.site}================output {content}')
                parseResultl = re.search(parse_pattern_l, content)
                parseResultr = re.search(parse_pattern_r, content)
                
                if parseResultl and parseResultr:
                    resultl = parseResultl.group(1)
                    resultr = parseResultr.group(1)
                    self.log(f"resultl:{resultl}")
                    self.log(f"resultr:{resultr}")
                    
                    millivolts_l = re.search(r'millivolts (\d+)', str(resultl))
                    millivolts_r = re.search(r'millivolts (\d+)', str(resultr))
                    
                    if not millivolts_l or not millivolts_r:
                        print(f"warning：failed to extract millivolts, retrying...")
                        time.sleep(0.2)
                        continue
                        
                    self.log(f"charge_current_match_l:{millivolts_l.group(1)}")
                    self.log(f"charge_current_match_r:{millivolts_r.group(1)}")
                    
                    millivolts_voltage_l = float(millivolts_l.group(1))
                    millivolts_voltage_r = float(millivolts_r.group(1))
                    
                    # 检查结果是否在范围内
                    # if 'OPAMP1' in keyname:
                    #     if millivolts_voltage_r >= lowerLimit and millivolts_voltage_r <= upperLimit:
                    #         self.log(f"log_in@Send cmd:[{bmt_cmd}]")
                    #         self.log(f"log_out@CMD Response:[{content}]")
                    #         break
                    # if 'OPAMP2' in keyname:
                    #     if millivolts_voltage_l >= lowerLimit and millivolts_voltage_l <= upperLimit:
                    #         self.log(f"log_in@Send cmd:[{bmt_cmd}]")
                    #         self.log(f"log_out@CMD Response:[{content}]")
                    #         break
                    if millivolts_voltage_l or millivolts_voltage_r:
                        self.log(f"log_in@Send cmd:[{bmt_cmd}]")
                        self.log(f"log_out@CMD Response:[{content}]")
                        break
                        
                time.sleep(0.2)
                
            except:
                print("error：parsing exception")
                time.sleep(0.2)
                continue

        if not millivolts_l or not millivolts_r:
            return '--FAIL--'
        if 'OPAMP1' in keyname:
            return millivolts_voltage_r
        elif 'OPAMP2' in keyname:
            return millivolts_voltage_l

    @test_item_logger
    def measureVoltageDMM(self, *args, **kwargs):
        argsDic = args[0]
        kwargsDic = kwargs
        netName = argsDic.get('netName')
        channel = argsDic.get('ch')
        count = int(argsDic.get('count'))
        lowerLimit = kwargsDic.get('lowerLimit')
        upperLimit = kwargsDic.get('upperLimit')
        for x in range(count):
            voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", [channel,'7000mv',netName])
            if float(voltage) >= lowerLimit and float(voltage) <= upperLimit:
                break
        return voltage


    @test_item_logger
    def measureTXPadCurrent(self, *args, **kwargs):
        argsDic = args[0]
        netName = argsDic.get('netName')
        channel = argsDic.get('ch')
        current = self.rp2_device.rpc_call("mixdevice.measureByDMM", [channel, '7000mv', netName, 0.1, 15, 'TXPadCurrent'])
        return current


    @test_item_logger
    def measureVoltageDMMABS(self, *args, **kwargs):
        argsDic = args[0]
        kwargsDic = kwargs
        netName = argsDic.get('netName')
        channel = argsDic.get('ch')
        lowerLimit = kwargsDic.get('lowerLimit')
        upperLimit = kwargsDic.get('upperLimit')
        repeatCount = argsDic.get('count') or 1
        voltage_list = []
        for count in range(repeatCount):
            voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", [channel, '7000mv', netName])
            voltage_list.append(voltage)
        voltage_list.sort()
        clean_list = voltage_list[1:-1]
        return clean_list[0]


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
        print('voltageList',eloadList)
        return eloadList[int(len(eloadList) / 2)]

    @test_item_logger
    def caculateVoltage(self, *args, **kwargs):
        voltValue = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch0', '7000mv','DMM_VIN2_SEL_SW_WIRELESS_CHARGE_VOLT', 0.2])
        self.log(f"log_in@voltValue raw:[{voltValue}]")
        voltage = float(voltValue) * 5.7
        self.log(f"log_out@voltValue cal:[{voltValue} * 5.7]")
        return voltage

    def usb_test(self, *args, **kwargs):
        usbCheck = 'wmic logicaldisk get name'
        self.log(f"log_in@Send cmd:[{usbCheck}]")
        process = subprocess.Popen(
            usbCheck,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        output, _ = process.communicate(timeout=20)
        resp = output.decode('utf-8', errors='ignore')
        self.log(f"log_out@CMD Response:[{resp}]")
        if 'E:' not in resp:
            return ReturnDef.FAIL_STRING
        return ReturnDef.PASS_STRING


    @test_item_logger
    def uart_test(self, *args, **kwargs):
        args_dict = args[0]
        print('site for vr', self.site)
        port = 'COM1' + str(self.site)
        baudrate = 115200
        cmd = args_dict.get("cmd", None)
        self.log(f"log_in@Send cmd:[{cmd}]")
        cmd = str(cmd) + "\r\n"
        cmd = cmd.encode()
        dutUart = serial.Serial(port, baudrate)
        self.log('CONNECT port pass {}'.format(port))
        dutUart.write(cmd)
        time.sleep(1)
        res = dutUart.read(dutUart.in_waiting)
        self.log('response of uart {}'.format(res))
        response = res.decode("utf-8")
        response = response.replace('\r\n', '')
        # response = re.search("version: SpitfireCoreServices//(\w+\.\w+\.\w+\+\w+)", response)
        if not response:
            for count in range(3):
                dutUart.write(cmd)
                time.sleep(1)
                res = dutUart.read(dutUart.in_waiting)
                self.log('response of uart {}'.format(res))
                response = res.decode("utf-8")
                response = response.replace('\r\n', '')
                response = re.search("version: SpitfireCoreServices//(\w+\.\w+\.\w+\+\w+)", response)
                if response:
                    break
        self.log(f"log_out@CMD Response:[{response}]")
        dutUart.close()
        print("response =====>",response)
        return response

    @test_item_logger
    def uart_read_flash(self, *args, **kwargs):
        args_dict = args[0]
        port = 'COM1' + str(self.site)
        baudrate = 115200
        cmd = args_dict.get("cmd", None)
        self.log(f"log_in@Send cmd:[{cmd}]")
        cmd = str(cmd) + "\r\n"
        cmd = cmd.encode()
        dutUart = serial.Serial(port, baudrate)
        self.log('CONNECT port pass {}'.format(port))
        dutUart.write(cmd)
        time.sleep(1)
        res = dutUart.read(dutUart.in_waiting)
        self.log('response of uart {}'.format(res))
        response = res.decode("utf-8")
        response = response.replace('\r\n', '')
        self.log(f"log_out@CMD Response:[{response}]")
        response = re.search("Total MCU Flash:\s*(\w+)", response)
        dutUart.close()
        print("response =====>",response.group(1))
        return response.group(1)


    @test_item_logger
    def checkUSB(self, *args, **kwargs):
        list_device_cmd = "wmic path Win32_PnPEntity where \"PNPClass='HIDClass'\" get Name, DeviceID"
        time_start = time.time()
        self.log(f"log_in@Send cmd:[{list_device_cmd}]")
        while True:
            time_now = time.time()
            return_code, resp, error = self.run_shell.run_shell_with_timeout(list_device_cmd)
            self.log(f"List USB Device:{resp}")
            if "USB\VID_05A7&PID_40FC" in resp:
                time.sleep(3)
                break
            if time_now - time_start > 20:
                return ReturnDef.FAIL_STRING
            time.sleep(0.5)
        time.sleep(2)
        self.log(f"log_out@CMD Response:[{resp}]")
        return ReturnDef.PASS_STRING


    @test_item_logger
    def writeSN(self, *args, **kwargs):
        sn = args[0]
        parse_pattern = 'Board SerialNumber=(\w+)'
        self.rp2_device.rpc_call("mixdevice.relay", ['USB_SEL_SW'])
        list_device_cmd = "wmic path Win32_PnPEntity where \"PNPClass='HIDClass'\" get Name, DeviceID"
        time_start = time.time()
        while True:
            time_now = time.time()
            return_code, resp, error = self.run_shell.run_shell_with_timeout(list_device_cmd)
            self.log(f"List USB Device:{resp}")
            if "USB\VID_05A7&PID_40FC" in resp:
                time.sleep(3)
                break
            if time_now - time_start > 20:
                return ReturnDef.FAIL_STRING
            time.sleep(0.5)
        # time.sleep(5) ## delay 5s for USB detect
        self.log(f"log_in@Send cmd:['BoseManufacturingTool.exe send \"Manufacturing.SerialNumber.SetGet 1, {sn}\" --expect \"Manufacturing\.SerialNumber\.Status SerialNumberID=Board SerialNumber={sn}\" --print_response‘]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout('BoseManufacturingTool.exe send \"Manufacturing.SerialNumber.SetGet 1, {}\" --expect \"Manufacturing\.SerialNumber\.Status SerialNumberID=Board SerialNumber={}\" --print_response'.format(sn, sn), 5000)
        self.log(f"log_out@CMD Response:{resp}")
        self.log(f"Return Code:{return_code}")
        self.log(f"BMT CMD Response:{resp}")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            return "--FAIL--CMD Run Fail"
        result = re.search(parse_pattern, resp)
        self.rp2_device.rpc_call("mixdevice.relay", ['USB_SEL_SW', 'DISCONNECT'])
        return result.group(1)

    # @test_item_logger
    # def caculateWireless(self, *args, **kwargs):
    #     # res = args[0].replace("'", "")
    #     # LSB, MSB = res.split("#")
    #     LSB = self.get_json_result({'result_key_word':'StatusQualifier=(\w+)'})
    #     MSB = self.get_json_result({'result_key_word':'StatusQualifier=(\w+)'})
    #     combined = hex((int(MSB) << 8) | int(LSB))
    #     result = str(combined)
    #     self.log(f"log_in@combined hex:[{result}]")
    #     result = int(result, 16)
    #     self.log(f"log_out@hex to int:[{result}]")
    #     return result
    # @test_item_logger
    # def caculateWireless(self, *args, **kwargs):
    #     sn = args[0]
    #     argsDic = kwargs
    #     timeout = 5000
    #     parse_pattern = 'StatusQualifier=(\w+)'
    #     keyname = argsDic.get('SubSubTestName')
    #     if 'IOUT' in keyname:
    #         lsb_bmt_cmd = 'BoseManufacturingTool.exe send \"Manufacturing.I2CCheck.Get 0x30, 1, 1, 0x28\" --expect \".\" --print_response --serial_number {}'.format(
    #             sn)
    #         msb_bmt_cmd = 'BoseManufacturingTool.exe send \"Manufacturing.I2CCheck.Get 0x30, 1, 1, 0x29\" --expect \".\" --print_response --serial_number {}'.format(
    #             sn)
    #     elif 'VOUT' in keyname:
    #         lsb_bmt_cmd = 'BoseManufacturingTool.exe send \"Manufacturing.I2CCheck.Get 0x30, 1, 1, 0x2a\" --expect \".\" --print_response --serial_number {}'.format(
    #             sn)
    #         msb_bmt_cmd = 'BoseManufacturingTool.exe send \"Manufacturing.I2CCheck.Get 0x30, 1, 1, 0x2b\" --expect \".\" --print_response --serial_number {}'.format(
    #             sn)

    #     self.log(f"log_in@Send cmd:[{lsb_bmt_cmd}]")
    #     return_code, resp, error = self.run_shell.run_shell_with_timeout(lsb_bmt_cmd, timeout)
    #     self.log(f"log_out@CMD Response:[{resp}]")
    #     if return_code != 0 or 'No messages seen' in resp:
    #         return "--FAIL--CMD Run Fail"
    #     lsbResponse = re.search(parse_pattern, resp)
    #     LSB = int(lsbResponse.group(1))

    #     self.log(f"log_in@Send cmd:[{msb_bmt_cmd}]")
    #     return_code, resp, error = self.run_shell.run_shell_with_timeout(msb_bmt_cmd, timeout)
    #     self.log(f"log_out@CMD Response:[{resp}]")
    #     if return_code != 0 or 'No messages seen' in resp:
    #         return "--FAIL--CMD Run Fail"
    #     msbResponse = re.search(parse_pattern, resp)
    #     MSB = int(msbResponse.group(1))

    #     # LSB = int(args[0])
    #     # MSB = int(args[1])
    #     combined = hex((MSB << 8) | LSB)
    #     result = str(combined)
    #     self.log(f"log_in@combined hex:[{result}]")
    #     result = int(result, 16)
    #     self.log(f"log_out@hex to int:[{result}]")
    #     return result

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
    def USBOVP(self, *args, **kwargs):
        results = []
        voltage_list = []
        repeatCount = 1
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [7000, 500], "expect": "done"}]))
        time.sleep(0.1)
        # for count in range(repeatCount):
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP5_VCHG_USB'])
        #     voltage_list.append(voltage)
        # voltage_list.sort()
        # clean_list = voltage_list[1:-1]
        self.rp2_device.rpc_call("mixdevice.reset", [])
        self.rp2_device.rpc_call("mixdevice.relay", ['NTC_SEL_SW_NORMAL_TEMP'])
        self.rp2_device.rpc_call("mixdevice.relay", ['PSU_VCHG_TO_DUT'])
        self.rp2_device.rpc_call("mixdevice.relay", ['DMM_VIN1_SEL_SW'])
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.chargeEnable", "args": [5000, 1000], "expect": "done"}]))
        time.sleep(0.5)
        return voltage

    @test_item_logger
    def USB_OCP(self, *args, **kwargs):
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP5_VCHG_USB'])
        self.rp2_device.rpc_call("mixdevice.enableEload", [0, 875])
        self.rp2_device.rpc_call("mixdevice.relay", ['ELOAD_SEL_SW_ELOAD_TP5_VCHG_USB'])
        # self.rp2_device.rpc_call("mixdevice.relay", ['VOLT_MEAS_DISCHARGE'])
        # time.sleep(3)
        # self.rp2_device.rpc_call("mixdevice.relay", ['VOLT_MEAS_DISCHARGE', 'DISCONNECT'])
        return voltage

    @test_item_logger
    def EXIT_USB_OCP(self, *args, **kwargs):
        results = []
        self.rp2_device.rpc_call("mixdevice.enableEload", [0, 0])
        results.append(self.runRpcWithCheck([{"cmd": "mixdevice.relay", "args": ['ELOAD_SEL_SW_ELOAD_TP5_VCHG_USB', 'DISCONNECT'], "expect": "True"}]))
        time.sleep(3)
        return self.check_fail(results)

    @test_item_logger
    def hallDetect(self, *args, **kwargs):
        self.rp2_device.rpc_call("mixdevice.relay", ['PP24V_TO_MAGNET'])
        self.log(f"log_in@delay:[(1000 / 1000)s]")
        time.sleep(1)
        self.log(f"log_out@CMD Response:[done]")
        voltage = self.rp2_device.rpc_call("mixdevice.measureByDMM", ['ch1', '7000mv', 'VOLT_MEAS_MUX_SEL_TP68_9_HALL_KEY'])
        return voltage


    @test_item_logger
    def writeStationFlag(self, *args, **kwargs):
        args_dict = args[0]
        sn = args_dict.get("cmd_args", None)
        testResult = args_dict.get("testResult", None)
        parse_pattern = 'Station1Status=Pass (\w+\=\w+)'
        print(f'test----:{testResult}')
        if testResult[0] == 'PASS':
            bmt_cmd = f'BoseManufacturingTool.exe  send \"Manufacturing.TestStation.SetGet 1, 1\" --expect \".\" --print_response --serial_number {sn[0]}'
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        elif testResult[0] == 'FAIL':
            bmt_cmd = f'BoseManufacturingTool.exe  send \"Manufacturing.TestStation.SetGet 1, 0\" --expect \".\" --print_response --serial_number {sn[0]}'
            self.log(f"log_in@Send cmd:[{bmt_cmd}]")
        return_code, resp, error = self.run_shell.run_shell_with_timeout(bmt_cmd, 5000)
        self.log(f"log_out@CMD Response:{resp}")
        self.log(f"Return Code:{return_code}")
        self.log(f"BMT CMD Response:{resp}")
        self.log(f"Error:{error}")
        if return_code != 0 or 'No messages seen' in resp:
            return "--FAIL--CMD Run Fail"
        result = re.search(parse_pattern, resp)
        return result.group(1)


    def parse_rgbi_data(self, raw_data):
        """parse rgbi data
        Args:
            raw_data: raw data from serial port
        Returns:
            list: a list contains 4 channels rgbi data
        """
        RGBI = namedtuple('RGBI', ['channel', 'r', 'g', 'b', 'i'])
        
        # 提取数据部分
        match = re.search(r'=([\d,.]+)', raw_data)
        if not match:
            raise ValueError("invalid data format")

        # 分割所有数值并验证
        values = match.group(1).split(',')[:-1]  # 去除最后一个空值
        if len(values) != 16:  # 4通道 × 4个值
            raise ValueError(f"expect 16 values, but get {len(values)}")

        # 使用列表推导式按通道解析
        return [
            RGBI(
                channel=i + 1,  # 通道号1-4
                r=int(values[i*4]),
                g=int(values[i*4+1]),
                b=int(values[i*4+2]),
                i=float(values[i*4+3])
            ) for i in range(4)
        ]

    def parse_lux(self, data_str):
        """parse lux data
        Args:
            data_str: data string
        Returns:
            list: a list contains 4 channels lux data
        """
        # 提取数据部分
        lux_str = data_str.split('=')[1].strip('\r\n').strip(',')
        lux_values = lux_str.split(',')
        
        # 每个通道的索引位置（每7个值取一个）
        indices = [0, 7, 14, 21]
        
        # 使用列表推导式提取并转换为float
        return [float(lux_values[i]) for i in indices]

    def _read_serial_with_timeout(self, terminator, timeout):
        """read serial with timeout
        Args:
            terminator: end of data
            timeout: timeout (millisecond)
            
        Returns:
            tuple: (received data, whether timeout)
        """
        recv = ""
        end_time = time.time() + timeout/1000.0
        
        while time.time() < end_time:
            # 读取可用数据
            temp = self._port.read(self._port.inWaiting())
            if temp:
                # 过滤无效字符并解码
                temp = temp.replace(b'0xff', b'').replace(b'\xff', b'')
                recv += str(temp.decode('latin1'))

            # 检查是否接收到结束符
            if terminator in recv:
                return recv, False
                
            # 短暂暂停，避免CPU占用过高
            time.sleep(0.01)
            
        # 超时返回
        return recv, True

    def _send_command_and_read(self, command, wait_time=0.1, timeout=3000):
        """send command and read response
        
        Args:
            command: command to send
            wait_time: time to wait after send (second)
            timeout: read timeout (millisecond)
            
        Returns:
            tuple: (response data, whether success)
        """
        try:
            self._port.write(command.encode())
            time.sleep(wait_time)
            
            response, timeout_happen = self._read_serial_with_timeout(':001', timeout)
            if timeout_happen:
                self.log(f'[Port Timeout] {response}')
                return None, False
                
            return response, True
        except Exception as e:
            self.log(f'[Command Error] {command}: {str(e)}')
            return None, False

    def measureLED(self, WB):
        """measure LED parameters
        Args:
            WB: target type (0=white, 4=amber, 13=blue)
        Returns:
            dict: a dict contains RGBI and lux data, None if failed
        """
        try:
            # 1. 串口初始化
            if not self.is_open():
                try:
                    self._port = serial.Serial('COM80', 115200)
                    self.log("[Port] open COM80")
                except Exception as e:
                    self.log(f'[Port Exception] {str(e)}')
                    return None

            # 清空缓冲区
            self._port.flushInput()
            self._port.flushOutput()
            
            # 2. 读取RGBI数据
            rgbi_cmd = ':001r_rgbi01-04\r\n'
            rgbi_data, success = self._send_command_and_read(rgbi_cmd)
            if not success:
                return None
                
            # 3. 设置目标类型
            target_cmd = f':001w_target_type01-04={WB}\r\n'
            self._port.write(target_cmd.encode())
            time.sleep(0.05)
            # 读取但不检查响应
            target_res = self._port.read(self._port.inWaiting())
            
            # 4. 读取色度数据
            chroma_cmd = ':001r_chroma01-04\r\n'
            chroma_data, success = self._send_command_and_read(chroma_cmd)
            if not success:
                return None
                
            # 5. 返回结果
            result = {
                'rgbData': rgbi_data,
                'luxData': chroma_data
            }
            return result

        except Exception as e:
            self.log(f'[Measure Exception] {str(e)}')
            return None
        finally:
            # 无论成功失败都关闭串口
            if hasattr(self, '_port') and self._port and self._port.is_open:
                self._port.close()

    def is_open(self):
        """检查串口是否已打开"""
        return self._port is not None and self._port.is_open


    @test_item_logger
    def led_test(self, *args, **kwargs):
        """led test
        Args:
            params: a dict contains test parameters
        Returns:
            str: result of led test, a dict contains rgb data and lux data and current
        """
        # 1. 提取参数
        params = args[0]
        color = params['color']
        
        # 颜色到目标类型的映射
        color_map = {
            'white': 0,
            'amber': 4,
            'blue': 13
        }
        WB = color_map.get(color, 0)  # 默认为白光

        # 3. 测量LED（使用文件锁处理串口冲突）
        base_dir = os.path.dirname(os.path.abspath(__file__))
        lock_file = os.path.join(base_dir, '.led_lock')
        data_file = os.path.join(base_dir, 'led_data.txt')

        try:
            # 使用原子操作创建锁文件，确保只有一个进程能获取锁
            lock_acquired = False
            while not lock_acquired:
                if os.path.exists(lock_file):
                    # 等待锁释放并读取缓存数据
                    self._wait_for_lock_release(lock_file)
                    with open(data_file, 'r') as f:
                        self.log(f"log_in@Send cmd:[:001r_rgbi01-04, :001r_lux01-04]")
                        response = json.load(f)
                    break
                else:
                    try:
                        # 原子操作创建锁文件（O_CREAT | O_EXCL 确保只有一个进程能创建成功）
                        with os.fdopen(os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY), 'w') as f:
                            f.write('locked')
                        lock_acquired = True

                        self.log(f"log_in@Send cmd:[:001r_rgbi01-04, :001r_lux01-04]")
                        response = self.measureLED(WB)
                        # self.log(f"log_out@Response:[{response}]")

                        # 缓存结果
                        with open(data_file, 'w') as f:
                            json.dump(response, f)
                            f.flush()
                            os.fsync(f.fileno())

                        # 释放锁
                        try:
                            if os.path.exists(lock_file):
                                os.remove(lock_file)
                        except Exception as e:
                            self.log(f"[Warning] Failed to remove lock file: {str(e)}")
                        break
                    except FileExistsError:
                        # 文件已存在，说明其他进程已经获取了锁
                        time.sleep(0.05)  # 短暂等待后重试
                        continue
            
            # 4. 解析数据
            result = self.parse_rgbi_data(response['rgbData'])
            if not result or any(item is None for item in result):
                self.log("[Error] RGBI数据解析结果无效")
                raise Exception("RGBI数据解析失败")
            # 打印通道信息
            for item in result:
                self.log(f"ch{item.channel}: R={item.r}, G={item.g}, B={item.b}, I={item.i:.3f}")
            
            # 5. 获取亮度和电流
            luxresult = self.parse_lux(response['luxData'])
            if not luxresult or any(item is None for item in luxresult):
                self.log("[Error] LUX数据解析结果无效")
                raise Exception("LUX数据解析失败")
            current = 0
            
        except Exception as e:
            self.log(f"[LED Test Exception] {str(e)}")
            return None, None, None
        finally:
            self.log(f"[LED Test value] {result} {luxresult}")
            self.log(f"log_out@Response:[RGBData: {result} LUXData:{luxresult}]")
        return (result, luxresult, current)

    def _wait_for_lock_release(self, lock_file, check_interval=0.1, max_wait=10):
        """wait for lock file release
        Args:
            lock_file: lock file path
            check_interval: check interval (second)
            max_wait: max wait time (second)
        Returns:
            bool: True if lock file is released, False if timeout
        """
        start_time = time.time()
        while os.path.exists(lock_file):
            time.sleep(check_interval)
            self.log(f"[Info] Wait for lock file release, wait time: {time.time() - start_time}")
            if time.time() - start_time > max_wait:
                # 超时强制删除锁
                try:
                    os.remove(lock_file)
                    self.log("[Warning] Lock file wait timeout, force delete")
                except:
                    pass
                break

    @test_item_logger
    # 加载校准数据的辅助方法
    def _load_calibration_data(self):
        """load calibration data from json file
        Returns:
            dict: calibration data dict
        """
        calibration_file = os.path.join(os.path.dirname(__file__), 'calibration.json')
        try:
            with open(calibration_file, 'r') as f:
                calibration_data = json.load(f)
                # 将字符串键转换为整数键
                for category in ['case']:
                    calibration_data[category] = {int(k): v for k, v in calibration_data[category].items()}
                return calibration_data
        except Exception as e:
            self.log(f"[Error] Load calibration data failed: {e}")
            # 返回默认值
            return {
                'case': {i: {'WHITE': {'gain': 1, 'offset': 0}, 'AMBER': {'gain': 1, 'offset': 0}, 'BLUE': {'gain': 1, 'offset': 0}} for i in range(4)}
            }

    @test_item_logger
    def getValueForLED(self, *args, **kwargs):
        """measure led test value
        Args:
            params: a dict contains test parameters
        Returns:
            str: action_map
        """
        # 从配置文件加载校准数据
        calibration_dict = self._load_calibration_data()
        # 站点到通道的映射
        channel_map = {
            0: {'caseCH': 1, 'caseLux': 0},
            1: {'caseCH': 2, 'caseLux': 1},
            2: {'caseCH': 3, 'caseLux': 2},
            3: {'caseCH': 4, 'caseLux': 3},
        }
        
        # 获取当前站点的通道映射
        ch_map = channel_map.get(self.site, channel_map[0])
        caseCH = ch_map['caseCH']
        caseLux = ch_map['caseLux']
        
        # 解析参数
        res = args[0]
        keyargs = kwargs.get("SubSubTestName", "")
        ch, color, type = keyargs.split("_")
        type = type.replace('@', '')
        type_index_map = {
            'R' : 0,
            'G' : 1,
            'B' : 2
        }
        index = type_index_map.get(type, 0)
        # 解析数据
        parse_data = ast.literal_eval(res)
        rgb_list, lux_list, current = parse_data
        print(f'lux_list_{color}------->{lux_list}')

        # 创建结果字典
        result_dict = {item[0]: item[1:] for item in rgb_list}
        
        if type == 'I':
            ch = '@CASELUX'
        # 使用字典映射替代if-elif
        action_map = {
            '@CASE': lambda: result_dict[caseCH][int(index)],
            '@CASELUX': lambda: lux_list[int(caseLux)] * calibration_dict['case'][self.site][color]['gain'] + 
                              calibration_dict['case'][self.site][color]['offset'],
            '@CURRENT': lambda: current
        }
        if type != 'I':
            self.log(f"log_in@Get Input from LED_TEST_{color}:[{rgb_list}]")
            time.sleep(0.1)
            self.log(f"log_out@Test value:[{action_map.get(ch, lambda: ReturnDef.FAIL_STRING)()}]")
        else:
            self.log(f"log_in@Get Input from LED_TEST_{color}:[{lux_list[int(caseLux)] * calibration_dict['case'][self.site][color]['gain'] + calibration_dict['case'][self.site][color]['offset']}]")
            time.sleep(0.1)
            self.log(f"log_out@Test value:[{action_map.get(ch, lambda: ReturnDef.FAIL_STRING)()}]")

        # 执行对应操作或返回失败
        return action_map.get(ch, lambda: ReturnDef.FAIL_STRING)()



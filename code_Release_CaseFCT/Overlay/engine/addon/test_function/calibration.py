import sys
import time
import os
import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import messagebox
import numpy as np
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = current_dir + "/lib"
sys.path.append(lib_path)
from rtRP2.rp2Device import Rp2Device
from rtlib.runShell import runShell
run_shell = runShell()


def init(client):
    client.init()
    client._pyb.exec_("from MixDevice import *")
    

def deinit(client):
    client._pyb.exec_("del mixdevice")
    client._pyb.exec_("import gc;gc.mem_free()")
    client.deinit()

def get_device_port():
    ports = serial.tools.list_ports.comports()
    usb_ports = [port.device for port in ports if port.device.startswith("usbmode")]
    return usb_ports[-1] if usb_ports else None

def reset_all(client):
    client.rpc_call("mixdevice.reset")


def parse_lux(data_str):
    # 1. 去掉前缀和换行符
    lux_str = data_str.split('=')[1].strip('\r\n').strip(',')
    # 2. 分割成列表
    lux_values = lux_str.split(',')
    # 3. 转换为 float 类型
    # lux_values = [float(x) for x in lux_values]
    lux_values = [float(lux_values[0]), float(lux_values[7]), float(lux_values[14]), float(lux_values[21])]
    # 4. 映射到 4 个 channel
    lux_dict = {f'{i + 1}': lux_values[i] for i in range(4)}
    return lux_values


def measureLED(WB):
    cmdTarget = f':001w_target_type01-04={WB}\r\n'
    timeout = 3000
    terminator = ':001'
    _port = serial.Serial('COM80', 115200)
    _port.write(cmdTarget.encode())
    time.sleep(0.05)
    cmdTargetRes = _port.read(_port.inWaiting())
    cmdlux = ':001r_chroma01-04\r\n'
    _port.write(cmdlux.encode())
    time.sleep(0.1)
    recvlux = ""
    timeout_happen = False
    time_out = timeout / 1000.0
    begin = time.time()
    while True:
        temp = _port.read(_port.inWaiting())
        if temp:
            temp = temp.replace(b'0xff', b'').replace(b'\xff', b'')
            recvlux += str(temp.decode('latin1'))

        if recvlux.rfind(str(terminator)) >= 0:
            break
        elif time.time() - begin > time_out:
            timeout_happen = True
            break
    if timeout_happen:
        print('[Port Timeout]' + recvlux)
        return None
    return recvlux



def led_test(client, color, slot, measure_type):
    if color == 'white':
        WB = 0
        bmtcmd = "BoseManufacturingTool.exe  send \"Debug.LEDs.SetGet 13, 31\" --expect \".\" --print_response"
        brightnesscmd = "BoseManufacturingTool.exe  send \"Manufacturing.LedAttribute.SetGet 1,1,255\" --expect \".\" --print_response"
    elif color == 'amber':
        WB = 4
        bmtcmd = "BoseManufacturingTool.exe  send \"Debug.LEDs.SetGet 13, 32\" --expect \".\" --print_response"
        brightnesscmd = "BoseManufacturingTool.exe  send \"Manufacturing.LedAttribute.SetGet 2,1,255\" --expect \".\" --print_response"
    elif color == 'blue':
        WB = 13
        bmtcmd = "BoseManufacturingTool.exe  send \"Debug.LEDs.SetGet 13, 33\" --expect \".\" --print_response"
        brightnesscmd = "BoseManufacturingTool.exe  send \"Manufacturing.LedAttribute.SetGet 3,1,255\" --expect \".\" --print_response"

    # 连接所有通道

    client.rpc_call("mixdevice.relay", 'NTC_SEL_SW_NORMAL_TEMP')
    client.rpc_call("mixdevice.relay", 'PSU_VCHG_TO_DUT')
    client.rpc_call("mixdevice.relay", 'PSU_BATT_TO_DUT')
    time.sleep(0.1)
    client.rpc_call("mixdevice.chargeEnable", 5000, 500)
    client.rpc_call("mixdevice.batteryEnable", 3800, 500)
    client.rpc_call("mixdevice.relay", 'USB_SEL_SW')
    time.sleep(3)
    # return_code, resp, error = run_shell.run_shell_with_timeout(brightnesscmd, 3000)
    # print(f'resp is :{resp}')
    # return_code, resp, error = run_shell.run_shell_with_timeout("BoseManufacturingTool.exe  send \"Control.Reset.Start\" --expect \".\" --print_response", 3000)
    # print(f'resp is :{resp}')
    # time.sleep(3)
    return_code, resp, error = run_shell.run_shell_with_timeout(bmtcmd, 3000)
    print(f'resp is :{resp}')
    time.sleep(1)
    response = measureLED(WB)
    # 测量Lux
    luxresult = parse_lux(response)
    print('luxresult---1', luxresult)
    if slot == 1 and measure_type == 'case':
        luxresult = luxresult[0]
    elif slot == 2 and measure_type == 'case':
        luxresult = luxresult[1]
    elif slot == 3 and measure_type == 'case':
        luxresult = luxresult[2]
    elif slot == 4 and measure_type == 'case':
        luxresult = luxresult[3]
    print('luxresult---2', luxresult)
    assert float(luxresult) != 0.0
    # # 清理

    client.rpc_call("mixdevice.relay", 'NTC_SEL_SW_NORMAL_TEMP', 'DISCONNECT')
    client.rpc_call("mixdevice.chargeEnable", 0, 10)
    client.rpc_call("mixdevice.batteryEnable", 0, 10)
    time.sleep(0.1)
    client.rpc_call("mixdevice.relay", 'PSU_VCHG_TO_DUT', 'DISCONNECT')
    client.rpc_call("mixdevice.relay", 'PSU_BATT_TO_DUT', 'DISCONNECT')
    client.rpc_call("mixdevice.relay", 'USB_SEL_SW', 'DISCONNECT')
    return luxresult

def show_message(msg):
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    messagebox.showinfo("提示", msg)
    root.destroy()

# slot和COM口映射
def get_com_port(slot):
    return f"COM10{slot-1}"

# netName和netName_list的映射
def get_netName_and_list(measure_type, color):
    base_list = [
        'CCS_CURRENT_OUTPUT_RANG_100MA',
        'CCS_CURRENT_MEASURE_RANG_100MA',
        'EXT_DUT_GND_TO_SYS_GND',
        'CCS_P_TO_DUT_MUX_SEL_DUT_VDD_LED'
    ]
    if measure_type == "case":
        if color == "white":
            netName = "CCS_N_TO_GND_MUX_SEL_DUT_LED_CASE_WHITE"
        elif color == "amber":
            netName = "CCS_N_TO_GND_MUX_SEL_DUT_LED_CASE_AMBER"
        elif color == "blue":
            netName = "CCS_N_TO_GND_MUX_SEL_DUT_LED_CASE_BLUE"
        else:
            raise ValueError("case supports white/amber/blue")
    else:
        raise ValueError("Unknown measure_type")
    return netName, base_list

if __name__ == "__main__":
    slots = [1, 2, 3, 4]
    duts = [1, 2]
    measure_types = [
        ("case", "white"),
        ("case", "amber"),
        ("case", "blue"),
    ]
    results = {}  # {(slot, dut, measure_type, color, idx): value}
    for slot in slots:
        client = Rp2Device(get_com_port(slot), 115200, None)
        init(client)
        reset_all(client)
        for dut in duts:
            idx = 1
            for idx in range(1, 4):
                for measure_type, color in measure_types:
                    try:
                        netName, netName_list = get_netName_and_list(measure_type, color)
                    except ValueError:
                        continue
                    value = led_test(client, color, slot, measure_type)
                    results[(slot, dut, measure_type, color, idx)] = value
                if idx < 3:
                    show_message(f"请取放DUT_{dut}")
                if idx == 3 and dut == 1:
                    show_message(f"请放入DUT_2")
        deinit(client)
        if slot < 4:
            show_message(f"请更换至通道{slot+1}并且放入DUT1")

    # 统计均值
    def get_avg(slot, dut, measure_type, color):
        vals = [results[(slot, dut, measure_type, color, idx)] for idx in range(1, 4)]
        print('vals--->',vals)
        return sum(vals) / len(vals) if vals else 0

    # 统计所有均值
    avg_dict = {}
    for slot in slots:
        for dut in duts:
            for measure_type, color in measure_types:
                avg_dict[(slot, dut, measure_type, color)] = get_avg(slot, dut, measure_type, color)

    # 全slot均值
    def allslot_avg(dut, measure_type, color):
        return sum([avg_dict[(slot, dut, measure_type, color)] for slot in slots]) / 4

    # polyfit并输出
    print(f'avg_dict------>{avg_dict}')
    
    # 创建校准数据字典
    calibration_data = {
        "case": {str(i): {"WHITE": {"gain": 1, "offset": 0}, "AMBER": {"gain": 1, "offset": 0}, "BLUE": {"gain": 1, "offset": 0}} for i in range(4)}
    }
    
    for measure_type, color in measure_types:
        for slot in slots:
            xlist = [avg_dict[(slot, 1, measure_type, color)], avg_dict[(slot, 2, measure_type, color)]]
            ylist = [allslot_avg(1, measure_type, color), allslot_avg(2, measure_type, color)]
            print(f'slot: {slot} xlist----->{xlist}')
            print(f'slot: {slot} ylist----->{ylist}')
            try:
                gain, offset = np.polyfit(xlist, ylist, 1)
                print(f'slot{slot}_{measure_type}_{color}_gain: {gain}, slot{slot}_{measure_type}_{color}_offset: {offset}')
                
                # 更新校准数据
                slot_idx = slot - 1  # 转换为0-based索引
                json_measure_type = "case"
                json_color = color.upper()
                calibration_data[json_measure_type][str(slot_idx)][json_color]["gain"] = float(gain)
                calibration_data[json_measure_type][str(slot_idx)][json_color]["offset"] = float(offset)
            except Exception as e:
                print(f'slot{slot}_{measure_type}_{color}_polyfit error: {e}')
    
    # 将校准数据保存到JSON文件

    def save_calibration_data(data):
        """将校准数据保存到JSON文件
        Args:
            data: 校准数据字典
        """
        import json
        calibration_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calibration.json')
        with open(calibration_file, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"校准数据已保存到: {calibration_file}")
    
    # 保存校准数据
    save_calibration_data(calibration_data)
    

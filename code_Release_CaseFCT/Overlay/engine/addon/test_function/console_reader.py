import ctypes
import sys
import time
import os


def attach_and_capture(pid: int, output_file: str, max_wait: float = 12.0) -> str:
    if os.name != 'nt':
        return ''

    kernel32 = ctypes.windll.kernel32

    # 基本常量
    STD_OUTPUT_HANDLE = -11
    STILL_ACTIVE = 259

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    PROCESS_QUERY_INFORMATION = 0x0400
    SYNCHRONIZE = 0x00100000

    # 结构体定义
    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class SMALL_RECT(ctypes.Structure):
        _fields_ = [("Left", ctypes.c_short), ("Top", ctypes.c_short), ("Right", ctypes.c_short), ("Bottom", ctypes.c_short)]

    class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [
            ("dwSize", COORD),
            ("dwCursorPosition", COORD),
            ("wAttributes", ctypes.c_uint16),
            ("srWindow", SMALL_RECT),
            ("dwMaximumWindowSize", COORD),
        ]

    # API 绑定
    AttachConsole = kernel32.AttachConsole
    AttachConsole.argtypes = [ctypes.c_uint32]
    AttachConsole.restype = ctypes.c_int

    FreeConsole = kernel32.FreeConsole
    FreeConsole.restype = ctypes.c_int

    CreateFileW = kernel32.CreateFileW
    CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p
    ]
    CreateFileW.restype = ctypes.c_void_p

    GetStdHandle = kernel32.GetStdHandle
    GetStdHandle.argtypes = [ctypes.c_int]
    GetStdHandle.restype = ctypes.c_void_p

    GetConsoleScreenBufferInfo = kernel32.GetConsoleScreenBufferInfo
    GetConsoleScreenBufferInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(CONSOLE_SCREEN_BUFFER_INFO)]

    ReadConsoleOutputCharacterW = kernel32.ReadConsoleOutputCharacterW
    ReadConsoleOutputCharacterW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, COORD, ctypes.POINTER(ctypes.c_uint32)]

    OpenProcess = kernel32.OpenProcess
    OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    OpenProcess.restype = ctypes.c_void_p

    GetExitCodeProcess = kernel32.GetExitCodeProcess
    GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [ctypes.c_void_p]
    CloseHandle.restype = ctypes.c_int

    # 1) 释放当前控制台并附着到子进程控制台（不影响主进程的控制台）
    try:
        FreeConsole()
    except Exception:
        pass

    attached = AttachConsole(pid)
    if not attached:
        time.sleep(0.1)
        attached = AttachConsole(pid)
        if not attached:
            return ''

    hOut = CreateFileW("CONOUT$", GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if hOut in (None, 0) or hOut == INVALID_HANDLE_VALUE:
        hOut = GetStdHandle(STD_OUTPUT_HANDLE)

    # 用于查询子进程是否结束
    hProc = OpenProcess(PROCESS_QUERY_INFORMATION | SYNCHRONIZE, False, pid)

    accumulated_lines = []
    seen = set()
    start_ts = time.time()

    # 2) 轮询读取窗口可见区域
    while True:
        csbi = CONSOLE_SCREEN_BUFFER_INFO()
        GetConsoleScreenBufferInfo(hOut, ctypes.byref(csbi))
        win_left = csbi.srWindow.Left
        win_top = csbi.srWindow.Top
        win_right = csbi.srWindow.Right
        win_bottom = csbi.srWindow.Bottom
        win_width = int(win_right - win_left + 1)

        start_row = max(win_top, win_bottom - 99)
        for row in range(start_row, win_bottom + 1):
            buf = ctypes.create_unicode_buffer(win_width)
            read = ctypes.c_uint32(0)
            ReadConsoleOutputCharacterW(hOut, buf, win_width, COORD(win_left, row), ctypes.byref(read))
            line = buf.value[:read.value].rstrip()
            if line and line not in seen:
                seen.add(line)
                accumulated_lines.append(line)

        # 结束条件：子进程结束或达到最大等待
        exit_code = ctypes.c_uint32()
        if hProc:
            GetExitCodeProcess(hProc, ctypes.byref(exit_code))
            if exit_code.value != STILL_ACTIVE:
                break
        if time.time() - start_ts > max_wait:
            break
        time.sleep(0.05)

    # 3) 进程结束后再完整读取一次可见窗口
    csbi = CONSOLE_SCREEN_BUFFER_INFO()
    GetConsoleScreenBufferInfo(hOut, ctypes.byref(csbi))
    win_left = csbi.srWindow.Left
    win_top = csbi.srWindow.Top
    win_right = csbi.srWindow.Right
    win_bottom = csbi.srWindow.Bottom
    win_width = int(win_right - win_left + 1)
    for row in range(win_top, win_bottom + 1):
        buf = ctypes.create_unicode_buffer(win_width)
        read = ctypes.c_uint32(0)
        ReadConsoleOutputCharacterW(hOut, buf, win_width, COORD(win_left, row), ctypes.byref(read))
        line = buf.value[:read.value].rstrip()
        if line and line not in seen:
            seen.add(line)
            accumulated_lines.append(line)

    content = "\n".join(accumulated_lines)

    # 写文件，出现路径错误时回退到临时目录
    try:
        with open(output_file, 'w', encoding='gbk', errors='ignore') as f:
            f.write(content)
    except Exception:
        try:
            fallback_path = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'outputFile_1.txt')
            with open(fallback_path, 'w', encoding='gbk', errors='ignore') as f:
                f.write(content)
        except Exception:
            pass

    # 清理
    try:
        CloseHandle(hProc)
    except Exception:
        pass
    try:
        FreeConsole()
    except Exception:
        pass

    return content


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(0)
    pid = int(sys.argv[1])
    out = sys.argv[2]
    result = attach_and_capture(pid, out)
    # 尝试把结果打印回父控制台（若可能）
    try:
        kernel32 = ctypes.windll.kernel32
        AttachConsole = kernel32.AttachConsole
        FreeConsole = kernel32.FreeConsole
        ATTACH_PARENT_PROCESS = ctypes.c_uint32(-1).value
        FreeConsole()
        AttachConsole(ATTACH_PARENT_PROCESS)
        print(f'response(helper) : {result}', flush=True)
    except Exception:
        pass
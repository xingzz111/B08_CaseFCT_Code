@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Check if serial number parameter is provided
if "%1"=="" (
    echo Error: Please provide serial number parameter
    echo Usage: run_bose_tool.bat ^<serial_number^>
    exit /b 1
)

set "sn=%1"
set "timestamp=%time::=%"
set "timestamp=%timestamp:.=%"
set "timestamp=%timestamp: =0%"
set "output_file=D:\\vault\\plc_current_%sn%_%timestamp%.txt"
set "final_file=D:\\vault\\plc_current_%sn%.txt"

REM Check if D drive exists
if not exist "D:\\" (
    echo Error: D drive not found or not accessible
    echo Please make sure D drive is available
    exit /b 1
)

REM Clean up any existing temporary files
if exist "%output_file%" del "%output_file%"
if exist "%final_file%" del "%final_file%"

REM Execute BoseManufacturingTool using PowerShell start command and save output to file
echo Executing BoseManufacturingTool, serial number: %sn%
echo Output will be saved to: %output_file%

REM Execute BoseManufacturingTool and capture complete console session using PowerShell transcript
powershell -Command "Start-Transcript -Path '%output_file%' -Append; BoseManufacturingTool.exe --verbose send \"cim.plc current\" --expect \".\" --print_response --protocol TAP --serial_number %sn%; Stop-Transcript"

REM Wait for file to be completely written
timeout /t 2 /nobreak >nul

REM Check if output file was created and has content
if not exist "%output_file%" (
    echo Error: Output file was not created
    exit /b 1
)

REM Check file size
for %%F in ("%output_file%") do set filesize=%%~zF
if "%filesize%"=="0" (
    echo Error: Output file is empty
    exit /b 1
)

REM Copy to final file location
copy "%output_file%" "%final_file%" >nul

echo Execution completed! Output saved to %final_file%

REM Display file content
echo.
echo Output content:
type "%final_file%"

REM Clean up temporary file
del "%output_file%" >nul
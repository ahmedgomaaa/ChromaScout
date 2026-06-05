#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Builds ONE self-contained Windows .bat (EmporiumChromaFinder.bat) that embeds
both Python files. Re-run this whenever you change the .py files.

The .bat:
  - finds Python (py launcher / python / common install dirs, skips the
    Microsoft Store stub), or installs it via winget,
  - unpacks the embedded .py files to %TEMP%\EmporiumChromaFinder,
  - runs the finder, which writes its output + a detailed run_log.txt next to
    the .bat (or to your home folder if that location is read-only),
  - prints precise, friendly errors and where the logs are.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["make_webpage.py", "be_chroma_finder.py"]   # order doesn't matter
OUT = os.path.join(HERE, "EmporiumChromaFinder.bat")

# NOTE: raw string. Uses ^ to escape > and ( ) in echoed text. Never reaches
# the embedded Python region because every path ends in `exit /b`.
BAT_HEADER = r"""@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Blue Essence Emporium - Chroma Finder

set "HERE=%~dp0"
set "SELF=%~f0"
set "WORK=%TEMP%\EmporiumChromaFinder"
set "EMPORIUM_OUT=%HERE%"
if not exist "%WORK%" mkdir "%WORK%" >nul 2>&1
set "LLOG=%WORK%\launcher_log.txt"
> "%LLOG%" echo [launcher] %DATE% %TIME%
>> "%LLOG%" echo HERE=%HERE%
>> "%LLOG%" echo SELF=%SELF%
>> "%LLOG%" echo WORK=%WORK%

echo ============================================================
echo   BLUE ESSENCE EMPORIUM - CHROMA / SHARD FINDER
echo ------------------------------------------------------------
echo   1. Open League of Legends and log in (reach the home screen).
echo   2. Leave this window to do the rest.
echo ============================================================
echo.

echo [1/4] Looking for Python...
call :findpy
if not defined PY goto :installpy
echo        Found Python: !PY!
>> "%LLOG%" echo [1] PY=!PY!
goto :extract

:installpy
echo [info] Python is not installed. Trying to install it automatically...
>> "%LLOG%" echo [1] python missing - trying winget
where winget >nul 2>&1
if errorlevel 1 goto :nowinget
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
>> "%LLOG%" echo [1] winget exit=!errorlevel!
echo.
echo [info] Re-checking for Python...
call :findpy
if defined PY ( echo        Found Python: !PY! & goto :extract )
echo.
echo   Python was installed, but this window started before it existed,
echo   so it can't see it yet. Please CLOSE this window and double-click
echo   the file again. It will work the second time.
echo.
pause
exit /b 0

:nowinget
echo [ERROR] Could not auto-install Python ('winget' is not on this PC).
echo.
echo   Install Python yourself (about 2 minutes):
echo     1. A download page will open now (or go to python.org/downloads).
echo     2. Run the installer.
echo     3. IMPORTANT: tick "Add python.exe to PATH" on the first screen.
echo     4. Double-click this file again.
echo.
start "" https://www.python.org/downloads/
pause
exit /b 1

:extract
echo [2/4] Unpacking the finder...
>> "%LLOG%" echo [2] extracting to %WORK%
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $raw=Get-Content -LiteralPath $env:SELF -Raw -Encoding UTF8; $m='#===PYTHON'+'_FILES_BELOW==='; $i=$raw.LastIndexOf($m); if($i -lt 0){throw 'embed marker not found - the file may be corrupted or edited'}; $body=$raw.Substring($i+$m.Length); $parts=$body -split ('#==='+'FILE:'); $enc=New-Object Text.UTF8Encoding $false; $cnt=0; foreach($p in $parts){ if($p.Trim() -eq ''){continue}; $nl=$p.IndexOf([char]10); if($nl -lt 0){continue}; $name=($p.Substring(0,$nl) -replace '=+\s*$','').Trim(); $content=$p.Substring($nl+1); [IO.File]::WriteAllText((Join-Path $env:WORK $name),$content,$enc); $cnt++ }; if($cnt -lt 2){throw ('expected 2 files, wrote '+$cnt)}; Write-Host ('        unpacked '+$cnt+' files') } catch { Write-Host ('[ERROR] '+$_.Exception.Message); exit 3 }"
if errorlevel 1 goto :extractfail

echo [3/4] Talking to your League client and building your report...
echo        (a browser tab will open when it's done)
echo.
>> "%LLOG%" echo [3] launching finder with !PY!
"!PY!" "%WORK%\be_chroma_finder.py"
set "RC=!errorlevel!"
>> "%LLOG%" echo [4] finder exit code !RC!
echo.
echo [4/4] Finished.
if not "!RC!"=="0" (
  echo.
  echo   ----------------------------------------------------------
  echo   Something went wrong ^(exit code !RC!^).
  echo   The finder printed a log path just above. Also useful:
  echo       launcher log:  %LLOG%
  echo   Send those file^(s^) to whoever shared this with you.
  echo   ----------------------------------------------------------
)
echo.
pause
exit /b !RC!

:extractfail
echo.
echo   ----------------------------------------------------------
echo   [ERROR] Could not unpack the embedded finder.
echo   Most common cause: you are running it from INSIDE the .zip.
echo   Fix: right-click the .zip, choose "Extract All", then run the
echo        .bat from the extracted folder.
echo   Launcher log: %LLOG%
echo   ----------------------------------------------------------
echo.
pause
exit /b 3

rem ---- subroutine: locate a working Python, skipping the Store stub -------
:findpy
set "PY="
call :trypy py.exe
if defined PY exit /b 0
call :trypy python.exe
if defined PY exit /b 0
call :trypy python3.exe
if defined PY exit /b 0
for %%D in ("%LOCALAPPDATA%\Programs\Python" "%ProgramFiles%\Python" "%ProgramFiles(x86)%\Python") do (
  if exist "%%~D" for /f "delims=" %%F in ('dir /b /s "%%~D\python.exe" 2^>nul') do (
    if not defined PY (
      "%%F" --version >nul 2>&1 && set "PY=%%F"
    )
  )
)
exit /b 0

:trypy
rem %1 = executable name to resolve on PATH; validates it actually runs
for /f "delims=" %%F in ('where %~1 2^>nul') do (
  if not defined PY (
    echo %%F| findstr /i "WindowsApps" >nul
    if errorlevel 1 (
      "%%F" --version >nul 2>&1 && set "PY=%%F"
    )
  )
)
exit /b 0

#===PYTHON_FILES_BELOW==="""


def main():
    out = [BAT_HEADER]
    for name in FILES:
        path = os.path.join(HERE, name)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "#===FILE:" in content or "#===PYTHON_FILES_BELOW===" in content:
            raise SystemExit(f"ERROR: {name} contains the embed marker text - rename the marker.")
        out.append(f"\r\n#===FILE:{name}===\r\n")
        out.append(content)
    # Write the .bat with CRLF so cmd is happy; UTF-8 (no BOM).
    text = "".join(out).replace("\r\n", "\n").replace("\n", "\r\n")
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    size = os.path.getsize(OUT)
    print(f"Wrote {OUT}  ({size/1024:.1f} KB)")
    print("Embedded:", ", ".join(FILES))


if __name__ == "__main__":
    main()

# Windows HDR brightness

On `nepe`, `pc-windows.py` now routes brightness for the existing OLED entry
(`\\.\DISPLAY1\Monitor0`) to Windows' **SDR content brightness** while HDR is on.
The other monitor keeps using ControlMyMonitor/DDC. With HDR off, both use the
previous DDC settings, including the OLED's -12 offset.

Pull the repository and restart the running Python controller in its existing
Windows environment. There are no new dependencies. Keep `windows_hdr.py` beside
`pc-windows.py`. Existing MQTT topics and invocation arguments are unchanged.
Add `--debug` to the usual invocation to see the chosen brightness route.

## Check on Windows

1. With HDR enabled, send a moderate brightness setting (e.g. 20 then 40) using
   the usual control. SDR desktop content should change brightness; the other
   screen should still respond normally. Check the SDR content brightness in
   Windows Settings (reopen the page if it does not refresh).
2. Turn HDR off and send a new brightness setting. The old DDC behavior should
   return. Turning HDR on/off alone does not apply a new MQTT brightness value.
3. If an API error is printed, capture its text and Windows version. The script
   skips OLED DDC on unknown HDR state or failed SDR-white control.

MQTT 0..100 maps to Windows' SDR slider 0..100 (nominal SDR white 80..480 nits),
without the DDC -12 offset. This is not the Linux backlight scale and does not
set OLED panel brightness or HDR peak brightness. Zero is not screen-off.

Windows' SDR-white setter is undocumented; it can vary with OS/driver updates.
The helper checks return codes and reads back the level. It never toggles HDR.
Newer Windows uses the explicit HDR mode query to distinguish HDR from SDR
with automatic color management; older Windows uses advanced-color status.
Display matching uses the existing configured DISPLAY identity, not enumeration
order. If Windows renumbers displays, update `PC_CONFIGS` as with the old script.

API layout references:
- Microsoft Windows SDK `wingdi.h` (DisplayConfig structures)
- https://github.com/res2k/HDRTray/blob/main/common/HDR.cpp (SDR-white setter ABI)

Local checks: `python -m unittest discover -s pc-node/tests -v`.
These are mocked API/ABI/routing checks, not a real Windows display test.

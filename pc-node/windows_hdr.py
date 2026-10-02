"""Per-display Windows HDR/SDR-white control, using only ctypes.

The setter is an undocumented Windows API (also used by HDRTray); failures
must not fall back to DDC while HDR state is unknown or enabled.
"""
import ctypes as C

U32 = C.c_uint32
I32 = C.c_int32


class Luid(C.Structure):
    _fields_ = [("low", U32), ("high", I32)]


class Header(C.Structure):
    _fields_ = [("type", U32), ("size", U32), ("adapter", Luid), ("id", U32)]


class Source(C.Structure):
    _fields_ = [("adapter", Luid), ("id", U32), ("mode", U32), ("flags", U32)]


class Target(C.Structure):
    _fields_ = [("adapter", Luid), ("id", U32), ("mode", U32),
                ("technology", U32), ("rotation", U32), ("scaling", U32),
                ("refresh_num", U32), ("refresh_den", U32), ("scanline", U32),
                ("available", I32), ("flags", U32)]


class Path(C.Structure):
    _fields_ = [("source", Source), ("target", Target), ("flags", U32)]


class Mode(C.Union):
    # DISPLAYCONFIG_MODE_INFO is 64 bytes, aligned to 8. Its contents aren't
    # needed: QueryDisplayConfig still requires a correctly sized mode buffer.
    _fields_ = [("storage", C.c_uint64 * 8)]


class SourceName(C.Structure):
    _fields_ = [("header", Header), ("name", C.c_uint16 * 32)]


class ColorInfo(C.Structure):
    _fields_ = [("header", Header), ("flags", U32), ("encoding", U32), ("bits", U32)]


class ColorInfo2(C.Structure):
    _fields_ = ColorInfo._fields_ + [("active_mode", U32)]


class WhiteLevel(C.Structure):
    _fields_ = [("header", Header), ("level", U32)]


class SetWhiteLevel(C.Structure):
    _fields_ = WhiteLevel._fields_ + [("final_value", C.c_ubyte)]


def _packet(cls, kind, endpoint):
    packet = cls()
    packet.header = Header(kind, C.sizeof(cls), endpoint.adapter, endpoint.id)
    return packet


def _check(rc, operation):
    if rc:
        raise OSError(rc, f"{operation} failed (Windows error {rc})")


def _user32():
    api = C.WinDLL("user32", use_last_error=True)
    api.GetDisplayConfigBufferSizes.argtypes = [U32, C.POINTER(U32), C.POINTER(U32)]
    api.QueryDisplayConfig.argtypes = [U32, C.POINTER(U32), C.POINTER(Path),
                                      C.POINTER(U32), C.POINTER(Mode), C.c_void_p]
    for name in ("GetDisplayConfigBufferSizes", "QueryDisplayConfig",
                 "DisplayConfigGetDeviceInfo", "DisplayConfigSetDeviceInfo"):
        getattr(api, name).restype = I32
    api.DisplayConfigGetDeviceInfo.argtypes = [C.POINTER(Header)]
    api.DisplayConfigSetDeviceInfo.argtypes = [C.POINTER(Header)]
    return api


def _find_target(api, monitor_id):
    # Match the existing ControlMyMonitor GDI display identity, NOT list order.
    display_name = monitor_id.split("\\Monitor", 1)[0].casefold()
    for _ in range(3):
        paths_count, modes_count = U32(), U32()
        _check(api.GetDisplayConfigBufferSizes(2, C.byref(paths_count), C.byref(modes_count)),
               "GetDisplayConfigBufferSizes")
        paths, modes = (Path * paths_count.value)(), (Mode * modes_count.value)()
        rc = api.QueryDisplayConfig(2, C.byref(paths_count), paths,
                                    C.byref(modes_count), modes, None)
        if rc == 122:  # ERROR_INSUFFICIENT_BUFFER: topology changed; re-enumerate.
            continue
        _check(rc, "QueryDisplayConfig")
        matches = []
        for path in paths[:paths_count.value]:
            name = _packet(SourceName, 1, path.source)
            _check(api.DisplayConfigGetDeviceInfo(C.byref(name.header)), "Get source name")
            decoded = bytes(name.name).decode("utf-16-le").split("\0", 1)[0]
            if decoded.casefold() == display_name:
                matches.append(path.target)
        if len(matches) != 1:
            raise OSError(f"Expected one active target for {monitor_id}; found {len(matches)}")
        return matches[0]
    raise OSError("Display topology kept changing")


def _hdr_enabled(api, target):
    info2 = _packet(ColorInfo2, 15, target)
    rc = api.DisplayConfigGetDeviceInfo(C.byref(info2.header))
    if rc == 0:
        return info2.active_mode == 2  # HDR, not SDR with auto color management.
    if rc not in (50, 87):  # Older Windows: NOT_SUPPORTED / INVALID_PARAMETER.
        _check(rc, "Get advanced color info 2")
    info = _packet(ColorInfo, 9, target)
    _check(api.DisplayConfigGetDeviceInfo(C.byref(info.header)), "Get advanced color info")
    return bool(info.flags & 2)


def set_sdr_brightness_if_hdr(monitor_id, percent):
    """Return False only for confirmed HDR-off; raise on unknown state/failure.

    Map 0..100 to the Windows SDR-content-brightness slider's 80..480 nits.
    This adjusts SDR white, not HDR peak brightness or HDR enablement.
    """
    api = _user32()
    target = _find_target(api, monitor_id)
    if not _hdr_enabled(api, target):
        return False
    level = 1000 + 50 * max(0, min(100, int(percent)))
    # Undocumented SET_SDR_WHITE_LEVEL = -18; final_value commits the change.
    # ABI reference: github.com/res2k/HDRTray/blob/main/common/HDR.cpp
    packet = _packet(SetWhiteLevel, 0xFFFFFFEE, target)
    packet.level, packet.final_value = level, 1
    _check(api.DisplayConfigSetDeviceInfo(C.byref(packet.header)), "Set SDR white level")
    actual = _packet(WhiteLevel, 11, target)
    _check(api.DisplayConfigGetDeviceInfo(C.byref(actual.header)), "Read SDR white level")
    if abs(actual.level - level) > 1:
        raise OSError(f"SDR white level readback {actual.level}, expected {level}")
    return True

"""Cross-platform ABI and routing checks; no display hardware is touched."""
import ctypes as C
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import windows_hdr as hdr


class FakeApi:
    def __init__(self, mode=2, legacy=False, set_error=0):
        self.mode, self.legacy, self.set_error = mode, legacy, set_error
        self.level = 1000
        self.writes = []

    def GetDisplayConfigBufferSizes(self, flags, paths, modes):
        paths._obj.value, modes._obj.value = 2, 2
        return 0

    def QueryDisplayConfig(self, flags, pc, paths, mc, modes, topology):
        for i in range(2):
            paths[i].source.id = i + 1
            paths[i].target.id = 10 + i
            paths[i].target.adapter.low = 42
        return 0

    def DisplayConfigGetDeviceInfo(self, pointer):
        head = pointer._obj
        def packet(cls):
            return C.cast(pointer, C.POINTER(cls)).contents
        if head.type == 1:
            name = rf"\\.\DISPLAY{head.id}".encode('utf-16-le')
            C.memmove(C.addressof(packet(hdr.SourceName)) + hdr.SourceName.name.offset,
                      name, len(name))
        elif head.type == 15:
            if self.legacy:
                return 87
            packet(hdr.ColorInfo2).active_mode = self.mode
        elif head.type == 9:
            packet(hdr.ColorInfo).flags = 3 if self.mode == 2 else 1
        elif head.type == 11:
            packet(hdr.WhiteLevel).level = self.level
        else:
            raise AssertionError(head.type)
        return 0

    def DisplayConfigSetDeviceInfo(self, pointer):
        packet = C.cast(pointer, C.POINTER(hdr.SetWhiteLevel)).contents
        assert packet.header.type == 0xFFFFFFEE
        assert packet.header.size == 28
        assert packet.final_value == 1
        self.writes.append((packet.header.id, packet.header.adapter.low, packet.level))
        self.level = packet.level
        return self.set_error


class HdrTests(unittest.TestCase):
    def test_abi(self):
        for cls, size in [(hdr.Header, 20), (hdr.Source, 20), (hdr.Target, 48),
                          (hdr.Path, 72), (hdr.Mode, 64), (hdr.SourceName, 84),
                          (hdr.ColorInfo, 32), (hdr.ColorInfo2, 36),
                          (hdr.WhiteLevel, 24), (hdr.SetWhiteLevel, 28)]:
            self.assertEqual(C.sizeof(cls), size)
        self.assertEqual(C.alignment(hdr.Mode), 8)

    def test_slider_and_target(self):
        for value, level in [(-1, 1000), (0, 1000), (50, 3500), (100, 6000), (120, 6000)]:
            api = FakeApi()
            with patch.object(hdr, '_user32', return_value=api):
                self.assertTrue(hdr.set_sdr_brightness_if_hdr(r'\\.\DISPLAY2\Monitor0', value))
            self.assertEqual(api.writes, [(11, 42, level)])

    def test_sdr_and_wcg_not_hdr(self):
        for mode in (0, 1):
            api = FakeApi(mode=mode)
            with patch.object(hdr, '_user32', return_value=api):
                self.assertFalse(hdr.set_sdr_brightness_if_hdr(r'\\.\DISPLAY1\Monitor0', 50))
            self.assertEqual(api.writes, [])

    def test_older_windows(self):
        api = FakeApi(legacy=True)
        with patch.object(hdr, '_user32', return_value=api):
            self.assertTrue(hdr.set_sdr_brightness_if_hdr(r'\\.\DISPLAY1\Monitor0', 50))

    def test_missing_display(self):
        api = FakeApi()
        with patch.object(hdr, '_user32', return_value=api), self.assertRaises(OSError):
            hdr.set_sdr_brightness_if_hdr(r'\\.\DISPLAY9\Monitor0', 50)
        self.assertEqual(api.writes, [])

    def test_set_failure(self):
        with patch.object(hdr, '_user32', return_value=FakeApi(set_error=5)):
            with self.assertRaises(OSError):
                hdr.set_sdr_brightness_if_hdr(r'\\.\DISPLAY1\Monitor0', 50)


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('pc_windows', Path(__file__).resolve().parents[1] / 'pc-windows.py')
        cls.pc = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'playsound': types.ModuleType('playsound'),
                                     'paho': types.ModuleType('paho'),
                                     'paho.mqtt': types.SimpleNamespace(client=None)}):
            spec.loader.exec_module(cls.pc)

    def check_route(self, hdr_result, expected_ddc, executable='ControlMyMonitor.exe'):
        with patch.object(self.pc, 'find_controlmymonitor', return_value=executable), \
             patch.object(self.pc, 'set_monitor_brightness', return_value=0) as ddc, \
             patch.object(self.pc, 'set_sdr_brightness_if_hdr') as setter, \
             patch.object(self.pc.time, 'sleep'), patch('builtins.print'):
            if isinstance(hdr_result, Exception):
                setter.side_effect = hdr_result
            else:
                setter.return_value = hdr_result
            self.pc.apply_brightness('nepe', 50)
        self.assertTrue(setter.called)
        self.assertEqual(setter.call_args.args, (r'\\.\DISPLAY1\Monitor0', 50))
        self.assertEqual({(c.args[1], c.args[2]) for c in ddc.call_args_list}, expected_ddc)

    def test_hdr(self):
        self.check_route(True, {(r'\\.\DISPLAY5\Monitor0', 50)})

    def test_sdr(self):
        self.check_route(False, {(r'\\.\DISPLAY5\Monitor0', 50), (r'\\.\DISPLAY1\Monitor0', 38)})

    def test_unknown_never_ddc(self):
        self.check_route(OSError('unavailable'), {(r'\\.\DISPLAY5\Monitor0', 50)})

    def test_hdr_without_ddc_tool(self):
        self.check_route(True, set(), executable=None)


if __name__ == '__main__':
    unittest.main()

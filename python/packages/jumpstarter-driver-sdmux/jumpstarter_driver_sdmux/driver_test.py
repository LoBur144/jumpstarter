import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from jumpstarter_driver_sdmux.driver import UsbSdMux


class TestUsbSdMux(unittest.TestCase):

    def setUp(self):
        self.driver = UsbSdMux()

    @patch("os.popen")
    def test_run_usbsdmux_success(self, mock_popen):
        mock_stream = MagicMock()
        mock_stream.read.return_value = "host"
        mock_stream.close.return_value = None
        mock_popen.return_value = mock_stream

        self.driver.sg_device = "/dev/sg0"

        result = self.driver.run_usbsdmux("get")
        self.assertEqual(result, "host")

    @patch("os.popen")
    def test_run_usbsdmux_fail(self, mock_popen):
        mock_stream = MagicMock()
        mock_stream.read.return_value = ""
        mock_stream.close.return_value = 1
        mock_popen.return_value = mock_stream

        self.driver.sg_device = "/dev/sg0"

        with self.assertRaises(RuntimeError):
            self.driver.run_usbsdmux("get")

    @patch("pathlib.Path.glob")
    def test_wait_for_sd_device(self, mock_glob):
        mock_glob.side_effect = [
            [],
            [],
            [Path("/dev/sda")]
        ]

        result = self.driver.wait_for_sd_device(timeout=1)
        self.assertTrue(result)

    @patch.object(UsbSdMux, "search_sd_card")
    def test_read_success(self, mock_search):
        mock_search.return_value = "/tmp"

        test_file = Path("/tmp/test.txt")
        test_file.write_text("hello")

        result = self.driver.read("test.txt")
        self.assertEqual(result, "hello")

        test_file.unlink()

    @patch.object(UsbSdMux, "search_sd_card")
    def test_read_fail(self, mock_search):
        mock_search.return_value = "/tmp"

        with self.assertRaises(RuntimeError):
            self.driver.read("does_not_exist.txt")

    @patch("os.sync")
    @patch("ctypes.CDLL")
    @patch.object(UsbSdMux, "search_sd_card")
    @patch.object(UsbSdMux, "sdmux_status")
    def test_write_success(self, mock_status, mock_search, mock_cdll, mock_sync):
        mock_status.return_value = "host"
        mock_search.return_value = "/tmp/test_device"

        Path("/tmp/test_device").write_bytes(b"")

        image = Path("/tmp/test.img")
        image.write_bytes(b"1234")

        libc_mock = MagicMock()
        mock_cdll.return_value = libc_mock
        libc_mock.umount.return_value = 0

        result = self.driver.write(str(image))
        self.assertEqual(result, "/tmp/test_device")

        image.unlink()
        Path("/tmp/test_device").unlink()


if __name__ == "__main__":
    unittest.main()

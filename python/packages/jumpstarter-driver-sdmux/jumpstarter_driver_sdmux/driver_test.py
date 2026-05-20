from unittest.mock import patch, MagicMock
from pathlib import Path
import unittest

from jumpstarter_driver_sdmux.driver import UsbSdMux


class TestUsbSdMux(unittest.TestCase):
    """Unit tests for the UsbSdMux driver"""

    def setUp(self):
        self.driver = UsbSdMux()

    @patch("os.popen")
    @patch.object(UsbSdMux, "search_sg_device", return_value="/dev/sg0")
    def test_run_usbsdmux_success(self, mock_search, mock_popen):
        """Test successful execution of usbsdmux command"""
        mock_stream = MagicMock()
        mock_stream.read.return_value = "host"
        mock_stream.close.return_value = None
        mock_popen.return_value = mock_stream

        result = self.driver.run_usbsdmux("get")

        self.assertEqual(result, "host")
        mock_search.assert_called_once()

    @patch("os.popen")
    @patch.object(UsbSdMux, "search_sg_device", return_value="/dev/sg0")
    def test_run_usbsdmux_fail(self, mock_search, mock_popen):
        """Test failed execution of usbsdmux command"""
        mock_stream = MagicMock()
        mock_stream.read.return_value = ""
        mock_stream.close.return_value = 1
        mock_popen.return_value = mock_stream

        with self.assertRaises(RuntimeError):
            self.driver.run_usbsdmux("get")

        mock_search.assert_called_once()

    @patch("pathlib.Path.glob")
    def test_wait_for_sd_device(self, mock_glob):
        """Test detection of newly appearing SD block device"""
        mock_glob.side_effect = [
            [],
            [],
            [Path("/dev/sda")]
        ]

        result = self.driver.wait_for_sd_device(timeout=1)
        self.assertTrue(result)

    @patch("os.sync")
    @patch("subprocess.run")
    @patch.object(UsbSdMux, "search_sd_card")
    @patch.object(UsbSdMux, "_sdmux_status", return_value="host")
    def test_read_success(self, mock_status, mock_search, mock_run, mock_sync):
        """Test successful full SD card read (dd)"""
        mock_search.return_value = "/dev/sda"

        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        output = "/tmp/test.img"

        result = self.driver.read(output)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        self.assertIn("dd", cmd)
        self.assertIn("if=/dev/sda", cmd)
        self.assertIn(f"of={output}", cmd)

        self.assertEqual(result, output)

    @patch("os.sync")
    @patch("subprocess.run")
    @patch.object(UsbSdMux, "search_sd_card")
    @patch.object(UsbSdMux, "_sdmux_status", return_value="host")
    def test_read_fail(self, mock_status, mock_search, mock_run, mock_sync):
        """Test failure when dd command fails"""
        mock_search.return_value = "/dev/sda"

        mock_result = MagicMock(returncode=1)
        mock_run.return_value = mock_result

        with self.assertRaises(RuntimeError):
            self.driver.read("/tmp/test.img")

    @patch.object(UsbSdMux, "search_sd_card")
    @patch.object(UsbSdMux, "_sdmux_status", return_value="host")
    def test_read_invalid_device(self, mock_status, mock_search):
        """Test invalid SD device detection"""
        mock_search.return_value = "/tmp/not_a_block_device"

        with self.assertRaises(RuntimeError):
            self.driver.read("/tmp/test.img")

    @patch("os.sync")
    @patch("subprocess.run")
    @patch.object(UsbSdMux, "search_sd_card")
    @patch.object(UsbSdMux, "_sdmux_status", return_value="host")
    @patch("jumpstarter_driver_sdmux.driver.libc") 
    def test_write_success(self, mock_libc, mock_status, mock_search, mock_run, mock_sync):
        """Test successful writing of an image to the SD card"""

        mock_search.return_value = "/dev/sda"

        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        mock_libc.umount.return_value = 0

        image = "/tmp/test.img"

        result = self.driver.write(image)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        self.assertIn("dd", cmd)
        self.assertIn(f"if={image}", cmd)
        self.assertIn("of=/dev/sda", cmd)

        self.assertEqual(result, "/dev/sda")

    @patch("os.sync")
    @patch("subprocess.run")
    @patch.object(UsbSdMux, "search_sd_card")
    @patch.object(UsbSdMux, "_sdmux_status", return_value="host")
    @patch("jumpstarter_driver_sdmux.driver.libc")
    def test_write_fail(self, mock_libc, mock_status, mock_search, mock_run, mock_sync):
        """Test failed writing of an image to the SD card"""

        mock_search.return_value = "/dev/sda"
        mock_libc.umount.return_value = 0

        mock_result = MagicMock(returncode=1)
        mock_run.return_value = mock_result

        with self.assertRaises(RuntimeError):
            self.driver.write("/tmp/test.img")


if __name__ == "__main__":
    unittest.main()
from dataclasses import dataclass
from jumpstarter.client import DriverClient
from jumpstarter.client.decorators import driver_click_group
import click


@dataclass(kw_only=True)
class UsbSdMuxClient(DriverClient):
    """Client interface for interacting with the UsbSdMux driver"""

    def switch_host(self):
        """Switches SD-Mux to host mode"""
        return self.call("switch_host")

    def switch_dut(self):
        """Switches SD-Mux to DUT mode"""
        return self.call("switch_dut")

    def off(self):
        """Powers off the SD-Mux"""
        return self.call("off")

    def sdmux_status(self):
        """Gets the status of the SD-Mux"""
        return self.call("sdmux_status")

    def write(self, image_file: str):
        """Writes an image to the SD card"""
        return self.call("write", image_file)

    def read(self, filepath: str):
        """Reads a file from the SD card"""
        return self.call("read", filepath)

    def get_sg_device(self):
        """Gets the SCSI generic device path"""
        return self.call("get_sg_device")

    def cli(self):
        """Register CLI commands for SD-Mux control"""
        @driver_click_group(self)
        def sdmux():
            """SDMux control commands"""
            pass

        @sdmux.command()
        def host():
            """Switch to host mode"""
            self.switch_host()

        @sdmux.command()
        def dut():
            """Switch to DUT mode"""
            self.switch_dut()

        @sdmux.command()
        def off():
            """Power off SDMux"""
            self.off()

        @sdmux.command()
        def status():
            """Get SDMux status"""
            print(self.sdmux_status())

        @sdmux.command()
        @click.argument("image_file")
        def write(image_file):
            """Write image to SD card"""
            self.write(image_file)

        @sdmux.command()
        @click.argument("filepath")
        def read(filepath):
            """Read file from SD card"""
            print(self.read(filepath))

        return sdmux
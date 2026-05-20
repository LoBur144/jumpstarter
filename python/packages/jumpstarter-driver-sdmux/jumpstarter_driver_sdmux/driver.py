from __future__ import annotations

from jumpstarter.driver import Driver, export
from pathlib import Path
import subprocess
import ctypes
import time
import os

# Gives direct access to libc for mount/umount syscalls
libc = ctypes.CDLL("libc.so.6")

class UsbSdMux(Driver):
    """Driver for UsbSdMux device, used for automated SD-Card access"""
    sg_device: str | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sg_device = None

    def start(self):
        """Called by the framework on startup"""
        self.logger.info("Starting UsbSdMux driver")
        self.sg_device = self.search_sg_device()

    def search_sg_device(self):
        """Locate the UsbSdMux via vendor/product ID and returns the corresponding /dev/sgX path"""
        valid_devices = {
            ("0424", "2640"),
            ("0424", "4041"),
        }

        for sg in Path("/sys/class/scsi_generic").glob("sg*"):
            resolved = sg.resolve()
            self.logger.info(f"Checking {sg.name}: {resolved}")

            for parent in resolved.parents:
                if (parent / "idVendor").exists():
                    vendor = (parent / "idVendor").read_text().strip()
                    product = (parent / "idProduct").read_text().strip()

                    self.logger.info(f"Checking {sg.name}: vendor={vendor}, product={product}")

                    if (vendor, product) in valid_devices:
                        self.logger.info(f"Found SDMux reader: /dev/{sg.name}")
                        return f"/dev/{sg.name}"

        raise RuntimeError("No USB-SD-Mux reader device found")

    def wait_for_sd_device(self, timeout=5):
        """Waits until a new /dev/sdX device appears"""
        start = time.time()

        existing_devices = set(Path("/dev").glob("sd?"))

        while time.time() - start < timeout:
            current_device = set(Path("/dev").glob("sd?"))

            new_devices = current_device - existing_devices
            if new_devices:
                self.logger.info(f"Detected new SD device: {new_devices}")
                return True

        raise RuntimeError("SD device not found")


    def search_sd_card(self):
        """Locates the SD-Card block device e.g. /dev/sdX"""
        if self._sdmux_status().strip() != "host":
            self.switch_host()
            self.wait_for_sd_device()

        self.logger.info("Searching for SD-Card...")

        self.search_sg_device()
        sg_name = Path(self.sg_device).name
        sg_path = Path(f"/sys/class/scsi_generic/{sg_name}")

        resolved = sg_path.resolve()

        for parent in resolved.parents:
            block_path = parent / "block"
            if block_path.exists():
                devices = list(block_path.glob("sd?"))
                if devices:
                    sd_device = f"/dev/{devices[0].name}"
                    self.logger.info(f"Found SD device: {sd_device}")
                    return sd_device

        raise RuntimeError("No SD card found")

    @export
    def read(self, output_file:str):
        """Read the full SD card content and store it as an image file"""
        self.logger.info("Reading image from SD card")

        if self._sdmux_status().strip() != "host":
            self.switch_host()
            self.wait_for_sd_device()

        sd_card = self.search_sd_card()
        self.logger.info(f"Using device: {sd_card}")

        if not sd_card.startswith("/dev/sd"):
            raise RuntimeError("Invalid SD device")

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Saving image to: {output_path}")

        result = subprocess.run(["sudo","dd",f"if={sd_card}",f"of={output_file}","bs=16M", "iflag=direct", "oflag=direct", "status=progress"],)

        os.sync()

        if result.returncode != 0:
            raise RuntimeError("Read failed")

        self.logger.info("Read complete")
        return str(output_path)



    @export
    def write(self, image_file):
        """Flashes an image file on to the SD-Card using dd"""
        self.logger.info("Writing image to SD card")

        if self._sdmux_status().strip() != "host":
            self.switch_host()
            self.wait_for_sd_device()

        sd_card = self.search_sd_card()
        self.logger.info(f"Using device: {sd_card}")

        self.logger.info("Unmounting SD before write")
        libc.umount(str(Path.home() / "sdmux").encode())

        self.logger.info(f"Flashing {image_file} to {sd_card}")

        result = subprocess.run(["sudo","dd",f"if={image_file}",f"of={sd_card}","bs=4M",],)

        os.sync()

        if result.returncode != 0:
            raise RuntimeError("Write failed")

        self.logger.info("Write complete")
        return sd_card

    def _sdmux_status(self):
        """Internal helper method that reads mux state"""
        return self.run_usbsdmux("get")

    def run_usbsdmux(self, mode):
        """Executes the usbsdmux command with the given mode and returns its output"""
        if not self.sg_device:
            self.sg_device = self.search_sg_device()

        self.logger.info(f"Running: usbsdmux {self.sg_device} {mode}")

        cmd = f"usbsdmux {self.sg_device} {mode}"
        stream = os.popen(cmd)

        output = stream.read()
        result = stream.close()

        if result is not None:
            raise RuntimeError(f"usbsdmux failed: {mode}")

        return output

    @export
    def switch_host(self):
        """Switches SD-Mux to host mode"""
        self.logger.info("Switching sdmux to host")
        return self.run_usbsdmux("host")

    @export
    def switch_dut(self):
        """Switches SD-Mux to dut mode"""
        self.logger.info("Switching sdmux to dut")
        try:
            libc.umount(str(Path.home() / "sdmux").encode())
        except OSError:
            pass
        return self.run_usbsdmux("dut")

    @export
    def off(self):
        """Powers off the SD-Mux"""
        self.logger.info("sdmux powering off")
        return self.run_usbsdmux("off")

    @export
    def sdmux_status(self):
        """Returns the current SD-Mux status (host/dut/off)"""
        self.logger.info("getting sdmux status/info")
        return self._sdmux_status()

    @export
    def get_sg_device(self):
        """Returns the /dev/sgX path of the SD-Mux device, or searches for it if not already set"""
        if not self.sg_device:
            self.sg_device = self.search_sg_device()
        return self.sg_device

    @classmethod
    def client(cls) -> str:
        """Jumpstarter client binding"""
        return "jumpstarter_driver_sdmux.client.UsbSdMuxClient"

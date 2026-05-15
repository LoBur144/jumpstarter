from jumpstarter.driver import Driver, export 
from pathlib import Path
import subprocess
import ctypes
import time
import os

libc = ctypes.CDLL("libc.so.6")

class UsbSdMux(Driver):
    sg_device: str | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #self.serial = kwargs.get("serial")
        #self.idVendor = kwargs.get("idVendor")
        #self.idProduct = kwargs.get("idProduct")
        self.sg_device = None
    
    def start(self):
        print("UsbSdMux Startet")
        self.sg_device = self.search_sg_device()

    def search_sg_device(self):
        VALID_DEVICES = {
            ("0424", "2640"),
            ("0424", "4041"),
        }

        for sg in Path("/sys/class/scsi_generic").glob("sg*"):
            resolved = sg.resolve()
            print(resolved)

            for parent in resolved.parents:
                if (parent / "idVendor").exists():
                    vendor = (parent / "idVendor").read_text().strip()
                    product = (parent / "idProduct").read_text().strip()

                    print(f"Checking {sg.name}: vendor={vendor}, product={product}")

                    if (vendor, product) in VALID_DEVICES:
                        print(f"Found SDMux reader: /dev/{sg.name}")
                        return f"/dev/{sg.name}"

        raise RuntimeError("No USB-SD-Mux reader device found")

    def wait_for_sd_device(self, timeout=5):
        start = time.time()

        existing_devices = set(Path("/dev").glob("sd?"))

        while time.time() - start < timeout:
            current_device = set(Path("/dev").glob("sd?"))

            new_devices = current_device - existing_devices
            if new_devices:
                print(f"Detected new SD device: {new_devices}")
                return True

        raise RuntimeError("SD device not found")


    def search_sd_card(self):
        if self.sdmux_status().strip() != "host":
            self.switch_host()
            self.wait_for_sd_device()

        print("Searching for SD-Card...")

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
                    print(f"Found SD device: {sd_device}")
        
                    disk = devices[0].name 
                    partitions = list(Path("/sys/class/block").glob(f"{disk}[0-9]*"))
                    if not partitions:
                        raise RuntimeError("No partition found on sd card")
                    
                    final_partition = f"/dev/{partitions[0].name}"

                    mount_point = Path.home() / "sdmux"
                    mount_point.mkdir(parents=True, exist_ok=True)
                    with open("/proc/self/mounts") as f:
                        mounts = f.read()

                    if mount_point.as_posix() in mounts:
                        print(f"{sd_device} already mounted")
                        return str(mount_point)

                    print(f"Mounting {sd_device} to {mount_point}")

                    result = libc.mount(
                        final_partition.encode(),
                        str(mount_point).encode(),
                        b"auto",
                        0,
                        None
                    )

                    if result != 0:
                        raise RuntimeError("mount failed")

                    print("Mount successful")
                    return str(mount_point)
        raise RuntimeError("No SD card found")
    
    @export
    def read(self, filepath):
        print("Read file from SD card")

        mount_point = self.search_sd_card()

        full_path = Path(mount_point) / filepath

        if not full_path.exists():
            raise RuntimeError(f"File not found: {full_path}")

        print(f"Reading file: {full_path}")

        with open(full_path, "r") as f:
            return f.read()

    @export
    def write(self, image_file):
        print("Writing image to SD card")

        if self.sdmux_status().strip() != "host":
            self.switch_host()
            self.wait_for_sd_device()

        sd_card = self.search_sd_card()
        print(f"Using device: {sd_card}")

        print("Unmounting SD before write")
        libc.umount(str(Path.home() / "sdmux").encode())

        print(f"Flashing {image_file} to {sd_card}")

        result = subprocess.run(
                [
                    "sudo",
                    "dd",
                    f"if={image_file}",
                    f"of={sd_card}",
                    "bs=4M",
                ]
            )

        os.sync()

        if result.returncode != 0:
            raise RuntimeError("Write failed")

        print("Write complete")
        return sd_card

    def run_usbsdmux(self, mode):
        if not self.sg_device:
            self.sg_device = self.search_sg_device()

        print(f"Running: usbsdmux {self.sg_device} {mode}")


        cmd = f"usbsdmux {self.sg_device} {mode}"
        stream = os.popen(cmd)

        output = stream.read()
        result = stream.close()

        if result is not None:
            raise RuntimeError(f"usbsdmux failed: {mode}")

        return output

    @export
    def switch_host(self):
        print("switching sdmux to host")
        return self.run_usbsdmux("host")

    @export
    def switch_dut(self):
        print("switching sdmux to dut")
        libc.umount(str(Path.home() / "sdmux").encode())
        return self.run_usbsdmux("dut")
    
    @export
    def off(self):
        print("sdmux powering off")
        return self.run_usbsdmux("off")
    
    @export
    def sdmux_status(self):
        print("getting sdmux status/info")
        return self.run_usbsdmux("get")

    @export
    def get_sg_device(self):
        if not self.sg_device:
            self.sg_device = self.search_sg_device()
        return self.sg_device

    @classmethod
    def client(cls) -> str:
        return "jumpstarter.driver.client.DriverClient"

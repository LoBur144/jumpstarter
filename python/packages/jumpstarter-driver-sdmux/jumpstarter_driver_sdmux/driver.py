from pathlib import Path
import time
from jumpstarter.driver import Driver, export 
import subprocess

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

    def search_sd_card(self):
        self.switch_host()
        time.sleep(2)

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
                    mounts = subprocess.run(["mount"], capture_output=True, text=True).stdout

                    if sd_device in mounts:
                        print(f"{sd_device} already mounted")
                        return str(mount_point)

                    print(f"Mounting {sd_device} to {mount_point}")

                    result = subprocess.run(["sudo", "mount", final_partition, str(mount_point)],capture_output=True,text=True,)

                    if result.returncode != 0:
                        print("Mount failed:")
                        print(result.stderr)
                        return sd_device

                    print("Mount successful")
                    return str(mount_point)
        raise RuntimeError("No SD card found")


    def run_usbsdmux(self, mode):
        if not self.sg_device:
            self.sg_device = self.search_sg_device()

        print(f"Running: usbsdmux {self.sg_device} {mode}")

        result = subprocess.run(
            ["usbsdmux", self.sg_device, mode],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError(f"usbsdmux failed: {mode}")

        return result.stdout


    @export
    def switch_host(self):
        print("switching sdmux to host")
        return self.run_usbsdmux("host")

    @export
    def switch_dut(self):
        print("switching sdmux to dut")
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
    
    @export
    def read(self, filepath):
        print("Read file from SD card")

        mount_point = self.search_sd_card()

        full_path = Path(mount_point) / filepath

        if not full_path.exists():
            raise RuntimeError(f"File not found: {full_path}")

        print(f"Reading file: {full_path}")

        with open(full_path, "rb") as f:
            return f.read()

    @export
    def write(self, image_file):
        print("Writing image to SD card")

        self.switch_host()
        time.sleep(2)

        sd_device = self.search_sd_card()

        print(f"Using device: {sd_device}")

        print("Unmounting SD before write")
        subprocess.run(
            ["sudo", "umount", f"{sd_device}*"],
            capture_output=True,
            text=True,
        )

        print(f"Flashing {image_file} to {sd_device}")

        result = subprocess.run(
            [
                "sudo",
                "dd",
                f"if={image_file}",
                f"of={sd_device}",
                "bs=4M",
                "status=progress",
                "conv=fsync",
            ],
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError("write failed")

        subprocess.run(["sync"])

        print("Write complete")
        return sd_device

    @classmethod
    def client(cls) -> str:
        return "jumpstarter.driver.client.DriverClient"

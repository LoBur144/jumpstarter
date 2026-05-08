from pathlib import Path
from jumpstarter.driver import Driver, export 
import subprocess

class UsbSdMux(Driver):
    sg_device: str | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.serial = kwargs.get("serial")
        self.idVendor = kwargs.get("idVendor")
        self.idProduct = kwargs.get("idProduct")
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
    def info(self):
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

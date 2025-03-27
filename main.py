import sys
import time
import uuid

import serial
import serial.tools.list_ports

CHIP_SIZE = 0x80000
CHUNK_SIZE = 32


class Main:
    def __init__(self):
        sys.stdout.write("AMD AM29F400B Reader\n")
        sys.stdout.write("(C) 2025 Tarek Poltermann - https://multilan.de\n\n")

        sys.stdout.write("Available Serial Ports:\n")
        ports = serial.tools.list_ports.comports()
        for index, port in enumerate(ports):
            sys.stdout.write(f"{index}: {port.description}\n")
        port = input("\nSelect Serial Port: ")

        if not port.isdigit() or int(port) < 0 or int(port) > len(ports) - 1:
            sys.stdout.write("Invalid Serial Port!\n")
            exit()

        port = ports[int(port)].name
        sys.stdout.write("\n")

        sys.stdout.write(f"Opening Serial Port '{port}'... ")
        self.ser = serial.Serial(port, baudrate=115200)
        sys.stdout.write("Success\n")

        sys.stdout.write("Waiting for Interface... ")
        self.ser.read_until(b"\x99")
        sys.stdout.write("Ready\n")

        sys.stdout.write("Init... ")
        self.execute_command(0x00)
        sys.stdout.write("Done\n\n")

        self.read_ident()
        self.data = self.read(0, CHIP_SIZE)
        self.save()

        sys.stdout.write("\nFinished\n")

    def execute_command(self, command, *args):
        data = [command, int(len(args))]
        data.extend(args)

        self.ser.write(bytearray(data))
        message_start = self.ser.read(2)

        message_type = message_start[0]
        message_length = message_start[1]

        if message_type != command:
            return None

        data = self.ser.read(message_length)
        return data

    def read_ident(self):
        sys.stdout.write("Reading Ident... ")
        ident = self.execute_command(0x01)

        if ident is None:
            sys.stdout.write("Failed\n")
            exit()

        sys.stdout.write("Success\n")

        manufacturer_id = ident[0]
        device_id = ident[1]

        sys.stdout.write(f"Manufacturer ID: 0x{manufacturer_id:02X}\n")
        sys.stdout.write(f"Device ID: 0x{device_id:02X}\n\n")

        if manufacturer_id != 0x01:
            sys.stdout.write("Expected 0x01 for Manufacturer ID!\n")
            exit()

        if device_id != 0x23 and device_id != 0xab:
            sys.stdout.write("Expected 0x23 or 0xAB for Device ID!\n")
            exit()

    def read(self, start, size):
        data = bytearray()
        got_some_data = False

        for address_big in range(start, size + start, CHUNK_SIZE):
            address = int(address_big).to_bytes(4)

            result = self.execute_command(0x02, address[0], address[1], address[2], address[3], CHUNK_SIZE)
            data += result

            if not got_some_data:
                got_some_data = 0x00 not in result

            sys.stdout.write(f"\rReading... {str(address_big + 1 - start)}/{size}")

            time.sleep(0.05)

        if not got_some_data:
            sys.stdout.write("\rReading... Failed\n")
            exit()

        sys.stdout.write("\rReading... Done\n")
        return data

    def save(self):
        sys.stdout.write("Writing Dump... ")
        filename = f"dump-{uuid.uuid4()}.bin"
        with open(filename, "wb") as file:
            file.write(self.data)
        sys.stdout.write("Done\n")
        sys.stdout.write(f"Saved as {filename}\n\n")


Main()

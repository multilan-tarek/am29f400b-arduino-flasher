import os
import sys
import time
from os import fdopen

import serial
import serial.tools.list_ports

# Declares how many bytes are sent during one serial transmission from/to the Arduino
CHUNK_SIZE = 32

# 512 KB
CHIP_SIZE = 0x80000

# Sector layouts for T and B variants
SECTORS = {
    0x23: [
        0x00000,
        0x10000,
        0x20000,
        0x30000,
        0x40000,
        0x50000,
        0x60000,
        0x70000,
        0x78000,
        0x7a000,
        0x7c000
    ],
    0xab: [
        0x00000,
        0x04000,
        0x06000,
        0x08000,
        0x10000,
        0x20000,
        0x30000,
        0x40000,
        0x50000,
        0x60000,
        0x70000
    ]
}


class Main:
    def __init__(self):
        sys.stdout.write("AMD AM29F400B Arduino Flasher\n")
        sys.stdout.write("(C) 2025 Tarek Poltermann - https://multilan.de\n\n")

        command, file, start, size, sector = self.parse_command()
        self.ser = self.start_serial()

        # Wait for Arduino to be ready
        sys.stdout.write("Waiting for interface... ")
        self.ser.read_until(b"\x99")
        sys.stdout.write("Ready\n")

        # Init Arduino IO and reset flash
        sys.stdout.write("Init... ")
        self.execute_command(0x00)
        sys.stdout.write("Done\n\n")

        # Identify and check device
        device_id = self.read_ident()

        # Set start and size from sector data
        # Can only be done after device ident, because we have to know which variant the flash is
        if sector is not None:
            start, size = SECTORS.get(device_id)[sector]

        if command == "-r":
            self.read(file, start or 0, size or CHIP_SIZE)

        elif command == "-w":
            # Check if filesize matches with the area we want to write
            # Can only be done after device ident, because we have to know which variant the flash is
            if file and os.path.getsize(file) != size:
                sys.stdout.write(f"Filesize must be {size} bytes!\n")
                exit()

            confirmation = input(f"The contents of '{file}' are about to be written to the flash. Confirm [y/N]: ")

            if confirmation.lower() != "y":
                exit()

            # Partial Write (no sector set, but start and size set)
            # We can't erase specific addresses so we don't even try
            # The user has to know what he's doing
            if not (sector is None and start is not None and size is not None):
                self.erase(SECTORS.get(device_id), sector)

            self.write(file, start or 0, size or CHIP_SIZE)

        elif command == "-e":
            confirmation = input(f"The contents of the flash are about to be erased. Confirm [y/N]: ")

            if confirmation.lower() != "y":
                exit()

            self.erase(SECTORS.get(device_id), sector)

        elif command == "-v":
            self.print_sector_protection_list(SECTORS.get(device_id))

        sys.stdout.write("\nFinished\n")

    def parse_command(self):
        args_length = len(sys.argv)

        if args_length == 1:
            sys.stdout.write(f"Please specify a command!\n\n")
            self.print_help()
            exit()

        command = sys.argv[1]
        sector = None
        start = None
        size = None
        file = None

        if command == "-h":
            self.print_help()
            exit()

        elif command in ["-r", "-w"] and 3 <= args_length <= 5:
            file = sys.argv[2]

            if command == "-r" and os.path.exists(file):
                sys.stdout.write(f"File '{file}' already exists!\n")
                exit()

            elif command == "-w" and not os.path.exists(file):
                sys.stdout.write(f"File '{file}' does not exist!\n")
                exit()

            if args_length == 4:
                sector = self.validate_sector(sys.argv[3])

            elif args_length == 5:
                start, size = self.validate_start_size(sys.argv[3], sys.argv[4])

        elif command == "-e" and args_length == 3:
            sector = self.validate_sector(sys.argv[3])

        elif command == "-v":
            pass

        else:
            sys.stdout.write(f"Unknown command: '{" ".join(sys.argv[1:])}'\n\n")
            self.print_help()
            exit()

        return command, file, start, size, sector

    @staticmethod
    def print_help():
        sys.stdout.write("Available commands:\n")
        sys.stdout.write(f"-r <file>{'\t' * 5}| Read full\n")
        sys.stdout.write(f"-r <file> <start> <size>\t| Read partial\n")
        sys.stdout.write(f"-r <file> <sector>{'\t' * 3}| Read sector\n")
        sys.stdout.write(f"-w <file>{'\t' * 5}| Write full\n")
        sys.stdout.write(f"-w <file> <start> <size>\t| Write partial (without erasing)\n")
        sys.stdout.write(f"-w <file> <sector>{'\t' * 3}| Write sector\n")
        sys.stdout.write(f"-e{'\t' * 7}| Erase full\n")
        sys.stdout.write(f"-e <sector>{'\t' * 5}| Erase sector\n")
        sys.stdout.write(f"-v{'\t' * 7}| Prints sector protection states\n")

    @staticmethod
    def validate_start_size(start, size):
        start_is_hex = "0x" in start
        start = start.replace("0x", "")

        size_is_hex = "0x" in size
        size = size.replace("0x", "")

        try:
            start = int(start, 16 if start_is_hex else 10)
        except ValueError:
            sys.stdout.write("<start> argument is invalid!\n")
            exit()

        try:
            size = int(size, 16 if size_is_hex else 10)
        except ValueError:
            sys.stdout.write("<size> argument is invalid!\n")
            exit()

        if start < 0 or start > CHIP_SIZE - 1:
            if start_is_hex:
                sys.stdout.write(f"<start> argument must be in range from 0x00 to 0x{CHIP_SIZE - 1:02X}!\n")
            else:
                sys.stdout.write(f"<start> argument must be in range from 0 to {CHIP_SIZE - 1}!\n")
            exit()

        if size > CHIP_SIZE - start or size < 1:
            if start_is_hex:
                sys.stdout.write(f"<size> argument must be in range from 0x01 to 0x{CHIP_SIZE - start:02X} (depending on the starting address)!\n")
            else:
                sys.stdout.write(f"<size> argument must be in range from 1 to {CHIP_SIZE - start} (depending on the starting address)!\n")
            exit()

        return start, size

    @staticmethod
    def validate_sector(sector):
        try:
            sector = int(sector)
        except ValueError:
            sys.stdout.write("<sector> argument is invalid!\n")
            exit()

        if sector < 0 or sector > 10:
            sys.stdout.write(f"<sector> argument must be in range from (SA)0 to (SA)10!\n")

        return sector

    @staticmethod
    def start_serial():
        ports = serial.tools.list_ports.comports()

        if len(ports) == 0:
            sys.stdout.write(f"No serial ports available!\n")

        sys.stdout.write("Available serial ports:\n")
        for index, port in enumerate(ports):
            sys.stdout.write(f"{index}: {port.description}\n")

        port = input("\nSelect serial port: ")

        if not port.isdigit() or int(port) < 0 or int(port) > len(ports) - 1:
            sys.stdout.write("Invalid serial port!\n")
            exit()

        port = ports[int(port)].name
        sys.stdout.write("\n")

        sys.stdout.write(f"Opening serial port '{port}'... ")
        ser = serial.Serial(port, baudrate=115200)
        sys.stdout.write("Success\n")

        return ser

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
        sys.stdout.write("Identifying... ")
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
            sys.stdout.write("Expected 0x01 for manufacturer ID!\n")
            exit()

        if device_id != 0x23 and device_id != 0xab:
            sys.stdout.write("Expected 0x23 or 0xAB for device ID!\n")
            exit()

        return device_id

    def read(self, file, start, size):
        output_file = open(file, "wb")

        for address_int in range(start, size + start, CHUNK_SIZE):
            address = int(address_int).to_bytes(4)
            cycle_chunk_size = min(CHUNK_SIZE, start + size - address_int)

            output_file.write(self.execute_command(0x02, address[0], address[1], address[2], address[3], cycle_chunk_size))

            sys.stdout.write(f"\rReading... 0x{str(address_int + 1 - start):02X}/0x{size:02X}")
            time.sleep(0.05)

        output_file.close()

        sys.stdout.write("\rReading... Done\n")
        sys.stdout.write(f"Saved to {file}\n\n")

    def write(self, file, start, size):
        with open(file, "rb") as input_file:
            data = input_file.read()

        for address_int in range(start, size + start, CHUNK_SIZE):
            address = int(address_int).to_bytes(4)
            cycle_chunk_size = min(CHUNK_SIZE, start + size - address_int)

            args = [
                address[0],
                address[1],
                address[2],
                address[3],
                cycle_chunk_size
            ]

            chunk_offset = address_int - start
            chunk = data[chunk_offset:chunk_offset + cycle_chunk_size]
            args.extend(chunk)

            self.execute_command(0x04, *args)

            sys.stdout.write(f"\rWriting... 0x{str(address_int + 1 - start):02X}/0x{size:02X}")
            time.sleep(0.05)

        sys.stdout.write("\rWriting... Done\n")

    def erase(self, device_layout, sector):
        found_protected_sectors = False

        sectors = device_layout
        if sector is not None:
            sectors = device_layout[sector]

        for address_int in sectors:
            address = int(address_int).to_bytes(4)

            if self.is_sector_protected(address_int):
                found_protected_sectors = True

            self.execute_command(0x03, address[0], address[1], address[2], address[3])

            sys.stdout.write(f"\rErasing... 0x{str(address_int):02X}")
            time.sleep(0.05)

        sys.stdout.write("\rErasing... Done\n")

        if found_protected_sectors:
            sys.stdout.write("\nWarning:\nSome sectors are protected and cannot be modified.\nCheck protection states with '-v' command.\n")

    def is_sector_protected(self, sector_address):
        address = int(sector_address).to_bytes(4)
        result = self.execute_command(0x05, address[0], address[1], address[2], address[3])
        return result == 0x01

    def print_sector_protection_list(self, device_layout):
        sectors = device_layout

        sys.stdout.write("Sector protection states:\n")
        for i, address in enumerate(sectors):
            state = 'Protected' if self.is_sector_protected(address) else 'Unprotected'
            sys.stdout.write(f"SA{i}: {state}\n")


Main()

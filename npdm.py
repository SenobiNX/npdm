#!/usr/bin/env python3

import argparse
import enum
import json
import struct
import sys
import typing


class ByteOrder(enum.Enum):
    little = "<"
    big = ">"

class BinaryWriter:
    def __init__(self, size: int = 0, byte_order: ByteOrder = ByteOrder.little):
        self.stream = bytearray(size)
        self.byte_order = byte_order
        self._position = 0

    @property
    def position(self) -> int:
        return self._position

    def save(self, filename: str):
        with open(filename, "wb") as f:
            f.write(self.stream)
    
    def write_sub(self, other: "BinaryWriter"):
        self.write_bytes(other.stream)

    def seek(self, offset: int, *, relative: bool = False):
        if relative:
            self._position += offset
        else:
            self._position = offset
        
        self._fill_bytes(0)
    
    def seek_rel(self, offset: int):
        self.seek(offset, relative=True)

    def align(self, alignment: int):
        pos = self.position
        delta = (-pos % alignment + alignment) % alignment
        self.seek(delta, relative=True)

    def _fill_bytes(self, offset: int, relative: bool = True):
        bytes_to_add = offset - len(self.stream)
        if relative:
            bytes_to_add += self.position

        if bytes_to_add > 0:
            self.stream += bytearray(bytes_to_add)

    def write(self, raw: bytes):
        self._fill_bytes(len(raw))
        for byte in raw:
            self.stream[self._position] = byte
            self._position += 1

    def _write(self, fmt: str, value):
        endianness = self.byte_order.value
        raw = struct.pack(endianness + fmt, value)
        self.write(raw)

    def write_bool(self, value: bool):
        self._write("?", value)

    def write_s8(self, value: int):
        self._write("b", value)

    def write_u8(self, value: int):
        self._write("B", value)

    def write_s16(self, value: int):
        self._write("h", value)

    def write_u16(self, value: int):
        self._write("H", value)

    def write_u24(self, value: int):
        if self.byte_order == ByteOrder.little:
            self.write(struct.pack("<I", value)[:3])
        else:
            self.write(struct.pack(">I", value)[1:])

    def write_s32(self, value: int):
        self._write("i", value)

    def write_u32(self, value: int):
        self._write("I", value)

    def write_s64(self, value: int):
        self._write("q", value)

    def write_u64(self, value: int):
        self._write("Q", value)

    def write_f32(self, value: float):
        self._write("f", value)

    def write_f64(self, value: float):
        self._write("d", value)

    def write_bytes(self, value: bytes):
        self.write(value)
    
    def write_string(self, value: str, *, max_len: int = -1):
        if max_len > 0:
            value = value[:max_len]
            self.write("{:\0<{max_len}}".format(value, max_len=max_len).encode("ascii"))
        else:
            self.write(value.encode("ascii"))


def json_read_value(json: dict, key: str, default: typing.Any) -> typing.Any:
    # if isinstance(keys, str):
    #     keys = (keys,)
    # 
    # for key in keys:
    if default is not None:
        return json.get(key, default)
    else:
        if key not in json:
            print(f"error: couldn't find key `{key}`", file=sys.stderr)
            sys.exit(1)
        return json[key]

def json_read_dict(json: dict, key: str, default: dict = None) -> dict:
    data = json_read_value(json, key, default)
    if not isinstance(data, dict):
        print(f"error: `{key}` must be a dict", file=sys.stderr)
        sys.exit(1)
    return data

def json_read_list(json: dict, key: str, default: list = None) -> list:
    data = json_read_value(json, key, default)
    if not isinstance(data, list):
        print(f"error: `{key}` must be a list", file=sys.stderr)
        sys.exit(1)
    return data

def json_read_bool(json: dict, key: str, default: bool = None) -> bool:
    data = json_read_value(json, key, default)
    if not isinstance(data, bool):
        print(f"error: `{key}` must be a boolean", file=sys.stderr)
        sys.exit(1)
    return data

def json_read_str(json: dict, key: str, max_len: int = -1, default: str = None) -> str:
    data = json_read_value(json, key, default)
    if not isinstance(data, str):
        print(f"error: `{key}` must be a string", file=sys.stderr)
        sys.exit(1)

    if max_len > 0 and len(data) > max_len:
        print(f"error: string `key` must be less than {max_len} in length", file=sys.stderr)
        sys.exit(1)

    return data

def json_read_int(json: dict, key: str, min_val: int, max_val: int, default: int = None) -> int:
    data = json_read_value(json, key, default)
    if isinstance(data, int):
        val = data
    elif isinstance(data, str):
        val = int(data, 16)
    else:
        print(f"error: `{key}` must be an integer", file=sys.stderr)
        sys.exit(1)

    if val < min_val or val > max_val:
        print(f"error: `{key}` must be between {min_val:#x} and {max_val:#x}", file=sys.stderr)
        sys.exit(1)
    return val

def json_read_u64(json: dict, key: str, default: int = None) -> int:
    return json_read_int(json, key, 0, 0xffffffffffffffff, default)

def json_read_u32(json: dict, key: str, default: int = None) -> int:
    return json_read_int(json, key, 0, 0xffffffff, default)

def json_read_u16(json: dict, key: str, default: int = None) -> int:
    return json_read_int(json, key, 0, 0xffff, default)

def json_read_u8(json: dict, key: str, default: int = None) -> int:
    return json_read_int(json, key, 0, 0xff, default)


def main():
    parser = argparse.ArgumentParser(description="generate NPDM file from JSON")
    parser.add_argument("infile")
    parser.add_argument("outfile", nargs="?", default="new.npdm")
    # parser.add_argument("-q", "--quiet", action="store_true")

    args = parser.parse_args()

    with open(args.infile) as f:
        contents = json.load(f)
    
    if "process_category" in contents:
        print("error: key `process_category` is invalid, did you mean `version`?", file=sys.stderr)
        sys.exit(1)
    if "title_id" in contents:
        print("error: key `title_id` is invalid, did you mean `program_id`?", file=sys.stderr)
        sys.exit(1)
    if "title_id_range_min" in contents:
        print("error: key `title_id_range_min` is invalid, did you mean `program_id_range_min`?", file=sys.stderr)
        sys.exit(1)
    if "title_id_range_max" in contents:
        print("error: key `title_id_range_max` is invalid, did you mean `program_id_range_max`?", file=sys.stderr)
        sys.exit(1)


    writer = BinaryWriter()

    # META section

    meta_size = 0x80
    writer.write_string("META")
    writer.write_u32(json_read_u32(contents, "signature_key_generation", 0))
    writer.seek(0x4)

    flags = 0
    flags |= 0b00000001 if json_read_bool(contents, "is_64_bit") else 0
    flags |= json_read_int(contents, "address_space_type", 0, 3) << 1
    flags |= 0b00010000 if json_read_bool(contents, "optimize_memory_allocation", False) else 0
    flags |= 0b00100000 if json_read_bool(contents, "disable_device_address_space_merge", False) else 0
    flags |= 0b01000000 if json_read_bool(contents, "enable_alias_region_extra_size", False) else 0
    flags |= 0b10000000 if json_read_bool(contents, "prevent_code_reads", False) else 0
    writer.write_u8(flags)
    writer.seek(0xe)
    writer.write_u8(json_read_int(contents, "main_thread_priority", 0, 0x3f))
    writer.write_u8(json_read_u8(contents, "default_cpu_id"))
    writer.seek(0x14)
    writer.write_u32(json_read_int(contents, "system_resource_size", 0, 0x1fe00000))
    writer.write_u32(json_read_u32(contents, "version", 0))

    main_thread_stack_size = json_read_u32(contents, "main_thread_stack_size")
    if main_thread_stack_size & 0xfff != 0:
        print("error: `main_thread_stack_size` must be aligned to 0x1000", file=sys.stderr)
        sys.exit(1)
    writer.write_u32(main_thread_stack_size)

    name = json_read_str(contents, "name", max_len=0x10)
    writer.write_string(name, max_len=0x10)
    writer.write_bytes(b"\0"*16) # product code

    # ACID section

    writer.seek(meta_size)
    acid_offset = writer.position
    writer.write_bytes(b"\x00"*0x100) # RSA2048 signature
    writer.write_bytes(b"\x00"*0x100) # RSA2048 public key

    writer.write_string("ACID")
    writer.seek_rel(4) # skip size for now
    writer.seek_rel(4) # TODO: skipped version and unknown 0x209 thingy
    
    acid_flags = 0
    acid_flags |= 0b00000001 if json_read_bool(contents, "is_retail") else 0
    acid_flags |= 0b00000010 if json_read_bool(contents, "unqualified_approval", False) else 0
    acid_flags |= json_read_int(contents, "pool_partition", 0, 3)
    writer.write_u32(acid_flags)
    writer.write_u64(json_read_u64(contents, "program_id_range_min"))
    writer.write_u64(json_read_u64(contents, "program_id_range_max"))
    writer.seek_rel(0x20)
    
    # ACID - Filesystem Access Control

    fs_access = json_read_dict(contents, "filesystem_access")
    content_owner_ids = json_read_list(fs_access, "content_owner_ids", [])

    fac_offset = writer.position
    writer.write_u8(1) # version
    writer.write_u8(0) # content owner ID count
    writer.write_u8(0) # save data owner ID count
    writer.seek(fac_offset + 4)
    writer.write_u64(json_read_u64(fs_access, "permissions"))
    writer.write_u64(0) # content owner ID min
    writer.write_u64(0) # content owner ID max
    writer.write_u64(0) # save data owner ID min
    writer.write_u64(0) # save data owner ID max
    fac_size = writer.position - fac_offset

    # ACID - Service Access Control

    writer.align(0x10)
    sac_offset = writer.position
    
    sac_writer = BinaryWriter()
    service_host = json_read_list(contents, "service_host")
    service_access = json_read_list(contents, "service_access")
    for service in service_host:
        if not isinstance(service, str):
            print(f"error: `service_host` elements must be strings", file=sys.stderr)
            sys.exit(1)
    
        


    writer.seek(sac_offset)
    writer.write_sub(sac_writer)


    writer.seek(acid_offset + 0x220)
    writer.write_u32(fac_offset - acid_offset)
    writer.write_u32(fac_size)
    # writer.write_u32(sac_offset - acid_offset)
    # writer.write_u32(sac_size)
    # writer.write_u32(kc_offset)
    # writer.write_u32(kc_size)

    # ACI0 section


    # writer.seek(0x70)
    # writer.write_u32(aci_offset)
    # writer.write_u32(aci_size)
    # writer.write_u32(acid_offset)
    # writer.write_u32(acid_size)

    # writer.seek(acid_offset + 0x204)
    # writer.write_u32(acid_size)

    writer.save(args.outfile)

if __name__ == "__main__":
    main()

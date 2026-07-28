"""Deterministic writer for uncompressed Sims 4 DBPF v2.1 packages."""

import struct
from typing import Iterable, NamedTuple

from util.datamining.package_reader import DBPF_HEADER_SIZE, DBPF_MAGIC


class PackageResource(NamedTuple):
    type_id: int
    group: int
    instance: int
    data: bytes


def _resource_key(resource):
    return resource.type_id, resource.group, resource.instance


def build_package(resources):
    # type: (Iterable[PackageResource]) -> bytes
    """Build an uncompressed DBPF package from uniquely keyed resources."""
    ordered = sorted(resources, key=_resource_key)
    seen = set()
    for resource in ordered:
        key = _resource_key(resource)
        if key in seen:
            raise ValueError(
                "Duplicate resource key: {:08X}!{:08X}!{:016X}".format(*key)
            )
        seen.add(key)

    data_blocks = []
    entries = []
    offset = DBPF_HEADER_SIZE
    for resource in ordered:
        data = bytes(resource.data)
        entries.append((resource, offset, len(data)))
        data_blocks.append(data)
        offset += len(data)

    index_offset = offset
    index_parts = [struct.pack("<I", 0)]
    for resource, data_offset, size in entries:
        instance_hi = (resource.instance >> 32) & 0xFFFFFFFF
        instance_lo = resource.instance & 0xFFFFFFFF
        index_parts.append(
            struct.pack(
                "<IIIIIIII",
                resource.type_id,
                resource.group,
                instance_hi,
                instance_lo,
                data_offset,
                size,
                size,
                0,
            )
        )
    index_data = b"".join(index_parts)

    header = bytearray(DBPF_HEADER_SIZE)
    header[0:4] = DBPF_MAGIC
    struct.pack_into("<I", header, 4, 2)
    struct.pack_into("<I", header, 8, 1)
    struct.pack_into("<I", header, 36, len(entries))
    struct.pack_into("<I", header, 44, len(index_data))
    struct.pack_into("<I", header, 60, 3)
    struct.pack_into("<I", header, 64, index_offset & 0xFFFFFFFF)
    struct.pack_into("<I", header, 68, (index_offset >> 32) & 0xFFFFFFFF)

    return bytes(header) + b"".join(data_blocks) + index_data

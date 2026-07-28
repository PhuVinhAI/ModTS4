import struct

import pytest

from util.datamining.package_reader import PackageReader
from util.datamining.package_writer import PackageResource, build_package


def test_build_package_round_trips_uncompressed_resources(tmp_path):
    resources = [
        PackageResource(0xE882D22F, 0, 0x123456789ABCDEF0, b"<I />"),
        PackageResource(0x220557DA, 0x80000000, 0xAABBCCDD, b"STBL data"),
    ]

    package_data = build_package(resources)
    package_path = tmp_path / "anime.package"
    package_path.write_bytes(package_data)

    reader = PackageReader(str(package_path))
    reader.read()

    assert reader.header.major_version == 2
    assert reader.header.minor_version == 1
    assert reader.header.index_size == 4 + 32 * 2
    assert len(reader.entries) == 2
    extracted = {
        (entry.key.type_id, entry.key.group, entry.key.instance):
        reader.extract_resource(entry)
        for entry in reader.entries
    }
    assert extracted == {
        (0xE882D22F, 0, 0x123456789ABCDEF0): b"<I />",
        (0x220557DA, 0x80000000, 0xAABBCCDD): b"STBL data",
    }
    assert struct.unpack_from("<I", package_data, 44)[0] == 4 + 32 * 2
    assert struct.unpack_from("<I", package_data, 60)[0] == 3


def test_build_package_is_deterministic():
    resources = [
        PackageResource(2, 3, 4, b"second"),
        PackageResource(1, 3, 4, b"first"),
    ]

    assert build_package(resources) == build_package(list(reversed(resources)))


def test_build_package_rejects_duplicate_keys():
    resources = [
        PackageResource(1, 2, 3, b"first"),
        PackageResource(1, 2, 3, b"second"),
    ]

    with pytest.raises(ValueError, match="Duplicate resource key"):
        build_package(resources)

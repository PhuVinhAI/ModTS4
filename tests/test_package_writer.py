import pytest

from util.datamining.package_reader import PackageReader
from util.datamining.package_writer import (
    LLAMALOGIC_PACKAGES_VERSION,
    PackageResource,
    build_package,
    encode_string_table,
    package_tool_version,
    validate_package,
    write_package,
)
from util.datamining.string_table import StringTableReader


def test_build_package_round_trips_uncompressed_resources(tmp_path):
    resources = [
        PackageResource(0xE882D22F, 0, 0x123456789ABCDEF0, b"<I />"),
        PackageResource(0x220557DA, 0x80000000, 0xAABBCCDD, b"STBL data"),
    ]

    package_path = tmp_path / "anime.package"
    write_package(resources, str(package_path))
    package_data = package_path.read_bytes()

    reader = PackageReader(str(package_path))
    reader.read()

    assert reader.header.major_version == 2
    assert reader.header.minor_version == 1
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
    assert package_data.startswith(b"DBPF")


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


def test_write_package_rejects_duplicate_keys_without_writing(tmp_path):
    output_path = tmp_path / "duplicate.package"
    resources = [
        PackageResource(1, 2, 3, b"first"),
        PackageResource(1, 2, 3, b"second"),
    ]

    with pytest.raises(ValueError, match="Duplicate resource key"):
        write_package(resources, str(output_path))

    assert not output_path.exists()


def test_package_tool_uses_pinned_llamalogic_version():
    assert LLAMALOGIC_PACKAGES_VERSION == "3.8.2"
    assert package_tool_version() == LLAMALOGIC_PACKAGES_VERSION


def test_encode_string_table_uses_llamalogic_model():
    strings = {0x12345678: "Xem Anime", 0xABCDEF01: "Tiếng Việt"}

    data = encode_string_table(strings)
    table = StringTableReader.parse(data)

    assert table.strings == strings
    expected_length = sum(len(value.encode("utf-8")) + 1 for value in strings.values())
    assert int.from_bytes(data[17:21], "little") == expected_length


def test_validate_package_rejects_mismatched_tuning_instance(tmp_path):
    package_path = tmp_path / "invalid.package"
    write_package(
        [PackageResource(0xE882D22F, 0, 123, b'<I s="456" />')],
        str(package_path),
    )

    with pytest.raises(RuntimeError, match="mismatched XML instance"):
        validate_package(str(package_path))

"""Build the tuning and localization package for the Xem Anime interaction."""

import os
import struct
import xml.etree.ElementTree as ET

from src.anime_tv.constants import (
    ANIME_INTERACTION_ID,
    BASE_TUNING_NAME,
    BASE_WATCH_INTERACTION_ID,
    DISPLAY_NAME_KEY,
    DISPLAY_TOOLTIP_KEY,
    STBL_INSTANCE_ID,
    TUNING_NAME,
)
from util.datamining.package_reader import PackageReader
from util.datamining.package_writer import PackageResource, write_package
from util.datamining.resource_types import STRING_TABLE_TYPE_ID
from util.datamining.tuning_splitter import split_combined_tuning


INTERACTION_RESOURCE_TYPE_ID = 0xE882D22F
TUNING_GROUP = 0x00000000
STBL_GROUP = 0x80000000

LOCALE_IDS = (
    0x00,
    0x01,
    0x02,
    0x03,
    0x04,
    0x05,
    0x06,
    0x07,
    0x08,
    0x0B,
    0x0C,
    0x0D,
    0x0E,
    0x0F,
    0x11,
    0x12,
    0x13,
    0x15,
)

LOCALIZED_STRINGS = {
    DISPLAY_NAME_KEY: "Xem Anime",
    DISPLAY_TOOLTIP_KEY: "Thư giãn với một tập anime đầy màu sắc.",
}


def _fnv1a(value, bits, offset_basis, prime):
    result = offset_basis
    mask = (1 << bits) - 1
    for byte in value.encode("utf-8"):
        result = ((result ^ byte) * prime) & mask
    return result


def fnv1a_32(value):
    return _fnv1a(value, 32, 2166136261, 16777619)


def fnv1a_64(value):
    return _fnv1a(value, 64, 14695981039346656037, 1099511628211)


def build_stbl(strings):
    """Encode a key-to-string mapping as an uncompressed version 5 STBL."""
    encoded = [
        (key, value.encode("utf-8")) for key, value in sorted(strings.items())
    ]
    string_data_length = sum(len(value) for _, value in encoded)
    header = b"STBL"
    header += struct.pack("<H", 5)
    header += struct.pack("<B", 0)
    header += struct.pack("<Q", len(encoded))
    header += struct.pack("<H", 0)
    header += struct.pack("<I", string_data_length)

    entries = []
    for key, value in encoded:
        if len(value) > 0xFFFF:
            raise ValueError("STBL string is too long for key 0x{:08X}".format(key))
        entries.append(struct.pack("<IBH", key, 0, len(value)) + value)
    return header + b"".join(entries)


def _find_named_element(root, name):
    for element in root.iter():
        if element.get("n") == name:
            return element
    raise ValueError("Base tuning has no '{}' field".format(name))


def customize_watch_tuning(base_xml):
    """Turn the base kids-channel tuning into the custom anime interaction."""
    if isinstance(base_xml, bytes):
        root = ET.fromstring(base_xml)
    else:
        root = ET.fromstring(base_xml.encode("utf-8"))

    for element in root.iter():
        element.attrib.pop("x", None)

    root.set("n", TUNING_NAME)
    root.set("s", str(ANIME_INTERACTION_ID))
    _find_named_element(root, "allow_autonomous").text = "False"
    _find_named_element(root, "display_name").text = "0x{:08X}".format(
        DISPLAY_NAME_KEY
    )

    tooltip = _find_named_element(root, "display_tooltip")
    tooltip_value = _find_named_element(tooltip, "enabled")
    tooltip_value.text = "0x{:08X}".format(DISPLAY_TOOLTIP_KEY)

    disallow = _find_named_element(root, "test_disallow_while_running")
    affordance_list = _find_named_element(disallow, "affordances")
    blocked_ids = {
        int(element.text)
        for element in affordance_list.findall("T")
        if element.text
    }
    if BASE_WATCH_INTERACTION_ID not in blocked_ids:
        ET.SubElement(affordance_list, "T").text = str(BASE_WATCH_INTERACTION_ID)
    if ANIME_INTERACTION_ID not in blocked_ids:
        ET.SubElement(affordance_list, "T").text = str(ANIME_INTERACTION_ID)

    body = ET.tostring(root, encoding="utf-8")
    return b'<?xml version="1.0" encoding="utf-8"?>\n' + body


def load_base_watch_tuning(game_folder):
    package_path = os.path.join(
        game_folder, "Data", "Simulation", "SimulationFullBuild0.package"
    )
    reader = PackageReader(package_path)
    reader.read()
    combined_entries = reader.extract_combined_tuning_entries()
    if not combined_entries:
        raise ValueError("Base game package contains no CombinedTuning resource")

    for combined_entry in combined_entries:
        data = reader.extract_resource(combined_entry)
        for tuning in split_combined_tuning(data):
            if tuning.name == BASE_TUNING_NAME:
                return tuning.xml.encode("utf-8")
    raise ValueError("Could not find base tuning '{}'".format(BASE_TUNING_NAME))


def build_anime_package(game_folder, output_path):
    """Build and write the complete Anime TV tuning package."""
    tuning_data = customize_watch_tuning(load_base_watch_tuning(game_folder))
    stbl_data = build_stbl(LOCALIZED_STRINGS)
    resources = [
        PackageResource(
            INTERACTION_RESOURCE_TYPE_ID,
            TUNING_GROUP,
            ANIME_INTERACTION_ID,
            tuning_data,
        )
    ]
    for locale_id in LOCALE_IDS:
        instance_id = (locale_id << 56) | STBL_INSTANCE_ID
        resources.append(
            PackageResource(
                STRING_TABLE_TYPE_ID,
                STBL_GROUP,
                instance_id,
                stbl_data,
            )
        )

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    return write_package(resources, output_path)

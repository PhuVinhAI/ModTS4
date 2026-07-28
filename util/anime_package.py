"""Build the tuning and localization package for the Xem Anime interaction."""

import os
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
from util.datamining.package_writer import (
    PackageResource,
    encode_string_table,
    write_package,
)
from util.datamining.resource_types import STRING_TABLE_TYPE_ID
from util.datamining.tuning_splitter import find_combined_tuning_by_name


INTERACTION_RESOURCE_TYPE_ID = 0xE882D22F
TUNING_GROUP = 0x00000000
STBL_GROUP = 0x80000000
SIMULATION_TUNING_PACKAGES = (
    "SimulationDeltaBuild0.package",
    "SimulationFullBuild0.package",
)

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
    """Encode strings with LlamaLogic's authoritative STBL model."""
    return encode_string_table(strings)


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

    if root.get("n") != BASE_TUNING_NAME:
        raise ValueError("Unexpected base tuning: {}".format(root.get("n")))
    if root.get("s") != str(BASE_WATCH_INTERACTION_ID):
        raise ValueError("Unexpected base tuning ID: {}".format(root.get("s")))

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
    """Load the effective game tuning, preferring patch overrides in Delta."""
    simulation_folder = os.path.join(game_folder, "Data", "Simulation")
    searched = []
    for package_name in SIMULATION_TUNING_PACKAGES:
        package_path = os.path.join(simulation_folder, package_name)
        if not os.path.isfile(package_path):
            continue
        searched.append(package_path)
        reader = PackageReader(package_path)
        reader.read()
        for combined_entry in reader.extract_combined_tuning_entries():
            data = reader.extract_resource(combined_entry)
            tuning = find_combined_tuning_by_name(data, BASE_TUNING_NAME)
            if tuning is not None:
                return tuning.xml.encode("utf-8")
    raise ValueError(
        "Could not find base tuning '{}' in {}".format(
            BASE_TUNING_NAME, ", ".join(searched) or simulation_folder
        )
    )


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

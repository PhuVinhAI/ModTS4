import xml.etree.ElementTree as ET

import util.anime_package as anime_package
from src.anime_tv.constants import (
    ANIME_INTERACTION_ID,
    BASE_WATCH_INTERACTION_ID,
    DISPLAY_NAME_KEY,
    DISPLAY_TOOLTIP_KEY,
    STBL_INSTANCE_ID,
    TUNING_NAME,
)
from util.anime_package import build_stbl, customize_watch_tuning, fnv1a_32, fnv1a_64
from util.datamining.string_table import StringTableReader
from util.datamining.package_reader import PackageReader


BASE_TUNING = b"""\
<I c="WatchSuperInteraction" i="interaction" m="objects.electronics.television"
   n="tv_WatchKids" s="9110">
  <T n="allow_autonomous" x="57">True</T>
  <T n="display_name">0x11111111</T>
  <V n="display_tooltip" t="enabled"><T n="enabled">0x22222222</T></V>
  <T n="required_channel">9101</T>
  <V n="test_disallow_while_running" t="enabled">
    <U n="enabled"><L n="affordances"><T>9110</T></L></U>
  </V>
</I>
"""


def _text_for_name(root, name):
    return next(element.text for element in root.iter() if element.get("n") == name)


def test_fnv_hashes_match_standard_vectors():
    assert fnv1a_32("hello") == 0x4F9F2CAB
    assert fnv1a_64("hello") == 0xA430D84680AABD0B
    assert fnv1a_32("tomis_AnimeTV_STBL") == STBL_INSTANCE_ID
    assert fnv1a_64(TUNING_NAME) == ANIME_INTERACTION_ID


def test_customize_watch_tuning_changes_identity_and_strings():
    result = customize_watch_tuning(BASE_TUNING)
    root = ET.fromstring(result)

    assert root.get("n") == TUNING_NAME
    assert root.get("s") == str(ANIME_INTERACTION_ID)
    assert _text_for_name(root, "allow_autonomous") == "False"
    assert _text_for_name(root, "display_name") == "0x{:08X}".format(DISPLAY_NAME_KEY)
    assert _text_for_name(root, "enabled") == "0x{:08X}".format(DISPLAY_TOOLTIP_KEY)
    assert _text_for_name(root, "required_channel") == "9101"
    assert all("x" not in element.attrib for element in root.iter())

    blocked = next(
        element for element in root.iter("L") if element.get("n") == "affordances"
    )
    blocked_ids = [int(element.text) for element in blocked.findall("T")]
    assert BASE_WATCH_INTERACTION_ID in blocked_ids
    assert ANIME_INTERACTION_ID in blocked_ids


def test_build_stbl_preserves_vietnamese_strings():
    data = build_stbl(
        {
            DISPLAY_NAME_KEY: "Xem Anime",
            DISPLAY_TOOLTIP_KEY: "Thư giãn với một tập anime.",
        }
    )

    table = StringTableReader.parse(data)

    assert table.version == 5
    assert table[DISPLAY_NAME_KEY] == "Xem Anime"
    assert table[DISPLAY_TOOLTIP_KEY] == "Thư giãn với một tập anime."


def test_build_anime_package_contains_tuning_and_all_locales(tmp_path, monkeypatch):
    monkeypatch.setattr(anime_package, "load_base_watch_tuning", lambda _: BASE_TUNING)
    output_path = tmp_path / "tomis_AnimeTV.package"

    anime_package.build_anime_package("unused", str(output_path))

    reader = PackageReader(str(output_path))
    reader.read()
    tuning_entries = [
        entry
        for entry in reader.entries
        if entry.key.type_id == anime_package.INTERACTION_RESOURCE_TYPE_ID
    ]
    stbl_entries = reader.extract_string_table_entries(None)
    assert len(tuning_entries) == 1
    assert tuning_entries[0].key.instance == ANIME_INTERACTION_ID
    assert len(stbl_entries) == len(anime_package.LOCALE_IDS)

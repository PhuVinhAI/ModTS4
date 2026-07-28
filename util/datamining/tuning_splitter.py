"""
Split CombinedTuning XML into individual standalone tuning files.

Resolves all <r x="..."> references inline so each output entry is
self-contained (no dependency on the shared <g> table).
"""

import copy
import xml.etree.ElementTree as ET
from typing import Dict, List, NamedTuple, Optional

from util.datamining.binary_tuning import decode_combined_tuning, is_binary_combined_tuning


class SplitEntry(NamedTuple):
    """A single tuning entry split from CombinedTuning."""
    cls: str            # class name (c attribute), e.g. "Skill"
    name: str           # instance name (n attribute), e.g. "skill_Cooking"
    instance_id: str    # instance ID (s attribute), e.g. "16700"
    module: str         # module path (m attribute), e.g. "statistics.skill"
    element_tag: str    # "I" for instance tuning, "M" for module tuning
    xml: str            # standalone XML string


def _build_ref_table(root):
    # type: (ET.Element) -> Dict[str, ET.Element]
    """Build reference table from <g> element."""
    table = {}  # type: Dict[str, ET.Element]
    g = root.find("g")
    if g is not None:
        for child in g:
            x = child.get("x")
            if x is not None:
                table[x] = child
    return table


def _resolve_refs_inplace(element, ref_table):
    # type: (ET.Element, Dict[str, ET.Element]) -> None
    """Recursively replace <r> references with resolved content in-place.

    For each <r x="..."> element found:
    - Look up x in the ref table
    - Deep-copy the resolved element
    - Preserve the n attribute from the <r> (field name binding)
    - Replace the <r> with the resolved copy in the parent
    """
    children = list(element)
    for i, child in enumerate(children):
        if child.tag == "r":
            x = child.get("x")
            if x is not None and x in ref_table:
                resolved = copy.deepcopy(ref_table[x])
                # Preserve the field name from the reference
                n = child.get("n")
                if n is not None:
                    resolved.set("n", n)
                element[i] = resolved
                # Recurse into the resolved element (it may contain refs too)
                _resolve_refs_inplace(resolved, ref_table)
        else:
            _resolve_refs_inplace(child, ref_table)


def _element_to_xml(element):
    # type: (ET.Element) -> str
    """Serialize an element to an XML string with declaration."""
    return ET.tostring(element, encoding="unicode")


def _decode_root(data):
    # type: (bytes) -> ET.Element
    if is_binary_combined_tuning(data):
        xml_str = decode_combined_tuning(data)
    else:
        xml_str = data.decode("utf-8")
    return ET.fromstring(xml_str)


def _split_entry(element, ref_table):
    # type: (ET.Element, Dict[str, ET.Element]) -> SplitEntry
    entry_element = copy.deepcopy(element)
    _resolve_refs_inplace(entry_element, ref_table)
    return SplitEntry(
        cls=element.get("c", ""),
        name=element.get("n", ""),
        instance_id=element.get("s", "0"),
        module=element.get("m", element.get("n", "")),
        element_tag=element.tag,
        xml=_element_to_xml(entry_element),
    )


def find_combined_tuning_by_name(data, name):
    # type: (bytes, str) -> Optional[SplitEntry]
    """Return one resolved tuning without copying every entry in the package."""
    root = _decode_root(data)
    ref_table = _build_ref_table(root)
    for element in root.iter():
        if element.tag not in ("I", "M"):
            continue
        if element.get("n") != name or element.get("s") is None:
            continue
        if element.tag == "I" and element.get("c") is None:
            continue
        return _split_entry(element, ref_table)
    return None


def split_combined_tuning(data):
    # type: (bytes) -> List[SplitEntry]
    """Split a CombinedTuning resource into individual standalone entries.

    Args:
        data: Raw (decompressed) CombinedTuning resource bytes.

    Returns:
        List of SplitEntry, each with resolved XML.
    """
    root = _decode_root(data)
    ref_table = _build_ref_table(root)

    entries = []  # type: List[SplitEntry]

    # Process <I> elements (instance tuning: Skills, Careers, Traits, etc.)
    for el in root.iter("I"):
        cls = el.get("c")
        if cls is None:
            continue  # skip <I> without class (not a tuning entry)

        entries.append(_split_entry(el, ref_table))

    # Process <M> elements (module tuning: collection_manager, etc.)
    for el in root.iter("M"):
        module = el.get("n", "")
        # Skip the root <M> that wraps everything in simple format
        if el is root:
            continue
        # Skip <M> without meaningful content
        if not module or el.get("s") is None:
            continue

        entries.append(_split_entry(el, ref_table))

    return entries

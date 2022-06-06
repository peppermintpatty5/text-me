"""
This module contains unit tests.
"""

import unittest
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from src import convert


def xml_equal(elem_a: Element, elem_b: Element) -> bool:
    """
    Recursively checks two elements for equality. Treats texts that are missing or
    entirely whitespace as empty strings.
    """

    str_norm = lambda s: "" if s is None or s.isspace() else s

    return (
        elem_a.tag == elem_b.tag
        and str_norm(elem_a.text) == str_norm(elem_b.text)
        and str_norm(elem_a.tail) == str_norm(elem_b.tail)
        and elem_a.attrib == elem_b.attrib
        and len(elem_a) == len(elem_b)
        and all(xml_equal(u, v) for u, v in zip(elem_a, elem_b))
    )


class TestMe(unittest.TestCase):
    """
    Unit test
    """

    def test_all_conversions(self):
        """
        Test conversions between all formats
        """
        test_files = {
            "Android": "test/static/android.xml",
            "Windows 10": "test/static/win10.msg",
        }
        from_ = {
            "Android": convert.from_android,
            "Windows 10": convert.from_win10,
        }
        to_ = {
            "Android": convert.to_android,
            "Windows 10": convert.to_win10,
        }
        ingest = {}

        for fmt, filename in test_files.items():
            with open(filename, "r") as file:
                ingest[fmt] = ET.parse(file).getroot()

        for src_fmt, src in ingest.items():
            i = from_[src_fmt](src)  # intermediary message format

            for dst_fmt, dst in ingest.items():
                converted = to_[dst_fmt](i, you="Obi-wan Kenobi")

                with self.subTest(src_fmt=src_fmt, dst_fmt=dst_fmt):
                    self.assertTrue(xml_equal(dst, converted))

#!/usr/bin/env python3

import sys
import textme
import unittest
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, ElementTree


def xml_equal(x: Element, y: Element) -> bool:
    """
    Recursively checks two elements for equality. Treats texts that are missing
    or entirely whitespace as empty strings.
    """

    f = lambda s: "" if s is None or s.isspace() else s

    return (
        x.tag == y.tag
        and f(x.text) == f(y.text)
        and f(x.tail) == f(y.tail)
        and x.attrib == y.attrib
        and len(x) == len(y)
        and all(xml_equal(u, v) for u, v in zip(x, y))
    )


class TestMe(unittest.TestCase):
    def test_all_conversions(self):
        test_files = {
            "Android": "test/android.xml",
            "Windows 10": "test/win10.msg",
        }
        from_ = {
            "Android": textme.from_android,
            "Windows 10": textme.from_win10,
        }
        to_ = {
            "Android": textme.to_android,
            "Windows 10": textme.to_win10,
        }
        F = {}

        for fmt, file in test_files.items():
            with open(file, "r") as fp:
                F[fmt] = ET.parse(fp).getroot()

        for src_fmt, src in F.items():
            i = from_[src_fmt](src)  # intermediary message format

            for dst_fmt, dst in F.items():
                converted = to_[dst_fmt](i, you="Obi-wan Kenobi")

                with self.subTest(src_fmt=src_fmt, dst_fmt=dst_fmt):
                    self.assertTrue(xml_equal(dst, converted))


if __name__ == "__main__":
    unittest.main()

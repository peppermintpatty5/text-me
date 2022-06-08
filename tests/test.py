"""
This module contains unit tests.
"""

import io
import json
import os
import unittest
from typing import Any

from src.convert import Android, Message, Platform, Windows10


class TestPlatforms(unittest.TestCase):
    """
    Test all platforms.
    """

    def setUp(self) -> None:
        static = os.path.join(os.path.dirname(__file__), "static")

        self.platforms: list[Platform] = [Android, Windows10]
        self.test_files: dict[Platform, str] = {
            Android: os.path.join(static, "android.xml"),
            Windows10: os.path.join(static, "win10.msg"),
        }
        self.write_kwargs: dict[Platform, dict[str, Any]] = {
            Android: {"you": "Obi-wan Kenobi"},
            Windows10: {},
        }

        # load messages
        with open(os.path.join(static, "int.json"), "r", encoding="Utf8") as file:
            self.messages = [Message(**obj) for obj in json.load(file)]

        # output control
        self.maxDiff = None  # pylint: disable=invalid-name

    def test_read_write(self):
        """
        Test read and write methods.
        """
        for platform in self.platforms:
            with self.subTest(platform=platform.__name__):
                with open(self.test_files[platform], "r", encoding="utf8") as file_in:
                    messages = platform.read(file_in)

                    file_in.seek(0)
                    expected_output = file_in.read()

                self.assertListEqual(messages, self.messages)

                with io.StringIO() as file_out:
                    platform.write(file_out, messages, **self.write_kwargs[platform])
                    self.assertMultiLineEqual(file_out.getvalue(), expected_output)

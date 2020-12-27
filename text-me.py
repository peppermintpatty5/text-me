#!/usr/bin/env python3

import argparse
import base64
import json
import mimetypes
import os.path
import sys
import time
from xml.etree import ElementTree
from xml.etree.ElementTree import Element


def from_json(fp) -> list:
    """
    Universal format
    """

    return json.load(fp)


def from_win10(fp) -> list:
    """
    Gets a list of messages converted from Windows format.
    """

    def get_timestamp(msg: Element) -> int:
        x = msg.find("LocalTimestamp").text
        return int(x) // (10 ** 7) - 11644473600

    def get_timestamp_ns(msg: Element) -> int:
        x = msg.find("LocalTimestamp").text
        return int(x) * 100 % (10 ** 9)

    def get_recipients(msg: Element) -> list:
        return [x.text for x in msg.find("Recepients").findall("string")]

    def get_attachments(msg: Element) -> list:
        return [
            {
                "content_type": x.find("AttachmentContentType").text,
                "data_base64": x.find("AttachmentDataBase64String").text,
            }
            for x in msg.find("Attachments").findall("MessageAttachment")
        ]

    root = ElementTree.parse(fp).getroot()

    return [
        {
            "timestamp": get_timestamp(msg),
            # "timestamp_ns": get_timestamp_ns(msg),
            "sender": msg.find("Sender").text,
            "recipients": get_recipients(msg),
            "body": msg.find("Body").text,
            "is_read": msg.find("IsRead").text == "true",
            "attachments": get_attachments(msg),
        }
        for msg in root.findall("Message")
    ]


def get_args():
    """
    Argument parser object for main
    """

    parser = argparse.ArgumentParser(
        description="An SMS/MMS translator between Android and Windows 10 Mobile"
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        metavar="FILE",
        help="list of input files to convert from, otherwise will read from stdin",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["win10"],
        help="format of ALL input files, omit to use universal JSON",
    )

    return parser.parse_args()


def main():
    args = get_args()

    convert_func = {"win10": from_win10, None: from_json}[args.format]

    messages = []
    if args.input is not None:
        for file in args.input:
            with open(file, "r") as fp:
                messages += convert_func(fp)
    else:
        messages += convert_func(sys.stdin)

    messages = sorted(messages, key=lambda msg: msg["timestamp"])
    json.dump(messages, sys.stdout, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()

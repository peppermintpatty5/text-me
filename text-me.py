#!/usr/bin/env python3

import argparse
import base64
import json
import mimetypes
import os.path
import sys
import time
from enum import Enum
from xml.etree import ElementTree
from xml.etree.ElementTree import Element


def from_json(fp) -> list:
    """
    Universal format
    """

    return json.load(fp)


def from_android(fp) -> list:
    class MessageType(Enum):
        RECEIVED = 1
        SENT = 2
        DRAFT = 3
        OUTBOX = 4
        FAILED = 5
        QUEUED = 6

    messages = []
    root = ElementTree.parse(fp).getroot()

    for elem in root:
        msg = {}
        if elem.tag == "sms":
            msg["timestamp"] = int(elem.attrib["date"]) // 1000

            address = elem.attrib["address"]
            if int(elem.attrib["type"]) == MessageType.RECEIVED.value:
                msg["sender"] = address
                msg["recipients"] = []
            elif int(elem.attrib["type"]) == MessageType.SENT.value:
                msg["sender"] = None
                msg["recipients"] = [address]

            msg["body"] = elem.attrib["body"]
            msg["is_read"] = elem.attrib["read"] == "1"
            msg["attachments"] = []
        elif elem.tag == "mms":
            msg["timestamp"] = int(elem.attrib["date"]) // 1000
            continue
        else:
            raise ValueError(f"Unrecognized tag '{elem.tag}'")
        messages.append(msg)

    return messages


def to_android(messages: list, your_phone: str) -> Element:
    """
    Convert list of messages to XML.
    """

    class MessageType(Enum):
        RECEIVED = 1
        SENT = 2
        DRAFT = 3
        OUTBOX = 4
        FAILED = 5
        QUEUED = 6

    class AddressType(Enum):
        BCC = 129
        CC = 130
        TO = 151
        FROM = 137

    smses = Element("smses")
    for message in messages:
        sender = message["sender"]  # if sender is None, you were the sender
        timestamp_ms = message["timestamp"] * 1000 + message["timestamp_ns"] // 1000000

        if len(message["attachments"]) > 0:
            mms = Element(
                "mms",
                {
                    # Extra bloat attributes that Android needs
                    "m_type": "132" if sender is not None else "128",
                    "msg_box": "1" if sender is not None else "2",
                },
            )
            mms.attrib["date"] = str(timestamp_ms)
            mms.attrib["address"] = "~".join(
                sorted(
                    (set(message["recipients"]) | {sender or your_phone}) - {your_phone}
                )
            )
            mms.attrib["read"] = "1" if message["is_read"] else "0"

            parts = Element("parts")
            for i, attachment in enumerate(message["attachments"]):
                content_type = attachment["content_type"]
                data_base64 = attachment["data_base64"]

                part = Element("part", {"chset": "106"})
                part.attrib["ct"] = content_type

                if content_type in {"text/plain", "application/smil"}:
                    part.attrib["text"] = base64.b64decode(data_base64).decode("utf_8")
                else:
                    part.attrib["data"] = data_base64

                parts.append(part)

            addrs = Element("addrs")
            addrs.append(
                Element(
                    "addr",
                    {
                        "chset": "106",
                        "address": sender or your_phone,
                        "type": str(AddressType.FROM.value),
                    },
                )
            )
            for recipient in message["recipients"]:
                addrs.append(
                    Element(
                        "addr",
                        {
                            "chset": "106",
                            "address": recipient,
                            "type": str(AddressType.TO.value),
                        },
                    )
                )

            mms.append(parts)
            mms.append(addrs)
            smses.append(mms)
        else:
            sms = Element("sms")
            sms.attrib["date"] = str(timestamp_ms)
            sms.attrib["address"] = message["sender"] or message["recipients"][0]
            sms.attrib["type"] = str(
                MessageType.RECEIVED.value
                if message["sender"] is not None
                else MessageType.SENT.value
            )
            sms.attrib["body"] = message["body"] or ""
            sms.attrib["read"] = "1" if message["is_read"] else "0"

            smses.append(sms)

    smses.attrib["count"] = str(len(smses))
    return smses


def from_win10(fp) -> list:
    """
    Gets a list of messages converted from Windows format.
    """

    def get_attachments(msg: Element) -> list:
        attachments = []
        for x in msg.find("Attachments").findall("MessageAttachment"):
            content_type = x.find("AttachmentContentType").text
            data_base64 = x.find("AttachmentDataBase64String").text

            # Some content types are encoded in UTF-16 LE on Windows Phone
            if content_type in {"text/plain", "application/smil"}:
                data_base64 = base64.b64encode(
                    base64.b64decode(data_base64).decode("utf_16_le").encode("utf_8")
                ).decode("utf_8")

            attachments.append(
                {"content_type": content_type, "data_base64": data_base64}
            )
        return attachments

    return [
        {
            "timestamp": int(msg.find("LocalTimestamp").text) // (10 ** 7)
            - 11644473600,
            "timestamp_ns": int(msg.find("LocalTimestamp").text) * 100 % (10 ** 9),
            "sender": msg.find("Sender").text,
            "recipients": [x.text for x in msg.find("Recepients").findall("string")],
            "body": msg.find("Body").text,
            "is_read": msg.find("IsRead").text == "true",
            "attachments": get_attachments(msg),
        }
        for msg in ElementTree.parse(fp).getroot().findall("Message")
    ]


def get_args():
    """
    Argument parser object for main
    """

    parser = argparse.ArgumentParser(
        description="An SMS/MMS translator between Android and Windows 10 Mobile"
    )
    parser.add_argument(
        "phone",
        help="your phone number (please see FAQ in README.md)",
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
        choices=["android", "win10"],
        help="format of ALL input files, omit to use universal JSON",
    )

    return parser.parse_args()


def main():
    args = get_args()

    convert_func = {
        "android": from_android,
        "win10": from_win10,
        None: from_json,
    }[args.format]

    messages = []
    if args.input is not None:
        for file in args.input:
            with open(file, "r") as fp:
                messages += convert_func(fp)
    else:
        messages += convert_func(sys.stdin)

    messages.sort(key=lambda msg: (msg["timestamp"], msg["timestamp_ns"]))
    # json.dump(messages, sys.stdout, ensure_ascii=False, indent=4)
    ElementTree.dump(to_android(messages, args.phone))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import argparse
import base64
import json
import sys
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, ElementTree


def from_android(root: Element) -> list:
    """
    Extract a list of messages from XML in the Android SMS/MMS backup format.
    """

    RECEIVED = "1"
    SENT = "2"
    TO = "151"
    FROM = "137"
    UTF_8 = "106"

    messages = []
    for elem in root.iterfind("*"):
        message = {
            "timestamp": int(elem.get("date")) // 1000,
            "timestamp_ns": int(elem.get("date")) % 1000 * (10 ** 6),
        }
        if elem.tag == "sms":
            address = elem.get("address")
            if elem.get("type") == RECEIVED:
                message["sender"] = address
                message["recipients"] = []
            elif elem.get("type") == SENT:
                message["sender"] = None
                message["recipients"] = [address]

            message["body"] = elem.get("body")
            message["is_read"] = elem.get("read") == "1"
            message["attachments"] = []
        elif elem.tag == "mms":
            message["sender"] = None
            message["recipients"] = []
            for addr in elem.iterfind("addrs/addr"):
                address = addr.get("address")
                if addr.get("type") == FROM:
                    if elem.get("msg_box") == RECEIVED:
                        message["sender"] = address
                elif addr.get("type") == TO:
                    message["recipients"].append(address)
                else:
                    raise ValueError(f"Unknown addr type '{addr.get('type')}'")

            message["body"] = None
            message["is_read"] = elem.get("read") == "1"

            attachments = []
            for part in elem.iterfind("parts/part"):
                attachment = {"content_type": part.get("ct")}
                data = part.get("data", default=None)
                if data is not None:
                    attachment["data_base64"] = data
                else:
                    attachment["text"] = part.get("text")
                attachments.append(attachment)
            message["attachments"] = attachments

        messages.append(message)

    return messages


def from_win10(root: Element) -> list:
    """
    Extract a list of messages from XML in the Windows 10 Mobile SMS/MMS backup
    format.
    """

    def get_attachments(msg: Element) -> list:
        attachments = []
        for x in msg.iterfind("Attachments/MessageAttachment"):
            attachment = {}
            content_type = x.find("AttachmentContentType").text
            data_base64 = x.find("AttachmentDataBase64String").text

            attachment["content_type"] = content_type

            # these formats are further encoded in UTF-16 LE
            if content_type in {"text/plain", "application/smil"}:
                attachment["text"] = base64.b64decode(data_base64).decode("utf_16_le")
            else:
                attachment["data_base64"] = data_base64

            attachments.append(attachment)

        return attachments

    return [
        {
            "timestamp": (
                int(msg.find("LocalTimestamp").text) // (10 ** 7) - 11644473600
            ),
            "timestamp_ns": int(msg.find("LocalTimestamp").text) % (10 ** 7) * 100,
            "sender": msg.find("Sender").text,
            "recipients": [x.text for x in msg.iterfind("Recepients/string")],
            "body": msg.find("Body").text,
            "is_read": msg.find("IsRead").text == "true",
            "attachments": get_attachments(msg),
        }
        for msg in root.iterfind("Message")
    ]


def to_android(messages: list, **kwargs) -> Element:
    """
    Convert a list of messages to XML in the Android SMS/MMS backup format.

    **MUST specify keyword argument `you`.** This argument should contain a
    phone number and is required by Android to identify your outgoing MMS
    messages. It has not been made a regular argument to keep the function
    signature consistent with the other `to_x` functions.
    """

    RECEIVED = "1"
    SENT = "2"
    TO = "151"
    FROM = "137"
    UTF_8 = "106"

    try:
        you = kwargs["you"]
    except KeyError as e:
        raise TypeError("missing required keyword argument 'you'") from None

    smses = Element("smses")
    for message in messages:
        sender = message["sender"]  # if sender is None, you were the sender
        timestamp_ms = message["timestamp"] * 1000 + message["timestamp_ns"] // 1000000

        if len(message["attachments"]) > 0:
            mms = Element("mms")
            mms.set("m_type", "132" if sender is not None else "128")
            mms.set("msg_box", RECEIVED if sender is not None else SENT)

            mms.set("date", str(timestamp_ms))
            mms.set(
                "address",
                "~".join(
                    sorted((set(message["recipients"]) | {sender or you}) - {you})
                ),
            )
            mms.set("read", "1" if message["is_read"] else "0")

            parts = Element("parts")
            for i, attachment in enumerate(message["attachments"]):  # TODO: seq attr?
                part = Element("part")
                part.set("chset", UTF_8)
                part.set("ct", attachment["content_type"])
                if "text" in attachment:
                    part.set("text", attachment["text"])
                else:
                    part.set("data", attachment["data_base64"])
                parts.append(part)
            mms.append(parts)

            addrs = Element("addrs")
            addrs.append(
                Element(
                    "addr",
                    {
                        "chset": UTF_8,
                        "address": sender or you,
                        "type": FROM,
                    },
                )
            )
            for recipient in message["recipients"]:
                addr = Element("addr")
                addr.set("chset", UTF_8)
                addr.set("address", recipient)
                addr.set("type", TO)
                addrs.append(addr)
            mms.append(addrs)

            smses.append(mms)
        else:
            sms = Element("sms")
            sms.set("date", str(timestamp_ms))
            sms.set("address", message["sender"] or message["recipients"][0])
            sms.set("type", RECEIVED if message["sender"] is not None else SENT)
            sms.set("body", message["body"] or "")
            sms.set("read", "1" if message["is_read"] else "0"),
            smses.append(sms)

    smses.set("count", str(len(smses)))

    return smses


def to_win10(messages: list, **kwargs) -> Element:
    """
    Convert a list of messages to XML in the Windows 10 Mobile SMS/MMS backup
    format.
    """

    def encode_text(text: str) -> str:
        """Two-step text encoding"""

        return base64.b64encode(text.encode("utf_16_le")).decode()

    def e(tag: str, text: str = None) -> Element:
        """Element constructor does not let you initialize the text"""

        elem = Element(tag)
        elem.text = text
        return elem

    e_array_of_message = e("ArrayOfMessage")
    for message in messages:
        e_message = e("Message")

        e_recepients = e("Recepients")
        for recipient in message["recipients"]:
            e_recepients.append(e("string", recipient))
        e_message.append(e_recepients)

        e_message.append(e("Body", message["body"] or ""))
        e_message.append(
            e("IsIncoming", "true" if message["sender"] is not None else "false")
        )
        e_message.append(e("IsRead", "true" if message["is_read"] else "false"))
        e_attachments = e("Attachments")
        for attachment in message["attachments"]:
            data_base64 = (
                attachment["data_base64"]
                if "data_base64" in attachment
                else encode_text(attachment["text"])
            )
            e_message_attachment = e("MessageAttachment")
            e_message_attachment.append(
                e("AttachmentContentType", attachment["content_type"])
            )
            e_message_attachment.append(e("AttachmentDataBase64String", data_base64))
            e_attachments.append(e_message_attachment)
        e_message.append(e_attachments)

        e_message.append(
            e(
                "LocalTimestamp",
                str(
                    (message["timestamp"] + 11644473600) * (10 ** 7)
                    + message["timestamp_ns"] // 100
                ),
            )
        )
        e_message.append(e("Sender", message["sender"] or ""))

        e_array_of_message.append(e_message)

    return e_array_of_message


def get_args():
    """
    Parse the command line arguments, checking for errors.
    """

    parser = argparse.ArgumentParser(
        description="An SMS/MMS translator between Android and Windows 10 Mobile",
    )
    parser.add_argument(
        "--from", choices=["android", "win10"], help="format of ALL input files"
    )
    parser.add_argument("--to", choices=["android", "win10"], help="format of output")
    parser.add_argument(
        "--phone", help="your phone number (please see FAQ in README.md)"
    )
    parser.add_argument(
        "--input",
        nargs="+",
        metavar="FILE",
        help="list of input files to convert from, omit to read from stdin",
    )

    args = parser.parse_args()

    if args.to == "android" and args.phone is None:
        print("Error: converting to Android requires --phone argument", file=sys.stderr)
        exit(1)

    return args


def main():
    # parse command line arguments
    args = get_args()
    src_fmt = getattr(args, "from")
    dst_fmt = getattr(args, "to")
    input_files = getattr(args, "input")
    your_phone = getattr(args, "phone")

    # prepare list of homogeneous source objects
    sources = []
    if input_files is None:
        sources.append(
            ET.parse(sys.stdin).getroot()  # all supported formats happen to be XML
            if src_fmt is not None
            else json.load(sys.stdin)
        )
    else:
        for file in input_files:
            with open(file, "r") as fp:
                sources.append(
                    ET.parse(fp).getroot() if src_fmt is not None else json.load(fp)
                )

    # convert and combine all sources to intermediary format
    from_ = {"android": from_android, "win10": from_win10}
    messages = []
    if src_fmt is None:
        for src in sources:
            messages += src
    else:
        for src in sources:
            messages += from_[src_fmt](src)

    # sort messages from oldest to newest
    messages.sort(key=lambda msg: (msg["timestamp"], msg["timestamp_ns"]))

    # convert messages to destination format and print out
    to_ = {"android": to_android, "win10": to_win10}
    if dst_fmt is None:
        json.dump(messages, sys.stdout, ensure_ascii=False)
    else:
        converted = to_[dst_fmt](messages, you=your_phone)
        ElementTree(converted).write(sys.stdout, encoding="unicode")


if __name__ == "__main__":
    main()

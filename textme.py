#!/usr/bin/env python3

import argparse
import base64
import json
import re
import sys
from typing import List
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, ElementTree


def norm(addr: str) -> str:
    """
    Normalizes addresses by simplifying phone numbers to only digits without
    country code. Leaves non phone numbers alone.
    """
    if addr is not None and re.fullmatch(r"[0-9() \-+]*", addr):
        return "".join(filter(str.isdigit, addr))[-10:]
    else:
        return addr


class Message(object):
    do_norm = False

    def __init__(
        self,
        timestamp: int,
        timestamp_ns: int,
        sender: str,
        recipients: list,
        body: str,
        is_read: bool,
        attachments: list,
    ):
        self.timestamp = timestamp
        self.timestamp_ns = timestamp_ns
        self.sender = norm(sender) if Message.do_norm else sender
        self.recipients = [norm(r) if Message.do_norm else r for r in recipients]
        self.body = body
        self.is_read = is_read
        self.attachments = attachments


def from_android(root: Element) -> List[Message]:
    RECEIVED = "1"
    SENT = "2"
    TO = "151"
    FROM = "137"

    def get_attachments(mms: Element) -> list:
        attachments = []
        for part in mms.iterfind("parts/part"):
            attachment = {"content_type": part.get("ct")}
            if part.get("data") is not None:
                attachment["data_base64"] = part.get("data")
            else:
                attachment["text"] = part.get("text")
            attachments.append(attachment)
        return attachments

    def from_sms(sms: Element) -> Message:
        return Message(
            timestamp=int(sms.get("date")) // 1000,
            timestamp_ns=int(sms.get("date")) % 1000 * (10 ** 6),
            sender=sms.get("address") if sms.get("type") == RECEIVED else None,
            recipients=[sms.get("address")] if sms.get("type") == SENT else [],
            body=sms.get("body"),
            is_read=sms.get("read") == "1",
            attachments=[],
        )

    def from_mms(mms: Element) -> Message:
        # everyone in the conversation, excluding yourself
        con = {norm(addr) for addr in mms.get("address").split("~")}

        return Message(
            timestamp=int(mms.get("date")) // 1000,
            timestamp_ns=int(mms.get("date")) % 1000 * (10 ** 6),
            sender=(
                mms.find(f"addrs/addr[@type='{FROM}']").get("address")
                if mms.get("msg_box") == RECEIVED
                else None
            ),
            recipients=[
                addr.get("address")
                for addr in mms.iterfind(f"addrs/addr[@type='{TO}']")
                if norm(addr.get("address")) in con
            ],
            body=None,
            is_read=mms.get("read") == "1",
            attachments=get_attachments(mms),
        )

    return [
        from_sms(msg) if msg.tag == "sms" else from_mms(msg)
        for msg in root.iterfind("*")
    ]


def from_win10(root: Element) -> List[Message]:
    def get_attachments(msg: Element) -> list:
        attachments = []
        for att in msg.iterfind("Attachments/MessageAttachment"):
            attachment = {}
            content_type = att.find("AttachmentContentType").text
            data_base64 = att.find("AttachmentDataBase64String").text

            attachment["content_type"] = content_type

            if content_type in {"text/plain", "application/smil"}:
                attachment["text"] = base64.b64decode(data_base64).decode("utf_16_le")
            else:
                attachment["data_base64"] = data_base64

            attachments.append(attachment)

        return attachments

    return [
        Message(
            timestamp=int(msg.find("LocalTimestamp").text) // (10 ** 7) - 11644473600,
            timestamp_ns=int(msg.find("LocalTimestamp").text) % (10 ** 7) * 100,
            sender=msg.find("Sender").text,
            recipients=[x.text for x in msg.iterfind("Recepients/string")],
            body=msg.find("Body").text,
            is_read=msg.find("IsRead").text == "true",
            attachments=get_attachments(msg),
        )
        for msg in root.iterfind("Message")
    ]


def to_android(messages: List[Message], **kwargs) -> Element:
    RECEIVED = "1"
    SENT = "2"
    TO = "151"
    FROM = "137"
    UTF_8 = "106"

    def addr(addr_type: str, address: str):
        a = Element("addr")
        a.set("charset", UTF_8)
        a.set("address", address)
        a.set("type", addr_type)
        return a

    try:
        you = kwargs["you"]
    except KeyError as e:
        raise TypeError("missing required keyword argument 'you'") from None

    smses = Element("smses")
    for message in messages:
        timestamp_ms = message.timestamp * 1000 + message.timestamp_ns // 1000000

        if len(message.attachments) > 0:
            mms = Element("mms")
            mms.set("m_type", "132" if message.sender is not None else "128")
            mms.set("msg_box", RECEIVED if message.sender is not None else SENT)

            mms.set("date", str(timestamp_ms))
            mms.set(
                "address",
                "~".join(
                    sorted(
                        message.recipients
                        + ([message.sender] if message.sender is not None else [])
                    )
                ),
            )
            mms.set("read", "1" if message.is_read else "0")

            parts = Element("parts")
            for attachment in message.attachments:
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
            if message.sender is not None:
                addrs.append(addr(FROM, message.sender))
                addrs.append(addr(TO, you))
            else:
                addrs.append(addr(FROM, you))
            for recipient in message.recipients:
                addrs.append(addr(TO, recipient))
            mms.append(addrs)

            smses.append(mms)
        else:
            sms = Element("sms")
            sms.set("date", str(timestamp_ms))
            sms.set("address", message.sender or message.recipients[0])
            sms.set("type", RECEIVED if message.sender is not None else SENT)
            sms.set("body", message.body or "")
            sms.set("read", "1" if message.is_read else "0"),
            smses.append(sms)

    smses.set("count", str(len(smses)))

    return smses


def to_win10(messages: List[Message], **kwargs) -> Element:
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
        for recipient in message.recipients:
            e_recepients.append(e("string", recipient))
        e_message.append(e_recepients)

        e_message.append(e("Body", message.body or ""))
        e_message.append(
            e("IsIncoming", "true" if message.sender is not None else "false")
        )
        e_message.append(e("IsRead", "true" if message.is_read else "false"))
        e_attachments = e("Attachments")
        for attachment in message.attachments:
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
                    (message.timestamp + 11644473600) * (10 ** 7)
                    + message.timestamp_ns // 100
                ),
            )
        )
        e_message.append(e("Sender", message.sender or ""))

        e_array_of_message.append(e_message)

    return e_array_of_message


def get_args():
    parser = argparse.ArgumentParser(
        description="An SMS/MMS translator between Android and Windows 10 Mobile",
    )
    parser.add_argument(
        "--from",
        choices=["android", "win10"],
        dest="src_fmt",
        help="format of ALL input files",
    )
    parser.add_argument(
        "--to",
        choices=["android", "win10"],
        dest="dst_fmt",
        help="format of output",
    )
    parser.add_argument(
        "--phone",
        help="your phone number (only required when converting to Android)",
    )
    parser.add_argument(
        "--input",
        help="list of input files to convert from",
        nargs="+",
        metavar="FILE",
    )
    parser.add_argument(
        "--norm",
        action="store_true",
        help="""normalize all phone numbers, e.g. transform +1 123-456-7890,
        (123)-456-7890, etc. into 1234567890""",
    )
    parser.add_argument(
        "--sort",
        action="store_true",
        help="sort messages from oldest to newest",
    )

    args = parser.parse_args()

    if args.dst_fmt == "android" and args.phone is None:
        parser.error("'--to android' requires --phone")

    return args


def main():
    args = get_args()
    Message.do_norm = args.norm

    # prepare list of homogeneous source objects
    sources = []
    object_hook = lambda m: Message(**m) if "timestamp" in m else m

    if args.input is None:
        sources.append(
            ET.parse(sys.stdin).getroot()  # all supported formats happen to be XML
            if args.src_fmt is not None
            else json.load(sys.stdin, object_hook=object_hook)
        )
    else:
        for file in args.input:
            with open(file, "r") as fp:
                sources.append(
                    ET.parse(fp).getroot()
                    if args.src_fmt is not None
                    else json.load(fp, object_hook=object_hook)
                )

    # convert and combine all sources to intermediary format
    from_ = {"android": from_android, "win10": from_win10}
    messages = []
    if args.src_fmt is None:
        for src in sources:
            messages += src
    else:
        for src in sources:
            messages += from_[args.src_fmt](src)

    # sort messages from oldest to newest, if requested
    if args.sort:
        messages.sort(key=lambda msg: (msg.timestamp, msg.timestamp_ns))

    # convert messages to destination format and print out
    to_ = {"android": to_android, "win10": to_win10}
    if args.dst_fmt is None:
        json.dump([vars(m) for m in messages], sys.stdout, ensure_ascii=False)
    else:
        converted = to_[args.dst_fmt](messages, you=args.phone)
        ElementTree(converted).write(sys.stdout, encoding="unicode")


if __name__ == "__main__":
    main()

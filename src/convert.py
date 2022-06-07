"""
This module contains SMS/MMS backup format conversion functions and classes.
"""

import base64
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import IO
from xml.etree.ElementTree import Element, ElementTree


def norm(addr: str | None) -> str:
    """
    Normalizes addresses by simplifying phone numbers to only digits without the country
    code. Addresses which are not phone numbers are left unchanged.

    This function makes several assumptions and should be used with caution.
    """
    if addr is not None and re.fullmatch(r"[0-9() \-+]*", addr):
        return "".join(filter(str.isdigit, addr))[-10:]

    return addr


@dataclass
class Message:
    """
    This class represents a single SMS/MMS message in an intermediary format.
    """

    timestamp: int
    timestamp_ns: int
    sender: str | None
    recipients: list[str]
    body: str | None
    is_read: bool
    attachments: list[dict[str, str]]


class Platform(ABC):
    """
    Abstract base class for classes that provide conversion capabilities for a specific
    mobile platform.
    """

    @staticmethod
    @abstractmethod
    def read(file: IO[str]) -> list[Message]:
        """
        Read input file and convert into list of messages.
        """

    @staticmethod
    @abstractmethod
    def write(file: IO[str], messages: list[Message], **kwargs) -> None:
        """
        Convert list of messages and write to output file.
        """


class Android(Platform):
    """
    Android
    """

    RECEIVED = "1"
    SENT = "2"
    TO = "151"
    FROM = "137"
    UTF_8 = "106"

    @staticmethod
    def read(file: IO[str]) -> list[Message]:
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
                timestamp_ns=int(sms.get("date")) % 1000 * (10**6),
                sender=sms.get("address")
                if sms.get("type") == Android.RECEIVED
                else None,
                recipients=[sms.get("address")]
                if sms.get("type") == Android.SENT
                else [],
                body=sms.get("body"),
                is_read=sms.get("read") == "1",
                attachments=[],
            )

        def from_mms(mms: Element) -> Message:
            # everyone in the conversation, excluding yourself
            con = {norm(addr) for addr in mms.get("address").split("~")}

            return Message(
                timestamp=int(mms.get("date")) // 1000,
                timestamp_ns=int(mms.get("date")) % 1000 * (10**6),
                sender=(
                    mms.find(f"addrs/addr[@type='{Android.FROM}']").get("address")
                    if mms.get("msg_box") == Android.RECEIVED
                    else None
                ),
                recipients=[
                    addr.get("address")
                    for addr in mms.iterfind(f"addrs/addr[@type='{Android.TO}']")
                    if norm(addr.get("address")) in con
                ],
                body=None,
                is_read=mms.get("read") == "1",
                attachments=get_attachments(mms),
            )

        return [
            from_sms(msg) if msg.tag == "sms" else from_mms(msg)
            for msg in ET.parse(file).getroot()
        ]

    @staticmethod
    def write(file: IO[str], messages: list[Message], **kwargs) -> None:
        def addr(addr_type: str, address: str):
            addr = Element("addr")
            addr.set("charset", Android.UTF_8)
            addr.set("address", address)
            addr.set("type", addr_type)

            return addr

        try:
            you = kwargs["you"]
        except KeyError:
            raise TypeError("missing required keyword argument 'you'") from None

        smses = Element("smses")
        for message in messages:
            timestamp_ms = message.timestamp * 1000 + message.timestamp_ns // 1000000

            if message.attachments:
                mms = Element("mms")
                mms.set("m_type", "132" if message.sender is not None else "128")
                mms.set(
                    "msg_box",
                    Android.RECEIVED if message.sender is not None else Android.SENT,
                )

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
                    part.set("chset", Android.UTF_8)
                    part.set("ct", attachment["content_type"])
                    if "text" in attachment:
                        part.set("text", attachment["text"])
                    else:
                        part.set("data", attachment["data_base64"])
                    parts.append(part)
                mms.append(parts)

                addrs = Element("addrs")
                if message.sender is not None:
                    addrs.append(addr(Android.FROM, message.sender))
                    addrs.append(addr(Android.TO, you))
                else:
                    addrs.append(addr(Android.FROM, you))
                for recipient in message.recipients:
                    addrs.append(addr(Android.TO, recipient))
                mms.append(addrs)

                smses.append(mms)
            else:
                sms = Element("sms")
                sms.set("date", str(timestamp_ms))
                sms.set("address", message.sender or message.recipients[0])
                sms.set(
                    "type",
                    Android.RECEIVED if message.sender is not None else Android.SENT,
                )
                sms.set("body", message.body or "")
                sms.set("read", "1" if message.is_read else "0")
                smses.append(sms)

        smses.set("count", str(len(smses)))

        ElementTree(smses).write(file, encoding="unicode")


class Windows10(Platform):
    """
    Windows 10 Mobile
    """

    @staticmethod
    def read(file: IO[str]) -> list[Message]:
        def get_attachments(msg: Element) -> list:
            attachments = []
            for att in msg.iterfind("Attachments/MessageAttachment"):
                attachment = {}
                content_type = att.find("AttachmentContentType").text
                data_base64 = att.find("AttachmentDataBase64String").text

                attachment["content_type"] = content_type

                if content_type in {"text/plain", "application/smil"}:
                    attachment["text"] = base64.b64decode(data_base64).decode(
                        "utf_16_le"
                    )
                else:
                    attachment["data_base64"] = data_base64

                attachments.append(attachment)

            return attachments

        return [
            Message(
                timestamp=int(msg.find("LocalTimestamp").text) // 10**7 - 11644473600,
                timestamp_ns=int(msg.find("LocalTimestamp").text) % 10**7 * 100,
                sender=msg.find("Sender").text,
                recipients=[x.text for x in msg.iterfind("Recepients/string")],
                body=msg.find("Body").text,
                is_read=msg.find("IsRead").text == "true",
                attachments=get_attachments(msg),
            )
            for msg in ET.parse(file).iterfind("Message")
        ]

    @staticmethod
    def write(file: IO[str], messages: list[Message], **kwargs) -> None:
        def encode_text(text: str) -> str:
            """Two-step text encoding"""

            return base64.b64encode(text.encode("utf_16_le")).decode()

        def elem(tag: str, text: str = None) -> Element:
            """Element constructor does not let you initialize the text"""

            elem = Element(tag)
            elem.text = text
            return elem

        e_array_of_message = elem("ArrayOfMessage")
        for message in messages:
            e_message = elem("Message")

            e_recepients = elem("Recepients")
            for recipient in message.recipients:
                e_recepients.append(elem("string", recipient))
            e_message.append(e_recepients)

            e_message.append(elem("Body", message.body or ""))
            e_message.append(
                elem("IsIncoming", "true" if message.sender is not None else "false")
            )
            e_message.append(elem("IsRead", "true" if message.is_read else "false"))
            e_attachments = elem("Attachments")
            for attachment in message.attachments:
                data_base64 = (
                    attachment["data_base64"]
                    if "data_base64" in attachment
                    else encode_text(attachment["text"])
                )
                e_message_attachment = elem("MessageAttachment")
                e_message_attachment.append(
                    elem("AttachmentContentType", attachment["content_type"])
                )
                e_message_attachment.append(
                    elem("AttachmentDataBase64String", data_base64)
                )
                e_attachments.append(e_message_attachment)
            e_message.append(e_attachments)

            e_message.append(
                elem(
                    "LocalTimestamp",
                    str(
                        (message.timestamp + 11644473600) * (10**7)
                        + message.timestamp_ns // 100
                    ),
                )
            )
            e_message.append(elem("Sender", message.sender or ""))

            e_array_of_message.append(e_message)

        ElementTree(e_array_of_message).write(file, encoding="unicode")

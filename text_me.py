#!/usr/bin/env python3

"""
Main program
"""

import argparse
import json
import sys
from xml.etree import ElementTree

from src import convert


def get_args():
    """
    Handles argument parsing
    """
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
    parser.add_argument(
        "input",
        nargs="*",
        help="list of input files to convert from",
        metavar="FILE",
    )

    args = parser.parse_args()

    if args.dst_fmt == "android" and args.phone is None:
        parser.error("'--to android' requires --phone")

    return args


def main():
    """
    The point of entry for the program
    """
    args = get_args()
    convert.Message.do_norm = args.norm

    # prepare list of homogeneous source objects
    sources = []
    object_hook = lambda m: convert.Message(**m) if "timestamp" in m else m

    if args.input is None:
        sources.append(
            # all supported formats happen to be XML
            ElementTree.parse(sys.stdin).getroot()
            if args.src_fmt is not None
            else json.load(sys.stdin, object_hook=object_hook)
        )
    else:
        for filename in args.input:
            with open(filename, "r", encoding="utf8") as file:
                sources.append(
                    ElementTree.parse(file).getroot()
                    if args.src_fmt is not None
                    else json.load(file, object_hook=object_hook)
                )

    # convert and combine all sources to intermediary format
    from_ = {"android": convert.from_android, "win10": convert.from_win10}
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
    to_ = {"android": convert.to_android, "win10": convert.to_win10}
    if args.dst_fmt is None:
        json.dump([vars(m) for m in messages], sys.stdout, ensure_ascii=False)
    else:
        converted = to_[args.dst_fmt](messages, you=args.phone)
        ElementTree.ElementTree(converted).write(sys.stdout, encoding="unicode")


if __name__ == "__main__":
    main()

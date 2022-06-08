#!/usr/bin/env python3

"""
Main program
"""

import argparse
import json
import sys

from src.convert import Android, Platform, Windows10


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


def main() -> None:
    """
    The point of entry for the program
    """
    args = get_args()

    platforms: dict[str, type[Platform]] = {
        "android": Android,
        "win10": Windows10,
    }
    with open(args.input[0], "r", encoding="utf8") as file:
        messages = platforms[args.src_fmt].read(file)

    # sort messages from oldest to newest, if requested
    if args.sort:
        messages.sort(key=lambda msg: (msg.timestamp, msg.timestamp_ns))

    # convert messages to destination format and print out
    write_kwargs = {"you": args.phone}
    if args.dst_fmt is None:
        json.dump(
            [vars(m) for m in messages], sys.stdout, ensure_ascii=False, indent="\t"
        )
        sys.stdout.write("\n")
    else:
        platforms[args.dst_fmt].write(sys.stdout, messages, **write_kwargs)


if __name__ == "__main__":
    main()

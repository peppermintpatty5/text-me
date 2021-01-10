<!-- markdownlint-disable no-blanks-blockquote -->

# text-me

The 2% or less of smartphone users with Windows Phones should be aware that Windows 10 Mobile reached end of life on December 10, 2019. For those who want to transfer their texts to their new devices, I hope you find this software useful.

This software has been designed with extensibility in mind. In the future, I may add support for more mobile platforms.

## Prerequisites

The supported data formats are tied to specific applications. So "converting to Android" really means "converting to a format used by a specific, unofficial Android SMS/MMS application". Refer to the chart below.

[A]: https://play.google.com/store/apps/details?id=com.riteshsahu.SMSBackupRestore
[B]: https://www.microsoft.com/en-us/p/contacts-message-backup/9nblgggz57gm

| ID        | Operating System  | SMS/MMS Application          |      Official      |
| :-------- | :---------------- | :--------------------------- | :----------------: |
| `android` | Android 5.0+      | [SMS Backup & Restore][A]    |        :x:         |
| `win10`   | Windows 10 Mobile | [contacts+message backup][B] | :heavy_check_mark: |

## Usage

> :warning: **Warning**
>
> To avoid potential data loss, **backup the SMS/MMS data on your destination device** before doing any restorations.

This repository includes some [test](test/) input files. Rather than using fake phone numbers, these files simply use the names of Star Wars characters (you are Obi-wan Kenobi). Here is a demonstration of converting from Windows 10 Mobile to Android:

```shell
python3 textme.py --from win10 --to android --phone "Obi-wan Kenobi" --input test/win10.msg
```

> :information_source: **Note**
>
> `--phone` is only required when converting to Android. With Android MMS attachments, not listing the sender's address—even when you are the sender—results in a non-fatal "Unrecognized sender" error.

> :information_source: **Note**
>
> `--input` accepts one or more filenames to be concatenated **without duplicate checking**. This is useful for Windows Phone where SMS and MMS are stored in separate backup files.

> :bulb: **Tip**
>
> Most shells support the UNIX-style pipe and redirect syntax. Include `> foo` in the command to redirect the output to a file named `foo`.

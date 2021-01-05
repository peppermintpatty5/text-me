# text-me

The unfortunate 2% or less of smartphone users with Windows Phones should be aware that Windows 10 Mobile reached end of life on December 10, 2019. For those who want to transfer their texts to their new devices, I hope you find this software useful.

This software has been designed with extensibility in mind. In the future, I may add support for more mobile platforms.

## Prerequisites

Before converting anything, you must be able to retrieve and restore your SMS/MMS data on *both* devices. Skip to [usage](#usage) if you have already done this. Otherwise, refer to this chart for the apps you will need.

[A]: https://play.google.com/store/apps/details?id=com.riteshsahu.SMSBackupRestore
[B]: https://www.microsoft.com/en-us/p/contacts-message-backup/9nblgggz57gm

| Operating System  | SMS/MMS Application          |      Official      |
| :---------------- | :--------------------------- | :----------------: |
| Android 5.0+      | [SMS Backup & Restore][A]    |        :x:         |
| Windows 10 Mobile | [contacts+message backup][B] | :heavy_check_mark: |

## Usage

> :warning: Please **backup your SMS/MMS data** before continuing!

This repository includes some [test](test/) input files. Rather than using fake phone numbers, these files simply use the names of Star Wars characters (you are Obi-wan Kenobi). Here is a demonstration of converting from Windows 10 Mobile to Android:

```shell
python3 textme.py --from win10 --to android --phone "Obi-wan Kenobi" --input test/win.msg
```

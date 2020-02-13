# Clone an Image of the Pi
Instructions from a Linux desktop.  For Windows, see [Beebom](https://beebom.com/how-clone-raspberry-pi-sd-card-windows-linux-macos/)

Determine the device path:
```bash
fdisk -l
```

Note that it is *not* and never will be **sda** - if you run a dd over this, you will wipe the hard drive of your machine.  Device drives are typically **sdb** (note the sequencing) but often can be **mmcblk**.

What it mounts as depends on how the blocks device is registered in the Linux kernel.

- SCSI disks are handled by *drivers/scsi/sd.c* and mount as **sdX**
- MMC devices are handled by *drivers/mmc/card/block.c* and mount as **mmcblk**

You'll see output similar to:
```bash
...sda stuff above here...
Disk /dev/mmcblk0: 14.9 GiB, 15931539456 bytes, 31116288 sectors
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 512 bytes / 512 bytes
Disklabel type: dos
Disk identifier: 0x0007131b

Device         Boot   Start      End Sectors  Size Id Type
/dev/mmcblk0p1         8192  2804687 2796496  1.3G  e W95 FAT16 (LBA)
/dev/mmcblk0p2      2804688 10362879 7558192  3.6G  5 Extended
/dev/mmcblk0p5      2809856  2875389   65534   32M 83 Linux
/dev/mmcblk0p6      2875392  3022845  147454   72M  c W95 FAT32 (LBA)
/dev/mmcblk0p7      3022848 10362879 7340032  3.5G 83 Linux
```
**mmcblk0 is the device path we need.**

## Clone All Partitions
```bash
dd if=/dev/mmcblk0 of=/home/angela/Desktop/tc_backup.img bs=1M status=progress
```
- Note that the in-file (**if**) value is only **mmcblk0** and lacks `pX` - that's because we don't want to target partitions, we want all of them.
- `bs` parameter = increases speed while writing
- `status` parameter = progress display
- A file will be created on my deskop with the filename `tc-backup.img` - I can use this to flash on multiple SD cards for various batteries

It took about 10 minutes to flash on an 8gb SD card (without the bs flag).

## Restore Parition to a New SD Card
Place the SD card into the laptop and check what the device ID is, again.
```bash
fdisk -l
```
Same rules as above apply..

Now, unmount it:
```bash
umount /dev/mmcblk0p1 /dev/mmcblk0p2 /dev/mmcblk0p5 /dev/mmcblk0p6 /dev/mmcblk0p7
```

Flashing the new image is a reversal of the clone command:
```bash
dd if=/home/angela/Desktop/tc_backup.img of=/dev/mmcblk0 bs=1M status=progress
```

Now, login to the Pi and set an IP, based on the closet number:

Increment it for each machine using `172.28.4.xx`; xx = *closet number*
```bash
pico /etc/dhcpcd.conf
```

On your desktop, make an SSH alias, so you can lazily enter the Pi, like so: `ssh tc3pi` instead of `ssh pi@172.28.4.3`:
```bash
Host tc3pi
HostName 172.28.4.3
Port 22
User pi
Compression yes
IdentityFile ~/.ssh/id_rsa
```

## Add an SSH Key to Your Pi
Because you're going to have to run OS upgrades (on the Pi) at some point

Assuming you already have an SSH key, from your desktop, run (destination being the Pi's IP):
```bash
ssh-copy-id -i ~/.ssh/id_rsa.pub pi@172.28.4.3
```

Lazily login now:
```bash
ssh tc3pi
```

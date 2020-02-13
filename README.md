# UPS Monitoring with Raspberry Pi's & PRTG
This super light script will give the ability to do network monitoring on a UPS backup battery that lacks networking (or requires proprietary software), via PRTG.

This script was tested/built for an APC SmartUPS 1500 via USB, but should work for any UPS that's [supported by NUT](https://networkupstools.org/stable-hcl.html).  You may need to adjust the driver used, my instructions were as-used in my environment.


## In Summary
- NUT monitors the battery statistics
- PRTG can monitor the health of the Pi + battery via NUT statistics
- PRTG is given a directive to login to the Pi and run a Python script (via PRTG settings)
- The Python script processes data from Nut and formats it for PRTG's XML and returns the data as sensor + channel values
- Clone the Pi for use in multiple tech closets/floors

## My Physical Setup (Yours may differ, depending on battery)
The APC SmartUPS uses the [usbhid-ups](https://networkupstools.org/docs/man/usbhid-ups.html) driver and is accessible by plugging a USB A to B (old printer style) from the UPS, into the Pi. (USB B port is native to the battery.)

**Pre-requisite**

The Pi will require wifi / network jack and/or a switch accessible, so PRTG can reach it.

**Worth Noting**

You can have one Pi monitor multiple batteries, but in my environment its one UPS per closet, so I didn't consider such environments in the code.  Feel free to adjust to suit your needs.

It is also possible to forgo the Python script and do this entirely via SNMP by [extending SNMP](http://net-snmp.sourceforge.net/wiki/index.php/Tut:Extending_snmpd_using_shell_scripts) with a [bash script](https://geekpeek.net/extend-snmp-run-bash-scripts-via-snmp/).

## Preliminary Setup
1. Set up a Pi with [Raspbian](https://www.raspberrypi.org/downloads/raspbian/) or Noobs
2. Install dependences: `sudo apt install nut snmpd snmp snmp-mibs-downloader git`
3. Prepare a 'default' setup for cloning, to use on multiple batteries:

### Set a Default Static IP
This should be a *reserved IP* (one you don't plan to use - and is outside of any DHCP scope), as you will have to login to each Pi after it is cloned to set a static IP.

Increment it for each machine using `172.28.4.xx`; xx = *closet number*
```bash
pico /etc/dhcpcd.conf
```

Add the following (make sure the static IP you assign, doesn't already exist -- customize to suit your environment)
```bash
# static ip config to the admin network:
interface eth0
static ip_address=172.28.4.xx/24
#static ip6_address=
static routers=172.28.10.1
static domain_name_servers=172.28.5.140 172.28.5.141
```

***
## Setting up NUT
- Declare the UPS in `/etc/nut/ups.conf`
```bash
# tc for tech closet.. name it anything that suits your environment
[tc]
  driver = usbhid-ups
  port = auto
  desc = "TC UPS"
```

- In `/etc/nut/nut.conf`, set NUT daemon to run in *standalone* mode. It's the mode to use on the machine to which the UPS is connected and when this same machine also monitors the UPS

```bash
# default config
#MODE=none

# config changed by angela
MODE=standalone
```

- In `/etc/nut/upsd.conf`, bind a listening port to the LAN interface if you want to allow other LAN hosts to monitor the UPS through upsd, the UPS network daemon. If not, just keep the first line:
```bash
# config added by angela
LISTEN 127.0.0.1
```

- Set the permissions for upsd in `/etc/nut/upsd.users`. Only the users (one section = one user) listed in this file will be allowed to read the UPS state:
```bash
# config added by angela
[tc]
  password = [yourpassword]
  upsmon master
```

- Configure the *upsmon* daemon. Its role is to communicate with upsd to know the UPS status and send specific commands when some events occur. Modify `/etc/nut/upsmon.conf` as follows:
```bash
# config added by angela
MONITOR tc@localhost 1 tc [yourpassword] master
```

- Make sure to modify the permissions of all NUT configuration files
```bash
chown root:nut /etc/nut/*
chmod 640 /etc/nut/*
```

Auto-start SNMP
```bash
systemctl enable snmpd
```

Start the SNMP daemon (this won't be necessary in subsequent logins, as the 'enable' sets it to auto-start upon boot.
```bash
systemctl start snmpd
```

***

### Allow SNMP Remote Probes
This is to monitor the health of the Pi, not the battery (I could not locate the MIBs needed for the APC Smart-UPS 1500)
```bash
pico /etc/snmp/snmpd.conf
```

Under AGENT BEHAVIOR, add (comment out any existing agentAddress entries):
```bash
agentAddress udp:161
```

Under ACCESS CONTROL, add (comment out any existing rocommunity strings) - add the IP of your PRTG installation here:
```bash
rocommunity public 172.28.5.1
# any other IP you want to have access to.  Port 161 is firewalled on networked PCs, so you'd need a firewall exception to probe locally.
```

Provision your changes with a restart:
```bash
service snmpd restart
```

## Testing Commands
To start NUT manually (upsd and upsmon daemons simultaneously):
```bash
service nut start
```

To check both daemons status:
```bash
service nut status
```

To launch the UPS driver (this will be configured to launch on reboot a few lines below here):
```bash
upsdrvctl start
```

To know the UPS status:
```bash
upsc ups
```


To test the server behavior in case of power outage, use the following command:
```bash
upsmon -c fsd
```

***

### PRTG Testing Commands
The script is owned by user *prtg*
`su - prtg`

Execute the script manually (no language prefix necessary, as the script has a shebang on line 1)
```python
/var/prtg/scriptsxml/battery_sensor.py
```

### Create a startup service
`rc.local` is for the sysadmin/root/sudo user to execute tasks or services after normal system services have started.

This was "deprecated" in distros with systemd but you can restore rc.local-like functionality by simply creating a service, enabling at startup and *calling it* rc-local.

Create the systemd service
```bash
pico /etc/systemd/system/rc-local.service
```
Add the following to `rc-local.service`
```bash
[Unit]
Description=Create rc.local functionality in systemd
ConditionPathExists=/etc/rc.local

[Service]
Type=forking
ExecStart=/etc/rc.local start
TimeoutSec=0
StandardOutput=tty
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Make the script executable so it may be invoked by the service
```bash
chmod +x /etc/rc.local
```

If you haven't already, pre-pend the shebang to the beginning of `/etc/rc.local`, otherwise systemd won't run it, and an **exit 0**
```bash
#!/bin/sh

# autostart upsdrvctl for nut
upsdrvctl start

exit 0
```
Enable it at startup and start it
```bash
systemctl enable rc-local && systemctl start rc-local.service
```
Check for errors (it would crash right away on start, typically)
```bash
service rc-local status
```

***

### Create a user so PRTG can login remotely to check on Nut
- Create an SSH key for PRTG to use on Linux-based servers (if you haven't already)
- Go into PRTG dashboard settings and add the key and `prtg` user for Linux
- Add PRTG's pubkey to `/home/prtg/.ssh/authorized_keys`
- Restart the SSH daemon for the changes to take effect:
```bash
service ssh restart
```
### On the Pi:
- Make sure PRTG's private key is accessible to `~/.ssh/prtg/` and that you have the SSH pubkey also accessible to any private repo, should you intend to keep a private, customized branch of this script - that way if you make changes, you can push it to all of your installations.

- Make a scripts directory that PRTG knows to look for (it [*has* to be this path](https://prtg.example.com/api.htm?tabid=7), for XML-based output!)
```bash
mkdir /var/prtg/scriptsxml
```

- Clone the remote repo and assign the PRTG **scriptsxml** directory as the destination:
```bash
git clone https://github.com/angela-d/prtg-ups-monitor.git /var/prtg/scriptsxml && chmod 750 -R $(find /var/prtg/ -type d) &&
chmod 544 $(find /var/prtg/scriptsxml -type f) && chmod 540 -R $(find /var/prtg/scriptsxml -type f)
```
In summary:
- `battery-sensor.py` is an executable
- `chown` to assign permissions to the PRTG user so it can read.
- `chmod` to change permissions mode.

**Useful:**
[Permissions cheatsheet](https://chmodcommand.com/)

***

## Reduce Writes to the Pi
Since this is a Pi, you don't want the SD cart constantly being written to.

Switch to root on the Pi:
```bash
sudo su
```

Create the file:
```bash
pico /etc/rsyslog.d/10-prtg.conf
```

Append to **10-prtg.conf**:
```bash
# do not log snmp hits from prtg
#
# do not add this until setup testing is done..
if $msg contains 'Connection from UDP: [your-PRTG-ip]' then stop

# include the brackets!
# if $msg contains 'Connection from UDP: [127.0.0.2]' then stop
```

Restart rsyslog daemon
```bash
service rsyslog restart
```
***

## Optional Test code for battery_sensor.py
For working on the script without immediate access to the battery (run `upsc tc` on your system to generate it).
- Have a textual copy of the xml output
- Replace the subprocess bits with:
```python
# do a loop on a text file of the results we're supposed to iterate from the upsc command
import io
battery_results = subprocess.Popen(["cat", "upsc-output"], stdout=subprocess.PIPE)
for line in io.TextIOWrapper(battery_results.stdout, encoding="utf-8"):
```

***
## Adding the Sensors to PRTG
- Add a new device
- Go to the new device and click the **+**  to Add a sensor
- Click the **SSH Script Advanced** option

> Select a script file from the list. The dropdown menu lists all script files available in the **/var/prtg/scriptsxml** directory on the target Linux/Unix system. For a script file to appear in this list, store the target file into this directory. Make sure that the script has executable rights.

> To show the expected sensor value and status, your files must return the expected XML or JSON format to standard output stdout. Values and message must be embedded in the XML or JSON.


- Customize the channel thresholds by clicking the dual-wheels > Enable alerting based on limits **(you won't get alerts or warnings without doing this step!)**


## Automate Future Installations
Or close enough to it! [Clone the Raspberry Pi](clone-pi.md) for easy setup on multiple batteries.

Don't forget to add the Pi's to your updates schedule!  They require security patches and bugfixes just like any other Linux system.

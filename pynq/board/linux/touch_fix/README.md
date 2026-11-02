# AC820 touch pinctrl service

This service reapplies the tested GT911 device-tree correction on each boot.
It does not change `BOOT.BIN` or `image.ub`. It uses Linux pinctrl and reads PS
registers only to verify MIO0 = `0x0600`, MIO50/51 = `0x1240`.

Install the matching, compiled `gt911_pads_fix.dtbo` and these files as root:

```sh
install -d /usr/local/share/ac820-touch
install -m 0644 gt911_pads_fix.dtbo /usr/local/share/ac820-touch/gt911_pads_fix.dtbo
install -m 0755 ac820-touch-pinctrl.py /usr/local/sbin/ac820-touch-pinctrl.py
install -m 0644 ac820-touch-pinctrl.service /etc/systemd/system/ac820-touch-pinctrl.service
systemctl daemon-reload
systemctl enable ac820-touch-pinctrl.service
```

If the correction is already applied and verified, `systemctl start
ac820-touch-pinctrl.service` is safe while the notebook runs. Otherwise stop
applications, close their GPIO objects, and release all GPIO exports first.
The script refuses to detach devices while GPIO consumers or exports exist.
It always attempts to rebind every device it detached, including on errors.

The service runs before `jupyter.service` and `pl_server.service`. A failure
is logged but does not prevent either application service from starting.

```sh
systemctl start ac820-touch-pinctrl.service
python3 /usr/local/sbin/ac820-touch-pinctrl.py --check
journalctl -u ac820-touch-pinctrl.service -b --no-pager
```

`--check` reads the current overlay status and registers without detaching or
reconfiguring devices. If an existing overlay is not `applied`, inspect that
configfs entry before retrying; the script does not automatically remove it.

## Rollback

```sh
systemctl disable --now ac820-touch-pinctrl.service
```

Stopping the service leaves the currently applied correction in place. To
return to the original boot device tree, stop applications normally and reboot
after disabling the service. The runtime configfs overlay disappears at reboot.
The original boot image is unchanged. The installed files can be removed after
the service has been disabled.

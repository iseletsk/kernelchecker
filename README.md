#KernelChecker

_kernelcheker.py_
KernelChecker was created to allow control panels to easily detect & advise
users on updating running kernel. It can be used to promote KernelCare
through the control panel. One of the goals behind creating this script was to to make it easier for control
panel providers to setup effective affiliate program with KernelCare to generate extra income.
If you are interested in affiliate program, contact us at sales@kernelcare.com


The purpose of KernelChecker is to determine if:
  * newer kernel is available
  * if update / reboot is needed
  * if KernelCare (http://kernelcare.com) is installed
  * if latest patches are installed using KernelCare


The script should work on dpkg & RPM based distributions. It should be able to detect if it is running inside container (Virtuozzo & LXC)

By defalt it produces YAML output. Additionally it understands --json / -j command line options that causes it to produce output in JSON

Usage:
```bash
python kernelchecker.py [--json]
```

Example output:
```YAML
latest : 3.13.0-79-generic
current : 3.13.0-79-generic
distro : dpkg
needs_update : False
latest_installed : True
latest_available : True
inside_container : False
kernelcare :
  installed : False
  up2date : False
  supported : True
```

* latest --> Latest available kernel
* current --> current booted kernel
* distro --> more like package manager, possible values: dpkg, rpm & unknown
* needs_update --> newer kernel exits, reboot will be needed
* latest_installed --> latest kernel already installed, no need to run yum update/etc...
* inside_container --> if True, other values could be ignored, as we are running inside container and cannot update kernel
* kernelcare : installed --> if True, KernelCare installed
* kernelcare : up2date --> if True, kernel is patched with all the security patches, no need to update kernel (even if needs_update shows up)
* kernelcare : supported --> if True, KernelCare supports this kernel, if False - KernelCare doesn't support this kernel

Some example of usages / advising customer based on results:

```
if inside_container == True: do nothing
// customer should not be advised to update/reboot no matter what
// as customer doesn't have ability to do so. 
// Also, node kernel might be patched using KernelCare or other tools.
else if needs_update == False : customer running latest kernel, nothing needs to be done
else if kernelcare.up2date == True: nothing needs to be done, Kernel is patched with KernelCare
else if needs_update == False {
  if kernelcare.installed: ask customer to run kcarectl --update
  else if kernelcare.supported: ask customer to deploy KernelCare
  else if latest_installed: ask customer to reboot
  else: ask customer to update using yum update/apt-get update, and reboot_
}
```


_kc-compat.py_
Checks if server is running kernel compatible with KernelCare.
Usage:
```bash
python kc-compat.py [--silent|-q]
```

Outputs COMPATIBLE if kernel supported, UNSUPPORTED and UNSUPPORTED; INSIDE CONTAINER
if --silent flag is provided -- doesn't print anything
Produces exit code 0 if compatible; 1 unsupported; 2 unsupported, inside container

Alternatively you can use: 
```bash
curl -s https://raw.githubusercontent.com/iseletsk/kernelchecker/master/py/kc-compat.py|python
```

or
```bash
wget -qq -O - https://raw.githubusercontent.com/iseletsk/kernelchecker/master/py/kc-compat.py|python
```

_Note: You cannot use exit code in this case, only output_


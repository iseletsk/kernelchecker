#KernelChecker

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
```

* latest --> Latest available kernel
* current --> current booted kernel
* distro --> more like package manager, possible values: dpkg, rpm & unknown
* needs_update --> newer kernel exits, reboot will be needed
* latest_installed --> latest kernel already installed, no need to run yum update/etc...
* inside_container --> if True, other values could be ignored, as we are running inside container and cannot update kernel
* kernelcare : installed --> if True, KernelCare installed
* kernelcare : up2date --> if True, kernel is patched with all the security patches, no need to update kernel (even if needs_update shows up)




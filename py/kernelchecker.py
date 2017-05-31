from distutils.version import LooseVersion
import platform
import subprocess
import os

__author__ = 'Igor Seletskiy'
__copyright__ = "Cloud Linux Zug GmbH 2016, KernelCare Project"
__credits__ = 'Igor Seletskiy'
__license__ = 'Apache License v2.0'
__maintainer__ = 'Igor Seletskiy'
__email__ = 'i@kernelcare.com'
__status__ = 'Production'
__version__ = '1.0'

# recognizable kernel package names
KERNEL_PREFIXES = ['pve-kernel', 'kernel-xen', 'vzkernel', 'kernel', 'linux']
DPKG_DISTRO = ['ubuntu', 'debian']
RPM_DISTRO = ['redhat', 'centos', 'cloudlinux', 'fedora']


def check_output(args):
    """
    Execute command, and return output stream. Provided for convenience/compatiblity with python 2.4
    :param args: command to execute
    :return: output stream
    """
    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]


class RpmHandler:
    def __init__(self, current_version):
        if 'stab' in current_version:
            self.kernel_name = 'vzkernel'
        else:
            self.kernel_name = 'kernel'

    def get_installed(self):
        result = []
        for version in check_output(
            ['rpm', '--queryformat=%{VERSION}-%{RELEASE}\n', '-qq', self.kernel_name]).split('\n'):
            version = RpmHandler.strip_version(version)
            if version:
                result.append(version)
        return result

    def get_available(self):
        yum_output = check_output(
            ['yum', 'list', 'updates', self.kernel_name]).split('\n')
        result = []
        for line in yum_output:
            if line.startswith(self.kernel_name):
                result.append(RpmHandler.strip_version(line.split()[1]))
        return result

    @staticmethod
    def strip_version(version):
        parts = version.split('.')
        result = parts[0]
        parts.pop(0)
        for part in parts:
            if part and part[0].isdigit():
                result += '.'+part
            else:
                break
        if ':' in result:
            result = result.split(':')[1]
        return result


class DpkgHandler:
    def __init__(self, current_version):
        parts = current_version.split('-')
        self.pkg_version = parts[0]
        self.pkg_prefix = 'linux-image-'+parts[0]
        self.pkg_suffix = parts[-1]
        self.is_rt = '-rt-' in current_version

    def extract_version(self, line):
        if len(line):
            pkg_name = line.split()[0]
            return pkg_name[len(self.pkg_prefix)-len(self.pkg_version):]
        else:
            return None

    def get_versions(self, command):
        out = check_output(command)
        result = []
        for line in out.split('\n'):
            ver = self.extract_version(line)
            if ver:
		if self.is_rt:
			if '-rt-' in ver: 
                		result.append(ver)
		elif '-rt-' not in ver:
			result.append(ver)
        return result

    def get_installed(self):
        return self.get_versions(['dpkg-query', '-W', self.pkg_prefix+'-*-'+self.pkg_suffix])

    def get_available(self):
        check_output(['apt-get', 'update'])
        return self.get_versions(['apt-cache', 'search', self.pkg_prefix+'-.*-'+self.pkg_suffix+'$'])


class UnknownHandler:
    def __init__(self):
        pass

    @staticmethod
    def get_installed():
        return []

    @staticmethod
    def get_available():
        return []


class KernelChecker:
    """
    This class performs checks to determine if kernel update & reboot needed
    """
    kernelcare = None

    def __init__(self):
        self.current_version = platform.release()
        self.inside_container = False
        self.distro_type = KernelChecker.get_distro_type()
        if 'stab' in self.current_version:
            self.inside_container = KernelChecker.inside_vz_container()
        else:
            self.inside_container = KernelChecker.inside_lxc_container()

        if self.distro_type == "rpm":
            handler = RpmHandler(self.current_version)
            self.current_version = handler.strip_version(self.current_version)
        elif self.distro_type == "dpkg":
            handler = DpkgHandler(self.current_version)
            pass
        else:
            handler = UnknownHandler()
            pass

        self.installed_versions = handler.get_installed()
        self.available_versions = handler.get_available()

        self.latest_version = self.get_latest()

        self.needs_update = self.latest_version != self.current_version
        self.latest_installed = self.latest_version in self.installed_versions
        self.latest_available = self.latest_version in self.available_versions

        self.check_kernelcare()


    @staticmethod
    def get_kernel_hash():
        try:
            # noinspection PyCompatibility
            from hashlib import sha1
        except ImportError:
            from sha import sha as sha1
        f = open('/proc/version', 'rb')
        try:
            return sha1(f.read()).hexdigest()
        finally:
            f.close()

    @staticmethod
    def is_kernelcare_supported_kernel():
        url = 'http://patches.kernelcare.com/'+KernelChecker.get_kernel_hash()+'/version'
        import urllib2
        try:
            urllib2.urlopen(url)
            return True
        except:
            return False

    def check_kernelcare(self):
        """
        checks if kernelcare (http://kernelcare.com) is installed, and kernel is patched
        :return: tupple ( INSTALLED, UP2DATE, SUPPORTED )
        """
        supported = KernelChecker.is_kernelcare_supported_kernel()
        kcare_bin = '/usr/bin/kcarectl'
        if os.path.exists(kcare_bin):
            p = subprocess.Popen([kcare_bin, '--check'], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            self.kernelcare = (True, p.wait() == 1, supported)
        else:
            self.kernelcare = (False, False, supported)

    @staticmethod
    def get_version(fullname):
        for prefix in KERNEL_PREFIXES:
            if fullname.startswith(prefix):
                return fullname[len(prefix)+1:]
        return None

    def get_latest(self):
        """
        Figures out latest kernel version
        :return: latest version from all versions
        """
        latest = '0'
        all = [self.current_version] + self.installed_versions + self.available_versions
        for k in all:
            if LooseVersion(latest) < LooseVersion(k):
                latest = k
        return latest

    @staticmethod
    def get_distro_type():
        import platform
        try:
            name = platform.dist()[0]
        except AttributeError:
            name = platform.linux_distribution()[0]
        if name.lower() in RPM_DISTRO:
            return "rpm"
        elif name.lower() in DPKG_DISTRO:
            return "dpkg"
        elif os.path.exists('/usr/bin/rpm'):
            return "rpm"
        elif os.path.exists('/usr/bin/dpkg'):
            return "dpkg"
        return "unknown"

    @staticmethod
    def inside_vz_container():
        """
        determines if we are inside Virtuozzo container
        :return: True if inside container, false otherwise
        """
        return os.path.exists('/proc/vz/veinfo') and not os.path.exists('/proc/vz/version')

    @staticmethod
    def inside_lxc_container():
        return '/lxc/' in open('/proc/1/cgroup').read()

    def get_data(self):
        return (self.latest_version, self.current_version, self.distro_type,
                self.needs_update, self.latest_installed,
                self.latest_available, self.inside_container,
                self.kernelcare[0], self.kernelcare[1], self.kernelcare[2])

    def tojson(self):
        result = '{ "latest" : "%s", ' \
                 '"current" : "%s", ' \
                 '"distro" : "%s", ' \
                 '"needs_update" : %r, ' \
                 '"latest_installed" : %r, ' \
                 '"latest_available" : %r, ' \
                 '"inside_container" : %r,' \
                 '"kernelcare" : { "installed" : %r, "up2date" : %r, "supported" : %r } }' % self.get_data()
        return result

    def toyaml(self):
        result = 'latest : %s\n' \
                 'current : %s\n' \
                 'distro : %s\n' \
                 'needs_update : %r\n' \
                 'latest_installed : %r\n' \
                 'latest_available : %r\n' \
                 'inside_container : %r\n' \
                 'kernelcare :\n    ' \
                 'installed : %r\n    up2date : %r\n    supported : %r\n' % self.get_data()
        return result



def main():
    """
    if --json or -j argument provided, print results in json, otherwise in yaml format
    :return: 0
    """
    kchecker = KernelChecker()
    import sys
    if len(sys.argv) > 1 and (sys.argv[1] == '--json' or sys.argv[1] == '-j'):
        print(kchecker.tojson())
    else:
        print(kchecker.toyaml())

if __name__ == "__main__":
    main()

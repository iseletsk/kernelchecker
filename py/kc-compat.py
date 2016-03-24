import urllib2
import sys

__author__ = 'Igor Seletskiy'
__copyright__ = "Cloud Linux Zug GmbH 2016, KernelCare Project"
__credits__ = 'Igor Seletskiy'
__license__ = 'Apache License v2.0'
__maintainer__ = 'Igor Seletskiy'
__email__ = 'i@kernelcare.com'
__status__ = 'Production'
__version__ = '1.0'


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


def is_compat():
    url = 'http://patches.kernelcare.com/'+get_kernel_hash()+'/latest.v1'
    try:
        urllib2.urlopen(url)
        return True
    except:
        return False


def main():
    """
    if --silent or -q argument provided, don't print anything, just use exit code
    otherwise print results (COMPATIBLE or UNSUPPORTED)
    else exit with 0 if COMPATIBLE, 1 otherwise
    """
    if len(sys.argv) > 1 and (sys.argv[1] == '--silent' or sys.argv[1] == '-q'):
        if is_compat():
            return 0
        else:
            return 1
    else:
        if is_compat():
            print("COMPATIBLE")
            return 0
        else:
            print("UNSUPPORTED")
            return 1

if __name__ == "__main__":
    main()
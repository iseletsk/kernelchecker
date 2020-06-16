#!/usr/bin/env python

import os
import json
import errno
import struct
import logging

from collections import namedtuple

ELF64_HEADER = "<16sHHIQQQIHHHHHH"
ELF_PH_HEADER = "<IIQQQQQQ"
ELF_NHDR = "<3I"
PT_NOTE = 4
NT_GNU_BUILD_ID = 3
IGNORED_PATHNAME = ["[heap]", "[stack]", "[vdso]", "[vsyscall]", "[vvar]"]

Range = namedtuple('Range', 'offset size start end')
Map = namedtuple('Map', 'addr perm offset dev inode pathname flag')

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

USERSPACE_JSON = 'http://patches04.kernelcare.com/userspace.json'
LOGLEVEL = os.environ.get('LOGLEVEL', 'ERROR').upper()
logging.basicConfig(level=LOGLEVEL, format='%(message)s')


def suppress_permission_error(default=None):

    def wrapper2(clbl):

        def wrapper(*args, **kwargs):
            try:
                return clbl(*args, **kwargs)
            except (IOError, OSError) as err:
                if err.errno == errno.EPERM or err.errno == errno.EACCES:
                    logging.warning('Permission error: {0}'.format(err))
                    return default
                else:
                    raise
        return wrapper

    return wrapper2


@suppress_permission_error()
def get_build_id(fileobj):

    try:
        header = fileobj.read(struct.calcsize(ELF64_HEADER))
        hdr = struct.unpack(ELF64_HEADER, header)
    except struct.error:
        # Can't read a header
        return

    (e_ident, e_type, e_machine, e_version, e_entry, e_phoff,
     e_shoff, e_flags, e_ehsize, e_phentsize, e_phnum,
     e_shentsize, e_shnum, e_shstrndx) = hdr

    # No program headers or not an ELF file
    if not e_ident.startswith(b'\x7fELF\x02\x01') or not e_phoff:
        return

    fileobj.seek(e_phoff)
    for idx in range(e_phnum):
        ph = fileobj.read(e_phentsize)
        (p_type, p_flags, p_offset, p_vaddr, p_paddr,
         p_filesz, p_memsz, p_align) = struct.unpack(ELF_PH_HEADER, ph)
        p_end = p_offset + p_filesz
        if p_type == PT_NOTE:
            fileobj.seek(p_offset)
            n_type = None
            while n_type != NT_GNU_BUILD_ID and fileobj.tell() <= p_end:
                nhdr = fileobj.read(struct.calcsize(ELF_NHDR))
                n_namesz, n_descsz, n_type = struct.unpack(ELF_NHDR, nhdr)
                fileobj.read(n_namesz)
                desc = struct.unpack("<{0}B".format(n_descsz), fileobj.read(n_descsz))
            if n_type is not None:
                return ''.join('{:02x}'.format(x) for x in desc)


def iter_maps(pid):
    with open('/proc/{:d}/maps'.format(pid), 'r') as mapfd:
        for line in mapfd:
            data = (line.split() + [None, None])[:7]
            yield Map(*data)


def get_ranges(pid, inode):
    result = []
    for mmap in iter_maps(pid):
        if mmap.inode == inode:
            start, _, end = mmap.addr.partition('-')
            offset, start, end = map(lambda x: int(x, 16), [mmap.offset, start, end])
            rng = Range(offset, end - start, start, end)
            result.append(rng)
    return result


def get_process_files(pid):
    result = set()
    for mmap in iter_maps(pid):
        if mmap.pathname and mmap.flag not in ['(deleted)'] and mmap.pathname not in IGNORED_PATHNAME and not mmap.pathname.startswith('anon_inode:') and not mmap.pathname.startswith('/dev/'):
            result.add((mmap.pathname, mmap.inode))
    return result


class FileMMapped(object):

    def __init__(self, pid, inode):
        self.fileobj = open('/proc/{:d}/mem'.format(pid), 'rb')
        self.ranges = get_ranges(pid, inode)
        self.pos = 0
        self.fileobj.seek(self._get_range(0).start)

    def _get_range(self, offset):
        for rng in self.ranges:
            if rng.offset <= offset < rng.offset + rng.size:
                return rng
        raise ValueError("Offset {0} is not in ranges {1}".format(offset, self.ranges))

    def tell(self):
        return self.pos

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.fileobj.close()

    def close(self):
        self.fileobj.close()

    def seek(self, offset, whence=0):
        rng = self._get_range(offset)
        addr = rng.start + (offset - rng.offset)
        self.fileobj.seek(addr, whence)
        self.pos = offset

    def read(self, size):
        result = self.fileobj.read(size)
        self.pos += size
        return result


open_mmapped = FileMMapped


def get_comm(pid):
    comm_filename = '/proc/{:d}/comm'.format(pid)
    with open(comm_filename, 'r') as fd:
        return fd.read().strip()


def iter_pids():
    for pid in os.listdir('/proc/'):
        try:
            yield int(pid)
        except ValueError:
            pass


def iter_proc_map():
    for pid in iter_pids():
        for pathname, inode in get_process_files(pid):
            yield pid, inode, pathname


def iter_proc_lib():
    cache = {}
    for pid, inode, pathname in iter_proc_map():
        if inode not in cache:
            # If mapped file exists and has the same inode
            if os.path.isfile(pathname) and os.stat(pathname).st_ino == int(inode):
                fileobj = open(pathname, 'rb')
            # If file exists only as a mapped to the mempory
            else:
                fileobj = open_mmapped(pid, inode)
                logging.warning("Library `%s` was gathered from memory.", pathname)

            try:
                cache[inode] = get_build_id(fileobj)
            finally:
                fileobj.close()

        build_id = cache[inode]
        yield pid, os.path.basename(pathname), build_id


def main():
    data = json.load(urlopen(USERSPACE_JSON))
    failed = False
    for pid, libname, build_id in iter_proc_lib():
        comm = get_comm(pid)
        logging.debug("For %s[%s] `%s` was found with buid id = %s",
                      comm, pid, libname, build_id)
        if libname in data and build_id and data[libname] != build_id:
            failed = True
            logging.error("Process %s[%s] linked to the `%s` that is not up to date",
                          comm, pid, libname)
    if not failed:
        print("Everything is OK.")


if __name__ == '__main__':
    exit(main())

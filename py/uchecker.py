#!/usr/bin/env python


import os
import json
import subprocess
import tempfile
import codecs
import collections
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

USERSPACE_JSON = 'http://patches04.kernelcare.com/userspace.json'


def get_build_id(filename):
    try:
        raw = subprocess.check_output(["objcopy", filename, "/dev/null", "--dump-section", ".note.gnu.build-id=/dev/stdout"], stderr=subprocess.PIPE)
        return codecs.getencoder('hex')(raw[16:])[0]
    except subprocess.CalledProcessError:
        pass


def get_comm(pid):
    comm_filename = '/proc/{:d}/comm'.format(pid)
    with open(comm_filename, 'r') as fd:
        return fd.read().strip()


def get_build_id_from_memory(pid, ranges):
    mem_filename = '/proc/{:d}/mem'.format(pid)
    with tempfile.NamedTemporaryFile() as f:
        for adr, offset in ranges:
            start, end, offset = map(lambda x: int(x, 16), adr.split('-') + [offset, ])
            if not os.path.exists(mem_filename):
                continue
            subprocess.call([
                "dd", "skip={:d}".format(start), "count={:d}".format(end - start), "seek={:d}".format(offset),
                "if={:s}".format(mem_filename), "of={:s}".format(f.name),
                "bs=1", "status=none", "conv=notrunc"
            ], stderr=subprocess.PIPE)
        return get_build_id(f.name)


def iter_pids():
    for pid in os.listdir('/proc/'):
        try:
            yield int(pid)
        except ValueError:
            pass


def iter_proc_map():
    for pid in iter_pids():
        data = collections.defaultdict(list)
        maps_filename = '/proc/{:d}/maps'.format(pid)
        if not os.path.exists(maps_filename):
            continue
        with open(maps_filename, 'r') as mapfd:
            for line in mapfd:
                adr, _, offset, _, inode, pathname = (line.split() + [None, ])[:6]
                data[(pathname, inode)].append([adr, offset])
        for pathname, inode in data:
            yield pid, inode, pathname, data[(pathname, inode)]


def iter_proc_lib():
    cache = {}
    for pid, inode, pathname, ranges in iter_proc_map():
        if pathname and pathname not in ["[heap]", "[stack]", "[vdso]", "[vsyscall]"] and pathname.endswith('.so'):
            if inode not in cache:
                # If mapped file exists and has the same inode
                if os.path.isfile(pathname) and os.stat(pathname).st_ino == int(inode):
                    build_id = get_build_id(pathname)
                else:
                    build_id = get_build_id_from_memory(pid, ranges)
                cache[inode] = build_id
            yield pid, os.path.basename(pathname), cache[inode]


def main():
    data = json.load(urlopen(USERSPACE_JSON))
    for pid, libname, build_id in iter_proc_lib():
        if libname in data and build_id and data[libname] != build_id:
            print("Process {0}[{1}] linked to the `{2}` that is not up to date".format(get_comm(pid), pid, libname))


if __name__ == '__main__':
    exit(main())

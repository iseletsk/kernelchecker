#!/usr/bin/env python

import os
import json
import errno
import subprocess
import tempfile
import collections
import logging

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

USERSPACE_JSON = 'http://patches04.kernelcare.com/userspace.json'
LOGLEVEL = os.environ.get('LOGLEVEL', 'ERROR').upper()
logging.basicConfig(level=LOGLEVEL, format='%(message)s')


def suppress_permission_error(default):

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


def get_build_id(filename):
    try:
        raw = subprocess.check_output(["eu-readelf", "-n", str(filename)], stderr=subprocess.PIPE).decode()
    except (subprocess.CalledProcessError, UnicodeDecodeError) as err:
        logging.warning(err)
        return None

    for line in raw.split('\n'):
        if line.strip().startswith("Build ID"):
            _, _, buildid = line.partition(": ")
            return buildid


def get_comm(pid):
    comm_filename = '/proc/{:d}/comm'.format(pid)
    with open(comm_filename, 'r') as fd:
        return fd.read().strip()


@suppress_permission_error(default=None)
def get_build_id_from_memory(pid, ranges):
    mem_filename = '/proc/{:d}/mem'.format(pid)
    with tempfile.NamedTemporaryFile(suffix='.so', prefix='libcare-') as f:
        for adr, offset in ranges:
            start, end, offset = map(lambda x: int(x, 16), adr.split('-') + [offset, ])
            if not os.path.exists(mem_filename):
                continue
            cmd = [
                "dd",
                "skip={:d}".format(start),
                # "bs={:d}".format(end - start),
                # "count={:d}".format(1),
                # "bs={:d}".format(1),
                # "ibs={:d}".format(4096),
                # "obs={:d}".format(4096),
                "count={:d}".format(end - start),
                "seek={:d}".format(offset),
                "if={:s}".format(mem_filename),
                "of={:s}".format(f.name),
                "conv=notrunc",
                "iflag=skip_bytes,count_bytes",
                "oflag=seek_bytes"
            ]
            try:
                subprocess.check_call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            except subprocess.CalledProcessError as err:
                logging.warning(err)
        return get_build_id(f.name)


def iter_pids():
    for pid in os.listdir('/proc/'):
        try:
            yield int(pid)
        except ValueError:
            pass


@suppress_permission_error(default={})
def parse_map_file(filename):
    data = collections.defaultdict(set)
    with open(filename, 'r') as mapfd:
        for line in mapfd:
            adr, perm, offset, _, inode, pathname, flag = (line.split() + [None, None])[:7]
            if flag not in ['(deleted)']:
                data[(pathname, inode)].add((adr, offset))
    return data


def iter_proc_map():
    for pid in iter_pids():
        maps_filename = '/proc/{:d}/maps'.format(pid)
        if not os.path.exists(maps_filename):
            continue
        data = parse_map_file(maps_filename)
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
                    logging.warning("Library `%s` was gathered from memory.", pathname)
                    build_id = get_build_id_from_memory(pid, ranges)
                cache[inode] = build_id
            yield pid, os.path.basename(pathname), cache[inode]


def main():
    data = json.load(urlopen(USERSPACE_JSON))
    failed = False
    for pid, libname, build_id in iter_proc_lib():
        comm = get_comm(pid)
        logging.debug("For %s[%s] `%s` was found with buid id = %s", comm, pid, libname, build_id)
        if libname in data and build_id and data[libname] != build_id:
            failed = True
            logging.error("Process %s[%s] linked to the `%s` that is not up to date", comm, pid, libname)
    if not failed:
        print("Everything is OK.")


if __name__ == '__main__':
    exit(main())

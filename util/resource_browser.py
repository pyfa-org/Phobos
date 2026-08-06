import csv
import hashlib
import os
from collections import namedtuple

from util import cachedproperty


FileInfo = namedtuple('FileInfo', ('resource_path', 'file_relpath', 'file_abspath', 'file_hash', 'file_size', 'compressed_size'))


def get_full_alias(short_alias):
    full_aliases = {
        'tq': 'tranquility',
        'sisi': 'singularity'}
    return full_aliases.get(short_alias, short_alias)


class ResourceBrowser(object):
    """
    Class, responsible for browsing and retrieval of resources.
    """

    def __init__(self, eve_path, server_alias):
        self._eve_path = eve_path
        self._server_alias = server_alias

    def respath_iter(self):
        """
        Aggregate filepaths from all resource files and return
        them in the form of single list.
        """
        for resource_path in self._resource_index:
            yield resource_path

    def get_file_info(self, resource_path, verify_content):
        """Return metadata for a resource, verifying the resource first if requested."""
        file_info = self._resource_index[resource_path]
        if verify_content:
            self.__verify_file(file_info=file_info)
        return file_info

    def get_file_data(self, resource_path):
        """Return file contents for requested resource."""
        file_info = self._resource_index[resource_path]
        file_path = file_info.file_abspath
        with open(file_path, 'rb') as f:
            data = f.read()
        self.__verify_data(data=data, file_info=file_info)
        return data

    def __verify_file(self, file_info):
        size = 0
        checksum = hashlib.md5()
        with open(file_info.file_abspath, 'rb') as resource_file:
            while True:
                chunk = resource_file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                checksum.update(chunk)
        if size != file_info.file_size:
            raise FileIntegrityError(u'file size mismatch when reading {}'.format(file_info.resource_path))
        if checksum.hexdigest() != file_info.file_hash:
            raise FileIntegrityError(u'file hash mismatch when reading {}'.format(file_info.resource_path))

    def __verify_data(self, data, file_info):
        if len(data) != file_info.file_size:
            raise FileIntegrityError('file size mismatch when reading {}'.format(file_info.resource_path))
        m = hashlib.md5()
        m.update(data)
        if m.hexdigest() != file_info.file_hash:
            raise FileIntegrityError('file hash mismatch when reading {}'.format(file_info.resource_path))

    @cachedproperty
    def _resource_index(self):
        index = {}
        res_index_path = os.path.join(self._eve_path, self._server_alias, 'resfileindex.txt')
        with open(res_index_path) as f:
            for resource_path, file_relpath, file_hash, file_size, compressed_size in csv.reader(f):
                index[resource_path] = FileInfo(
                    resource_path=resource_path,
                    file_relpath=os.path.join(*file_relpath.split('/')),
                    file_abspath=os.path.join(self._eve_path, 'ResFiles', *file_relpath.split('/')),
                    file_hash=file_hash,
                    file_size=int(file_size),
                    compressed_size=int(compressed_size))
        app_index_path = os.path.join(self._eve_path, 'index_{}.txt'.format(get_full_alias(self._server_alias)))
        with open(app_index_path) as f:
            for resource_path, file_relpath, file_hash, file_size, compressed_size, version in csv.reader(f):
                index[resource_path] = FileInfo(
                    resource_path=resource_path,
                    file_relpath=os.path.join(*file_relpath.split('/')),
                    file_abspath=os.path.join(self._eve_path, 'ResFiles', *file_relpath.split('/')),
                    file_hash=file_hash,
                    file_size=int(file_size),
                    compressed_size=int(compressed_size))
        return index


class FileIntegrityError(Exception):
    pass

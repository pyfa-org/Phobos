#===============================================================================
# Copyright (C) 2014 Anton Vorobyov
#
# This file is part of Phobos.
#
# Phobos is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Phobos is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Phobos. If not, see <http://www.gnu.org/licenses/>.
#===============================================================================


import os

from reverence import blue

from .abstract_miner import AbstractMiner
from .eve_normalize import EveNormalizer
from .exception import TableNameError


class CallData(object):
    """
    Simple container class for holding service call data, also provides
    printing functionality for error printing.
    """

    def __init__(self, rawinfo):
        # Info has one of 2 following formats:
        # ((service name, service arg1, service arg2, ...), call name, call arg1, call arg2, ...)
        # (service name, call name, call arg1, call arg2, ...)
        self.rawinfo = rawinfo

    @property
    def sdata(self):
        return self.rawinfo[0]

    @property
    def sname(self):
        if self.__is_composite_service_call() is False:
            return self.sdata
        else:
            return self.sdata[0]

    @property
    def sargs(self):
        if self.__is_composite_service_call() is False:
            return ()
        else:
            return self.sdata[1:]

    @property
    def cdata(self):
        return self.rawinfo[1:]

    @property
    def cname(self):
        return self.cdata[0]

    @property
    def cargs(self):
        return self.cdata[1:]

    def __is_composite_service_call(self):
        # If service info (1st element of info tuple) is tuple itself,
        # then service has some arguments passed to it, because otherwise
        # 1st element contains just service info
        if isinstance(self.rawinfo[0], (tuple, list)):
            return True
        else:
            return False

    def __repr__(self):
        sargs = u', '.join(unicode(i) for i in self.sargs)
        cargs = u', '.join(unicode(i) for i in self.cargs)
        return u'{}({})_{}({})'.format(self.sname, sargs, self.cname, cargs)

    def __eq__(self, other):
        """
        Comparison operator, which returns True when either data is equal
        or readable representation.
        """
        # Compare info only when other object actually has it
        try:
            other_rawinfo = other.rawinfo
        except AttributeError:
            pass
        else:
            if self.rawinfo == other_rawinfo is True:
                return True
        if unicode(self) == other:
            return True
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)


class CacheMiner(AbstractMiner):
    """
    Class, responsible for fetching data out of EVE client cache.
    """

    def __init__(self, path_eve, path_cache, server):
        # Initialize reverence
        self.eve = blue.EVE(path_eve, cachepath=path_cache, server=server)
        self.path_cachedcalls = os.path.join(self.eve.getcachemgr().machocachepath, 'CachedMethodCalls')

    def tablename_iter(self):
        calls = []
        # Cycle through CachedMethodCalls and find all .cache files
        for filename in sorted(os.listdir(self.path_cachedcalls)):
            fileext = os.path.splitext(filename)[1]
            filepath = os.path.join(self.path_cachedcalls, filename)
            if not os.path.isfile(filepath) or fileext != '.cache':
                continue
            with open(filepath, 'rb') as cachefile:
                # When reading fails due to some unexpected reason, skip file
                try:
                    filedata = cachefile.read()
                except KeyboardInterrupt:
                    raise
                except:
                    print(u'  unable to read cache file {}'.format(filename))
                    continue
            try:
                info, _ = blue.marshal.Load(filedata)
            except KeyboardInterrupt:
                raise
            except:
                print(u'  unable to load cache file {}'.format(filename))
                continue
            calldata = CallData(rawinfo=info)
            calls.append(calldata)
        for calldata in sorted(calls, key=str):
            yield calldata


    def get_table(self, calldata):
        try:
            cache_table = getattr(self.eve.RemoteSvc(calldata.sdata), calldata.cname)(*calldata.cargs)
        except AttributeError:
            msg = u'table "{}" is not available for miner {}'.format(calldata, type(self).__name__)
            raise TableNameError(msg)
        lines = EveNormalizer().run(cache_table)
        return lines

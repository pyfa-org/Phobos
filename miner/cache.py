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

    def __init__(self, sname='', sargs=(), cname='', cargs=()):
        # Here and further we use 's' prefix to indicate service-related attributes,
        # and 'c' as call-related attributes
        self.sname = sname
        self.sargs = sargs
        self.cname = cname
        self.cargs = cargs

    def __repr__(self):
        sargs = u', '.join(unicode(i) for i in self.sargs)
        cargs = u', '.join(unicode(i) for i in self.cargs)
        return u'{}({})_{}({})'.format(self.sname, sargs, self.cname, cargs)


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
            # Info has following format:
            # ((service name, service arg1, service arg2, ...), call name, call arg1, call arg2, ...)
            sdata, cname = info[0:2]
            cargs = info[2:]
            if isinstance(sdata, (tuple, list)):
                sname = sdata[0]
                sargs = sdata[1:]
            else:
                sname = sdata
                sargs = ()
            calldata = CallData(sname=sname, sargs=sargs, cname=cname, cargs=cargs)
            calls.append(calldata)
        for calldata in sorted(calls, key=str):
            yield calldata


    def get_table(self, calldata):
        if len(calldata.sargs) > 0:
            sdata = (calldata.sname, calldata.sargs)
        else:
            sdata = calldata.sname
        try:
            cache_table = getattr(self.eve.RemoteSvc(sdata), calldata.cname)(*calldata.cargs)
        except AttributeError:
            msg = u'table "{}" is not available for miner {}'.format(calldata, type(self).__name__)
            raise TableNameError(msg)
        lines = EveNormalizer().run(cache_table)
        return lines

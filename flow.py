#===============================================================================
# Copyright (C) 2014-2015 Anton Vorobyov
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


import re

from util import CachedProperty


class FlowManager(object):
    """
    Class for handling high-level flow of script.
    """

    def __init__(self, miners, writers):
        self._miners = miners
        self._writers = writers

    def run(self, filter_string, language):
        # Compose set with flow container names which will be
        # processed (all processed if empty)
        filter_set = set()
        filter_set.update(self._parse_filter(filter_string))
        spec = self._make_spec()
        # Set with flow names we will be actually dealing with
        flow_names = set(spec)
        # Filter something out only if filter was actually specified
        if filter_set:
            flow_names.intersection_update(filter_set)
        for miner in self._miners:
            # Take flow names belonging to this miner
            miner_flow_names = filter(lambda fn: spec[fn][0][0] is miner, flow_names)
            # Skip miner altogether if we do not plan to fetch anything
            # from it
            if not miner_flow_names:
                continue
            print(u'Miner {}:'.format(type(miner).__name__))
            for flow_name in sorted(miner_flow_names):
                print(u'  processing {}'.format(flow_name))
                src, dest = spec[flow_name]
                miner, miner_resolved_name = src
                # Fetch data from client
                try:
                    container_data = miner.get_data(miner_resolved_name, language=language, verbose=True)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(u'    failed to fetch data - {}: {}'.format(type(e).__name__, e))
                else:
                    # Write data using passed writers
                    for writer in self._writers:
                        writer_resolved_name = dest[writer]
                        try:
                            writer.write(writer_resolved_name, container_data)
                        except KeyboardInterrupt:
                            raise
                        except Exception as e:
                            print(u'    failed to write data with {} - {}: {}'.format(type(writer).__name__, type(e).__name__, e))
        # Print info messages about requested, but unavailable containers
        if filter_set:
            missing_set = filter_set.difference(spec)
            if missing_set:
                print('Containers which were requested, but are not available:')
                for flow_name in sorted(missing_set):
                    print(u'  {}'.format(flow_name))

    def _parse_filter(self, name_filter):
        """
        Take filter string and return set of container names.
        """
        name_set = NameSet()
        # Flag which indicates if we're within parenthesis
        # (are parsing argument substring)
        inarg = False
        pos_current = 0
        # Cycle through all parenthesis and commas, split string using
        # out-of-parenthesis commas
        for match in re.finditer('[(),]', name_filter):
            pos_start = match.start()
            pos_end = match.end()
            symbol = match.group()
            if symbol == ',' and inarg is False:
                name_set.add(name_filter[pos_current:pos_start])
                pos_current = pos_end
            elif symbol == ',' and inarg is True:
                continue
            elif symbol == '(' and inarg is False:
                inarg = True
            elif symbol == ')' and inarg is True:
                inarg = False
            else:
                msg = 'unexpected character "{}" at position {}'.format(symbol, pos_start)
                raise FilterParseError(msg)
        if inarg is True:
            msg = 'parenthesis is not closed'
            raise FilterParseError(msg)
        # Add last segment of string after last seen comma
        name_set.add(name_filter[pos_current:])
        return name_set

    def _make_spec(self):
        """
        Make specification on what we're processing: where
        to fetch data from, where exactly to write it to.
        """
        # Format: {flow name: ((miner, resolved miner name), {writer: resolved writer name})}
        spec = {}
        for flow_name, src in self._flow_src_map.items():
            dest = self._flow_dest_map[flow_name]
            spec[flow_name] = (src, dest)
        return spec

    @CachedProperty
    def _flow_src_map(self):
        """
        Resolve name collisions on cross-miner level by appending
        miner name to container name when necessary, as result -\
        compose map between flow names and miners/miner source names.
        Format: {flow name: (miner: resolved miner name)}
        """
        # Intermediate map
        # Format: {resolved miner name: [miners]}
        minerresolved_miner_map = {}
        for miner in self._miners:
            for miner_resolved_name in miner.contname_iter():
                miners = minerresolved_miner_map.setdefault(miner_resolved_name, [])
                miners.append(miner)
        flow_src_map = {}
        for miner_resolved_name, miners in minerresolved_miner_map.items():
            # If there're collisions, compose flow name by taking
            # resolved miner name and appending miner name to it
            if len(miners) > 1:
                for miner in miners:
                    flow_name = u'{}_{}'.format(miner_resolved_name, type(miner).__name__)
                    flow_src_map[flow_name] = (miner, miner_resolved_name)
            # Do not modify name if there're no collisions
            else:
                flow_src_map[miner_resolved_name] = (miners[0], miner_resolved_name)
        return flow_src_map

    @CachedProperty
    def _flow_dest_map(self):
        """
        Resolve possible issues on writer-specific level, and return
        mapping of flow names to writers/writer destination names.
        Format: {flow name: {writer: resolved writer name}}
        """
        flow_dest_map = {}
        for writer in self._writers:
            # Format: {flow name: safe writer name}
            flow_writersafe_map = {}
            # Transform proposed names into safe and resolve collisions
            for flow_name in self._flow_src_map:
                flow_writersafe_map[flow_name] = writer.secure_name(flow_name)
            flow_writerresolved_map = writer.resolve_name_collisions(flow_writersafe_map)
            for flow_name, writer_resolved_name in flow_writerresolved_map.items():
                dest = flow_dest_map.setdefault(flow_name, {})
                dest[writer] = writer_resolved_name
        return flow_dest_map


class NameSet(set):
    """
    Set derivative, which automatically strips added
    elements and actually adds them to internal storage
    only if they still contain something meaningful.
    """

    def add(self, name):
        name = name.strip()
        if name:
            set.add(self, name)


class FilterParseError(Exception):
    """
    When received filter string cannot be parsed,
    this exception is raised.
    """
    pass

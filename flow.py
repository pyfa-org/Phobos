#===============================================================================
# Copyright (C) 2014-2019 Anton Vorobyov
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


class FlowManager(object):
    """
    Class for handling high-level flow of script.
    """

    def __init__(self, miners, writers):
        self._miners = miners
        self._writers = writers

    def run(self, filter_string, language):
        filter_set = self._parse_filter(name_filter=filter_string)
        missing_set = set(filter_set)
        # Filter something out only if filter was actually specified
        for miner in self._miners:
            container_names = [
                cn for cn in miner.contname_iter()
                if not filter_set or cn in filter_set]
            if not container_names:
                continue
            print(u'Miner {}:'.format(miner.raw_name))
            for container_name in sorted(container_names):
                print(u'  processing {}'.format(container_name))
                missing_set.discard(container_name)
                # Fetch data from client
                try:
                    container_data = miner.get_data(container_name=container_name, language=language, verbose=True)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(u'    unable to fetch data - {}: {}'.format(type(e).__name__, e))
                else:
                    # Write data using passed writers
                    for writer in self._writers:
                        try:
                            writer.write(miner_name=miner.name, container_name=container_name, container_data=container_data)
                        except KeyboardInterrupt:
                            raise
                        except Exception as e:
                            print(u'    unable to write data with {} - {}: {}'.format(type(writer).__name__, type(e).__name__, e))
        # Print info messages about requested, but unavailable containers
        if missing_set:
            print(u'Containers which were requested, but are not available:')
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
                msg = u'unexpected character "{}" at position {}'.format(symbol, pos_start)
                raise FilterParseError(msg)
        if inarg is True:
            msg = 'parenthesis is not closed'
            raise FilterParseError(msg)
        # Add last segment of string after last seen comma
        name_set.add(name_filter[pos_current:])
        return name_set


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

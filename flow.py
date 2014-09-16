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


import re


class FilterParseError(BaseException):
    """
    When received filter string cannot be parsed,
    this exception is raised.
    """
    pass


class FlowManager(object):
    """
    Class for handling high-level flow of script.
    """

    def __init__(self, miners, writers):
        self._miners = miners
        self._writers = writers
        self.__name_source_map = None

    def run(self, name_filter):
        # Cycle through miners in the order they were provided
        for miner in sorted(self._name_source_map, key=self._miners.index):
            print(u'Miner {}:'.format(type(miner).__name__))
            for modified_name in sorted(self._name_source_map[miner]):
                print(u'  processing {}'.format(modified_name))
                source_name = self._name_source_map[miner][modified_name]
                # Consume errors thrown by miners, just print a message about it
                try:
                    container_data = miner.get_data(source_name)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(u'    failed to fetch data - {}: {}'.format(type(e).__name__, e))
                else:
                    for writer in self._writers:
                        try:
                            writer.write(modified_name, container_data)
                        except KeyboardInterrupt:
                            raise
                        except Exception as e:
                            print(u'    failed to write data with {} - {}: {}'.format(type(writer).__name__, type(e).__name__, e))

    @property
    def _name_source_map(self):
        """
        Resolve name collisions on cross-miner level by appending
        miner name to container name when necessary.
        """
        if self.__name_source_map is None:
            # Intermediate map
            # Format: {container name: [miners]}
            name_miner_map = {}
            for miner in self._miners:
                for original_name in miner.contname_iter():
                    miners = name_miner_map.setdefault(original_name, [])
                    miners.append(miner)
            # Format: {miner: {modified name: original name}}
            self.__name_source_map = {}
            for original_name, miners in name_miner_map.items():
                # If there're collisions, append miner name to container name
                if len(miners) > 1:
                    for miner in miners:
                        modified_name = u'{}_{}'.format(original_name, type(miner).__name__)
                        miner_containers = self.__name_source_map.setdefault(miner, {})
                        miner_containers[modified_name] = original_name
                # Do not modify name if there're no collisions
                else:
                    miner_containers = self.__name_source_map.setdefault(miners[0], {})
                    miner_containers[original_name] = original_name
        return self.__name_source_map

    def _parse_filter(self, name_filter):
        """
        Take filter string and return list of container names.
        """
        names = []
        # Flag which indicates if we're within parenthesis
        # (parsing argument substring)
        inarg = False
        pos_current = 0
        # Cycle through all parenthesis and commas, split string using
        # out-of-parenthesis commas
        for match in re.finditer('[(),]', name_filter):
            pos_start = match.start()
            pos_end = match.end()
            symbol = match.group()
            if symbol == ',' and inarg is False:
                # Also strip name from whitespace characters
                name = name_filter[pos_current:pos_start].strip()
                names.append(name)
                pos_current = pos_end
            elif symbol == ',' and inarg is True:
                pass
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
        names.append(name_filter[pos_current:].strip())
        return names

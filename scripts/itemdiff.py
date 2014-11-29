#!/usr/bin/env python3

import argparse
import enum
import json
import os.path
from collections import namedtuple
from datetime import datetime, timedelta, timezone


ChangedItem = namedtuple('ChangedItem', ('old', 'new'))
Changes = namedtuple('Changes', ('removed', 'changed', 'added'))


class Container:

    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)

    def __repr__(self):
        attrs = ', '.join('{}={}'.format(attr, self.__dict__[attr]) for attr in sorted(self.__dict__))
        return '{}({})'.format(type(self).__name__, attrs)


class Type(Container):

    def __init__(self, **kwargs):
        self.id = None
        self.published = None
        self.name = None
        self.group_id = None
        self.market_group_id = None
        self.attributes = {}
        self.effects = []
        Container.__init__(self, **kwargs)

    def __eq__(self, o):
        if (
            self.id != o.id or
            self.published != o.published or
            self.name != o.name or
            self.group_id != o.group_id or
            self.market_group_id != o.market_group_id or
            self.attributes != o.attributes or
            self.effects != o.effects
        ):
            return False
        else:
            return True

    def __neq__(self, o):
        return not self.__eq__(o)


@enum.unique
class BasicAttribs(enum.IntEnum):
    mass = 4
    capacity = 38
    volume = 161
    radius = 162


class DataLoader:

    def __init__(self, path_old, path_new):
        self.path_old = path_old
        self.path_new = path_new
        # Items
        self.items_old = {}
        self.items_new = {}
        self.load_item_data()
        # Names
        self.names_old = {}
        self.names_new = {}
        self.load_name_data()
        # Group-category relations
        self.group_cat_old = {}
        self.group_cat_new = {}
        self.load_group_categories()
        # Market group full paths
        self.market_path_old = {}
        self.market_path_new = {}
        self.load_market_paths()
        # Metadata
        self.version_old = None
        self.version_new = None
        self.timestamp_old = None
        self.timestamp_new = None
        self.load_metadata()

    # Item-related methods

    def load_item_data(self):
        for base_path, items in (
            (self.path_old, self.items_old),
            (self.path_new, self.items_new)
        ):

            for row in self.get_file(base_path, 'invtypes'):
                basic_attrs = {}
                for basic_attr in BasicAttribs:
                    basic_attrs[basic_attr.value] = row[basic_attr.name]
                type_id = row['typeID']
                items[type_id] = Type(
                    id=type_id,
                    published=row['published'],
                    name=row['typeName_en-us'],
                    group_id = row['groupID'],
                    market_group_id = row['marketGroupID'],
                    attributes=basic_attrs
                )

            for row in self.get_file(base_path, 'dgmtypeattribs'):
                type_id = row['typeID']
                try:
                    item = items[type_id]
                except KeyError:
                    continue
                item.attributes[row['attributeID']] = row['value']

            for row in self.get_file(base_path, 'dgmtypeeffects'):
                type_id = row['typeID']
                try:
                    item = items[type_id]
                except KeyError:
                    continue
                item.effects.append(row['effectID'])

    def get_removed_items(self, unpublished):
        typeids_old = self._get_old_typeids(unpublished)
        typeids_new = self._get_new_typeids(unpublished)
        return dict((tid, self.items_old[tid]) for tid in typeids_old.difference(typeids_new))

    def get_changed_items(self, unpublished):
        typeids_old = self._get_old_typeids(unpublished)
        typeids_new = self._get_new_typeids(unpublished)
        changed_items = {}
        for type_id in typeids_old.intersection(typeids_new):
            type_old = self.items_old[type_id]
            type_new = self.items_new[type_id]
            if type_old != type_new:
                changed_items[type_id] = ChangedItem(old=type_old, new=type_new)
        return changed_items

    def get_added_items(self, unpublished):
        typeids_old = self._get_old_typeids(unpublished)
        typeids_new = self._get_new_typeids(unpublished)
        return dict((tid, self.items_new[tid]) for tid in typeids_new.difference(typeids_old))

    def _get_old_typeids(self, unpublished):
        if unpublished:
            return set(self.items_old)
        else:
            return set(filter(lambda i: self.items_old[i].published, self.items_old))

    def _get_new_typeids(self, unpublished):
        if unpublished:
            return set(self.items_new)
        else:
            return set(filter(lambda i: self.items_new[i].published, self.items_new))

    # Methods related to mapping groups onto categories

    def load_group_categories(self):
        for base_path, group_cat in (
            (self.path_old, self.group_cat_old),
            (self.path_new, self.group_cat_new)
        ):
            for row in self.get_file(base_path, 'invgroups'):
                group_cat[row['groupID']] = row['categoryID']

    def get_group_category(self, group_id):
        try:
            return self.group_cat_new[group_id]
        except KeyError:
            return self.group_cat_old[group_id]

    # Market-related methods

    def load_market_paths(self):
        for base_path, market_path in (
            (self.path_old, self.market_path_old),
            (self.path_new, self.market_path_new)
        ):

            parent_map = {}

            market_data = self.get_file(base_path, 'mapbulk_marketGroups')
            for row in market_data:
                parent_map[row['marketGroupID']] = row['parentGroupID']

            def compose_chain(market_group_id):
                chain = [market_group_id]
                parent = parent_map[market_group_id]
                while parent is not None:
                    chain.append(parent)
                    parent = parent_map[parent]
                return chain

            for row in market_data:
                market_group_id = row['marketGroupID']
                market_path[market_group_id] = compose_chain(market_group_id)

    def get_market_path(self, mktgrp_id):
        try:
            return self.market_path_new[mktgrp_id]
        except KeyError:
            return self.market_path_old[mktgrp_id]

    # Name-related methods

    def load_name_data(self):
        for base_path, names in (
            (self.path_old, self.names_old),
            (self.path_new, self.names_new)
        ):

            type_names = names['types'] = {}
            for row in self.get_file(base_path, 'invtypes'):
                type_names[row['typeID']] = row['typeName_en-us']

            grp_names = names['groups'] = {}
            for row in self.get_file(base_path, 'invgroups'):
                grp_names[row['groupID']] = row['groupName_en-us']

            cat_names = names['categories'] = {}
            for row in self.get_file(base_path, 'invcategories'):
                cat_names[row['categoryID']] = row['categoryName_en-us']

            mktgrp_names = names['market_groups'] = {}
            for row in self.get_file(base_path, 'mapbulk_marketGroups'):
                mktgrp_names[row['marketGroupID']] = row['marketGroupName_en-us']

            attr_names = names['attribs'] = {}
            for row in self.get_file(base_path, 'dgmattribs'):
                attr_names[row['attributeID']] = row['attributeName']

            eff_names = names['effects'] = {}
            for row in self.get_file(base_path, 'dgmeffects'):
                eff_names[row['effectID']] = row['effectName']

    # Metadata stuff

    def load_metadata(self):
        metadata_old = self.get_metadata_fields(self.path_old)
        self.version_old = metadata_old['client_build']
        self.timestamp_old = metadata_old['dump_time']
        metadata_new = self.get_metadata_fields(self.path_new)
        self.version_new = metadata_new['client_build']
        self.timestamp_new = metadata_new['dump_time']

    def get_metadata_fields(self, path):
        fields = {}
        metadata = self.get_file(path, 'phbmetadata')
        for row in metadata:
            name = row['field_name']
            value = row['field_value']
            fields[name] = value
        return fields

    def get_type_name(self, type_id):
        return self.__get_name('types', type_id)

    def get_group_name(self, group_id):
        return self.__get_name('groups', group_id)

    def get_category_name(self, category_id):
        return self.__get_name('categories', category_id)

    def get_attr_name(self, attr_id):
        return self.__get_name('attribs', attr_id)

    def get_effect_name(self, effect_id):
        return self.__get_name('effects', effect_id)

    def get_mktgrp_name(self, mktgrp_id):
        return self.__get_name('market_groups', mktgrp_id)

    def __get_name(self, alias, entity_id):
        try:
            return self.names_new[alias][entity_id]
        except KeyError:
            return self.names_old[alias][entity_id]

    # Auxiliary methods

    def get_file(self, base_path, fname):
        """
        Loads contents of JSON file with specified name.
        """
        fpath = os.path.join(base_path, '{}.json'.format(fname))
        with open(fpath) as f:
            data = json.load(f)
        return data

    def category_iter(self):
        for category_id in sorted(set(self.names_old['categories']).union(self.names_new['categories'])):
            yield category_id

    def group_iter(self):
        for group_id in sorted(set(self.names_old['groups']).union(self.names_new['groups'])):
            yield group_id


class PrinterSkeleton:

    def __init__(self, data_loader, unpublished):
        self._dl = data_loader
        self._changes = self._get_changes_summary(unpublished)

    def _iter_category(self):
        """
        Iterate through all category IDs of categories
        which contain changed items.
        """
        cat_ids = set(self._dl.get_group_category(grp_id) for grp_id in self._changes)
        for cat_id in sorted(cat_ids, key=self._dl.get_category_name):
            cat_name = self._dl.get_category_name(cat_id)
            yield cat_id, cat_name

    def _iter_group(self, cat_id):
        """
        Iterate over group IDs of groups which contain
        changed items and belong to certain category.
        """
        grp_ids = set(filter(lambda grp_id: self._dl.get_group_category(grp_id) == cat_id, self._changes))
        for grp_id in sorted(grp_ids, key=self._dl.get_group_name):
            grp_name = self._dl.get_group_name(grp_id)
            yield grp_id, grp_name

    def _iter_types_removed(self, grp_id):
        """
        Iterate through all types which have been
        removed and belonged to given group.
        """
        removed = self._changes[grp_id].removed
        for type_ in sorted(removed.values(), key=lambda t: t.name):
            yield type_

    def _iter_types_changed(self, grp_id):
        """
        Iterate through all types which have been
        changed and belonged or now belong to given
        group.
        """
        changed = self._changes[grp_id].changed
        for type_id in sorted(changed, key=self._dl.get_type_name):
            yield changed[type_id].old, changed[type_id].new

    def _iter_types_added(self, grp_id):
        """
        Iterate through all types which have been
        added and belong to given group.
        """
        added = self._changes[grp_id].added
        for type_ in sorted(added.values(), key=lambda t: t.name):
            yield type_

    def _iter_attrib(self, item):
        """
        Iterate over attribute names and values of passed item.
        """
        for attr_id in sorted(item.attributes, key=self._dl.get_attr_name):
            attr_name = self._dl.get_attr_name(attr_id)
            attr_val = item.attributes[attr_id]
            yield attr_name, attr_val

    def _iter_effect(self, item):
        """
        Iterate over effect names of passed item.
        """
        for eff_id in sorted(item.effects, key=self._dl.get_effect_name):
            eff_name = self._dl.get_effect_name(eff_id)
            yield eff_name

    def _get_market_path(self, item):
        """
        Convert path exposed by loader into human-readable
        Path > To > Item's > Market > Group.
        """
        mktgrp = item.market_group_id
        if mktgrp is None:
            return None
        mkt_path = ' > '.join(self._dl.get_mktgrp_name(i) for i in reversed(self._dl.get_market_path(mktgrp)))
        return mkt_path

    def _get_changes_summary(self, unpublished):
        """
        Convert data exposed by loader into format specific for printing
        logic we're using - top-level sections are categories, then groups
        are sub-sections, and items are listed in these sub-sections.
        Format: {group ID: (removed, changed, added)}
        Removed and added: {type ID: type}
        Changed: {type ID: (old type, new type)}
        """
        changes = {}
        removed = self._dl.get_removed_items(unpublished)
        changed = self._dl.get_changed_items(unpublished)
        added = self._dl.get_added_items(unpublished)
        for grp_id in self._dl.group_iter():
            # Check which items were changed for this particular group
            filfunc = lambda i: removed[i].group_id == grp_id
            removed_grp = dict((i, removed[i]) for i in filter(filfunc, removed))
            filfunc = lambda i: added[i].group_id == grp_id
            added_grp = dict((i, added[i]) for i in filter(filfunc, added))
            filfunc = lambda i: changed[i].old.group_id == grp_id or changed[i].new.group_id == grp_id
            changed_grp = dict((tid, changed[tid]) for tid in filter(filfunc, changed))
            # Do not fill anything if nothing changed
            if not removed_grp and not changed_grp and not added_grp:
                continue
            # Fill container with data we gathered
            changes[grp_id] = Changes(removed=removed_grp, changed=changed_grp, added=added_grp)
        return changes


class moreindent:
    """
    Context manager for text printer's indentation.
    """

    def __init__(self, instance):
        self.instance = instance

    def __enter__(self):
        self.instance._indent_more()

    def __exit__(self, *exc_details):
        self.instance._indent_less()
        return False


class TextPrinter(PrinterSkeleton):
    """
    Print item changes as text.
    """

    def __init__(self, data_loader, unpublished, indent_increment):
        PrinterSkeleton.__init__(self, data_loader, unpublished)
        self._indent_length = 0
        self._indent_increment = indent_increment

    def run(self):
        self._print_metadata()
        self._print_categories()

    # Indentation stuff

    def _indent_more(self):
        self._indent_length += self._indent_increment

    def _indent_less(self):
        self._indent_length -= self._indent_increment

    @property
    def _indent(self):
        return ' ' * self._indent_length

    def _print_metadata(self):
        """
        Print version and timestamp info about dumps being compared.
        """
        tz_utc = timezone(timedelta(), 'UTC')
        time_fmt = '%Y-%m-%d %H:%M:%S %Z'
        time_old = datetime.fromtimestamp(self._dl.timestamp_old, tz=tz_utc).strftime(time_fmt)
        time_new = datetime.fromtimestamp(self._dl.timestamp_new, tz=tz_utc).strftime(time_fmt)
        print('{}Comparing EVE client versions:'.format(self._indent))
        with moreindent(self):
            print('{}{} (data extracted at {})'.format(self._indent, self._dl.version_old, time_old))
            print('{}{} (data extracted at {})'.format(self._indent, self._dl.version_new, time_new))
        print()

    def _print_categories(self):
        """
        Print data for all categories.
        """
        for cat_id, cat_name in self._iter_category():
            print('{}Category: {}'.format(self._indent, cat_name), end='\n\n')
            with moreindent(self):
                self._print_groups(cat_id)

    def _print_groups(self, cat_id):
        """
        Print data for all groups which belong to passed
        category.
        """
        for grp_id, grp_name in self._iter_group(cat_id):
            print('{}Group: {}'.format(self._indent, grp_name), end='\n\n')
            with moreindent(self):
                self._print_items_removed(grp_id)
                self._print_items_changed(grp_id)
                self._print_items_added(grp_id)

    def _print_items_removed(self, grp_id):
        """
        Print data for all removed items belonging to
        passed group.
        """
        for item in self._iter_types_removed(grp_id):
            print('{}[-] {}'.format(self._indent, item.name), end='\n\n')
            print()

    def _print_items_changed(self, grp_id):
        """
        Print data for all changed items belonging to
        passed group.
        """
        for old, new in self._iter_types_changed(grp_id):
            if old.group_id != new.group_id:
                # When item was moved from current group to another, print just
                # short notice about it, no details...
                if old.group_id == grp_id:
                    new_grp = self.dl.get_group_name(new.group_id)
                    new_cat = self.dl.get_category_name(self.dl.get_group_category((new.group_id)))
                    print('{}[*] {} (moved to {} > {})'.format(self._indent, new.name, new_cat, new_grp), end='\n\n')
                    continue
                # ...and details are written in the target group
                else:
                    old_grp = self.dl.get_group_name(old.group_id)
                    old_cat = self.dl.get_category_name(self.dl.get_group_category((old.group_id)))
                    suffix = ' (moved from {} > {})'.format(old_cat, old_grp)
            else:
                suffix = ''
            print('{}[*] {}{}'.format(self._indent, new.name, suffix))
            with moreindent(self):
                self._print_attrs_comparison(old, new)
                self._print_effects_comparison(old, new)
                self._print_market_group_comparison(old, new)
                self._print_published_comparison(old, new)
            print()

    def _print_items_added(self, grp_id):
        """
        Print data for all added items belonging to
        passed group.
        """
        for item in self._iter_types_added(grp_id):
            print('{}[+] {}'.format(self._indent, item.name))
            with moreindent(self):
                self._print_attrs(item)
                self._print_effects(item)
                self._print_market_group(item)
                self._print_published(item)
            print()

    def _print_attrs(self, item):
        """
        Print attributes for single item.
        """
        attribs = tuple(self._iter_attrib(item))
        if attribs:
            print('{}Attributes:'.format(self._indent))
            with moreindent(self):
                for attr_name, attr_val in attribs:
                    print('{}{}: {}'.format(self._indent, attr_name, attr_val))

    def _print_attrs_comparison(self, old, new):
        """
        Print attribute comparison for two items.
        """
        if old.attributes != new.attributes:
            print('{}Attributes:'.format(self._indent))
            attrid_rmvd = set(old.attributes).difference(new.attributes)
            attrid_changed = set(filter(lambda i: old.attributes[i] != new.attributes[i], set(new.attributes).intersection(old.attributes)))
            attrid_add = set(new.attributes).difference(old.attributes)
            for attr_id in sorted(attrid_rmvd.union(attrid_changed).union(attrid_add), key=self._dl.get_attr_name):
                with moreindent(self):
                    attr_name = self._dl.get_attr_name(attr_id)
                    if attr_id in attrid_rmvd:
                        attr_val = old.attributes[attr_id]
                        print('{}[-] {}: {}'.format(self._indent, attr_name, attr_val))
                    if attr_id in attrid_changed:
                        attr_val_old = old.attributes[attr_id]
                        attr_val_new = new.attributes[attr_id]
                        print('{}[*] {}: {} => {}'.format(self._indent, attr_name, attr_val_old, attr_val_new))
                    if attr_id in attrid_add:
                        attr_val = new.attributes[attr_id]
                        print('{}[+] {}: {}'.format(self._indent, attr_name, attr_val))

    def _print_effects(self, item):
        """
        Print effects for single item.
        """
        effects = tuple(self._iter_effect(item))
        if effects:
            print('{}Effects:'.format(self._indent))
            with moreindent(self):
                for eff_name in effects:
                    print('{}{}'.format(self._indent, eff_name))

    def _print_effects_comparison(self, old, new):
        """
        Print effect comparison for two items.
        """
        if old.effects != new.effects:
            print('{}Effects:'.format(self._indent))
            with moreindent(self):
                eff_rmvd = set(old.effects).difference(new.effects)
                eff_add = set(new.effects).difference(old.effects)
                for eff_id in sorted(eff_rmvd.union(eff_add), key=self._dl.get_effect_name):
                    eff_name = self._dl.get_effect_name(eff_id)
                    if eff_id in eff_rmvd:
                        print('{}[-] {}'.format(self._indent, eff_name))
                    if eff_id in eff_add:
                        print('{}[+] {}'.format(self._indent, eff_name))

    def _print_market_group(self, item):
        """
        Print market group for single item.
        """
        mkt_path = self._get_market_path(item)
        if mkt_path is not None:
            print('{}Market group:'.format(self._indent))
            with moreindent(self):
                print('{}{}'.format(self._indent, mkt_path))

    def _print_market_group_comparison(self, old, new):
        """
        Print market group comparison for two items.
        """
        if old.market_group_id != new.market_group_id:
            print('{}Market group:'.format(self._indent))
            with moreindent(self):
                mktgrp_old = self._get_market_path(old)
                mktgrp_new = self._get_market_path(new)
                print('{}From: {}'.format(self._indent, mktgrp_old))
                print('{}To: {}'.format(self._indent, mktgrp_new))

    def _print_published(self, item):
        """
        Print published flag for single item.
        """
        print('{}Published flag:'.format(self._indent))
        with moreindent(self):
            print('{}{}'.format(self._indent, bool(item.published)))

    def _print_published_comparison(self, old, new):
        """
        Print published flag comparison for two items.
        """
        if old.published != new.published:
            print('{}Published flag:'.format(self._indent))
            with moreindent(self):
                print('{}{} => {}'.format(self._indent, bool(old.published), bool(new.published)))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='This script pulls data out of EVE client and writes it in JSON format')
    parser.add_argument('-o', '--old', help='path to phobos JSON dump with old data', required=True)
    parser.add_argument('-n', '--new', help='path to phobos JSON dump with new data', required=True)
    parser.add_argument('-a', '--all', help='print data for all items, not just published', required=False, default=False, action='store_true')
    args = parser.parse_args()

    path_old = os.path.expanduser(args.old)
    path_new = os.path.expanduser(args.new)

    dl = DataLoader(path_old, path_new)
    TextPrinter(dl, unpublished=args.all, indent_increment=2).run()

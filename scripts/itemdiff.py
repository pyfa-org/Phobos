#!/usr/bin/env python3

import argparse
import enum
import json
import os.path
from collections import namedtuple


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
        self.items_old = {}
        self.items_new = {}
        self.load_item_data()
        self.names_old = {}
        self.names_new = {}
        self.load_name_data()
        self.group_cat_old = {}
        self.group_cat_new = {}
        self.load_group_categories()
        self.market_path_old = {}
        self.market_path_new = {}
        self.load_market_paths()

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

    def get_removed_items(self, published_only):
        typeids_old = self._get_old_typeids(published_only)
        typeids_new = self._get_new_typeids(published_only)
        return dict((tid, self.items_old[tid]) for tid in typeids_old.difference(typeids_new))

    def get_changed_items(self, published_only):
        typeids_old = self._get_old_typeids(published_only)
        typeids_new = self._get_new_typeids(published_only)
        changed_items = {}
        for type_id in typeids_old.intersection(typeids_new):
            type_old = self.items_old[type_id]
            type_new = self.items_new[type_id]
            if type_old != type_new:
                changed_items[type_id] = ChangedItem(old=type_old, new=type_new)
        return changed_items

    def get_added_items(self, published_only):
        typeids_old = self._get_old_typeids(published_only)
        typeids_new = self._get_new_typeids(published_only)
        return dict((tid, self.items_new[tid]) for tid in typeids_new.difference(typeids_old))

    def _get_old_typeids(self, published_only):
        if published_only:
            return set(filter(lambda i: self.items_old[i].published, self.items_old))
        else:
            return set(self.items_old)

    def _get_new_typeids(self, published_only):
        if published_only:
            return set(filter(lambda i: self.items_new[i].published, self.items_new))
        else:
            return set(self.items_new)

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

    # Name-related methods

    def load_name_data(self):
        for base_path, names in (
            (self.path_old, self.names_old),
            (self.path_new, self.names_new)
        ):

            attr_names = names['types'] = {}
            for row in self.get_file(base_path, 'invtypes'):
                attr_names[row['typeID']] = row['typeName_en-us']

            attr_names = names['groups'] = {}
            for row in self.get_file(base_path, 'invgroups'):
                attr_names[row['groupID']] = row['groupName_en-us']

            attr_names = names['categories'] = {}
            for row in self.get_file(base_path, 'invcategories'):
                attr_names[row['categoryID']] = row['categoryName_en-us']

            attr_names = names['market_groups'] = {}
            for row in self.get_file(base_path, 'mapbulk_marketGroups'):
                attr_names[row['marketGroupID']] = row['marketGroupName_en-us']

            attr_names = names['attribs'] = {}
            for row in self.get_file(base_path, 'dgmattribs'):
                attr_names[row['attributeID']] = row['attributeName']

            attr_names = names['effects'] = {}
            for row in self.get_file(base_path, 'dgmeffects'):
                attr_names[row['effectID']] = row['effectName']

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

    def __init__(self, data_loader):
        self.dl = data_loader

    def fake_run(self, published_only=False):
        changes = self.get_changes_summary(published_only=published_only)
        for cat_id in sorted(changes, key=self.dl.get_category_name):
            cat_changes = changes[cat_id]
            cat_name = self.dl.get_category_name(cat_id)
            print('Category: {}'.format(cat_name), end='\n\n')
            for grp_id in sorted(cat_changes, key=self.dl.get_group_name):
                grp_name = self.dl.get_group_name(grp_id)
                print('  Group: {}'.format(grp_name), end='\n\n')
                itm_rmvd, itm_chg, itm_add = cat_changes[grp_id]

                # Removed items
                for tid in sorted(itm_rmvd, key=lambda tid: itm_rmvd[tid].name):
                    print('    [-] {}'.format(itm_rmvd[tid].name), end='\n\n')

                # Changed items
                for tid in sorted(itm_chg, key=lambda tid: itm_chg[tid].new.name):
                    old = itm_chg[tid].old
                    new = itm_chg[tid].new
                    if old.group_id != new.group_id:
                        # If some item was moved from one group to another, it was added
                        # to both; here we print only small notice in group from which it
                        # was moved, and full data in target group
                        if old.group_id == grp_id:
                            new_grp = self.dl.get_group_name(new.group_id)
                            new_cat = self.dl.get_category_name(self.dl.get_group_category((new.group_id)))
                            print('    [*] {} (moved to {} > {})'.format(itm_chg[tid].new.name, new_cat, new_grp), end='\n\n')
                            continue
                        else:
                            old_grp = self.dl.get_group_name(old.group_id)
                            old_cat = self.dl.get_category_name(self.dl.get_group_category((old.group_id)))
                            suffix = ' (moved from {} > {})'.format(old_cat, old_grp)
                    else:
                        suffix = ''
                    print('    [*] {}{}'.format(itm_chg[tid].new.name, suffix))
                    if old.attributes != new.attributes:
                        print('      Attributes:')
                        attrid_rmvd = set(old.attributes).difference(new.attributes)
                        attrid_changed = set(filter(lambda i: old.attributes[i] != new.attributes[i], set(new.attributes).intersection(old.attributes)))
                        attrid_add = set(new.attributes).difference(old.attributes)
                        for attr_id in sorted(attrid_rmvd.union(attrid_changed).union(attrid_add), key=self.dl.get_attr_name):
                            attr_name = self.dl.get_attr_name(attr_id)
                            if attr_id in attrid_rmvd:
                                attr_val = old.attributes[attr_id]
                                print('        [-] {}: {}'.format(attr_name, attr_val))
                            if attr_id in attrid_changed:
                                attr_val_old = old.attributes[attr_id]
                                attr_val_new = new.attributes[attr_id]
                                print('        [*] {}: {} => {}'.format(attr_name, attr_val_old, attr_val_new))
                            if attr_id in attrid_add:
                                attr_val = new.attributes[attr_id]
                                print('        [+] {}: {}'.format(attr_name, attr_val))
                    if old.effects != new.effects:
                        print('      Effects:')
                        eff_rmvd = set(old.effects).difference(new.effects)
                        eff_add = set(new.effects).difference(old.effects)
                        for eff_id in sorted(eff_rmvd.union(eff_add), key=self.dl.get_effect_name):
                            eff_name = self.dl.get_effect_name(eff_id)
                            if eff_id in eff_rmvd:
                                print('        [-] {}'.format(eff_name))
                            if eff_id in eff_add:
                                print('        [+] {}'.format(eff_name))
                    if old.market_group_id != new.market_group_id:
                        print('      Market group:')
                        if old.market_group_id is None:
                            old_mktgrp = None
                        else:
                            old_mktgrp = ' > '.join(self.dl.get_mktgrp_name(i) for i in reversed(self.dl.market_path_old[old.market_group_id]))
                        if new.market_group_id is None:
                            new_mktgrp = None
                        else:
                            new_mktgrp = ' > '.join(self.dl.get_mktgrp_name(i) for i in reversed(self.dl.market_path_new[new.market_group_id]))
                        print('        From: {}'.format(old_mktgrp))
                        print('        To: {}'.format(new_mktgrp))
                    if old.published != new.published:
                        print('      Published flag:\n        {} => {}'.format(bool(old.published), bool(new.published)))

                    print()

                # Added items
                for tid in sorted(itm_add, key=lambda tid: itm_add[tid].name):
                    item = itm_add[tid]
                    print('    [+] {}'.format(item.name))
                    if item.attributes:
                        print('      Attributes:')
                        for attr_id in sorted(item.attributes, key=self.dl.get_attr_name):
                            attr_name = self.dl.get_attr_name(attr_id)
                            attr_val = item.attributes[attr_id]
                            print('        {}: {}'.format(attr_name, attr_val))
                    if item.effects:
                        print('      Effects:')
                        for eff_id in sorted(item.effects, key=self.dl.get_effect_name):
                            eff_name = self.dl.get_effect_name(eff_id)
                            print('        {}'.format(eff_name))
                    if item.market_group_id:
                        print('      Market group:')
                        mktgrp = ' > '.join(self.dl.get_mktgrp_name(i) for i in reversed(self.dl.market_path_new[item.market_group_id]))
                        print('        {}'.format(mktgrp))
                    print('      Published flag:\n        {}'.format(bool(item.published)))
                    print()

    def get_changes_summary(self, published_only):
        """
        Convert data exposed by loader into format specific for printing
        logic we're using - top-level sections are categories, then groups
        are sub-sections, and items are listed in these sub-sections.
        Format: {category ID: {group ID: (removed, changed, added)}}
        Removed and added: {type ID: type}
        Changed: {type ID: (old type, new type)}
        """
        changes = {}
        removed_items = self.dl.get_removed_items(published_only)
        changed_items = self.dl.get_changed_items(published_only)
        added_items = self.dl.get_added_items(published_only)
        for grp_id in self.dl.group_iter():
            # Check which items were changed for this particular group
            filfunc = lambda i: removed_items[i].group_id == grp_id
            removed_items_grp = dict((i, removed_items[i]) for i in filter(filfunc, removed_items))
            filfunc = lambda i: added_items[i].group_id == grp_id
            added_items_grp = dict((i, added_items[i]) for i in filter(filfunc, added_items))
            filfunc = lambda i: changed_items[i].old.group_id == grp_id or changed_items[i].new.group_id == grp_id
            changed_items_grp = dict((tid, changed_items[tid]) for tid in filter(filfunc, changed_items))
            # Do not fill anything if nothing changed
            if not removed_items_grp and not changed_items_grp and not added_items_grp:
                continue
            # Fill container with data we gathered
            cat_id = self.dl.get_group_category(grp_id)
            cat_changes = changes.setdefault(cat_id, {})
            cat_changes[grp_id] = Changes(removed=removed_items_grp, changed=changed_items_grp, added=added_items_grp)
        return changes


class TextPrinter(PrinterSkeleton):
    pass


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='This script pulls data out of EVE client and writes it in JSON format')
    parser.add_argument('-o', '--old', help='path to phobos JSON dump with old data', required=True)
    parser.add_argument('-n', '--new', help='path to phobos JSON dump with new data', required=True)
    args = parser.parse_args()

    path_old = os.path.expanduser(args.old)
    path_new = os.path.expanduser(args.new)

    dl = DataLoader(path_old, path_new)
    TextPrinter(dl).fake_run(published_only=False)




"""Cache dumper script, uses phobos to dump a json dump to disk"""


import argparse
import json
import os.path
import re
import sys

from reverence import blue


tags = re.compile("\<.+?\>")

ROLE_BONUS_TYPE = -1
MISC_BONUS_TYPE = -2


def striptags(text):
    return tags.sub("", text)

def getbonuses(bonusdata):
    for i, data in bonusdata.iteritems():
        if hasattr(data, 'bonus'):
            value = round(data.bonus, 1)
            if int(data.bonus) == data.bonus:
                value = int(data.bonus)
            text = cfg._localization.GetByLabel('UI/InfoWindow/TraitWithNumber', color="", value=value, unit=cfg.dgmunits.Get(data.unitID).displayName, bonusText=cfg._localization.GetByMessageID(data.nameID))
        else:
            text = cfg._localization.GetByLabel('UI/InfoWindow/TraitWithoutNumber', color="", bonusText=cfg._localization.GetByMessageID(data.nameID))

        bonus, text = text.split("<t>")

        return "%s %s" % (striptags(bonus), striptags(text))


def gettraits(fsdType):
    if not hasattr(fsdType, 'infoBubbleTypeBonuses'):
        return None
    type_traits = {}
    typeBonuses = fsdType.infoBubbleTypeBonuses
    for skillTypeID, skillData in typeBonuses.iteritems():
        type_skill_traits = type_traits.setdefault(skillTypeID, [])
        type_skill_traits.append(getbonuses(skillData))

    return type_traits




if __name__ == '__main__':
    try:
        major = sys.version_info.major
        minor = sys.version_info.minor
    except AttributeError:
        major = sys.version_info[0]
        minor = sys.version_info[1]
    if major != 2 or minor < 7:
        sys.stderr.write('This application requires Python 2.7 to run, but {0}.{1} was used\n'.format(major, minor))
        sys.exit()

    parser = argparse.ArgumentParser(description='This scripts dumps effects from an sqlite cache dump to mongo')
    parser.add_argument('-e', '--eve', help='path to eve folder', required=True)
    parser.add_argument('-c', '--cache', help='path to eve cache folder', required=True)
    parser.add_argument('-s', '--server', default='tranquility', help='server which was specified in EVE shortcut, defaults to tranquility')
    parser.add_argument('-j', '--json', help='output folder for the json files')
    parser.add_argument('-l', '--language', help='Which language to dump in. Suggested values: de, ru, en-us, ja, zh, fr, it, es', default='en-us')
    args = parser.parse_args()

    # Needed args & helpers
    evePath = os.path.expanduser(args.eve)
    cachePath = os.path.expanduser(args.cache)
    jsonPath = os.path.expanduser(args.json)

    eve = blue.EVE(evePath, cachepath=cachePath, server=args.server, languageID=args.language)
    cfg = eve.getconfigmgr()

    idTraitMap = {}

    for fsdId, fsdType in cfg.fsdTypeOverrides.iteritems():
        traits = gettraits(fsdType)
        if traits is not None:
            idTraitMap[fsdId] = traits


    with open(os.path.join(jsonPath, 'phobostraits.json'), 'w') as f:
        json.dump(idTraitMap, f, indent=4, encoding='cp1252')


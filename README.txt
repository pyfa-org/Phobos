Phobos is a cache dumper library,

its not as general purpose as reverence is, its sole purpose is to read cache tables and dump them out.
By default, a json writer is supplied, however, the code is general enough that the RowSetProcessor class could be used within another application.

The writers are made to be extendible, when more writers get written, they'll be added as extra scripts.


Basic usage:
Install it:
python27 setup.py install

Dump stuff:
python2.7 dumpToJson.py --eve c:/games/eve/ --cache c:/users/username/appdata/local/CCP/EVE/c_games_eve_tranquility/cache --output c:/tq

Or discover available service calls in your cache:
python2.7 discoverRemoteSvcCalls.py --eve c:/games/eve/ --cache c:/users/username/appdata/local/CCP/EVE/c_games_eve_tranquility/cache

Optionally, specify the -t argument to only dump certain tables to json

Please note that the output folder has to exist already.
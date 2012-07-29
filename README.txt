Phobos is a cache dumper library,

its not as general purpose as reverence is, its sole purpose is to read cache tables and dump them out.
By default, a json writer is supplied, however, the code is general enough that the RowSetProcessor class could be used within another application.

The writers are made to be extendible, when more writers get written, they'll be added as extra scripts.
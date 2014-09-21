Phobos is script for dumping EVE client data into JSON format.

How to use:
python run.py --eve=<path to EVE client> --cache=<path to EVE client cache>  --translate=<language> --json=<output folder> [--list=<comma-separated list of containers to dump>]

Example (how I usually launch it on Linux):
$ python run.py --eve="~/.wine_eve/drive_c/Program Files/CCP/EVE/" --cache="~/.wine_eve/drive_c/users/"$USER"/Local Settings/Application Data/CCP/EVE/c_program_files_ccp_eve_tranquility/" --translate=en-us --json=~/Desktop/phobos_dump_exp --list="invtypes, marketProxy()_GetMarketGroups(), metadata"

todo list:
- Add YAML file export (from embedFS contents)
- Add SQLite export (file in bulkdata)
- Add CachedObjects export
- Rework localization engine to support multi-language translations

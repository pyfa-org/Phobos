Phobos is script for dumping EVE client data into JSON format.

How to use:
python run_json.py --eve=<path to EVE client> --cache=<path to EVE client cache>  --json=<output folder>

Example (how I usually launch it on Linux):
$ python run_json.py --eve="~/.wine_eve/drive_c/Program Files/CCP/EVE/" --cache="~/.wine_eve/drive_c/users/"$USER"/Local Settings/Application Data/CCP/EVE/c_program_files_ccp_eve_tranquility/"  --json=~/Desktop/phobos_dump_tq

Output:
Everything is dumped into single folder (specified as --json argument). Files are named following way:
1) Metadata - single metadata.json file with eve client version and UNIX-style timestamp of when the dump was made
2) Bulk data - <table_name>.json, where table name is taken out of the list of available tables from reverence
3) Cached method calls - <service name>(service, arguments)_<call name>(call, arguments).json, e.g. marketProxy()_GetNewPriceHistory(10000002, 13244).json. Sometimes it is possible that there will be multiple files describing same call, thus final name might include original cache file name (e.g. marketProxy()_GetOrders(10000043, 39)_962.json & marketProxy()_GetOrders(10000043, 39)_5f8e.json)

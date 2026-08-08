# Phobos
Phobos is script for extracting EVE client static data into JSON format.

It uses collection of data miners which extract data from files of various formats. It does not provide stable "API" by design: if CCP changes data scheme within EVE client, output files will also change.

### A note on safety
Some data miners process executable or serialized client data and should be
treated carefully:

- FsdBuiltMiner: executes native loaders provided by the EVE client
- ResourcePickleMiner: [unpickles](https://docs.python.org/2.7/library/pickle.html) serialized python files

It doesn't mean that you should not use these miners. Generally speaking, if you trust EVE client and Phobos - you should have no issues with these miners. Phobos runs simple validation on files which will be worked upon (checksum according to the client's file registry). Still, it is recommended to run Phobos in some sandboxed environment (e.g. separate Wine prefix for Linux).

### Requirements

* Python 3.12
* 64-bit Python built for Windows is needed for FSD Built `.fsdbinary` loaders
* Dependencies from `requirements.txt` (`PyYAML` is used for external `.schema` files)

Install dependencies with `pip install -r requirements.txt`.

### Arguments:

* `--eve`: Required. Path to EVE client directory, e.g. `C:\CCP\EVE Online`.
* `--json`: Required. Output directory for JSON files.
* `--server`: Optional. Server to pull data from. Defaults to `tq`. Other options are `sisi`, `thunderdome` and `serenity`.
* `--cache`: Optional. Some miners extract data from the client cache directory. To enable those, pass a path to the cache, e.g. `C:\users\<user>\AppData\Local\CCP\EVE\<client directory>\cache`.
* `--translate`: Optional. Specifies language to which strings will be translated.
  * When option is not specified, nothing is translated.
  * When individual language is chosen (run script with `--help` argument for a list), localized text is written into the text field, replacing whatever was there. In case translation for requested language is not available, `en-us` translation is used as a fallback.
  * When `multi` option is passed, the text field is replaced by map with language and localized text instead, e.g. `"typeName": {"en-us": "Rifter", "ru": "Rifter"}`. Only languages which actually have a translation are listed, there are no fallbacks. When the field held a value of its own before translation, that value is kept in the same map under the `orig` key.
* `--list`: Optional. Specifies list of comma-separated 'containers' to extract. It uses names the script prints to stdout. For list of all available names you can launch script without specifying this option, as by default it extracts everything it can find.

### Example

    $ python run.py --eve=E:\eve\client\ --json=~\Desktop\phobos_tq_en-us --list="evetypes, marketgroups, metadata"

### Phobos-specific data
Besides raw data Phobos pulls from client, it provides a custom container.

#### phobos/metadata
Contains just two parameters: client version and UNIX timestamp of the time script was invoked.

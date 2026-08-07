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

* Python 2.7
* 64-bit Python built for Windows is needed for FSD Built `.fsdbinary` loaders
* Dependencies from `requirements.txt` (`PyYAML` is used for external `.schema` files)

Install dependencies with `pip install -r requirements.txt`.

### Arguments:

* `--eve`: Required. Path to EVE client directory, e.g. `C:\CCP\EVE Online`.
* `--json`: Required. Output directory for JSON files.
* `--server`: Optional. Server to pull data from. Defaults to `tq`. Other options are `sisi`, `thunderdome` and `serenity`.
* `--cache`: Optional. Some miners extract data from the client cache directory. To enable those, pass a path to the cache, e.g. `C:\users\<user>\AppData\Local\CCP\EVE\<client directory>\cache`.
* `--translate`: Optional. Specifies language to which strings will be translated. You can choose either individual languages (run script with `--help` argument for a list) or 'multi' option. For individual language, translation will be done in-place (replaces original text with localized text), for multi-language translation, original text is not modified, but new text fields are added, named using `<field name>_<language code>` convention (e.g. `typeName_en-us`). Multi-language translation mode is default.
* `--list`: Optional. Specifies list of comma-separated 'containers' to extract. It uses names the script prints to stdout. For list of all available names you can launch script without specifying this option, as by default it extracts everything it can find.

### Example

    $ python run.py --eve=E:\eve\client\ --json=~\Desktop\phobos_tq_en-us --list="evetypes, marketgroups, metadata"

### Phobos-specific data
Besides raw data Phobos pulls from client, it provides two custom containers.

#### phobos/metadata
Contains just two parameters: client version and UNIX timestamp of the time script was invoked.

#### phobos/traits
Traits for various ships. Data has the following format:

    Returned value:
      For single language: ({'typeID': int, 'traits': traits}, ...)
      For multi-language: ({'typeID': int, 'traits_en-us': traits, 'traits_ru': traits, ...}, ...)
      Traits: {'skills': (skill section, ...), 'role': role section, 'misc': misc section}
        // skills, role and misc fields are optional
      Section: {'header': string, 'bonuses': (bonus, ...)}
      Bonus: {'number': string, 'text': string}
        // number field is optional

For example, Cambion traits in JSON format:

    {
      "traits": {
        "role": {
          "bonuses": [
            {"number": "115%", "text": "bonus to kinetic Light Missile and Rocket damage"},
            {"number": "50%", "text": "reduction in module heat damage amount taken"},
            {"text": "·Can fit Assault Damage Controls"}
          ],
          "header": "Role Bonus:"
        }, 
        "skills": [
          {
            "bonuses": [{"number": "5%", "text": "bonus to Light Missile and Rocket Launcher rate of fire"}],
            "header": "Assault Frigates bonuses (per skill level):"
          },
          {
            "bonuses": [{"number": "4%", "text": "bonus to all shield resistances"}],
            "header": "Caldari Frigate bonuses (per skill level):"
          }
        ]
      },
      "typeID": 32788
    },

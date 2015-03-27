# Phobos
Phobos is script for dumping EVE client data into JSON format.

### How to use

    python run.py --eve=<path to EVE client> --res=<path to shared resource cache> --cache=<path to EVE client cache>  [--translate=<language>] --json=<output folder> [--list=<comma-separated list of containers to dump>]

### Example
(or, how I usually launch it on Linux)

    $ python run.py --eve="~/.wine_eve/drive_c/Program Files/CCP/EVE/" --res="~/.wine_eve/drive_c/users/Public/Application Data/CCP/EVE/SharedCache" --cache="~/.wine_eve/drive_c/users/"$USER"/Local Settings/Application Data/CCP/EVE/c_program_files_ccp_eve_tranquility/" --translate=en-us --json=~/Desktop/phobos_dump_tq --list="invtypes, marketProxy()_GetMarketGroups(), phbmetadata"

### Arguments:

* --eve: path to EVE client, on Windows usually C:\Program Files (x86)\CCP\EVE\;
* --res: path to shared cache with resources, on Windows usually C:\ProgramData\CCP\EVE\SharedCache\;
* --cache: path to client-server specific data (which contains client cache and settings), on Windows usually C:\Users\<user_name>\AppData\Local\CCP\EVE\c_program_files_ccp_eve_tranquility
* --translate: specify language to which strings will be translated. You can choose either individual languages (for a list - invoke script with --help argument) or 'multi' option. For individual language, translation will be done in-place (replaces original text with localized text), for multi-language translation - original text is not modified, but new text fields are added, named using <field name>_<language code> convention. Multi-language translation mode is default.
* --json: output folder for JSON files.
* --list: you can provide list of comma-separated 'containers' to dump, it uses names script prints to stdout. For list of all available names you can launch script without specifying this option (by default it dumps everything it can find).

### Phobos-specific data
Besides raw data Phobos pulls from client, it provides two custom containers.

#### phbmetadata
Contains just two parameters: client version and UNIX timestamp of the time script was invoked.

#### phbtraits
Traits for various ships. Data has following format:

    Returned value:
      For single language: ({'typeID': int, 'traits': traits}, ...)
      For multi-language: ({'typeID': int, 'traits_en-us': traits, 'traits_ru': traits, ...}, ...)
      Traits: {'skills': (skill section, ...), 'role': role section, 'misc': misc section}
        // skills, role and misc fields are optional
      Section: {'header': string, 'bonuses': (bonus, ...)}
      Bonus: {'number': string, 'text': string}
        // number field is optional

For example, Cambion traits in JSON format:

    [
      {
        "typeID": 32788,
        "traits": {
          "skills": [
            {
              "header": "Assault Frigates bonuses (per skill level):",
              "bonuses": [
                {
                  "text": "bonus to Light Missile and Rocket Launcher rate of fire",
                  "number": "5%"
                }
              ]
            },
            {
              "header": "Caldari Frigate bonuses (per skill level):",
              "bonuses": [
                {
                  "text": "bonus to all shield resistances",
                  "number": "4%"
                }
              ]
            }
          ],
          "role": {
            "header": "Role Bonus:",
            "bonuses": [
              {
                "text": "bonus to kinetic Light Missile and Rocket damage",
                "number": "115%"
              },
              {
                "text": "reduction in module heat damage amount taken",
                "number": "50%"
              }
            ]
          }
        }
      },
    ]

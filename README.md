# Phobos
Phobos is script for dumping EVE client data into JSON format.

### Dependencies

* [Reverence](https://github.com/ntt/reverence)

### Arguments:

* `--res`: Required.
     * Path to SharedCache with resources. eg: `C:\EVE\SharedCache`.
* `--json`: Required.
    * Output folder for JSON files.
* `--server`: Optional.
    * Server to pull data from. Defaults to `tranquility`. If server is Serenity, must set --eve option (如果服务器选择为“晨曦”，必须设置--eve的值，否则可能会出错).
* `--eve`: Optional.
    * Path to EVE client (this is different for each server). If none is provided, Phobos will try to resolve it under the `SharedCache` directory based on server provided. eg: `C:\EVE\SharedCache\tq`.
* `--cache`: Optional.
    * Path to client-server specific data (which contains client cache and settings). If none is provided, reverence will attempt to resolve it automatically. eg: `C:\Users\<user>\AppData\Local\CCP\EVE\c_eve_sharedcache_tq_tranquility`
* `--translate`: Optional.
    * Specify language to which strings will be translated. You can choose either individual languages (for a list, invoke script with `--help` argument) or 'multi' option. For individual language, translation will be done in-place (replaces original text with localized text), for multi-language translation, original text is not modified, but new text fields are added, named using `<field name>_<language code>` convention (eg: `typeName_en-us`). Multi-language translation mode is default.
* `--list`: Optional.
    * Specify list of comma-separated 'containers' to dump, it uses names script prints to stdout. For list of all available names you can launch script without specifying this option (by default it dumps everything it can find).

### A note on paths
When the new EVE launcher was introduced, it allowed the launching against test servers from within the launcher without having a separate installation of client per server. This was made possible by the Shared Resource Cache that the different client versions share between themselves.

When CCP first released the beta, the Shared Cache was usually located at `C:\ProgramData\CCP\EVE\SharedCache` and the old client was still used (eg: `C:\Program Data (x86)\CCP\EVE`). However, with the release of the new launcher, the default install path is `C:\EVE\SharedCache`, and the separate eve clients are located in sub directories of the Shared Cache (eg: `C:\EVE\SharedCache\tq`). Please note that the old client may still be available wherever it was installed; be sure not to use that one as it is no longer updated. Double check your paths.

### Example

    $ python run.py --res=C:\EVE\SharedCache --json=~\Desktop\phobos_dump_tq --translate=en-us --list="invtypes, marketProxy()_GetMarketGroups(), phbmetadata"

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

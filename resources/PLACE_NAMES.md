Place spellings in `place_name_aliases.json` are derived from GeoNames country
datasets for Denmark, Norway and Sweden, retrieved 2026-09-06.

Source: https://download.geonames.org/export/dump/
Attribution: GeoNames, https://www.geonames.org/
License: Creative Commons Attribution 4.0, https://creativecommons.org/licenses/by/4.0/

The derived data maps unambiguous ASCII spellings of populated places to their
Unicode names. Copenhagen/København aliases are added explicitly. Existing native
spellings take precedence, so names such as Aalborg are not mechanically changed.
Regenerate with `python scripts/build_place_name_aliases.py`.

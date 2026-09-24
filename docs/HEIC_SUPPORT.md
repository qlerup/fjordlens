# HEIC-understøttelse

Webappen, konverteringstjenesten og AI-tjenesten bruger alle `pillow-heif==1.4.0`.
Versionen er fastlåst, så genopbygninger bruger den samme testede HEIC-læser.
Konverteringen foregår fortsat lokalt.

Den tidligere begrænsning `<1.0` installerede 0.22.0 med libheif 1.19.7.
En konkret HEIC-fil fra iOS 18 kunne ikke læses med den version: libheif
meldte `Invalid input: No 'hvcC' box`, mens Pillow viste `cannot identify
image file`. Samme fil kunne afkodes og konverteres med 1.4.0/libheif 1.23.0.

## Kontrol ved opdatering

- Kontrollér både afkodning, JPEG-konvertering og bevarelse af EXIF.
- Kør konverteringstestene i Linux/Docker med `tests` på `PYTHONPATH`.
- Kontrollér health, datamapper, port og GPU-understøttelse efter genstart.
- Genprøv en berørt fil gennem den normale pipeline, inklusive miniature
  og ansigtsanalyse.

## Tilbagerulning

Gem de kørende images under særskilte rollback-tags før opdatering. Gem også
de tre requirements-filer, Compose-filerne og miljøkonfigurationen. Brug
applikationens egen `.env`; værtsprogrammets miljøvariabler må ikke overstyre
blandt andet `APP_PORT` og `DATA_DIR`.

Ved udrulningen 24. september 2026 blev der i Proxmox-container 1000 gemt
en backup med et færdigt rollback-script:

```sh
/opt/fjordlens-backups/heif-20260924-185719/rollback.sh
```

Scriptet gendanner de tidligere image-tags og requirements og genopretter
kun de tre berørte tjenester uden at genbygge. Backup-images skal bevares,
så længe tilbagerulning ønskes. Opdateringen ændrer ikke databaseskemaet;
tilbagerulning sletter ikke billeder eller allerede konverterede JPG-filer.

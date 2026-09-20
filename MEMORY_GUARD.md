# RAM-styring via FjordHub

Opdater først FjordHub og derefter FjordLens gennem FjordHub. FjordHub tilføjer
`FJORDLENS_MEMORY_GUARD=1` og startgrænser til installationens `.env`.
Ved selvstændig installation er funktionen som standard slået fra: ingen dynamiske
Docker-grænser, RAM-adgangskontrol eller automatisk oprydning fra denne funktion.
Et eksisterende eksplicit `FJORDLENS_MEMORY_GUARD=0` bevares ved opdatering.

Budgettet beregnes løbende som:

    tildelt RAM - andre processers RAM-forbrug - 2 GiB

Andre processer omfatter FjordHub, andre apps, systemprocesser og cache. Hele
FjordLens-stakken indgår: web, AI, konvertering og updater. LXC-grænsen bruges,
hvis den er lavere end maskinens fysiske RAM; swap tæller ikke som ledig RAM.
10 GiB i alt og 3 GiB til andre giver således et FjordLens-budget på 5 GiB.

Updateren måler via værtsmaskinens skrivebeskyttede `/proc` og cgroup-mounts samt
den eksisterende Docker-socket. Den fordeler budgettet mellem containerne og
kontrollerer, at Docker faktisk har anvendt RAM-grænserne. RAM+swap-grænsen
sættes lig RAM-grænsen, så stakken ikke fortsætter væksten i swap.

Tunge job venter på plads, og AI frigiver ledige modeller under pres. Det valgte
antal ansigtspladser er derfor et maksimum: 8 pladser kan køre samtidig, når
RAM-budgettet tillader det. Efter 45 sekunders ventetid kan jobbet fejle med en
RAM-budget-fejl og efterfølgende genkøres. Ukendte eller forældede målinger
blokerer nye tunge job. Eksisterende Docker-grænser bevares ved målefejl.

Grænserne beskytter mod ubegrænset vækst, men en proces kan stadig blive dræbt
af containerens OOM-grænse, hvis en enkelt allokering er for stor, eller andre
apps pludselig tvinger budgettet ned. De 2 GiB er en reserve i beregningen, ikke
en garanti mod andre apps, der selv opbruger hele maskinens RAM. Startgrænserne
gælder inden første gyldige måling; den dynamiske reserve er først aktiv derefter.

Indstillinger viser aktuelt FjordLens-budget, andre processers forbrug og reserve.
`Genkør manglende` vælger understøttede filer uden `faces_indexed_at`, svarende til
statuslinjens manglende-tal. En færdig fil med nul fundne ansigter genkøres ikke.

Diagnostik:

```sh
docker logs -f --tail 100 fjordlens-updater
docker exec fjordlens-ai python -c "import urllib.request; print(urllib.request.urlopen('http://fjordlens-updater:8090/memory').read().decode())"
docker exec -it fjordlens-ai python face_monitor.py --slots 8
docker stats fjordlens fjordlens-ai fjordlens-convert fjordlens-updater
```

Automatiske tests dækker budgetberegning, LXC-begrænsning, udløbne målinger,
reservationer, Docker-grænser og deaktiveret standalone-installation. Linux/Docker
OOM-adfærd og den konkrete servers cgroup-visning skal også kontrolleres efter
udrulning. Ingen billedfiler eller databaser slettes ved ændringen.

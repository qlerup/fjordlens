# RAM-styring via FjordHub

Opdater først FjordHub og derefter FjordLens gennem FjordHub. FjordHub tilføjer
`FJORDLENS_MEMORY_GUARD=1` og startgrænser til installationens `.env`.
Ved selvstændig installation er funktionen som standard slået fra: ingen dynamiske
Docker-grænser, RAM-adgangskontrol eller automatisk oprydning fra denne funktion.
FjordHub reparerer også gamle `Guard=0`/ubegrænsede installationer, selv når
FjordLens allerede er opdateret. Hub kontrollerer installationen ved opstart og
hvert minut; aktivering bygger og genskaber FjordLens-containerne én gang.

Budgettet beregnes løbende som:

    tildelt RAM - andre processers RAM-forbrug - 2 GiB

Andre processer omfatter FjordHub, andre apps og systemprocesser. Hele
FjordLens-stakken indgår: web, AI, konvertering og updater. Målingerne kommer fra
FjordHubs ressourceoversigt (Proxmox LXC-total og Docker-forbrug). Swap tæller ikke
som ledig RAM. Mangler en gyldig systemmåling i Hub, startes nye tunge job ikke.
10 GiB i alt og 3 GiB til andre giver således et FjordLens-budget på 5 GiB.

Updateren henter budgettet fra FjordHub via en API beskyttet med appens Hub-nøgle.
Den ændrer aldrig andre apps' grænser. Den fordeler budgettet mellem egne containere og
kontrollerer, at Docker faktisk har anvendt RAM-grænserne. RAM+swap-grænsen
sættes lig RAM-grænsen, så stakken ikke fortsætter væksten i swap.

Tunge job venter på plads, og AI frigiver ledige modeller under pres. Det valgte
antal ansigtspladser er derfor et maksimum: 8 pladser kan køre samtidig, når
RAM-budgettet tillader det. Konverteringsjob venter på plads uden RAM-kontrollens
tidligere 45-sekunders timeout; `memory_wait` og `memory_resume` logges ved ventetid.
Fordelingen afsætter plads til et konverteringsjob før den vægtede fordeling af
overskuddet, hvis budgettet tillader det. Andre job kan efter 45 sekunders ventetid
fejle med en RAM-budget-fejl og efterfølgende genkøres. Ukendte eller forældede målinger
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

Automatiske tests dækker Hub-budgetberegning, automatisk aktivering, udløbne målinger,
reservationer, Docker-grænser og deaktiveret standalone-installation. Linux/Docker
OOM-adfærd og den konkrete servers cgroup-visning skal også kontrolleres efter
udrulning. Ingen billedfiler eller databaser slettes ved ændringen.

## Rettelse efter OOM 21. september 2026

RAM-styringen udskyder nu en reduktion, hvis den nye grænse ligger for tæt på det målte forbrug (1 GiB margin for AI, 512 MiB for andre tjenester). I så fald bevares de eksisterende hårde grænser, og admission sættes på pause. Summen af de eksisterende grænser kan midlertidigt overstige det nye budget; igangværende arbejde får mulighed for at afslutte. Dette beskytter ikke mod enhver pludselig allokering eller værts-OOM.

Web og AI har nu 2 GiB som fordelingsminimum, når budgettet tillader det. Billedforberedelse serialiseres i webappen og får RAM-adgangskontrol. AI pakker først billedet ud efter tildeling af en model. Matchcache læser JSON-rækker løbende. Midlertidige forbindelsesfejl og HTTP 502/503/504 holder samme køelement til genforsøg, med fem sekunders pause og én genoptagelsesprøve ad gangen. Stop-knappen afslutter ventetiden; en allerede aktiv HTTP-forespørgsel afsluttes efter sin timeout. Statusmonitoren venter ikke længere på modellås eller budgetserver.

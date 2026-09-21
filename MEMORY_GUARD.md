# F?lles RAM-styring for hele FjordHub

FjordLens bruger FjordHubs samlede RAM-m?ling for v?rten/LXC-containeren ?
samme samlede forbrug som ressourceoversigten. Forbruget inkluderer FjordHub,
FjordLens og alle andre processer. Det er ikke kun AI-containerens forbrug,
og tallet ?andre/system? bruges ikke l?ngere til at fordele RAM.

    ledig jobplads = samlet RAM - samlet aktuelt forbrug - 2 GiB reserve - jobreservationer

Eksempel: 10 GiB samlet, 4,88 GiB brugt og ingen reservationer giver 3,12 GiB
til nye tunge job. Swap t?ller ikke som ledig RAM. Status viser samlet
forbrug/total, reserve, reservationer og ledig jobplads.

## ?n f?lles reservationstjeneste

Updateren henter de eksisterende `total_bytes` og `used_bytes` fra FjordHubs
n?glebeskyttede RAM-endpoint. Web, AI og konvertering reserverer deres estimerede
behov atomisk hos updateren f?r tungt arbejde. Samtidige job kan derfor ikke
alle tage den samme ledige plads. Reservationen er en forsigtig ekstra margen;
allerede allokeret hukommelse kan samtidig indg? i v?rtsm?lingen.

Reservationer fornyes hvert 20. sekund og udl?ber efter 120 sekunder uden
fornyelse. De gemmes i updaterens `/state/memory-leases.json` og overlever dens
genstart. N?r et job afsluttes, beholdes reservationen indtil n?ste friske
v?rtsm?ling, s? en gammel m?ling ikke genbruges f?r nye modeller/buffere t?lles med.
Ved crash frigives reservationen efter udl?b. Indlejrede operationer reserverer
kun deres ekstra behov. Fejlede eller over 10 sekunder gamle v?rtsm?linger
blokerer nye job; allerede igangv?rende arbejde afbrydes ikke.

Jobestimaterne er ikke pr?cise m?linger af deres maksimale forbrug. Store enkeltfiler,
andre apps og bortfald af reservationernes fornyelse kan stadig medf?re RAM-pres.
Den samlede LXC-gr?nse er den sidste beskyttelse, og der er ingen garanti mod OOM.

## Opgradering og Docker-gr?nser

Opdater hele FjordLens-stakken, inklusive updater, AI og konvertering, gennem
FjordHub. Der kr?ves ikke en ny FjordHub-version for det eksisterende RAM-endpoint.
`FJORDLENS_MEMORY_GUARD=1` aktiverer funktionen; selvst?ndige installationer er
som f?r deaktiveret som standard.

Updateren h?ver de gamle individuelle Docker-gr?nser til v?rtens samlede
RAM-loft og kontrollerer dem ved readback. Den fordeler ikke l?ngere en fast
andel til hver tjeneste og s?nker ikke gr?nser under igangv?rende arbejde.
Hver tjeneste kan bruge den f?lles plads, men hele LXC-containerens faktiske
forbrug er stadig begr?nset af Proxmox. Summen af de individuelle loftstal er
ikke en RAM-reservation. Andre apps' gr?nser ?ndres ikke.

Eksisterende boot-gr?nser g?lder indtil updateren har verificeret m?lingen og
h?vet gr?nserne. Gamle klienter f?r ikke nye jobbudgetter af den nye updater;
alle billeder skal opdateres samlet. Nye klienter beholder den gamle kontrol,
hvis updateren endnu ikke er opdateret. Tilbagef?r hele stakken ved rollback;
bland ikke gamle og nye tjenester permanent.

## Ansigtsk? og monitor

Webappen forbereder ?t billede ad gangen. AI pakker f?rst billedet ud efter
at have f?et en model. Matchcache l?ser JSON-r?kker l?bende. Midlertidige
forbindelsesfejl og HTTP 502/503/504 holder samme k?element til genfors?g
med fem sekunders pause og ?n genoptagelsespr?ve ad gangen.

Konvertering venter p? RAM uden timeout. Andre tunge operationer kan efter
45 sekunder melde ventetid; ansigtsk?en beholder elementet til genfors?g.
Stop afslutter k?ens ventetid, men et aktivt HTTP-kald m? f?rst afsluttes eller
time ud. Statusmonitoren blokeres ikke af modelindl?sning eller budgetserveren.

```sh
docker logs -f --tail 100 fjordlens-updater
docker exec fjordlens-ai python -c "import urllib.request; print(urllib.request.urlopen('http://fjordlens-updater:8090/memory').read().decode())"
docker exec -it fjordlens-ai python face_monitor.py --slots 8
docker stats fjordlens fjordlens-ai fjordlens-convert fjordlens-updater
```

## Ansigtsgenkendelse p? videoer

Under Ansigtsindeksering gemmer togglen valget for videoanalyse (standard: til).
N?r den sl?s fra, springer uploadk? og manuel indeksering videoer over, og de
udelades fra manglende-tallet. En igangv?rende video stopper f?r n?ste frame;
et aktivt AI-kald kan afsluttes f?rst. Eksisterende ansigter og indeksmarkeringer
bevares. Oversprungne videoer registreres ikke som fejl eller f?rdiganalyserede.
Sl?s funktionen til igen, kan manglende videoer genk?res. Kun administratorer
kan ?ndre indstillingen.

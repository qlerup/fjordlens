# Momenter

Åbn **Momenter → Find nye momenter** som administrator. Scanningen bruger hele
det indekserede bibliotek, inklusive uploads, og fjerner ekstra lagerkopier af
samme upload. Der foretages ingen nye billedanalyser eller eksterne AI-kald under
scanningen. GPS uden stednavn slås op i den allerede installerede lokale
geografidatabase. Stedopslag efter attraktioner sender udvalgte koordinater til
OpenStreetMap/Overpass, men ingen billeder, datoer eller personoplysninger fra
billedbeskrivelserne. AI-fortælling bruges fortsat først, når diasshowet åbnes.

## Sådan findes oplevelser

- Byer i samme land og sammenhængende rejser på tværs af lande kan samles i én
  tur. Op til fire døgn uden billeder accepteres, når stedoplysningerne eller
  et kendt hjemområde understøtter sammenhængen. Hjemkomst afslutter turen.
- Hjemsted kræver mindst fem fotograferede dage over mindst 45 dage, så en
  billedrig ferie ikke alene bliver til et hjemsted. Analysen foretages separat
  for hver uploader. Under **Hjemområde** kan administratoren i stedet vælge et
  fælles fast hjemområde; med koordinater bruges en radius på 40 km.
- Gentagne dagsbesøg over længere tid behandles som hverdag. Usædvanligt mange
  billeder kan stadig udløse en dagsoplevelse. Antallet sammenlignes med
  uploaderens median af billeder på fotograferede dage.
- Dagsoplevelser kan være helt ned til en halv time. Gentagne eksisterende
  beskrivelser af zoo, strand eller skov kan give en mere relevant titel.
- Billeder uden GPS inkluderes kun i en kendt tur, når billeder fra samme
  uploader/kameratype omslutter dem inden for seks timer og viser et foreneligt
  sted. Andre billeder uden GPS kan danne selvstændige tidsbaserede forslag.
- Dagsgrupper fra forskellige kameraer/uploadere samles, når tid og sted passer
  sammen (op til seks timers mellemrum og højst otte km mellem stedpositionerne).
  Billeder uden GPS kan også samles med dagens eneste tidsmæssigt sammenfaldende
  destination. Det forklares som en usikker tilknytning; flere mulige destinationer
  forbliver adskilt. Et rent datosammenfald mellem to forskellige byer er ikke nok.
- Første og sidste billede giver datoerne. Det er ikke en garanti for de faktiske
  rejsedatoer. Manglende optagelsesdato bruger fildato med en forklaring om
  usikkerheden. Historiske optagelsesdatoer, der allerede blev udledt af fildato
  ved import, kan ikke skelnes sikkert uden yderligere dataproveniens.

**Hvorfor dette moment?** viser grundlaget og turens steder som kapitler.
Forslagene er heuristikker, ikke sikre konklusioner om ferie eller personers
ophold. Biblioteker med begrænset GPS/historik får mere forsigtige forslag.

## Attraktioner ved koordinaterne

For dagsoplevelser undersøges op til tre forskellige GPS-positioner. Overpass
søger først efter navngivne områder, som indeholder positionen, eksempelvis
forlystelsesparker, zoologiske haver, museer, akvarier og vandlande. Et flertal af
prøvepositionerne inden for samme område kan give en titel som **En dag i
LEGOLAND**. Nærliggende punkter inden for 100 meter markeres som mulige besøg;
de erstatter ikke titlen med et sikkert stednavn.

Der bruges højst 18 nye positionsopslag pr. scanning, nyeste oplevelser først.
Resultater gemmes i 30 dage, tomme resultater i syv dage og mislykkede opslag i
en time. Flere steder kan undersøges ved næste scanning. En reserveinstans
forsøges ved fejl; manglende netværk eller manglende kortdata stopper ikke den
almindelige momentanalyse. Miljøvariablen `MOMENT_POI_LOOKUP=0` slår opslag fra.

Steddata: [© OpenStreetMap-bidragydere](https://www.openstreetmap.org/copyright).
Områdeopslag følger [Overpass QL](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL).

## Film og billedkvalitet

Diasshowet bruger billedernes fulde visningsversion først og forudindlæser næste
billede. Thumbnails bruges kun som reserve, hvis visningsversionen ikke kan hentes.
MP4 eksporteres i **1920 × 1080 / 25 fps**, fra originalen eller dens fulde
visningskopi. Færdige videosegmenter samles uden en ekstra komprimering.

Filmene har en fælles tidslinje med åbningskort, sted-/datokapitler, varierede
billedtekster, diskrete klokkeslæt og afslutning. Serifoverskrifter kombineres med
enkle småtekster i varme hvide/guldfarver. Teksten animeres ind, og billederne
panorerer/zoomer langsomt. Browseren bruger bløde krydsfade; MP4 bruger korte
toninger gennem en mørk farve. Højformatfotos vises hele på en sløret baggrund.
Browseren respekterer indstillingen for reduceret bevægelse.

Ældre tidslinjer opgraderes automatisk ved åbning eller eksport. Brugerens titel
og billedvalg bevares. Eksisterende MP4-filer skal genereres igen for at få den
nye stil. Dato/tid vises ikke som fotograferingstid, når kun en fildato findes.

## Ret og organisér

Administratorer og medieadministratorer kan bruge **Rediger** til at:

- ændre titel og datoer;
- vælge/fravælge billeder og søge efter flere inden for datoer og gemte stednavne;
- flytte de valgte billeder til et nyt moment, mens resten bliver i det gamle;
- samle to momenter. Årsoversigter kan redigeres, men ikke opdeles eller samles.

Gem titel-/datoændringer før opdeling eller sammenlægning. Billederne slettes
ikke fra biblioteket, når de fravælges. En redigering låser momentets automatiske
medlemskab. Ny scanning opdaterer kun urørte forslag og genskaber ikke afviste,
slettede eller manuelt opdelte momenter. Gemte momenter bevares også, herunder
ældre gemte momenter, som kun indeholdt et udvalg fra den tidligere algoritme.
Manglende billeder kan tilføjes via søgningen i redigeringen.

Alle relevante billeder gemmes på nye momenter. Diasshowet vælger særskilt et
udvalg fordelt på dage og steder, prioriterer favoritter inden for grupperne og
fravælger lignende billedhashes. Det ændrer ikke momentets fulde billedliste.

Almindelige brugere ser kun et moment, hvis de har adgang til alle dets billeder.
Redigering afvises med en konfliktbesked, hvis momentet er ændret siden åbningen,
eller hvis en video er under opbygning.

## Drift og validering

Databasefelter til forklaringer, redigeringsmarkering og revision samt tabeller
til hjemområde og scanningsstatus oprettes automatisk af `init_db()`. Opgraderingen
bevarer eksisterende momenter. Scanningsstatus deles mellem serverprocesser;
en efterladt status kan genstartes efter en time.

De eksisterende `MOMENT_MIN_PHOTOS` (10, kan ikke sættes lavere), `MOMENT_MIN_SPAN_HOURS` (4),
`MOMENT_GAP_HOURS` (30), `MOMENT_MAX_SLIDES` (60),
`MOMENT_YEAR_REVIEW_MIN_PHOTOS` (30) og `MOMENT_YEAR_REVIEW_MAX_PHOTOS` (60)
bevares. Dagsoplevelser og stedunderstøttede rejsepauser har ovenstående særregler.

Kør de relevante tests fra projektmappen:

```sh
python -m unittest tests.test_moment_cinema tests.test_moments tests.test_moments_v2 tests.test_ui_design tests.test_manager_role
node --check static/app.js
node --check static/moments.js
```

# Musik til Fjordlens

16 MP3-numre fordelt på otte stemninger, med to varianter af hver:

| Stemning | Anvendelse | Filnavne |
|---|---|---|
| Vores dag | Bryllup og konfirmation | `wedding-1.mp3`, `wedding-2.mp3` |
| Sommerminder | Ferie og strand | `summer-1.mp3`, `summer-2.mp3` |
| På eventyr | Rejser og oplevelser | `adventure-1.mp3`, `adventure-2.mp3` |
| Små store øjeblikke | Børn og udflugter | `playful-1.mp3`, `playful-2.mp3` |
| Året der gik | Nostalgiske årsoversigter | `year-1.mp3`, `year-2.mp3` |
| Vinterlys | Jul og vinter | `winter-1.mp3`, `winter-2.mp3` |
| Stille stunder | Natur og rolige minder | `quiet-1.mp3`, `quiet-2.mp3` |
| Minder om dig | Eftertænksomme og personlige momenter | `memory-1.mp3`, `memory-2.mp3` |

Fjordlens vælger et startnummer ud fra momentets titel. I **Rediger diasshow**
kan du lytte, vælge et andet nummer, ændre lydstyrken eller vælge **Ingen musik**.
Musikken fortsætter mellem slides og gentages med et seks sekunders krydsfade.
MP4-eksporten bruger samme overgang og toner musikken ud ved filmens slutning.
På telefoner og delingslinks kan browseren kræve et tryk på **Slå musik til**.

`catalog.json` indeholder stabile ID'er, oprindelige titler, varigheder og
grænser for indledende/afsluttende stilhed. MP3-filerne er kopier af de leverede
originaler; beskæring foretages kun under afspilning/eksport. Numrene hentes
lokalt fra Fjordlens-serveren, ikke fra Suno eller en musiktjeneste.

Musikvalget gemmes på tidslinjen. Nye delingslinks gemmer deres egen version;
senere ændringer af nummer eller lydstyrke ændrer ikke eksisterende links.
Ældre links uden musikvalg får et fast startnummer ud fra deres gemte titel.

Se [COPYRIGHT.md](COPYRIGHT.md) for rettigheder og tilladt brug.

# Fejlede filer

I **Logs** fjerner **Ryd filens fejl** alle eksisterende logfejl for den valgte
fil på tværs af behandlingstrin. Midlertidige konverteringsstier regnes som
samme fil; ens filnavne i forskellige mapper ryddes hver for sig. Fejl uden
filsti har **Ryd fejl**, som kun fjerner den valgte logpost. Rydningen gemmes
og overlever genstart. Nye fejl vises stadig, og selve billedfilen og listen
**Fejlede filer** ændres ikke. Den almindelige **Ryd** bevarer fortsat uløste fejl.

Administratorer finder **Fejlede filer** i indstillingerne ved ansigtsindeksering.
Vælg **Vis / opdater fejl** for at se filnavn, behandlingstrin og seneste fejl.
**Prøv igen** genkører ét fejlet trin; **Genkør fejlede trin** tager en enkelt
gennemgang af de registrerede fejl, én fil og ét trin ad gangen.

Fejl ved metadata, konvertering, miniaturer, ansigter, AI-beskrivelser og
AI-embeddings gemmes i SQLite-tabellen `processing_failures`. Listen overlever
genstart og kræver ikke, at filen allerede har en række i billedindekset.
Et vellykket trin fjerner kun fejlen for netop den fil og det trin. En tom,
vellykket ansigtsanalyse er gyldig; en manglende AI-respons er en fejl.

Konverteringsgenkørsel bruger den eksisterende upload-pipeline, så destination,
metadata og afledte filer bliver håndteret korrekt. Øvrige trin genkøres direkte.
Konverteringsindstillinger respekteres. En fejlet fil, som ikke længere findes,
bliver på listen med en forklaring. Genkørsel starter ikke samtidig med en
allerede aktiv ansigts-, AI- eller uploadbehandling.

Fejl fra før opdateringen bliver ikke rekonstrueret fra gamle tællere. Et hårdt
processtop, før programmet kan registrere en fejl, kan heller ikke registreres
som en konkret behandlingsfejl. Allerede registrerede fejl bevares dog, hvis en
genkørsel afbrydes.

**Mangler** ved ansigtsindeksering er uændret: antallet af understøttede filer
uden `faces_indexed_at`. Det omfatter både ubehandlede filer og fejlede første
forsøg. En fejlet genkørsel af en tidligere indekseret fil øger ikke dette tal.

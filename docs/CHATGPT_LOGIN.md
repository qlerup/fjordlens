# ChatGPT-forbindelse

Første trin til ekstern AI under Indstillinger → AI beskrivelser. Denne ændring
tilslutter en ChatGPT-konto og gemmer forbindelsen. Den aktiverer ingen
billedbehandling og sender ingen billeder til OpenAI.

Login følger OpenAI's offentlige flow for open source-apps og ChatGPT plan usage:
https://developers.openai.com/siwc/token-sharing-open-source/sign-in

FjordLens er self-hosted. OpenAI kræver et loopback-callback på computeren med
browseren, så login gennemføres med det downloadbare lokale Python-program.
https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms

1. Åbn Indstillinger → AI beskrivelser → Ekstern AI · ChatGPT.
2. Tryk Fortsæt med ChatGPT, hent ZIP-filen og pak den ud på din computer.
3. Med Python 3.10+ installeret: `python -m pip install -r requirements.txt`,
   derefter `python chatgpt_login.py`.
4. Log ind hos OpenAI og godkend adgang til abonnementet.
5. Vælg den genererede forbindelsesfil i FjordLens via HTTPS. Slet filen efter
   overførslen. Filen indeholder adgangs- og fornyelsestokens.

For en anden konto eller et andet workspace: `python chatgpt_login.py --new-account`.
Et almindeligt nyt login genbruger det gemte klient-ID og værts-ID.

Ved TLS-terminering i en reverse proxy skal `CHATGPT_TRUST_PROXY_HTTPS=1` sættes
i FjordLens-miljøet. Aktivér kun dette, hvis proxyen overskriver
`X-Forwarded-Proto`, og applikationsporten er beskyttet mod direkte adgang fra
utroværdige klienter. Ellers kræves direkte HTTPS eller en SSH-tunnel til
`http://127.0.0.1:PORT`. Almindelig HTTP til serverens LAN-adresse afvises ved import.

Kun administratorer kan læse og ændre forbindelsen. Kontoen er fælles for
installationen. Tokens gemmes krypteret i `DATA_DIR/chatgpt-connection.sqlite3`
med en nøgle afledt af appens eksisterende hemmelige nøgle. Bevar `secret.key`
sammen med data ved backup. Klientens host-ID erstatter ikke serverens eget ID.
Status-API'et returnerer kun kontoens email og forbindelsestidspunkt.

Log ud fjerner forbindelsen fra FjordLens. Tilbagekald selve OpenAI-tilladelsen
i ChatGPT Settings → Usage. Import af en ny konto sker først efter kontrol af
ID-tokenets signatur, issuer, audience, udløb og identitet, så et mislykket
login bevarer den eksisterende konto.

Der er endnu ingen automatisk tokenfornyelse eller modelvalg. De tilføjes med
billedbehandlingen. Et gemt login er ikke en verificering af modeladgang,
abonnementsgrænser eller senere tilbagekaldelse. Et virkeligt OAuth-login kræver
brugerens godkendelse i browseren og er ikke del af de automatiske tests.

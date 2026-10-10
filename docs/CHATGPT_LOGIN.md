# ChatGPT-login i FjordLens

Login foregår under Indstillinger → AI beskrivelser → Ekstern AI · ChatGPT.
Runtime og loginoplysninger håndteres på FjordLens-serveren.

1. Opdatér FjordLens-containeren til denne version.
2. Tryk **Fortsæt med ChatGPT** i panelet.
3. Panelet viser en engangskode og **Åbn ChatGPT-login**.
4. Åbn linket, log ind hos OpenAI og indtast koden.
5. Vend tilbage til FjordLens. Kontostatus opdateres automatisk.

Hvis OpenAI afviser device-login, skal det aktiveres i ChatGPT-kontoens
sikkerhedsindstillinger eller tillades af workspace-administratoren.

Dette bruger OpenAI's officielle Codex app-server og device-code-login.
Forbindelsen er ChatGPT-kontoens Codex-adgang. Billedbeskrivelser og kontrol af
modeladgang tilføjes i næste trin.

Officielle kilder:

- https://learn.chatgpt.com/docs/auth#login-on-headless-devices
- https://learn.chatgpt.com/docs/app-server#authentication

Docker-imaget indeholder den officielle Codex CLI, fastlåst til version 0.162.1.
Runtime starter kun login/account-metoder over privat stdio. Der startes ingen
agenttråde, prompts, kommandoer eller billedoverførsler.

En tidsbegrænset loginproces kører på serveren. Loginstatus ligger i SQLite, så
navigation, browseropdatering og flere web-workers virker. Koden vises kun til
den administrator, der startede login. Mislykket login bevarer eksisterende
kontotilslutning. Genstart af server/container kan afbryde et ventende login;
prøv igen, når det er udløbet.

Codex bruger en isoleret midlertidig credential-mappe på serveren under login.
Efter godkendelse gemmes dens auth-record krypteret i
`DATA_DIR/chatgpt-connection.sqlite3`, og den midlertidige mappe fjernes.
Krypteringsnøglen afledes af appens eksisterende hemmelige nøgle. Bevar
`secret.key` sammen med data ved backup. Tokens returneres aldrig til browseren.

Log ud fjerner forbindelsen og annullerer et eventuelt ventende login.
Tilbagekald den overordnede OpenAI-tilladelse i din ChatGPT-konto, hvis nødvendigt.
HTTPS anbefales som for resten af administratorpanelet. OAuth-tokens overføres
udelukkende mellem OpenAI og serveren.

Login er første trin. Automatisk fornyelse under billedbehandling og faktisk
kontrol af abonnements-/modeladgang implementeres sammen med næste trin.
Et virkeligt OAuth-login kræver brugerens godkendelse hos OpenAI; automatiske
tests simulerer loginresultatet og udfører ingen modelkald.

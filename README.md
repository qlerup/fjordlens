# FjordLens for Synology (GitHub-klar starter)

En Docker-baseret photo-app starter til Synology NAS med:

- Web UI (Flask + HTML/CSS/JS)
- Scan af fotomappe (`/photos`)
- Metadata extraction (EXIF + filinfo)
- Thumbnails
- SQLite indeksdatabase
- Søgning/sortering/filtrering
- Favoritter
- Detaljevisning med rå metadata JSON
- **AI-klargjort data-model** til senere ONNX/CLIP og ansigtsgenkendelse

## Status lige nu

Denne version er lavet som **testbar base**:
- ✅ Metadata + thumbnails + søgning virker
- ✅ Synology Docker/Container Manager klar
- ✅ GitHub klar (inkl. GHCR workflow)
- 🔜 Næste trin: ONNX/CLIP (dansk semantisk søgning) + ansigtsgenkendelse + clustering

---

## Projektstruktur

```txt
fjordlens/
├─ app.py
├─ Dockerfile
├─ docker-compose.yml
├─ docker-compose.ghcr.yml.example
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ README.md
├─ scripts/
│  ├─ first_install_nas.sh
│  └─ update.sh
├─ .github/
│  └─ workflows/
│     └─ docker-ghcr.yml
├─ templates/
│  └─ index.html
└─ static/
   ├─ styles.css
   └─ app.js
```

---

## 1) Lokal test (valgfrit)

Hvis du vil teste på din PC først:

```bash
cp .env.example .env
# ret evt. PHOTO_DIR og DATA_DIR
docker compose up -d --build
```

Åbn:
- `http://localhost:9080` (eller den port du satte i `.env`)

---

## 2) Synology installation via SSH (anbefalet)

### Aktivér SSH i DSM
- **Kontrolpanel → Terminal & SNMP → Aktivér SSH**

### Log ind på NAS
```bash
ssh ditbrugernavn@DIN_NAS_IP
```

### Hent koden (fra GitHub) eller kopiér projektet
```bash
mkdir -p /volume1/docker
cd /volume1/docker
git clone https://github.com/YOUR_USER/YOUR_REPO.git fjordlens
cd fjordlens
```

### Opret `.env`
```bash
cp .env.example .env
vi .env
```

Eksempel:
```env
APP_PORT=9080
PHOTO_DIR=/volume1/photos
DATA_DIR=/volume1/docker/fjordlens/data
TZ=Europe/Copenhagen
LOG_LEVEL=INFO
```

> Sæt `PHOTO_DIR` til den mappe hvor dine billeder ligger på NAS'en.

### Start containeren
```bash
docker compose up -d --build
```

Åbn:
- `http://DIN_NAS_IP:9080`

Tryk **“Scan bibliotek”** i UI.

---

## 3) Synology Container Manager (GUI)
Du kan også bruge **Projects** i Container Manager:

1. Upload projektet til `/volume1/docker/fjordlens`
2. Opret `.env`
3. I Container Manager → **Project** → **Create**
4. Peg på `docker-compose.yml`
5. Start projektet

---

## 4) GitHub opsætning (repo)

Hvis du starter med en lokal mappe og vil skubbe til GitHub:

```bash
git init
git add .
git commit -m "Initial FjordLens Synology starter"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

### Privat repo?
Brug enten:
- GitHub Personal Access Token (PAT), eller
- SSH keys

---

## 5) Nem opdatering senere (NAS)
Når repoet er clonet på NAS:

```bash
cd /volume1/docker/fjordlens
git pull
docker compose up -d --build
```

Du kan også bruge scriptet:
```bash
sh scripts/update.sh
```

---

## 6) GitHub Container Registry (GHCR) klar (valgfrit, senere)
Der er en workflow med i repoet:
- `.github/workflows/docker-ghcr.yml`

Den bygger og publicerer image til GHCR på:
- push til `main`
- tags som `v1.0.0`

### Fordel
NAS'en skal så **ikke bygge** imaget selv.

### Brug GHCR image på NAS
Kopiér `docker-compose.ghcr.yml.example` til `docker-compose.yml` og ret image-navn:

```yaml
image: ghcr.io/YOUR_GITHUB_USERNAME/fjordlens:latest
```

---

## 7) Hvad appen indekserer (nu)
Ved scan gemmes bl.a.:

- filnavn / sti
- filstørrelse
- dato (EXIF hvis muligt, ellers fil-dato)
- dimensioner
- kamera / linse (hvis EXIF findes)
- GPS koordinater (hvis EXIF findes)
- SHA256 checksum
- pHash (simpel duplicate-støtte)
- thumbnails
- rå metadata JSON (`metadata_json`)
- `ai_tags` (placeholder til dansk søgning)
- felter til fremtidig `embedding_json`

---

## 8) Dansk søgning (nu vs senere)
### Nu
Søgning virker på:
- metadata (filnavn, kamera, dato, tags)
- simple danske synonym-tags (fx strand/hav, bil, skov)

### Senere (næste trin)
Vi kobler på:
- **ONNX/CLIP** for rigtig semantisk søgning på dansk
- **Face-service** (detektion + embeddings)
- **Clustering** (gruppering af personer)
- evt. PostgreSQL + pgvector

---

## 9) Kendte begrænsninger (starter)
- HEIC/HEIF kræver ekstra decoder i nogle miljøer (Pillow kan ikke altid åbne dem direkte)
- Ingen reverse geocoding endnu (GPS → bynavn)
- Ingen rigtig ansigtsgenkendelse endnu (tabeller er klargjort)
- SQLite er fint til start; PostgreSQL/pgvector anbefales senere

---

## 10) Næste trin jeg vil anbefale
1. ONNX Runtime container til ansigtsdetektion + embeddings
2. ONNX/CLIP tekst↔billede embeddings til dansk AI-søgning
3. Job-queue (Redis) + worker til baggrundsindexering
4. PostgreSQL + pgvector
5. Personer/Steder visninger med rigtige grupper

---

## Sikkerhed / drift
- Commit **ikke** `.env` til GitHub
- Monter fotos `:ro` (read-only), som i compose-filen
- Gem data (DB + thumbnails) i en persistent mappe (`/volume1/docker/fjordlens/data`)

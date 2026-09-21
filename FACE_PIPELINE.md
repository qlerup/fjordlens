# Ansigtsbehandling på GPU og CPU

Den eksisterende indstilling **Ansigtsbatch** bestemmer det maksimale antal
aktive jobs ved upload og manuel indeksering. En ledig plads fyldes straks igen.
Jobs deler én InsightFace-model; tallet betyder ikke et tilsvarende antal
modelkopier eller samtidige ONNX-kørsler. Modelkørsler er låst, mens andre
GPU-jobs kan klargøre billeder. CPU-vejen klargør og analyserer ét billede ad
gangen for at begrænse RAM-forbruget.

## Automatisk valg

- En fungerende CUDA-provider i ansigtsmodellen aktiverer GPU-pipelinen.
- Uden CUDA bruger den samme kø Pillow og CPU-modellen automatisk.
- JPEG udpakkes med torchvision/nvJPEG til GPU-hukommelse. EXIF-rotation,
  skalering, normalisering og ansigtsudsnit udføres med Torch på GPU'en.
  ONNX får GPU-tensoren direkte gennem I/O binding.
- Andre billedformater og JPEG-varianter uden decoder-understøttelse udpakkes
  på CPU under RAM-kontrol og behandles derefter på GPU, når den er tilgængelig.
- Detektorens små resultater, NMS og beregning af transformation fra fem
  ansigtspunkter behandles på CPU. Hele originalbilledet kopieres ikke tilbage.
- Originalfiler ændres ikke. Webappen videresender komprimerede billeddata
  uden en ekstra RGB-udpakning og JPEG-komprimering. RAW-formater kan stadig
  kræve den eksisterende konvertering til en visningsfil.
- Videoframes bruger samme ansigtspipeline og eksisterende videotoggle.
  Denne ændring flytter ikke selve frame-udtrækningen fra konverteringstjenesten.
  Ved fejl genforsøges samme frame én gang efter to sekunder. Første fejl giver
  en besked om genforsøget; først anden fejl bliver en fejlregistrering. Hvis
  kun AI-kaldet fejler, genbruges den allerede udpakkede frame. Nul ansigter er
  et gyldigt resultat og udløser ikke genforsøg. Ved vedvarende fejl markeres
  videoen ikke som færdig, og tidligere gemte ansigter bevares. Stop af køen
  eller videotoggle afbryder genforsøget ved næste kontrol; et allerede sendt
  HTTP-kald kan dog først afsluttes eller nå sin timeout.

## Hukommelse og status

GPU-adgang styres ud fra billedets dimensioner, igangværende reservationer,
faktisk ledig VRAM og en margen på 512 MiB. Otte køpladser er derfor ikke en
garanti for otte udpakkede billeder samtidig. Der er fortsat en risiko ved
uforudsete allokeringer fra ONNX eller andre GPU-programmer; fejl returneres
som midlertidige AI-fejl, så filen kan genforsøges.

RAM-reservationerne følger nu arbejdet: komprimerede bytes i webappen, mindre
værtsbuffere ved GPU-behandling og et dimensionsbaseret estimat ved CPU-decode.
Den fælles FjordHub-reserve er bevaret. Central reservation kan fortsat være
konservativ, når allokeret RAM også indgår i den samlede værtsmåling.

`/health` viser `face_pipeline=shared_model`, `face_model_instances` og
`face_preprocessing` (`cuda_jpeg`, `cpu_decode_cuda_prepare` eller `cpu`).
`face_preprocessing_fallback` viser seneste JPEG-decoderfejl, hvis fallback
var nødvendig. `/faces/status` og loggen viser jobs under `waiting_gpu`,
`decode_gpu`, `decode_cpu`, `prepare_gpu`, `inference` og `done`.

CPU-fallback bruger samme historiske farverækkefølge som eksisterende
ansigtsvektorer. GPU-resultater kan variere lidt på grund af JPEG-decode og
interpolation; eksisterende persondata nulstilles ikke.

## Verifikation og opdatering

Unit-tests dækker CPU-fallback, rotation, køstyring, frigivelse efter fejl,
VRAM-adgang og uændret originalupload. De opt-in tests i
`tests/test_face_pipeline_gpu.py` kører rigtige CUDA- og CPU-modeller mod et
offentligt testbillede og sammenligner ansigtsbokse og embeddings. Aktivér dem
med `FJORDLENS_GPU_TEST=1` i AI-imaget med repoet monteret og kør
`python -m unittest tests.test_face_pipeline_gpu -v`.

Verificeret lokalt med det byggede AI-image på RTX 4090: fem integrationstests,
inklusive otte 24-megapixel-billeder i køen. Embedding-cosinus mod den hidtidige
modelvej var over 0,999 på prøvebilledet. CPU-behandling er også kørt i en
Docker-container helt uden GPU-adgang. Dette er funktionstest, ikke en måling
af hastighed eller maksimal kapacitet på en RTX 2060.

Opdater både web- og AI-image. Det nye AI-image kan behandle gamle klienters
allerede roterede JPEG-filer, men en gammel AI-service anvender ikke EXIF på
de nye originale uploads. Undgå derfor indeksering under en delvis opdatering.
Ved rollback tilbageføres begge images sammen. Ingen databaseændringer kræves.

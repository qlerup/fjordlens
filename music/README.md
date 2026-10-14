# Music for FjordLens

Sixteen bundled MP3 tracks in eight moods, with two variations each:

| Mood | Use | Files |
| --- | --- | --- |
| Our day | Weddings and confirmations | `wedding-1.mp3`, `wedding-2.mp3` |
| Summer memories | Holidays and beaches | `summer-1.mp3`, `summer-2.mp3` |
| On an adventure | Travel and experiences | `adventure-1.mp3`, `adventure-2.mp3` |
| Little big moments | Children and outings | `playful-1.mp3`, `playful-2.mp3` |
| The year in review | Nostalgic annual highlights | `year-1.mp3`, `year-2.mp3` |
| Winter light | Christmas and winter | `winter-1.mp3`, `winter-2.mp3` |
| Quiet moments | Nature and calm memories | `quiet-1.mp3`, `quiet-2.mp3` |
| Memories of you | Reflective personal memories | `memory-1.mp3`, `memory-2.mp3` |

An initial track is selected from the moment title. In Edit slideshow, preview/change the track, adjust volume or choose No music. Music continues across slides and loops with a six-second equal-power crossfade. MP4 export uses matching transitions and start/end fades; source-video audio is muted in the presentation. Phones/public links may require tapping Enable music.

`catalog.json` stores stable IDs, original titles, duration and leading/trailing-silence bounds. MP3s retain supplied originals; trimming happens during playback/export. Tracks are served by your Lens server, without a Suno/streaming-service connection.

Track/volume settings persist with the editable timeline. New sharing links snapshot them; later changes do not alter old links. Earlier links without a music choice receive a deterministic default from their stored title. Previously silent exports must be regenerated to include music.

The recordings were supplied under their own rights notice. See [COPYRIGHT.md](COPYRIGHT.md) for permission/restrictions; these files are not offered as unrestricted stock music.

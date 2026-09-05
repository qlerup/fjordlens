# Google Nest Hub Photo Frame

FjordLens can feed selected photos into the **normal Google Nest Hub Photo Frame / ambient slideshow** without taking over the display with Cast.

The integration creates and manages an app-owned Google Photos album. You select that album once in Google Home for any Nest Hub that should display it. The Nest Hub remains a normal Nest Hub: touching it, using Assistant, music, smart-home controls, and other functions work as usual. When the display returns to idle/ambient mode, Google Photo Frame uses the FjordLens album.

## What the integration can and cannot see

Google Photos exposes the album and media items, but it does **not** expose the Nest Hub device heartbeat, IP address, software version, or a reliable list of which Nest displays use the album. For that reason, the Google card in FjordLens intentionally differs from the Raspberry Pi frame cards.

The Google card shows:

- Google connection status
- Google Photos album name/link
- number of photos in the album
- number of photos uploaded/tracked by FjordLens
- last sync time
- setup guidance for Google Home

Multiple Nest Hubs can select the same FjordLens album.

## 1. Create a Google Cloud OAuth client

1. Open Google Cloud Console and create or choose a project.
2. Enable **Google Photos Library API**.
3. Configure the OAuth consent screen.
4. If the consent screen is in **Testing**, add the Google account used by the Nest Hub as a test user.
5. Create an **OAuth 2.0 Client ID** of type **Web application**.
6. In FjordLens, open **Photoframe → Google Photo Frame → Opsæt Google**.
7. Copy the exact **Authorized redirect URI** shown by FjordLens into the OAuth client's **Authorized redirect URIs** list.
8. Copy the OAuth Client ID and Client Secret into FjordLens and save.

For a FjordLens instance exposed through a reverse proxy/Cloudflare, use the public HTTPS FjordLens URL for the callback. The redirect URI must match exactly.

FjordLens requests only the Google Photos permissions needed to create/upload app-owned content, read app-created content, and edit/remove app-created album associations.

## 2. Connect Google Photos

In **Photoframe → Google Photo Frame**, click **Forbind Google** and authorize the Google account that owns/uses the Nest Hub Photo Frame.

FjordLens then creates an album named **FjordLens Photo Frame** (or the name configured in settings).

OAuth tokens and the FjordLens↔Google media mapping are stored in:

```text
DATA_DIR/google_photo_frame.json
```

The file is written with owner-only permissions (`0600`) on Linux. It belongs in the persistent FjordLens data directory and must not be committed to Git.

Optional environment overrides:

```env
GOOGLE_PHOTOS_CLIENT_ID=
GOOGLE_PHOTOS_CLIENT_SECRET=
GOOGLE_PHOTOS_REDIRECT_URI=
GOOGLE_PHOTOS_ALBUM_TITLE=FjordLens Photo Frame
GOOGLE_PHOTO_FRAME_MAX_EDGE=2048
GOOGLE_PHOTO_FRAME_JPEG_QUALITY=88
```

Client ID/secret can be stored through the UI instead, so the environment variables are optional.

## 3. Select the album on Nest Hub

Do this once for each Nest Hub that should use the FjordLens slideshow:

1. Open Google Home.
2. Open the Nest Hub.
3. Open **Photo Frame**.
4. Choose **Google Photos**.
5. Select the **FjordLens Photo Frame** album.

Google Home controls the device assignment. FjordLens controls the album contents.

## 4. Add or remove photos from FjordLens

From the Google card, choose **Vælg billeder**. FjordLens opens the normal folder/photo view. Long-press a photo to start selection, select the desired photos, then use **Google Frame** in the selection toolbar.

Choose:

- **Tilføj valgte** — generates a display-sized JPEG, uploads it to Google Photos, and adds it to the FjordLens album.
- **Fjern valgte** — removes the app-created Google media item from the Photo Frame album.

FjordLens keeps the Google media item ID so a removed photo can be added back to the album without creating another upload when Google still has the item.

## Storage behavior

FjordLens does not upload the original full-resolution file. Before upload it creates an in-memory JPEG copy, by default with a maximum edge of 2048 px and JPEG quality 88. The FjordLens original is not modified.

Google Photos API uploads consume storage according to the Google account's storage rules.

Removing an item in FjordLens removes it from the **Photo Frame album**. The Google Photos Library API does not provide the same simple delete-from-library operation for this integration, so the uploaded copy can remain in the Google Photos library after removal from the album.

## Current v1 scope

The first version manages one Google Photo Frame album per FjordLens installation. Any number of Nest Hubs can use that same album. A later version can extend this to multiple named Google albums/cards (for example, `Køkken`, `Stue`, and `Soveværelse`) if separate slideshows per Nest Hub are wanted.

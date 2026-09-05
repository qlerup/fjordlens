# FjordLens native AirPlay (iOS / Capacitor)

FjordLens creates a short-lived media session on the server and turns it into an incremental **HLS EVENT stream**. The iOS Capacitor wrapper hands that HLS URL to `AVPlayer`, while `AVRoutePickerView` provides Apple's native AirPlay device picker.

This means FjordLens does **not** use Screen Mirroring and does **not** have to render the complete selection into one MP4 before playback starts.

## Native files

Add these files to the iOS App target in Xcode:

- `FjordLensAirPlayPlugin.swift`
- `FjordLensBridgeViewController.swift`

Use `FjordLensBridgeViewController` as the Capacitor bridge view controller, or register `FjordLensAirPlayPlugin()` from an existing `CAPBridgeViewController.capacitorDidLoad()`.

The plugin exposes the JavaScript name `FjordLensAirPlay` with:

- `start({ url, title })`
- `stop()`
- `status()`
- event `externalPlaybackChanged`
- event `closed`

`static/airplay_hls.js` automatically detects `window.Capacitor.Plugins.FjordLensAirPlay`. In Safari it falls back to an HLS `<video>` player. In the installed iOS app it opens the native player and native route picker.

## Playback flow

1. User selects images, videos or folders in FjordLens.
2. FjordLens creates the normal short-lived Cast/AirPlay selection token.
3. `POST /api/airplay-hls/<token>/prepare` starts background HLS generation.
4. As soon as the first HLS segment exists, the API returns `playable: true`.
5. The native plugin starts `AVPlayer` immediately while FjordLens continues producing later segments in the background.
6. The user chooses Apple TV / an AirPlay-compatible display through the native route picker.

The HLS playlist and segments are protected by the same high-entropy, expiring selection token as the rest of the Cast/AirPlay flow.

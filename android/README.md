# PolyKybd Flasher (Android)

Flashes a PolyKybd firmware `.bin` from an Android phone connected to the keyboard's
master half over USB-C. It uses the HID update path the desktop host uses. The
master relays the image to the slave half over the split cable, so one cable updates
both halves.

Status: builds, and the protocol logic passes its unit tests. It has not run against
a real keyboard yet.

## Use

1. Connect the keyboard's master half to the phone (USB-C to USB-C, or an OTG adapter).
   Android offers to open PolyKybd Flasher. Tick "always". The keyboard re-enumerates
   during an update, and "always" grants USB access again without a dialog each time.
2. Tap **Choose .bin (and its .sig)** and select both files in one go. The `.sig` is
   optional:
   - with a matching `.sig` (a release), the keyboard accepts the image by itself;
   - without one (your own build), the keycaps turn into an A/R prompt, and you press
     A on the left half within 60 s.
3. Tap **Flash**. Staging takes a few minutes. With **Apply after it is verified**
   ticked, the keyboard then copies the image over its running firmware and reboots.

The first Flash asks how the update should run. The main screen can change it later.

- **Keep this app open.** No notification and no notification permission. The screen
  stays on, and the update can stop if you leave the app.
- **Run in the background.** You can lock the phone or switch apps. Android requires a
  foreground service to show an ongoing notification, so this mode shows one progress
  notification (silent, removed when the update ends). On Android 13+ the app asks for
  notification permission when you choose this mode. Declining it only hides the
  notification.

The app refuses to start below 20% phone battery, because some phones cut USB power
when the battery runs low. An interrupted transfer is harmless: nothing is applied
until COMMIT has verified the CRC and the signature.

## Layout

| File | Role |
|---|---|
| `Flasher.kt` | BEGIN → CHUNK × N → SIGNATURE → COMMIT, then APPLY. A port of `polyhost/device/hid_fw_up.py`. |
| `FwImage.kt` | Image checks: RP2040 boot2 CRC, initial SP, PolyKybd USB string, size limit. |
| `UsbHidTransport.kt` | Finds VID `0x2021` / PID `0x2007` (split72) or `0x2008` (split42), claims the raw-HID interface (usage page `0xFF61`) and exchanges 64-byte reports. |
| `FlashJob.kt` | One update run on a worker thread with a wake lock. Both run modes use it. |
| `FlashService.kt` | Background mode: `FlashJob` inside a foreground service, plus its progress notification. |
| `MainActivity.kt` | File picker, battery and device checks, run-mode choice, progress. |
| `tools/gen_launcher_icon.py` | Writes the launcher, themed and notification icons as vector drawables. |

⚠️ `Flasher.kt` and `hid_fw_up.py` implement the same protocol. A change to the
FW_UP commands, status bytes, chunk size or `FW_UP_MAX_SIZE` needs both edited, and
the tests in `app/src/test/` updated. Nothing checks the two against each other.

## Icon

The icon is a variant of the host's brand mark (`tools/gen_brand_icons.py`): the same
keycap grid and colours, with a down arrow drawn in lit keys. The generator imports its
geometry from the host script. Edit the script, never the drawables:

```bash
python3 android/tools/gen_launcher_icon.py                # rewrite the drawables
python3 android/tools/gen_launcher_icon.py --sheet x.png  # preview under launcher masks
```

## Build

Needs JDK 17+ and the Android SDK (platform 35, build-tools 35).

```bash
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew testDebugUnitTest      # protocol tests against a fake keyboard, no device needed
./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
```

Install the debug APK with `adb install app-debug.apk`, or copy it to the phone and
open it (allow installs from that source).

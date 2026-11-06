# PolyKybd Flasher (Android)

Flashes a PolyKybd firmware `.bin` from an Android phone connected to the keyboard's
master half over USB-C. It uses the HID update path the desktop host uses. The
master relays the image to the slave half over the split cable, so one cable updates
both halves.

Status: builds, and the protocol logic passes its unit tests. One flash on a real
keyboard succeeded (2026-09-25).

## Use

1. Connect the keyboard's master half to the phone (USB-C to USB-C, or an OTG adapter).
   Android offers to open PolyKybd Flasher. Tick "always". The keyboard re-enumerates
   during an update, and "always" grants USB access again without a dialog each time.
2. Choose the firmware:
   - **Get latest release (signed)** downloads the newest release from
     `thpoll83/qmk_firmware`: the `.bin` for the connected keyboard and its `.bin.sig`.
     Both must match the size and SHA-256 that GitHub lists. The keyboard verifies the
     signature and installs the image without asking.
   - **Choose a .bin file (unsigned)** takes a file from the phone, such as your own
     build. It is always sent without a signature, so the keycaps turn into an A/R
     prompt, and you press A on the left half within 60 s.

   Either way, the app refuses an image built for the other keyboard (split72 vs
   split42). The image carries its USB product string, and the keyboard reports its PID.
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
| `Releases.kt` | Finds the latest release's `.bin` + `.bin.sig` for a variant, downloads both, checks size and SHA-256. |
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

## Look

One dark design on every phone: the icon's navy (`#0B1220`) as background, a blue
(`#1D4ED8`) header drawn in the layout itself, and cards for Keyboard, Firmware and
Update. The header is not the system title bar, because phones that draw their own
title bar (Samsung) ignore theme colours there. The colours and their measured
contrast are in `res/values/colors.xml`.

`ScreenshotTest` renders the screen with Paparazzi (layoutlib), so a UI change can be
checked without a phone or an emulator:

```bash
./gradlew recordPaparazziDebug   # writes app/src/test/snapshots/images/*.png
./gradlew verifyPaparazziDebug   # fails when the rendering no longer matches
```

## Build

Needs JDK 17+ and the Android SDK (platform 35, build-tools 35).

```bash
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew testDebugUnitTest      # protocol tests against a fake keyboard, no device needed
POLYKYBD_LIVE=1 ./gradlew testDebugUnitTest                  # + fetch the live latest release
POLYKYBD_RELEASE_BIN=path/to.bin ./gradlew testDebugUnitTest # + check a real release image
./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
```

Install the debug APK with `adb install app-debug.apk`, or copy it to the phone and
open it (allow installs from that source).

## Distribution

For now the APK is attached by hand to a PolyKybdHost release as
`polykybd-flasher-v<versionName>.apk`, the version from `app/build.gradle.kts`. There
is no workflow for it.

⚠️ That APK is debug-signed. Android installs an update only over an app signed with
the same key, so moving to a proper release key later means users uninstall once.
A release key belongs in repo secrets together with a build workflow, and it must be
backed up: a lost key means every user has to uninstall again.

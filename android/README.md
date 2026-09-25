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

The app refuses to start below 20% phone battery, because some phones cut USB power
when the battery runs low. An interrupted transfer is harmless: nothing is applied
until COMMIT has verified the CRC and the signature.

## Layout

| File | Role |
|---|---|
| `Flasher.kt` | BEGIN → CHUNK × N → SIGNATURE → COMMIT, then APPLY. A port of `polyhost/device/hid_fw_up.py`. |
| `FwImage.kt` | Image checks: RP2040 boot2 CRC, initial SP, PolyKybd USB string, size limit. |
| `UsbHidTransport.kt` | Finds VID `0x2021` / PID `0x2007` (split72) or `0x2008` (split42), claims the raw-HID interface (usage page `0xFF61`) and exchanges 64-byte reports. |
| `FlashService.kt` | Runs the update as a foreground service with a wake lock, so screen-off or an app switch does not stop it. |
| `MainActivity.kt` | File picker, battery and device checks, progress. |

⚠️ `Flasher.kt` and `hid_fw_up.py` implement the same protocol. A change to the
FW_UP commands, status bytes, chunk size or `FW_UP_MAX_SIZE` needs both edited, and
the tests in `app/src/test/` updated. Nothing checks the two against each other.

## Build

Needs JDK 17+ and the Android SDK (platform 35, build-tools 35).

```bash
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew testDebugUnitTest      # protocol tests against a fake keyboard, no device needed
./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
```

Install the debug APK with `adb install app-debug.apk`, or copy it to the phone and
open it (allow installs from that source).

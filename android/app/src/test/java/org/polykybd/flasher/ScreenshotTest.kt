package org.polykybd.flasher

import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import org.junit.Rule
import org.junit.Test

/**
 * Renders the main screen with layoutlib, so a UI change can be looked at without a
 * phone or an emulator. `./gradlew recordPaparazziDebug` writes the PNGs to
 * app/src/test/snapshots/images/; `verifyPaparazziDebug` fails when they change.
 * The texts below are samples: MainActivity sets the real ones at run time.
 */
class ScreenshotTest {
    @get:Rule
    val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_5, theme = "AppTheme")

    private fun screen(): View = paparazzi.inflate<View>(R.layout.activity_main).apply {
        findViewById<TextView>(R.id.device).text = "PolyKybd Split72 (2021:2007)"
        findViewById<CheckBox>(R.id.apply).isChecked = true
        findViewById<RadioGroup>(R.id.mode).check(R.id.mode_background)
    }

    @Test fun idle() {
        val v = screen()
        v.findViewById<TextView>(R.id.files).text = "No firmware chosen."
        v.findViewById<TextView>(R.id.sig).visibility = View.GONE   // as MainActivity does when empty
        v.findViewById<Button>(R.id.flash).isEnabled = false
        paparazzi.snapshot(v)
    }

    @Test fun updating() {
        val v = screen()
        v.findViewById<TextView>(R.id.files).text = "polykybd_split72_v0.28.0.bin (release 0.28.0) (507 KB)"
        v.findViewById<TextView>(R.id.sig).text =
            "Signed release. The keyboard checks the signature (polykybd_split72_v0.28.0.bin.sig) and installs it without asking."
        v.findViewById<Button>(R.id.flash).isEnabled = false
        v.findViewById<Button>(R.id.latest).isEnabled = false
        v.findViewById<Button>(R.id.pick).isEnabled = false
        v.findViewById<ProgressBar>(R.id.progress).apply { visibility = View.VISIBLE; progress = 42 }
        v.findViewById<TextView>(R.id.status).text = "Chunk 3901/9284 (213 KB sent)…"
        v.findViewById<Button>(R.id.cancel).visibility = View.VISIBLE
        paparazzi.snapshot(v)
    }
}

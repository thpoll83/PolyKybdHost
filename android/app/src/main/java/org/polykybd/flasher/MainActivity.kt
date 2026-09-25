package org.polykybd.flasher

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.usb.UsbManager
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.CheckBox
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    companion object {
        private const val PICK_FILES = 1
        private const val MIN_BATTERY_PCT = 20
        private const val PREFS = "settings"
        private const val PREF_MODE = "run_mode"
        private const val MODE_BACKGROUND = "background"
        private const val MODE_IN_APP = "in_app"
    }

    /** How an update runs: [MODE_BACKGROUND] (service + notification), [MODE_IN_APP], or null = not chosen yet. */
    private var runMode: String?
        get() = getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(PREF_MODE, null)
        set(v) { getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(PREF_MODE, v).apply() }

    private lateinit var usb: UsbManager
    private lateinit var deviceText: TextView
    private lateinit var filesText: TextView
    private lateinit var sigText: TextView
    private lateinit var applyBox: CheckBox
    private lateinit var modeGroup: RadioGroup
    private lateinit var flashButton: Button
    private lateinit var cancelButton: Button
    private lateinit var progressBar: ProgressBar
    private lateinit var statusText: TextView

    private val listener: () -> Unit = { render() }

    /** True while [getLatest] downloads; the buttons that change the firmware wait for it. */
    @Volatile private var fetching = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        usb = getSystemService(USB_SERVICE) as UsbManager
        deviceText = findViewById(R.id.device)
        filesText = findViewById(R.id.files)
        sigText = findViewById(R.id.sig)
        applyBox = findViewById(R.id.apply)
        modeGroup = findViewById(R.id.mode)
        flashButton = findViewById(R.id.flash)
        cancelButton = findViewById(R.id.cancel)
        progressBar = findViewById(R.id.progress)
        statusText = findViewById(R.id.status)

        findViewById<Button>(R.id.pick).setOnClickListener { pickBin() }
        findViewById<Button>(R.id.latest).setOnClickListener { getLatest() }
        findViewById<Button>(R.id.refresh).setOnClickListener { render() }
        applyBox.isChecked = FlashState.applyAfterFlash
        applyBox.setOnCheckedChangeListener { _, checked -> FlashState.applyAfterFlash = checked }
        flashButton.setOnClickListener { startFlash() }
        cancelButton.setOnClickListener {
            FlashState.cancelRequested = true
            FlashState.update(message = "Cancelling after the current chunk…")
        }

        when (runMode) {
            MODE_BACKGROUND -> modeGroup.check(R.id.mode_background)
            MODE_IN_APP -> modeGroup.check(R.id.mode_in_app)
        }
        modeGroup.setOnCheckedChangeListener { _, id ->
            chooseRunMode(if (id == R.id.mode_background) MODE_BACKGROUND else MODE_IN_APP)
        }
    }

    private fun chooseRunMode(mode: String) {
        runMode = mode
        // Only background mode shows a notification, so only it asks for the permission.
        // Declining is fine: the update still runs, Android just hides the notification.
        if (mode == MODE_BACKGROUND && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 0)
        }
    }

    /** Asked once, on the first Flash; the radio buttons change it later. */
    private fun askRunMode(then: () -> Unit) {
        AlertDialog.Builder(this)
            .setTitle("How should the update run?")
            .setMessage("The transfer takes a few minutes.\n\n" +
                "Keep this app open: no notification. The screen stays on, and the update " +
                "can stop if you leave the app.\n\n" +
                "Run in the background: you can lock the phone or switch apps. Android requires " +
                "a progress notification while it runs.\n\n" +
                "You can change this later on the main screen.")
            .setPositiveButton("Run in background") { _, _ ->
                modeGroup.check(R.id.mode_background)
                then()
            }
            .setNegativeButton("Keep app open") { _, _ ->
                modeGroup.check(R.id.mode_in_app)
                then()
            }
            .show()
    }

    override fun onStart() {
        super.onStart()
        FlashState.addListener(listener)
        render()
    }

    override fun onStop() {
        if (FlashState.running && runMode == MODE_IN_APP && !isChangingConfigurations) {
            Toast.makeText(this, "The firmware update needs this app open. Leaving it can stop the update.",
                Toast.LENGTH_LONG).show()
        }
        FlashState.removeListener(listener)
        super.onStop()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        render()   // USB_DEVICE_ATTACHED while open
    }

    private fun pickBin() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType("*/*")
        startActivityForResult(intent, PICK_FILES)
    }

    /**
     * A file the user picks is always flashed UNSIGNED, so the keyboard asks for the
     * A/R keypress. A signature only ever comes with a release, from [getLatest].
     */
    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != PICK_FILES || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        val name = displayName(uri)
        val bytes = try {
            contentResolver.openInputStream(uri)?.use { it.readBytes() }
        } catch (e: Exception) {
            null
        }
        FlashState.result = null
        if (bytes == null) {
            FlashState.update(0, "Could not read $name.")
            return
        }
        setFirmware(bytes, name, null, null)
        FlashState.update(0, "")
    }

    private fun setFirmware(fw: ByteArray, name: String, sig: ByteArray?, sigName: String?) {
        FlashState.fw = fw
        FlashState.fwName = name
        FlashState.sig = sig
        FlashState.sigName = sigName
    }

    /** Downloads the newest release's .bin and .sig for the connected keyboard. */
    private fun getLatest() {
        val dev = UsbHidTransport.findKeyboard(usb)
        val variant = dev?.let { FwImage.Variant.forPid(it.productId) } ?: FwImage.Variant.SPLIT72
        fetching = true
        FlashState.result = null
        FlashState.update(0, "Checking GitHub for the latest ${variant.productString} release…")
        Thread({
            try {
                val rel = Releases.fetchLatest(variant)
                FlashState.update(0, "Downloading ${rel.bin.name}…")
                val bin = Releases.download(rel.bin)
                val sig = Releases.download(rel.sig)
                FwImage.validate(bin)?.let { throw Releases.ReleaseException(it) }
                setFirmware(bin, "${rel.bin.name} (release ${rel.version})", sig, rel.sig.name)
                FlashState.update(0, "Release ${rel.version} downloaded and checked. Tap Flash to install it.")
            } catch (e: Releases.ReleaseException) {
                FlashState.update(0, "Could not get the latest release: ${e.message}")
            } catch (e: Exception) {
                FlashState.update(0, "Could not reach GitHub: ${e.message ?: e.javaClass.simpleName}")
            } finally {
                fetching = false
                FlashState.notifyChanged()
            }
        }, "fw-release").start()
    }

    private fun displayName(uri: Uri): String {
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) return c.getString(0)
        }
        return uri.lastPathSegment ?: "file"
    }

    private fun batteryPct(): Int =
        getSystemService(BatteryManager::class.java).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)

    private fun startFlash() {
        val fw = FlashState.fw ?: return
        FwImage.validate(fw)?.let {
            statusText.text = it
            return
        }
        val battery = batteryPct()
        if (battery in 0 until MIN_BATTERY_PCT) {
            statusText.text = "Phone battery is at $battery%. Charge it to at least $MIN_BATTERY_PCT% first: " +
                "some phones cut USB power when the battery runs low."
            return
        }
        val dev = UsbHidTransport.findKeyboard(usb)
        if (dev == null) {
            statusText.text = "No PolyKybd found. Connect the keyboard's master half to the phone."
            return
        }
        FwImage.checkVariant(fw, dev.productId)?.let {
            statusText.text = it
            return
        }
        if (!usb.hasPermission(dev)) {
            UsbHidTransport.requestPermission(this, usb, dev)
            statusText.text = "Allow USB access to the keyboard, then tap Flash again."
            return
        }
        if (runMode == null) askRunMode { launch() } else launch()
    }

    private fun launch() {
        FlashState.result = null
        if (runMode == MODE_BACKGROUND) {
            startForegroundService(Intent(this, FlashService::class.java))
        } else {
            FlashJob.start(this)
        }
    }

    private fun render() {
        val dev = UsbHidTransport.findKeyboard(usb)
        deviceText.text = when {
            dev == null -> "Not connected. Plug the master half into the phone."
            else -> "${dev.productName ?: "PolyKybd"} (%04x:%04x)".format(dev.vendorId, dev.productId) +
                if (usb.hasPermission(dev)) "" else " — USB access not granted yet"
        }

        val fw = FlashState.fw
        filesText.text = if (fw == null) "No firmware chosen." else "${FlashState.fwName} (${fw.size / 1024} KB)" +
            (FwImage.validate(fw)?.let { "\n⚠ $it" } ?: "")
        val (signed, advice) = FwImage.describeSignature(FlashState.sig)
        sigText.text = if (fw == null) "" else if (signed) "Signed release. The keyboard checks the signature " +
            "(${FlashState.sigName}) and installs it without asking." else advice
        sigText.visibility = if (sigText.text.isEmpty()) View.GONE else View.VISIBLE

        val running = FlashState.running
        flashButton.isEnabled = !running && !fetching && fw != null && dev != null
        findViewById<Button>(R.id.latest).isEnabled = !running && !fetching
        findViewById<Button>(R.id.pick).isEnabled = !running && !fetching
        cancelButton.visibility = if (running && FlashState.cancellable) View.VISIBLE else View.GONE
        applyBox.isEnabled = !running
        for (i in 0 until modeGroup.childCount) modeGroup.getChildAt(i).isEnabled = !running
        progressBar.progress = FlashState.pct
        progressBar.visibility = if (running || FlashState.result != null) View.VISIBLE else View.GONE
        val result = FlashState.result
        statusText.text = when {
            result != null -> (if (result.ok) "✓ " else "✗ ") + result.message
            else -> FlashState.message
        }
        if (running) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }
}

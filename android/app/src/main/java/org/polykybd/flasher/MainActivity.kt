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

        findViewById<Button>(R.id.pick).setOnClickListener { pickFiles() }
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

    private fun pickFiles() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType("*/*")
            .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
        startActivityForResult(intent, PICK_FILES)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != PICK_FILES || resultCode != RESULT_OK || data == null) return
        val uris = buildList {
            data.clipData?.let { clip -> for (i in 0 until clip.itemCount) add(clip.getItemAt(i).uri) }
            if (isEmpty()) data.data?.let { add(it) }
        }
        var fw: Pair<String, ByteArray>? = null
        var sig: Pair<String, ByteArray>? = null
        for (uri in uris) {
            val name = displayName(uri)
            val bytes = try {
                contentResolver.openInputStream(uri)?.use { it.readBytes() }
            } catch (e: Exception) {
                null
            }
            if (bytes == null) {
                statusText.text = "Could not read $name."
                continue
            }
            // A .sig is 64 raw bytes; anything else is taken as the image.
            if (name.endsWith(".sig", ignoreCase = true) || bytes.size == FwImage.SIG_LEN) sig = name to bytes
            else fw = name to bytes
        }
        if (fw != null) {
            FlashState.fw = fw.second
            FlashState.fwName = fw.first
            FlashState.sig = sig?.second
            FlashState.sigName = sig?.first
        } else if (sig != null) {
            FlashState.sig = sig.second
            FlashState.sigName = sig.first
        }
        FlashState.result = null
        FlashState.update(0, "")
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
            dev == null -> "Keyboard: not connected"
            else -> "Keyboard: ${dev.productName ?: "PolyKybd"} (%04x:%04x)".format(dev.vendorId, dev.productId) +
                if (usb.hasPermission(dev)) "" else " — USB access not granted yet"
        }

        val fw = FlashState.fw
        filesText.text = if (fw == null) "No firmware chosen." else "Firmware: ${FlashState.fwName} (${fw.size / 1024} KB)" +
            (FwImage.validate(fw)?.let { "\n⚠ $it" } ?: "")
        val (signed, advice) = FwImage.describeSignature(FlashState.sig)
        sigText.text = if (fw == null) "" else if (signed) "Signature: ${FlashState.sigName}" else advice

        val running = FlashState.running
        flashButton.isEnabled = !running && fw != null && dev != null
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

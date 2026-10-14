package org.polykybd.flasher

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.SystemClock

/**
 * The keyboard's raw-HID interface over Android's USB host API.
 *
 * QMK gives raw HID (usage page 0xFF61, usage 0x62) its own interface with an
 * interrupt IN and an interrupt OUT endpoint of 64 bytes. We claim only that
 * interface with force=true, which detaches the kernel HID driver from it alone,
 * so the keyboard keeps typing on the phone while it is being updated.
 *
 * Reports carry no report-ID byte on the wire: hidapi's leading 0x00 on the
 * desktop is stripped before it reaches USB, so here byte 0 is 'P'.
 */
class UsbHidTransport(private val context: Context) : HidTransport {
    companion object {
        const val VID = 0x2021
        val PIDS = setOf(0x2007 /* split72 */, 0x2008 /* split42 */)
        const val REPORT_SIZE = 64
        const val ACTION_USB_PERMISSION = "org.polykybd.flasher.USB_PERMISSION"

        private const val HID_GET_DESCRIPTOR_REQTYPE = 0x81   // IN, standard, interface
        private const val GET_DESCRIPTOR = 0x06
        private const val REPORT_DESCRIPTOR = 0x22

        /** Usage Page (0xFF61), 2-byte item: 06 61 FF. */
        private val RAW_USAGE_PAGE_ITEM = byteArrayOf(0x06, 0x61, 0xFF.toByte())

        fun findKeyboard(usb: UsbManager): UsbDevice? =
            usb.deviceList.values.firstOrNull { it.vendorId == VID && it.productId in PIDS }

        fun requestPermission(context: Context, usb: UsbManager, device: UsbDevice) {
            val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_MUTABLE else 0
            val intent = Intent(ACTION_USB_PERMISSION).setPackage(context.packageName)
            usb.requestPermission(device, PendingIntent.getBroadcast(context, 0, intent, flags))
        }
    }

    private val usb = context.getSystemService(Context.USB_SERVICE) as UsbManager
    private var conn: UsbDeviceConnection? = null
    private var iface: UsbInterface? = null
    private var epIn: UsbEndpoint? = null
    private var epOut: UsbEndpoint? = null

    val isOpen: Boolean get() = conn != null

    /** Opens the keyboard's raw-HID interface. Returns null on success, else the reason. */
    fun open(): String? {
        close()
        val dev = findKeyboard(usb) ?: return "No PolyKybd found. Connect the keyboard's master half to the phone."
        if (!usb.hasPermission(dev)) return "No USB permission for the keyboard yet."
        val c = usb.openDevice(dev) ?: return "Android could not open the keyboard."
        val pick = pickRawHid(dev, c)
        if (pick == null) {
            c.close()
            return "The keyboard exposes no raw-HID interface. Is this PolyKybd firmware?"
        }
        val (intf, inEp, outEp) = pick
        if (!c.claimInterface(intf, true)) {
            c.close()
            return "Android refused to hand over the keyboard's raw-HID interface."
        }
        conn = c; iface = intf; epIn = inEp; epOut = outEp
        return null
    }

    private fun pickRawHid(dev: UsbDevice, c: UsbDeviceConnection): Triple<UsbInterface, UsbEndpoint, UsbEndpoint>? {
        val candidates = (0 until dev.interfaceCount).map { dev.getInterface(it) }
            .filter { it.interfaceClass == UsbConstants.USB_CLASS_HID }
            .mapNotNull { intf ->
                var inEp: UsbEndpoint? = null
                var outEp: UsbEndpoint? = null
                for (e in 0 until intf.endpointCount) {
                    val ep = intf.getEndpoint(e)
                    if (ep.type != UsbConstants.USB_ENDPOINT_XFER_INT) continue
                    if (ep.direction == UsbConstants.USB_DIR_IN) inEp = ep else outEp = ep
                }
                if (inEp != null && outEp != null) Triple(intf, inEp, outEp) else null
            }
        // Prefer the interface whose report descriptor names the raw usage page; fall
        // back to the only IN+OUT HID interface (the keyboard and console have no OUT).
        return candidates.firstOrNull { hasRawUsagePage(c, it.first) } ?: candidates.singleOrNull()
    }

    private fun hasRawUsagePage(c: UsbDeviceConnection, intf: UsbInterface): Boolean {
        val buf = ByteArray(256)
        val n = c.controlTransfer(HID_GET_DESCRIPTOR_REQTYPE, GET_DESCRIPTOR, REPORT_DESCRIPTOR shl 8,
            intf.id, buf, buf.size, 1000)
        if (n < RAW_USAGE_PAGE_ITEM.size) return false
        outer@ for (i in 0..n - RAW_USAGE_PAGE_ITEM.size) {
            for (j in RAW_USAGE_PAGE_ITEM.indices) if (buf[i + j] != RAW_USAGE_PAGE_ITEM[j]) continue@outer
            return true
        }
        return false
    }

    private fun readOne(timeoutMs: Int): ByteArray? {
        val c = conn ?: return null
        val buf = ByteArray(REPORT_SIZE)
        val n = c.bulkTransfer(epIn, buf, buf.size, timeoutMs.coerceAtLeast(1))
        return if (n > 0) buf.copyOf(n) else null
    }

    override fun sendAndRead(pkt: ByteArray, timeoutMs: Int): ByteArray? {
        val c = conn ?: return null
        val report = ByteArray(REPORT_SIZE)
        System.arraycopy(pkt, 0, report, 0, minOf(pkt.size, REPORT_SIZE))
        if (c.bulkTransfer(epOut, report, report.size, timeoutMs) < 0) return null
        val deadline = SystemClock.elapsedRealtime() + timeoutMs
        while (true) {
            val left = (deadline - SystemClock.elapsedRealtime()).toInt()
            if (left <= 0) return null
            val r = readOne(left) ?: return null
            // Skip a stale reply to an earlier command; a NACK has the same prefix.
            if (r.size >= 2 && r[0] == pkt[0] && r[1] == pkt[1]) return r
        }
    }

    override fun drain() {
        repeat(16) { readOne(20) ?: return }
    }

    override fun waitForReconnect(timeoutS: Int): Boolean {
        close()
        var deadline = SystemClock.elapsedRealtime() + timeoutS * 1000L
        var asked = false
        // Give the keyboard time to actually drop off the bus before looking for it.
        SystemClock.sleep(500)
        while (SystemClock.elapsedRealtime() < deadline) {
            val dev = findKeyboard(usb)
            if (dev != null) {
                if (usb.hasPermission(dev)) {
                    if (open() == null) {
                        drain()
                        return true
                    }
                } else if (!asked) {
                    // A re-enumerated device is a new device to Android, and permission may
                    // have to be granted again unless this app is the default for it.
                    requestPermission(context, usb, dev)
                    asked = true
                    // Leave the user a minute to tap the dialog.
                    deadline = maxOf(deadline, SystemClock.elapsedRealtime() + 60_000)
                }
            }
            SystemClock.sleep(250)
        }
        return false
    }

    override fun close() {
        conn?.let { c ->
            iface?.let { c.releaseInterface(it) }
            c.close()
        }
        conn = null; iface = null; epIn = null; epOut = null
    }
}

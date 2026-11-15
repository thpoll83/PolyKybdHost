// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.bitwig;

import com.bitwig.extension.controller.ControllerExtension;
import com.bitwig.extension.controller.api.Application;
import com.bitwig.extension.controller.api.ControllerHost;
import com.bitwig.extension.controller.api.Preferences;
import com.bitwig.extension.controller.api.SettableBooleanValue;
import com.bitwig.extension.controller.api.SettableRangedValue;
import com.bitwig.extension.controller.api.SettableStringValue;

/**
 * The Bitwig glue: observes {@code Application.panelLayout()} and hands each change, plus a
 * keep-alive every {@link ContextReport#KEEPALIVE_MS}, to the {@link ReportSender}.
 *
 * <p>Bitwig cannot tell an extension whether its window has OS focus, so reports always say
 * {@code focused: true}. The host uses a report only while Bitwig Studio is the focused
 * application and only while it is fresh, so a Bitwig in the background never changes the
 * overlay of the app in front.
 */
public class PolyKybdReporterExtension extends ControllerExtension
{
   private static final String CATEGORY = "PolyKybd";
   private static final int MAX_PORT = 65535;

   private ReportSender sender;
   private ContextReport.SendPolicy policy;
   private SettableBooleanValue enabled;
   private SettableRangedValue port;
   private SettableStringValue token;
   private volatile String layout = "";
   private volatile long lastChangeMs;
   private volatile boolean running;
   private boolean withdrawn;
   private final long pid;

   protected PolyKybdReporterExtension(final PolyKybdReporterDefinition definition,
                                       final ControllerHost host)
   {
      super(definition, host);
      pid = currentPid();
   }

   @Override
   public void init()
   {
      final ControllerHost host = getHost();
      final Preferences prefs = host.getPreferences();
      enabled = prefs.getBooleanSetting("Report context", CATEGORY, true);
      // The number setting is normalised 0..1; getRaw() is the port number.
      port = prefs.getNumberSetting("Port", CATEGORY, 1024, MAX_PORT, 1, "",
                                    ContextReport.DEFAULT_PORT);
      token = prefs.getStringSetting("Token", CATEGORY, 64, "");
      enabled.markInterested();
      port.markInterested();
      token.markInterested();
      enabled.addValueObserver(on -> {
         if (!on)
            withdraw();
         else
         {
            withdrawn = false;
            tick();
         }
      });

      sender = newSender(host);
      policy = new ContextReport.SendPolicy(ContextReport.KEEPALIVE_MS);
      lastChangeMs = System.currentTimeMillis();

      final Application app = host.createApplication();
      app.panelLayout().addValueObserver(value -> {
         layout = value == null ? "" : value;
         lastChangeMs = System.currentTimeMillis();
         tick();
      });
      running = true;
      scheduleKeepalive();
      host.println("PolyKybd Context Reporter: reporting the panel layout to 127.0.0.1:"
                   + portNumber());
   }

   @Override
   public void exit()
   {
      running = false;
      withdraw();
      if (sender != null)
         sender.stop(1000);
   }

   @Override
   public void flush()
   {
      // Nothing to send to hardware.
   }

   /** The sender; a test replaces the HTTP POST. */
   ReportSender newSender(final ControllerHost host)
   {
      return new ReportSender(null, host::errorln);
   }

   private void scheduleKeepalive()
   {
      getHost().scheduleTask(() -> {
         if (!running)
            return;
         tick();
         scheduleKeepalive();
      }, ContextReport.KEEPALIVE_MS / 3);
   }

   /** Sends the current layout if it changed or the keep-alive is due. */
   private void tick()
   {
      if (sender == null || !enabled.get())
         return;
      final String url = ContextReport.contextUrl(layout);
      final long now = System.currentTimeMillis();
      if (!policy.due(url, now))
         return;
      final double age = Math.max(0, now - lastChangeMs) / 1000.0;
      sender.submit(portNumber(), ContextReport.payload(url, token.get(), pid, age, true));
      policy.sent(url, now);
   }

   /** One last report with no URL, so the keyboard leaves Bitwig's layout overlay at once. */
   private void withdraw()
   {
      if (sender == null || withdrawn)
         return;
      withdrawn = true;
      sender.submit(portNumber(), ContextReport.payload(null, token.get(), pid, -1, false));
      policy = new ContextReport.SendPolicy(ContextReport.KEEPALIVE_MS);
   }

   private int portNumber()
   {
      final long p = Math.round(port.getRaw());
      return (p >= 1 && p <= MAX_PORT) ? (int)p : ContextReport.DEFAULT_PORT;
   }

   private static long currentPid()
   {
      try
      {
         return ProcessHandle.current().pid();
      }
      catch (final Throwable t)
      {
         return -1;
      }
   }
}

// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.bitwig;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.bitwig.extension.callback.BooleanValueChangedCallback;
import com.bitwig.extension.callback.StringValueChangedCallback;
import com.bitwig.extension.controller.api.Application;
import com.bitwig.extension.controller.api.ControllerHost;
import com.bitwig.extension.controller.api.Preferences;
import com.bitwig.extension.controller.api.SettableBooleanValue;
import com.bitwig.extension.controller.api.SettableRangedValue;
import com.bitwig.extension.controller.api.SettableStringValue;
import com.bitwig.extension.controller.api.StringValue;

/**
 * Drives the extension through init, a panel layout change, the keep-alive task,
 * the "Report context" switch and exit against a fake ControllerHost (dynamic
 * proxies). This is not Bitwig Studio: it checks the extension calls only the API
 * it means to and sends what the contract says.
 */
class ExtensionLifecycleTest
{
   private final List<String> sent = Collections.synchronizedList(new ArrayList<>());
   private StringValueChangedCallback layoutObserver;
   private BooleanValueChangedCallback enabledObserver;
   private Runnable scheduled;
   private boolean enabled = true;

   @SuppressWarnings("unchecked")
   private static <T> T proxy(final Class<T> type, final java.lang.reflect.InvocationHandler h)
   {
      return (T)Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, h);
   }

   private ControllerHost host()
   {
      final SettableBooleanValue enabledSetting = proxy(SettableBooleanValue.class, (p, m, a) -> {
         if (m.getName().equals("get"))
            return enabled;
         if (m.getName().equals("addValueObserver"))
            enabledObserver = (BooleanValueChangedCallback)a[0];
         return null;
      });
      final SettableRangedValue port = proxy(SettableRangedValue.class, (p, m, a) ->
         m.getName().equals("getRaw") ? 50164.0 : null);
      final SettableStringValue token = proxy(SettableStringValue.class, (p, m, a) ->
         m.getName().equals("get") ? "" : null);
      final Preferences prefs = proxy(Preferences.class, (p, m, a) -> {
         switch (m.getName())
         {
            case "getBooleanSetting": return enabledSetting;
            case "getNumberSetting": return port;
            case "getStringSetting": return token;
            default: throw new AssertionError("unexpected Preferences." + m.getName());
         }
      });
      final StringValue layout = proxy(StringValue.class, (p, m, a) -> {
         if (m.getName().equals("addValueObserver"))
            layoutObserver = (StringValueChangedCallback)a[0];
         return null;
      });
      final Application app = proxy(Application.class, (p, m, a) -> {
         if (m.getName().equals("panelLayout"))
            return layout;
         throw new AssertionError("unexpected Application." + m.getName());
      });
      return proxy(ControllerHost.class, (p, m, a) -> {
         switch (m.getName())
         {
            case "getPreferences": return prefs;
            case "createApplication": return app;
            case "scheduleTask": scheduled = (Runnable)a[0]; return null;
            case "println": case "errorln": return null;
            default: throw new AssertionError("unexpected ControllerHost." + m.getName());
         }
      });
   }

   private PolyKybdReporterExtension extension()
   {
      final ControllerHost host = host();
      return new PolyKybdReporterExtension(new PolyKybdReporterDefinition(), host)
      {
         @Override
         ReportSender newSender(final ControllerHost h)
         {
            return new ReportSender((port, body) ->
               sent.add(port + " " + new String(body, StandardCharsets.UTF_8)), null);
         }
      };
   }

   private void waitFor(final int n) throws InterruptedException
   {
      for (int i = 0; i < 200 && sent.size() < n; i++)
         Thread.sleep(10);
      assertTrue(sent.size() >= n, "expected " + n + " reports, got " + sent);
   }

   @Test
   void reportsLayoutKeepsAliveAndWithdraws() throws Exception
   {
      final PolyKybdReporterExtension ext = extension();
      ext.init();
      assertTrue(scheduled != null, "no keep-alive scheduled");

      layoutObserver.valueChanged("EDIT");
      waitFor(1);
      assertTrue(sent.get(0).startsWith("50164 {\"app\": \"bitwig\", \"url\": \"bitwig://edit\", "
                                        + "\"focused\": true, \"pid\": "), sent.get(0));

      scheduled.run();                      // keep-alive not yet due: nothing new
      Thread.sleep(50);
      assertEquals(1, sent.size());

      layoutObserver.valueChanged("MIX");
      waitFor(2);
      assertTrue(sent.get(1).contains("\"url\": \"bitwig://mix\""), sent.get(1));

      enabled = false;                      // "Report context" off -> withdrawal
      enabledObserver.valueChanged(false);
      waitFor(3);
      assertTrue(sent.get(2).contains("\"url\": null, \"focused\": false"), sent.get(2));

      layoutObserver.valueChanged("ARRANGE");   // off: nothing sent
      Thread.sleep(50);
      assertEquals(3, sent.size());

      enabled = true;
      enabledObserver.valueChanged(true);
      waitFor(4);
      assertTrue(sent.get(3).contains("\"url\": \"bitwig://arrange\""), sent.get(3));

      ext.exit();
      assertEquals(5, sent.size(), sent.toString());
      assertTrue(sent.get(4).contains("\"url\": null, \"focused\": false"), sent.get(4));
   }
}

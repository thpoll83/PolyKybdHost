// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.bitwig;

import java.util.Locale;

/**
 * The Bitwig-free half of the PolyKybd Context Reporter: building the pseudo-URL,
 * the JSON body, and deciding when to send. Unit-tested without Bitwig.
 *
 * <p>What is sent, and nothing else:
 *
 * <pre>
 * POST http://127.0.0.1:&lt;port&gt;/report      Content-Type: application/json
 * {"app": "bitwig", "url": "bitwig://edit", "focused": true,
 *  "pid": 4242, "input_age": 0.4, "token": "&lt;only if one is configured&gt;"}
 * </pre>
 *
 * <p>The URL names the active panel layout ({@code Application.panelLayout()}:
 * ARRANGE, MIX, EDIT, and PLAY in the Tablet display profile) in lower case. No
 * project name, track or clip data, no window title.
 */
public final class ContextReport
{
   public static final String APP = "bitwig";
   /** PolyKybdHost's {@code browser_report_port}, the same receiver the Blender add-on uses. */
   public static final int DEFAULT_PORT = 50164;
   /**
    * The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S), so the
    * extension re-sends its context well inside that window.
    */
   public static final long KEEPALIVE_MS = 3000;

   private ContextReport()
   {
   }

   /** A panel layout name as a URL token: lower case ASCII letters, digits and '_', at most 32 characters. */
   static String token(final String value)
   {
      if (value == null)
         return "";
      final String s = value.trim().toLowerCase(Locale.ROOT);
      if (s.isEmpty() || s.length() > 32)
         return "";
      for (int i = 0; i < s.length(); i++)
      {
         final char c = s.charAt(i);
         if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_'))
            return "";
      }
      return s;
   }

   /** {@code bitwig://<layout>}, or null when the layout name is empty or not a plain identifier. */
   public static String contextUrl(final String panelLayout)
   {
      final String t = token(panelLayout);
      return t.isEmpty() ? null : "bitwig://" + t;
   }

   /**
    * One report body. {@code url == null} with {@code focused == false} withdraws this instance's
    * context, so the host stops showing its layout when the extension is removed or Bitwig exits.
    * {@code pid} is omitted when {@code <= 0}, {@code inputAgeS} when negative, {@code token} when empty.
    */
   public static String payload(final String url, final String token, final long pid,
                                final double inputAgeS, final boolean focused)
   {
      final StringBuilder b = new StringBuilder(128);
      b.append("{\"app\": \"").append(APP).append("\", \"url\": ");
      if (url == null)
         b.append("null");
      else
         appendString(b, url);
      b.append(", \"focused\": ").append(focused ? "true" : "false");
      if (pid > 0)
         b.append(", \"pid\": ").append(pid);
      if (inputAgeS >= 0)
         b.append(", \"input_age\": ").append(String.format(Locale.ROOT, "%.1f", inputAgeS));
      if (token != null && !token.isEmpty())
      {
         b.append(", \"token\": ");
         appendString(b, token);
      }
      b.append('}');
      return b.toString();
   }

   /** A JSON string literal (quotes, backslash and control characters escaped). */
   static void appendString(final StringBuilder b, final String s)
   {
      b.append('"');
      for (int i = 0; i < s.length(); i++)
      {
         final char c = s.charAt(i);
         if (c == '"' || c == '\\')
            b.append('\\').append(c);
         else if (c < 0x20)
            b.append(String.format(Locale.ROOT, "\\u%04x", (int)c));
         else
            b.append(c);
      }
      b.append('"');
   }

   /** Send on change, plus a keep-alive while nothing changes. */
   public static final class SendPolicy
   {
      private final long keepaliveMs;
      private String lastUrl;
      private long lastSentMs = -1;

      public SendPolicy(final long keepaliveMs)
      {
         this.keepaliveMs = keepaliveMs;
      }

      public boolean due(final String url, final long nowMs)
      {
         if (url == null)
            return false;
         if (!url.equals(lastUrl) || lastSentMs < 0)
            return true;
         return nowMs - lastSentMs >= keepaliveMs;
      }

      public void sent(final String url, final long nowMs)
      {
         lastUrl = url;
         lastSentMs = nowMs;
      }
   }
}

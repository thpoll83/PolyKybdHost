// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.bitwig;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Proxy;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import java.util.function.Consumer;

/**
 * One daemon thread that POSTs the LATEST report; an older pending one is dropped.
 *
 * <p>{@link #submit} only stores and signals, so Bitwig's control thread never touches the
 * network. A host that is not running refuses the loopback connect at once; a hung one costs
 * this thread at most {@link #TIMEOUT_MS} per attempt. Failures are logged once per distinct
 * error and otherwise ignored: the next change or keep-alive retries.
 */
public final class ReportSender
{
   /** Sends one body to a port. Replaced in tests. */
   public interface Post
   {
      void post(int port, byte[] body) throws IOException;
   }

   static final int TIMEOUT_MS = 500;

   private final Post post;
   private final Consumer<String> log;
   private final Object lock = new Object();
   private final Set<String> seen = new HashSet<>();
   private final Thread thread;
   private int pendingPort;
   private byte[] pendingBody;
   private boolean stop;

   public ReportSender(final Post post, final Consumer<String> log)
   {
      this.post = post != null ? post : ReportSender::httpPost;
      this.log = log != null ? log : s -> {};
      thread = new Thread(this::run, "polykybd-reporter");
      thread.setDaemon(true);
      thread.start();
   }

   public void submit(final int port, final String json)
   {
      synchronized (lock)
      {
         pendingPort = port;
         pendingBody = json.getBytes(StandardCharsets.UTF_8);
         lock.notifyAll();
      }
   }

   /**
    * Stops the thread after it delivers the report still pending (the withdrawal sent on exit),
    * waiting at most {@code waitMs} for it.
    */
   public void stop(final long waitMs)
   {
      synchronized (lock)
      {
         stop = true;
         lock.notifyAll();
      }
      try
      {
         thread.join(waitMs);
      }
      catch (final InterruptedException e)
      {
         Thread.currentThread().interrupt();
      }
   }

   private void run()
   {
      while (true)
      {
         final int port;
         final byte[] body;
         synchronized (lock)
         {
            while (pendingBody == null && !stop)
            {
               try
               {
                  lock.wait();
               }
               catch (final InterruptedException e)
               {
                  return;
               }
            }
            if (pendingBody == null)
               return;
            port = pendingPort;
            body = pendingBody;
            pendingBody = null;
         }
         try
         {
            post.post(port, body);
         }
         catch (final Exception e)
         {
            final String key = e.getClass().getSimpleName() + ": " + e.getMessage();
            if (seen.add(key))
               log.accept("PolyKybd Context Reporter: report not delivered: " + key);
         }
      }
   }

   static void httpPost(final int port, final byte[] body) throws IOException
   {
      final URL url = new URL("http", "127.0.0.1", port, "/report");
      // No proxy: a loopback report must never go through a configured HTTP proxy.
      final HttpURLConnection c = (HttpURLConnection)url.openConnection(Proxy.NO_PROXY);
      try
      {
         c.setConnectTimeout(TIMEOUT_MS);
         c.setReadTimeout(TIMEOUT_MS);
         c.setRequestMethod("POST");
         c.setDoOutput(true);
         c.setUseCaches(false);
         c.setRequestProperty("Content-Type", "application/json");
         c.setFixedLengthStreamingMode(body.length);
         try (OutputStream out = c.getOutputStream())
         {
            out.write(body);
         }
         final int code = c.getResponseCode();
         try (InputStream in = code < 400 ? c.getInputStream() : c.getErrorStream())
         {
            if (in != null)
               while (in.read() >= 0)
               {
                  // drain, so the connection closes cleanly
               }
         }
         if (code != 200)
            throw new IOException("HTTP " + code);
      }
      finally
      {
         c.disconnect();
      }
   }
}

// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.bitwig;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;

class ContextReportTest
{
   @Test
   void layoutNamesBecomeLowerCaseTokens()
   {
      assertEquals("bitwig://arrange", ContextReport.contextUrl("ARRANGE"));
      assertEquals("bitwig://mix", ContextReport.contextUrl("MIX"));
      assertEquals("bitwig://edit", ContextReport.contextUrl("EDIT"));
      assertEquals("bitwig://play", ContextReport.contextUrl(" PLAY "));
   }

   @Test
   void unknownOrUnsafeLayoutSendsNothing()
   {
      assertNull(ContextReport.contextUrl(null));
      assertNull(ContextReport.contextUrl(""));
      assertNull(ContextReport.contextUrl("My Layout"));
      assertNull(ContextReport.contextUrl("edit/../x"));
      assertNull(ContextReport.contextUrl("x".repeat(33)));
   }

   @Test
   void payloadHasExactlyTheContractFields()
   {
      assertEquals("{\"app\": \"bitwig\", \"url\": \"bitwig://edit\", \"focused\": true, "
                   + "\"pid\": 4242, \"input_age\": 0.4}",
                   ContextReport.payload("bitwig://edit", "", 4242, 0.42, true));
   }

   @Test
   void withdrawalHasNullUrlAndNoAge()
   {
      assertEquals("{\"app\": \"bitwig\", \"url\": null, \"focused\": false, \"pid\": 7}",
                   ContextReport.payload(null, null, 7, -1, false));
   }

   @Test
   void tokenIsEscaped()
   {
      assertEquals("{\"app\": \"bitwig\", \"url\": \"bitwig://mix\", \"focused\": true, "
                   + "\"token\": \"a\\\"b\\\\c\\u000a\"}",
                   ContextReport.payload("bitwig://mix", "a\"b\\c\n", 0, -1, true));
   }

   @Test
   void sendPolicySendsOnChangeAndKeepalive()
   {
      final ContextReport.SendPolicy p = new ContextReport.SendPolicy(3000);
      assertFalse(p.due(null, 0));
      assertTrue(p.due("bitwig://arrange", 0));
      p.sent("bitwig://arrange", 0);
      assertFalse(p.due("bitwig://arrange", 2999));
      assertTrue(p.due("bitwig://arrange", 3000));
      assertTrue(p.due("bitwig://edit", 10));
   }

   @Test
   void senderDeliversTheWithdrawalPendingAtStop() throws Exception
   {
      final List<String> got = Collections.synchronizedList(new ArrayList<>());
      final CountDownLatch first = new CountDownLatch(1);
      final ReportSender s = new ReportSender((port, body) -> {
         got.add(port + " " + new String(body, StandardCharsets.UTF_8));
         first.countDown();
      }, null);
      s.submit(50164, "{\"a\": 1}");
      assertTrue(first.await(2, TimeUnit.SECONDS));
      s.submit(50164, "{\"url\": null}");
      s.stop(2000);
      assertEquals(List.of("50164 {\"a\": 1}", "50164 {\"url\": null}"), got);
   }

   @Test
   void senderSurvivesAFailedPostAndLogsOnce() throws Exception
   {
      final List<String> logged = Collections.synchronizedList(new ArrayList<>());
      final Semaphore attempts = new Semaphore(0);
      final ReportSender s = new ReportSender((port, body) -> {
         attempts.release();
         throw new IOException("refused");
      }, logged::add);
      for (int i = 0; i < 3; i++)
      {
         s.submit(1, "{}");
         assertTrue(attempts.tryAcquire(2, TimeUnit.SECONDS));
      }
      s.stop(1000);
      assertEquals(1, logged.size());
   }
}

// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.bitwig;

import java.util.UUID;

import com.bitwig.extension.api.PlatformType;
import com.bitwig.extension.controller.AutoDetectionMidiPortNamesList;
import com.bitwig.extension.controller.ControllerExtensionDefinition;
import com.bitwig.extension.controller.api.ControllerHost;

/**
 * Registers the reporter with Bitwig Studio. It has no MIDI ports and is not auto-detected:
 * add it by hand in Settings &gt; Controllers &gt; Add controller &gt; PolyKybd &gt; Context Reporter.
 */
public class PolyKybdReporterDefinition extends ControllerExtensionDefinition
{
   private static final UUID ID = UUID.fromString("d191805f-cbf5-5a7e-a42f-8be81f7dcdc0");

   @Override
   public String getName()
   {
      return "PolyKybd Context Reporter";
   }

   @Override
   public String getAuthor()
   {
      return "PolyKybd";
   }

   @Override
   public String getVersion()
   {
      return "1.0.0";
   }

   @Override
   public UUID getId()
   {
      return ID;
   }

   @Override
   public String getHardwareVendor()
   {
      return "PolyKybd";
   }

   @Override
   public String getHardwareModel()
   {
      return "Context Reporter";
   }

   /** API 10 (Bitwig Studio 3.0). Every call used exists since API 7 or earlier. */
   @Override
   public int getRequiredAPIVersion()
   {
      return 10;
   }

   @Override
   public int getNumMidiInPorts()
   {
      return 0;
   }

   @Override
   public int getNumMidiOutPorts()
   {
      return 0;
   }

   @Override
   public void listAutoDetectionMidiPortNames(final AutoDetectionMidiPortNamesList list,
                                              final PlatformType platformType)
   {
      // No hardware to detect.
   }

   @Override
   public PolyKybdReporterExtension createInstance(final ControllerHost host)
   {
      return new PolyKybdReporterExtension(this, host);
   }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Build: `gradle buildPlugin` -> build/distributions/polykybd-context-reporter-<version>.zip
// Needs the IntelliJ Platform Gradle Plugin 2.x and downloads the IntelliJ IDEA
// Community SDK (about 1 GB) on the first run.
import org.jetbrains.intellij.platform.gradle.TestFrameworkType

plugins {
    id("org.jetbrains.kotlin.jvm") version "2.1.20"
    id("org.jetbrains.intellij.platform") version "2.10.5"
}

group = "org.polykybd"
version = "1.0.0"

repositories {
    mavenCentral()
    intellijPlatform { defaultRepositories() }
}

dependencies {
    intellijPlatform {
        // The oldest platform the plugin is built against; `sinceBuild` below.
        intellijIdeaCommunity("2024.2.6")
        testFramework(TestFrameworkType.Platform)
    }
    testImplementation("junit:junit:4.13.2")
}

kotlin { jvmToolchain(21) }

intellijPlatform {
    pluginConfiguration {
        ideaVersion {
            sinceBuild = "242"
            untilBuild = provider { null }   // no upper bound
        }
    }
    buildSearchableOptions = false
}

// The zip is committed (polyhost/res/jetbrains/, see README "Build") and CI
// rebuilds it and compares the bytes, so the archives must not depend on the
// time or the machine: no file times, a fixed order, and no build-machine
// lines (Build-JVM, Build-OS) in the jar manifest.
tasks.withType<AbstractArchiveTask>().configureEach {
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
}
tasks.named("generateManifest") {
    doLast {
        outputs.files.filter { it.isFile }.forEach { f ->
            f.writeText(f.readLines().filterNot {
                it.startsWith("Build-JVM:") || it.startsWith("Build-OS:")
            }.joinToString("\n", postfix = "\n"))
        }
    }
}

// `gradle shipPlugin`: build the zip and copy it to where the host app ships it
// (polyhost/res/jetbrains/polykybd-context-reporter.zip, no version in the name).
tasks.register<Copy>("shipPlugin") {
    from(tasks.named("buildPlugin"))
    into(layout.projectDirectory.dir("../polyhost/res/jetbrains"))
    rename { "polykybd-context-reporter.zip" }
}

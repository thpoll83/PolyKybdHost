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

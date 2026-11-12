plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("app.cash.paparazzi")
}

android {
    namespace = "org.polykybd.flasher"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.polykybd.flasher"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"

        // Client ID of the GitHub App behind "Sign in with GitHub" (maintenance menu).
        // Public, not a secret: the device flow uses no client secret. Empty = sign-in
        // is shown as not set up. Set polykybd.githubClientId in gradle.properties.
        val clientId = providers.gradleProperty("polykybd.githubClientId").getOrElse("")
        require(Regex("[A-Za-z0-9._-]*").matches(clientId)) { "polykybd.githubClientId has odd characters" }
        buildConfigField("String", "GITHUB_CLIENT_ID", "\"$clientId\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    // android.jar only stubs org.json; JVM tests need the real implementation.
    testImplementation("org.json:json:20240303")
}

import java.util.Properties

plugins {
    id("com.android.application")
}

// Versione e variante le scrive costruisci.py (le stesse della build senza Gradle).
val preparato = file("../../build/gradle")
val conf = Properties().apply { file("$preparato/config.properties").inputStream().use { load(it) } }

android {
    namespace = "com.rikyroky.pagebrawl"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.rikyroky.pagebrawl"
        minSdk = 26
        targetSdk = 36
        versionCode = conf.getProperty("versionCode").toInt()
        versionName = conf.getProperty("versionName")
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("$preparato/AndroidManifest.xml")
            java.setSrcDirs(listOf("../../app/java", "../../app/java-billing", "$preparato/gen"))
            res.setSrcDirs(listOf("../../app/res"))
            assets.setSrcDirs(listOf("../../build/assets"))
        }
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false          // niente R8: il codice è piccolo e le interfacce JS restano com'erano
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

dependencies {
    // Dal 31/08/2026 il Play vuole la Billing Library 8 o successiva.
    implementation("com.android.billingclient:billing:9.1.0")
    // Le dipendenze della libreria tirano dentro kotlin-stdlib 1.8 e i vecchi -jdk7/-jdk8 1.6: classi doppie.
    // Il BOM allinea tutto alla stessa versione (dalla 1.8 i -jdk7/-jdk8 sono vuoti).
    implementation(platform("org.jetbrains.kotlin:kotlin-bom:1.8.22"))
}

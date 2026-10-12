// Il progetto Gradle di Page Brawl (12/10/2026): serve solo per la versione del Play Store, che ha la
// libreria di Google Play Billing (e le sue dipendenze AndroidX e Play Services, che senza Gradle non si
// mettono insieme a mano). I sorgenti sono quelli di android/app; asset, manifest e la costante della
// variante li prepara `python3 android/costruisci.py --gradle --aab [--leggera]` in android/build.
// Si costruisce su GitHub Actions (.github/workflows/android-play.yml), che arriva al Maven di Google.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "PageBrawl"
include(":app")

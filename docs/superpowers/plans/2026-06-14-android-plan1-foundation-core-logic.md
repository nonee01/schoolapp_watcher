# SchoolApp Android — Plan 1: Foundation & Core Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an installable Android debug APK that logs into ENSAM SchoolApp on-device, scrapes and displays the grades table, and runs the S3/S4 grade calculator — with the entire scraping/fingerprint/calculator/diff core covered by runnable JVM unit tests.

**Architecture:** Native Kotlin + Jetpack Compose (Material 3), MVVM, Hilt DI. Pure-logic classes (scraper parsing, fingerprint, calculator, diff, Telegram) are kept free of Android dependencies so they run as fast JVM unit tests. OkHttp (with a persistent in-memory CookieJar) replaces `requests.Session`; Jsoup replaces BeautifulSoup; `java.security.MessageDigest` replaces `hashlib`. Background service, full multi-screen UI, Room persistence, and MIUI survival come in Plans 2 and 3.

**Tech Stack:** Kotlin 2.0.21, AGP 8.7.3, Gradle 8.11.1, JDK 17, compileSdk 35 / minSdk 26 / targetSdk 34, Jetpack Compose (BOM 2024.12.01), Hilt 2.52 (KSP 2.0.21-1.0.28), OkHttp 4.12.0, Jsoup 1.18.3, androidx.security-crypto 1.1.0-alpha06, JUnit4 + OkHttp MockWebServer for tests.

**Target device (verified on adb):** Redmi 2209116AG (`sweet`), HyperOS 1.0, Android 13 / API 33, arm64-v8a.

---

## Conventions

- **Project root for all paths below:** `/home/notadil/Projects/schoolapp_watcher/android/`
- **App package / namespace:** `ma.ensam.schoolapp`
- **Run all gradle commands from** `/home/notadil/Projects/schoolapp_watcher/android/`
- **Run JVM unit tests with:** `./gradlew testDebugUnitTest`
- **Device is connected** (`adb devices` shows `3ad2f4880013`). Install with `./gradlew installDebug`.

## File Structure (Plan 1 scope)

```
android/
├── gradlew, gradlew.bat, gradle/wrapper/...        # Task 1
├── settings.gradle.kts, gradle.properties          # Task 1
├── gradle/libs.versions.toml                        # Task 1
├── build.gradle.kts                                 # Task 2 (root)
├── .gitignore                                        # Task 2
└── app/
    ├── build.gradle.kts                              # Task 2
    ├── proguard-rules.pro                            # Task 2
    └── src/
        ├── main/
        │   ├── AndroidManifest.xml                   # Task 3
        │   ├── java/ma/ensam/schoolapp/
        │   │   ├── SchoolApp.kt                      # Task 3 (Application + Hilt)
        │   │   ├── MainActivity.kt                   # Task 3
        │   │   ├── domain/model/Models.kt            # Task 5
        │   │   ├── domain/Presets.kt                 # Task 6
        │   │   ├── domain/Calculator.kt              # Task 7
        │   │   ├── data/Fingerprint.kt              # Task 8
        │   │   ├── data/remote/SchoolAppParsing.kt   # Task 9 (Jsoup helpers)
        │   │   ├── data/remote/SchoolAppClient.kt    # Task 10 (OkHttp client)
        │   │   ├── data/remote/InMemoryCookieJar.kt  # Task 10
        │   │   ├── data/remote/TelegramNotifier.kt   # Task 11
        │   │   ├── domain/Diff.kt                    # Task 12
        │   │   ├── data/prefs/EncryptedPrefs.kt      # Task 13
        │   │   ├── di/AppModule.kt                   # Task 14
        │   │   ├── ui/MainViewModel.kt               # Task 14
        │   │   ├── ui/MainScreen.kt                  # Task 15
        │   │   └── ui/theme/Theme.kt                 # Task 15
        │   └── res/values/{strings.xml,themes.xml}   # Task 3
        └── test/java/ma/ensam/schoolapp/
            ├── PresetsTest.kt                        # Task 6
            ├── CalculatorTest.kt                     # Task 7
            ├── FingerprintTest.kt                    # Task 8
            ├── SchoolAppParsingTest.kt               # Task 9
            ├── SchoolAppClientTest.kt                # Task 10
            ├── TelegramNotifierTest.kt               # Task 11
            └── DiffTest.kt                           # Task 12
```

---

## Phase 0 — Scaffolding

### Task 1: Gradle wrapper, settings, version catalog

**Files:**
- Create: `android/gradle/wrapper/gradle-wrapper.properties`
- Create: `android/gradle/wrapper/gradle-wrapper.jar` (downloaded)
- Create: `android/gradlew`, `android/gradlew.bat` (downloaded)
- Create: `android/settings.gradle.kts`
- Create: `android/gradle.properties`
- Create: `android/gradle/libs.versions.toml`

- [ ] **Step 1: Create directories**

```bash
mkdir -p /home/notadil/Projects/schoolapp_watcher/android/gradle/wrapper
mkdir -p /home/notadil/Projects/schoolapp_watcher/android/app/src/main/java/ma/ensam/schoolapp
mkdir -p /home/notadil/Projects/schoolapp_watcher/android/app/src/main/res/values
mkdir -p /home/notadil/Projects/schoolapp_watcher/android/app/src/test/java/ma/ensam/schoolapp
```

- [ ] **Step 2: Download the Gradle wrapper files (pinned to v8.11.1)**

Run:
```bash
cd /home/notadil/Projects/schoolapp_watcher/android
curl -fSL -o gradle/wrapper/gradle-wrapper.jar https://raw.githubusercontent.com/gradle/gradle/v8.11.1/gradle/wrapper/gradle-wrapper.jar
curl -fSL -o gradlew     https://raw.githubusercontent.com/gradle/gradle/v8.11.1/gradlew
curl -fSL -o gradlew.bat https://raw.githubusercontent.com/gradle/gradle/v8.11.1/gradlew.bat
chmod +x gradlew
```
Expected: three files downloaded, `gradlew` executable. Verify: `ls -la gradle/wrapper/gradle-wrapper.jar` shows a ~43–60 KB file.

- [ ] **Step 3: Write `gradle/wrapper/gradle-wrapper.properties`**

```properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.11.1-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
```

- [ ] **Step 4: Write `settings.gradle.kts`**

```kotlin
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

rootProject.name = "SchoolAppAndroid"
include(":app")
```

- [ ] **Step 5: Write `gradle.properties`**

```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
```

- [ ] **Step 6: Write `gradle/libs.versions.toml`**

```toml
[versions]
agp = "8.7.3"
kotlin = "2.0.21"
ksp = "2.0.21-1.0.28"
hilt = "2.52"
hiltNavigationCompose = "1.2.0"
coreKtx = "1.15.0"
lifecycle = "2.8.7"
activityCompose = "1.9.3"
composeBom = "2024.12.01"
coroutines = "1.9.0"
okhttp = "4.12.0"
jsoup = "1.18.3"
securityCrypto = "1.1.0-alpha06"
junit = "4.13.2"

[libraries]
androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "coreKtx" }
androidx-lifecycle-runtime-ktx = { group = "androidx.lifecycle", name = "lifecycle-runtime-ktx", version.ref = "lifecycle" }
androidx-lifecycle-viewmodel-compose = { group = "androidx.lifecycle", name = "lifecycle-viewmodel-compose", version.ref = "lifecycle" }
androidx-activity-compose = { group = "androidx.activity", name = "activity-compose", version.ref = "activityCompose" }
androidx-compose-bom = { group = "androidx.compose", name = "compose-bom", version.ref = "composeBom" }
androidx-ui = { group = "androidx.compose.ui", name = "ui" }
androidx-ui-graphics = { group = "androidx.compose.ui", name = "ui-graphics" }
androidx-ui-tooling = { group = "androidx.compose.ui", name = "ui-tooling" }
androidx-ui-tooling-preview = { group = "androidx.compose.ui", name = "ui-tooling-preview" }
androidx-material3 = { group = "androidx.compose.material3", name = "material3" }
hilt-android = { group = "com.google.dagger", name = "hilt-android", version.ref = "hilt" }
hilt-compiler = { group = "com.google.dagger", name = "hilt-android-compiler", version.ref = "hilt" }
androidx-hilt-navigation-compose = { group = "androidx.hilt", name = "hilt-navigation-compose", version.ref = "hiltNavigationCompose" }
kotlinx-coroutines-android = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-android", version.ref = "coroutines" }
okhttp = { group = "com.squareup.okhttp3", name = "okhttp", version.ref = "okhttp" }
jsoup = { group = "org.jsoup", name = "jsoup", version.ref = "jsoup" }
androidx-security-crypto = { group = "androidx.security", name = "security-crypto", version.ref = "securityCrypto" }
junit = { group = "junit", name = "junit", version.ref = "junit" }
okhttp-mockwebserver = { group = "com.squareup.okhttp3", name = "mockwebserver", version.ref = "okhttp" }
kotlinx-coroutines-test = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-test", version.ref = "coroutines" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
ksp = { id = "com.google.devtools.ksp", version.ref = "ksp" }
hilt = { id = "com.google.dagger.hilt.android", version.ref = "hilt" }
```

- [ ] **Step 7: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/gradlew android/gradlew.bat android/gradle android/settings.gradle.kts android/gradle.properties
git commit -m "chore(android): add gradle wrapper, settings, version catalog"
```

---

### Task 2: Root + app build files

**Files:**
- Create: `android/build.gradle.kts`
- Create: `android/app/build.gradle.kts`
- Create: `android/app/proguard-rules.pro`
- Create: `android/.gitignore`

- [ ] **Step 1: Write root `build.gradle.kts`**

```kotlin
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.hilt) apply false
}
```

- [ ] **Step 2: Write `app/build.gradle.kts`**

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

android {
    namespace = "ma.ensam.schoolapp"
    compileSdk = 35

    defaultConfig {
        applicationId = "ma.ensam.schoolapp"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
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
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    debugImplementation(libs.androidx.ui.tooling)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.androidx.hilt.navigation.compose)

    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.okhttp)
    implementation(libs.jsoup)
    implementation(libs.androidx.security.crypto)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
}
```

- [ ] **Step 3: Write `app/proguard-rules.pro`**

```proguard
# Jsoup
-keep class org.jsoup.** { *; }
# OkHttp (R8 friendly; suppress warnings for optional deps)
-dontwarn okhttp3.**
-dontwarn okio.**
# Keep Hilt generated components
-keep class dagger.hilt.** { *; }
-keep class * extends dagger.hilt.android.lifecycle.HiltViewModel { *; }
```

- [ ] **Step 4: Write `android/.gitignore`**

```gitignore
*.iml
.gradle/
/local.properties
/.idea/
.DS_Store
/build
/captures
.externalNativeBuild
.cxx
local.properties
app/build/
```

- [ ] **Step 5: Create `local.properties` pointing at the SDK** (not committed)

```bash
cd /home/notadil/Projects/schoolapp_watcher/android
printf 'sdk.dir=/opt/android-sdk\n' > local.properties
```

- [ ] **Step 6: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/build.gradle.kts android/app/build.gradle.kts android/app/proguard-rules.pro android/.gitignore
git commit -m "chore(android): root and app gradle build files"
```

---

### Task 3: Manifest, Application (Hilt), MainActivity, resources

**Files:**
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/SchoolApp.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/MainActivity.kt`
- Create: `android/app/src/main/res/values/strings.xml`
- Create: `android/app/src/main/res/values/themes.xml`

- [ ] **Step 1: Write `AndroidManifest.xml`** (full permission set declared now for forward-compat; service/receiver added in Plan 2)

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <application
        android:name=".SchoolApp"
        android:allowBackup="false"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.SchoolApp">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.SchoolApp">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

- [ ] **Step 2: Write `SchoolApp.kt`**

```kotlin
package ma.ensam.schoolapp

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class SchoolApp : Application()
```

- [ ] **Step 3: Write `res/values/strings.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">SchoolApp Watcher</string>
</resources>
```

- [ ] **Step 4: Write `res/values/themes.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.SchoolApp" parent="android:Theme.Material.Light.NoActionBar" />
</resources>
```

- [ ] **Step 5: Write `MainActivity.kt`** (placeholder UI; replaced in Task 15)

```kotlin
package ma.ensam.schoolapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface {
                    Text("SchoolApp Watcher")
                }
            }
        }
    }
}
```

- [ ] **Step 6: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main
git commit -m "feat(android): manifest, Hilt Application, MainActivity scaffold"
```

---

### Task 4: Verify the empty app builds and installs on device

- [ ] **Step 1: Build the debug APK** (first run downloads Gradle 8.11.1 + dependencies; needs internet)

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew assembleDebug`
Expected: `BUILD SUCCESSFUL`. APK at `app/build/outputs/apk/debug/app-debug.apk`.

- [ ] **Step 2: Install on the connected device**

Run: `./gradlew installDebug`
Expected: `BUILD SUCCESSFUL` and `Installed on 1 device`.

- [ ] **Step 3: Launch and confirm**

Run: `adb shell am start -n ma.ensam.schoolapp/.MainActivity`
Expected: app opens on the phone showing "SchoolApp Watcher". Confirm no crash with: `adb logcat -d -t 200 | grep -i "ma.ensam.schoolapp\|AndroidRuntime"` (expect no `FATAL EXCEPTION`).

- [ ] **Step 4: Commit** (nothing to commit if clean; otherwise commit any fixups)

```bash
cd /home/notadil/Projects/schoolapp_watcher && git add -A android && git commit -m "chore(android): verified buildable, installable skeleton" --allow-empty
```

---

## Phase 1 — Core Logic (TDD, JVM unit tests)

### Task 5: Domain models

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/domain/model/Models.kt`

- [ ] **Step 1: Write the models** (faithful to `presets.py` `ElementDef`/`ModuleDef` plus a `Snapshot`)

```kotlin
package ma.ensam.schoolapp.domain.model

data class ElementDef(
    val code: String,
    val title: String,
    val coefCc: Double,
    val coefEx: Double,
    val coefEcrit: Double,
    val coefTp: Double,
    val coefEelem: Double,
)

data class ModuleDef(
    val code: String,
    val title: String,
    val niveau: String,
    val semestre: String,
    val coefMod: Double,
    val seuil: Double,
    val eliminatoire: Double,
    val elements: List<ElementDef>,
)

/** A parsed marks table. Mirrors the Python Snapshot (headers/rows/fingerprint). */
data class Snapshot(
    val headers: List<String>,
    val rows: List<List<String>>,
    val fingerprint: String,
)
```

- [ ] **Step 2: Compile-check**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew compileDebugKotlin`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/domain/model/Models.kt
git commit -m "feat(android): domain models for modules, elements, snapshot"
```

---

### Task 6: Presets S3/S4

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/domain/Presets.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/PresetsTest.kt`

- [ ] **Step 1: Write the failing test**

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Presets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class PresetsTest {
    @Test fun s3_has_seven_modules() {
        assertEquals(7, Presets.modulesForSemester("S3").size)
    }

    @Test fun s4_has_seven_modules() {
        assertEquals(7, Presets.modulesForSemester("s4").size)
    }

    @Test fun s3_first_module_is_analyse3() {
        val m = Presets.modulesForSemester("S3").first()
        assertEquals("API31", m.code)
        assertEquals(5.0, m.coefMod, 0.0001)
        assertEquals("API311", m.elements.first().code)
        assertEquals(0.3, m.elements.first().coefCc, 0.0001)
        assertEquals(0.7, m.elements.first().coefEx, 0.0001)
    }

    @Test fun s4_api45_prog_avancee_coefficients() {
        val mod = Presets.modulesForSemester("S4").first { it.code == "API45" }
        val prog = mod.elements.first { it.code == "API452" }
        assertEquals(0.3, prog.coefCc, 0.0001)
        assertEquals(1.0, prog.coefEcrit, 0.0001)
        assertEquals(1.0, prog.coefEelem, 0.0001)
    }

    @Test fun unsupported_semester_throws() {
        assertThrows(IllegalArgumentException::class.java) {
            Presets.modulesForSemester("S5")
        }
    }

    @Test fun total_coef_mod_s4_is_30() {
        val total = Presets.modulesForSemester("S4").sumOf { it.coefMod }
        assertTrue(total in 29.9..30.1)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.PresetsTest"`
Expected: FAIL — `Presets` unresolved reference.

- [ ] **Step 3: Write `Presets.kt`** (translated verbatim from `schoolapp/presets.py`)

```kotlin
package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.ElementDef
import ma.ensam.schoolapp.domain.model.ModuleDef

object Presets {

    private fun el(
        code: String, title: String,
        coefCc: Double, coefEx: Double, coefEcrit: Double, coefTp: Double, coefEelem: Double,
    ) = ElementDef(code, title, coefCc, coefEx, coefEcrit, coefTp, coefEelem)

    private fun mod(
        code: String, title: String, coefMod: Double, elements: List<ElementDef>,
        niveau: String = "2A", semestre: String, seuil: Double = 11.0, eliminatoire: Double = 7.0,
    ) = ModuleDef(code, title, niveau, semestre, coefMod, seuil, eliminatoire, elements)

    val PRESET_2A_S3: List<ModuleDef> = listOf(
        mod("API31", "Analyse 3", 5.0, listOf(
            el("API311", "Analyse 3", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S3"),
        mod("API32", "Chimie organique et métallurgie", 5.0, listOf(
            el("API321", "Chimie organique", 0.3, 0.7, 2.5, 0.5, 3.0),
            el("API322", "Métallurgie", 0.0, 1.0, 1.5, 0.5, 2.0),
        ), semestre = "S3"),
        mod("API33", "Mécanique du solide et usinage", 5.0, listOf(
            el("API331", "Mécanique du solide appliquée", 0.3, 0.7, 3.0, 0.0, 3.0),
            el("API332", "Usinage 2", 0.0, 1.0, 1.5, 0.5, 2.0),
        ), semestre = "S3"),
        mod("API34", "Automatique et RDM", 5.0, listOf(
            el("API341", "Automatique des systèmes", 0.3, 0.7, 2.25, 0.5, 2.75),
            el("API342", "RDM", 0.0, 1.0, 1.75, 0.5, 2.25),
        ), semestre = "S3"),
        mod("API35", "Programmation et Probabilités", 4.0, listOf(
            el("API351", "Programmation C++ et Algorithmique", 0.3, 0.7, 2.25, 0.0, 2.25),
            el("API352", "Calcul des Probabilités", 0.3, 0.7, 1.75, 0.0, 1.75),
        ), semestre = "S3"),
        mod("API36", "Langues 3", 3.0, listOf(
            el("API361", "Initiation à la communication", 0.3, 0.7, 1.5, 0.0, 1.5),
            el("API362", "English for International communication", 0.3, 0.7, 1.5, 0.0, 1.5),
        ), semestre = "S3"),
        mod("API37", "Culture et Arts", 3.0, listOf(
            el("API371", "Culture et Arts", 0.3, 0.7, 3.0, 0.0, 3.0)
        ), semestre = "S3"),
    )

    val PRESET_2A_S4: List<ModuleDef> = listOf(
        mod("API41", "Analyse 4", 5.0, listOf(
            el("API411", "Analyse 4", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S4"),
        mod("API42", "Algèbre 2", 5.0, listOf(
            el("API421", "Algèbre 2", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S4"),
        mod("API43", "Eléments de machine", 5.0, listOf(
            el("API431", "Eléments de machine", 0.3, 0.7, 5.0, 0.0, 5.0)
        ), semestre = "S4"),
        mod("API44", "Electromagnétisme et Optique", 5.0, listOf(
            el("API441", "Electromagnétisme", 0.3, 0.7, 2.75, 0.25, 3.0),
            el("API442", "Optique physique", 0.0, 1.0, 1.75, 0.25, 2.0),
        ), semestre = "S4"),
        mod("API45", "Programmation avancée et méthodes numériques", 4.0, listOf(
            el("API451", "Méthodes numériques", 0.0, 1.0, 1.0, 0.75, 1.75),
            el("API452", "Programmation Avancée", 0.3, 0.7, 1.0, 0.0, 1.0),
        ), semestre = "S4"),
        mod("API46", "Langues 4", 3.0, listOf(
            el("API461", "Techniques d'écriture", 0.3, 0.7, 1.5, 0.0, 1.5),
            el("API462", "English for International Communication", 0.3, 0.7, 1.5, 0.0, 1.5),
        ), semestre = "S4"),
        mod("API47", "Savoir être, Développement personnel", 3.0, listOf(
            el("API471", "Développement personnel", 0.3, 0.7, 1.5, 0.0, 1.5),
            el("API472", "Savoir être", 0.3, 0.7, 1.5, 0.0, 1.5),
        ), semestre = "S4"),
    )

    fun modulesForSemester(semester: String): List<ModuleDef> =
        when (semester.trim().uppercase()) {
            "S3" -> PRESET_2A_S3
            "S4" -> PRESET_2A_S4
            else -> throw IllegalArgumentException(
                "Unsupported semester '$semester'. Expected S3 or S4."
            )
        }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.PresetsTest"`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/domain/Presets.kt android/app/src/test/java/ma/ensam/schoolapp/PresetsTest.kt
git commit -m "feat(android): S3/S4 presets translated from presets.py (tested)"
```

---

### Task 7: Grade calculator

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/domain/Calculator.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/CalculatorTest.kt`

- [ ] **Step 1: Write the failing test** (values cross-checked against `calculator.py` formulas)

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Calculator
import ma.ensam.schoolapp.domain.Presets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CalculatorTest {

    private val api311 = Presets.PRESET_2A_S3.first { it.code == "API31" }.elements.first()

    @Test fun toFloat_parses_and_rejects() {
        assertEquals(12.5, Calculator.toFloat("12.5")!!, 0.0001)
        assertNull(Calculator.toFloat("--"))
        assertNull(Calculator.toFloat(""))
        assertNull(Calculator.toFloat("abc"))
    }

    // API311: coefCc=0.3, coefEx=0.7 → cc*0.3 + ex*0.7
    @Test fun element_grade_cc_ex() {
        val marks = mapOf("API311.cc" to 10.0, "API311.ex" to 20.0)
        // 10*0.3 + 20*0.7 = 3 + 14 = 17
        assertEquals(17.0, Calculator.calcElementGrade(api311, marks), 0.0001)
    }

    // When ecrit/tp present, ex = (ecrit*coefEcrit + tp*coefTp)/(coefEcrit+coefTp)
    @Test fun element_grade_with_ecrit_tp() {
        val api321 = Presets.PRESET_2A_S3.first { it.code == "API32" }.elements.first { it.code == "API321" }
        // coefCc=0.3 coefEx=0.7 coefEcrit=2.5 coefTp=0.5
        val marks = mapOf("API321.cc" to 12.0, "API321.ecrit" to 14.0, "API321.tp" to 8.0)
        val ex = (14.0 * 2.5 + 8.0 * 0.5) / (2.5 + 0.5) // = (35+4)/3 = 13.0
        val expected = 12.0 * 0.3 + ex * 0.7            // = 3.6 + 9.1 = 12.7
        assertEquals(expected, Calculator.calcElementGrade(api321, marks), 0.0001)
    }

    @Test fun rattrapage_returns_ordinary_when_no_rat() {
        val marks = mapOf("API311.cc" to 10.0, "API311.ex" to 8.0)
        val ord = Calculator.calcElementGrade(api311, marks)
        assertEquals(ord, Calculator.calcElementRattrapage(api311, marks, ord), 0.0001)
    }

    @Test fun rattrapage_takes_max() {
        // cc=10 (coefCc 0.3), rat=15 (coefEx 0.7): weighted = 10*0.3 + 15*0.7 = 13.5; max(13.5,15)=15
        val marks = mapOf("API311.cc" to 10.0, "API311.ex" to 5.0, "API311.rat" to 15.0)
        val ord = Calculator.calcElementGrade(api311, marks) // 10*0.3+5*0.7 = 6.5
        // final rattrapage = max(ord, max(13.5,15)) = 15
        assertEquals(15.0, Calculator.calcElementRattrapage(api311, marks, ord), 0.0001)
    }

    @Test fun semester_all_tens_is_ten_and_validated() {
        // Every element exactly 10 → every module 10 → semester 10, status VORD (>= seuil 11? no)
        val s4 = Presets.modulesForSemester("S4")
        val marks = HashMap<String, Double>()
        for (m in s4) for (e in m.elements) {
            marks["${e.code}.cc"] = 10.0
            marks["${e.code}.ex"] = 10.0
            marks["${e.code}.ecrit"] = 10.0
            marks["${e.code}.tp"] = 10.0
        }
        val result = Calculator.computeSemester(s4, marks)
        assertEquals(10.0, result.semesterAverageFinal, 0.0001)
        // 10 < seuil 11 → all NV
        assertEquals(s4.size, result.modules.count { it.status == "NV" })
    }

    @Test fun semester_all_twelves_validates_ordinaire() {
        val s4 = Presets.modulesForSemester("S4")
        val marks = HashMap<String, Double>()
        for (m in s4) for (e in m.elements) {
            marks["${e.code}.cc"] = 12.0
            marks["${e.code}.ex"] = 12.0
            marks["${e.code}.ecrit"] = 12.0
            marks["${e.code}.tp"] = 12.0
        }
        val result = Calculator.computeSemester(s4, marks)
        assertEquals(12.0, result.semesterAverageFinal, 0.0001)
        assertEquals(s4.size, result.modules.count { it.status == "VORD" })
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.CalculatorTest"`
Expected: FAIL — `Calculator` unresolved.

- [ ] **Step 3: Write `Calculator.kt`** (translated from `calculator.py`)

```kotlin
package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.ElementDef
import ma.ensam.schoolapp.domain.model.ModuleDef

data class ModuleResult(
    val code: String,
    val title: String,
    val averageOrdinaire: Double,
    val averageRattrapage: Double,
    val averageFinal: Double,
    val status: String, // VORD | RAT | NV
)

data class SemesterResult(
    val modules: List<ModuleResult>,
    val semesterAverageOrdinaire: Double,
    val semesterAverageFinal: Double,
    val nonValidatedCodes: List<String>,
)

object Calculator {

    fun toFloat(value: String): Double? {
        val raw = value.trim()
        if (raw.isEmpty() || raw == "--") return null
        return raw.toDoubleOrNull()
    }

    /** Mirrors _calc_element_grade in calculator.py. */
    fun calcElementGrade(defn: ElementDef, marks: Map<String, Double>): Double {
        val cc = marks["${defn.code}.cc"] ?: 0.0
        val ex: Double = if (marks.containsKey("${defn.code}.ecrit") || marks.containsKey("${defn.code}.tp")) {
            val ecrit = marks["${defn.code}.ecrit"] ?: 0.0
            val tp = marks["${defn.code}.tp"] ?: 0.0
            val denom = defn.coefEcrit + defn.coefTp
            if (denom > 0) (ecrit * defn.coefEcrit + tp * defn.coefTp) / denom else 0.0
        } else {
            marks["${defn.code}.ex"] ?: 0.0
        }
        return cc * defn.coefCc + ex * defn.coefEx
    }

    /** Mirrors _calc_element_rattrapage in calculator.py. */
    fun calcElementRattrapage(defn: ElementDef, marks: Map<String, Double>, ordinaryGrade: Double): Double {
        val rat = marks["${defn.code}.rat"] ?: return ordinaryGrade
        val cc = marks["${defn.code}.cc"] ?: 0.0
        val weightedRat = cc * defn.coefCc + rat * defn.coefEx
        val ratSession = maxOf(weightedRat, rat)
        return maxOf(ordinaryGrade, ratSession)
    }

    /** Mirrors the per-module + semester loop in run_calculator (calculator.py). */
    fun computeSemester(modules: List<ModuleDef>, marks: Map<String, Double>): SemesterResult {
        val results = ArrayList<ModuleResult>()
        var semPointsOrd = 0.0
        var semPointsFinal = 0.0
        val semWeight = modules.sumOf { it.coefMod }.takeIf { it > 0 } ?: 1.0
        val nonValidated = ArrayList<String>()

        for (mod in modules) {
            var ptsOrd = 0.0
            var ptsRatt = 0.0
            var ptsFinal = 0.0
            for (el in mod.elements) {
                val ord = calcElementGrade(el, marks)
                val ratt = calcElementRattrapage(el, marks, ord)
                val finalG = maxOf(ord, ratt)
                ptsOrd += ord * el.coefEelem
                ptsRatt += ratt * el.coefEelem
                ptsFinal += finalG * el.coefEelem
            }
            val coef = if (mod.coefMod > 0) mod.coefMod else 1.0
            val avgOrd = ptsOrd / coef
            val avgRatt = ptsRatt / coef
            var avgFinal = ptsFinal / coef
            if (avgOrd < mod.seuil && mod.seuil <= avgRatt) avgFinal = mod.seuil

            semPointsOrd += avgOrd * mod.coefMod
            semPointsFinal += avgFinal * mod.coefMod

            val status = when {
                avgOrd >= mod.seuil -> "VORD"
                avgRatt >= mod.seuil -> "RAT"
                else -> "NV"
            }
            if (status == "NV") nonValidated.add(mod.code)
            results.add(ModuleResult(mod.code, mod.title, avgOrd, avgRatt, avgFinal, status))
        }

        return SemesterResult(
            modules = results,
            semesterAverageOrdinaire = semPointsOrd / semWeight,
            semesterAverageFinal = semPointsFinal / semWeight,
            nonValidatedCodes = nonValidated,
        )
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.CalculatorTest"`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/domain/Calculator.kt android/app/src/test/java/ma/ensam/schoolapp/CalculatorTest.kt
git commit -m "feat(android): grade calculator translated from calculator.py (tested)"
```

---

### Task 8: Fingerprint & marks-state diffing

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/Fingerprint.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/FingerprintTest.kt`

**Behavior note:** Faithful to `watcher.py`. `marksState` extracts only real grade fields (`CC, EX, TP, MoySO, RAT, MoySR, Moy, Dec`) per `CodeElem`, filtered to the semester's module-code prefixes, ignoring row order. Change detection = `marksState(old) != marksState(new)` (exactly Python's rule). `fingerprint` = SHA-256 over canonical JSON of the marks-state so equal state ⇒ equal hash.

- [ ] **Step 1: Write the failing test**

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.Fingerprint
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class FingerprintTest {
    private val headers = listOf("CodeElem", "AU", "CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec")

    private fun row(code: String, cc: String, ex: String, moy: String, dec: String) =
        listOf(code, "2024", cc, ex, "--", "--", "--", "--", moy, dec)

    @Test fun reordering_rows_does_not_change_state() {
        val r1 = row("API411", "12", "14", "13.4", "VORD")
        val r2 = row("API421", "10", "11", "10.7", "NV")
        val a = Fingerprint.marksState(headers, listOf(r1, r2), "S4")
        val b = Fingerprint.marksState(headers, listOf(r2, r1), "S4")
        assertEquals(a, b)
        assertEquals(Fingerprint.of(headers, listOf(r1, r2), "S4"), Fingerprint.of(headers, listOf(r2, r1), "S4"))
    }

    @Test fun changing_a_grade_changes_state() {
        val a = Fingerprint.marksState(headers, listOf(row("API411", "12", "14", "13.4", "VORD")), "S4")
        val b = Fingerprint.marksState(headers, listOf(row("API411", "12", "16", "14.8", "VORD")), "S4")
        assertNotEquals(a, b)
    }

    @Test fun elements_outside_semester_are_ignored() {
        // API311 is an S3 element; under S4 it must be filtered out of the state.
        val withForeign = Fingerprint.marksState(
            headers,
            listOf(row("API411", "12", "14", "13.4", "VORD"), row("API311", "9", "9", "9", "NV")),
            "S4",
        )
        val withoutForeign = Fingerprint.marksState(
            headers,
            listOf(row("API411", "12", "14", "13.4", "VORD")),
            "S4",
        )
        assertEquals(withoutForeign, withForeign)
    }

    @Test fun sha256_is_hex_64_chars() {
        val fp = Fingerprint.of(headers, listOf(row("API411", "12", "14", "13.4", "VORD")), "S4")
        assertEquals(64, fp.length)
        assertEquals(true, fp.all { it in "0123456789abcdef" })
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.FingerprintTest"`
Expected: FAIL — `Fingerprint` unresolved.

- [ ] **Step 3: Write `Fingerprint.kt`**

```kotlin
package ma.ensam.schoolapp.data

import ma.ensam.schoolapp.domain.Presets
import java.security.MessageDigest

object Fingerprint {

    private val STATE_FIELDS = listOf("CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec")

    /**
     * Mirrors _marks_state in watcher.py: per-element grade values for the
     * semester's modules, ignoring row order and cosmetic columns. Returns a
     * map of CodeElem -> (field -> value). If there is no CodeElem column,
     * falls back to the raw row list under "__rows__".
     */
    fun marksState(headers: List<String>, rows: List<List<String>>, semester: String): Map<String, Map<String, String>> {
        val codeIdx = headers.indexOf("CodeElem")
        if (codeIdx < 0) {
            // No CodeElem column: represent the whole table positionally.
            val fallback = LinkedHashMap<String, Map<String, String>>()
            rows.forEachIndexed { i, r -> fallback["__row_$i"] = mapOf("raw" to r.joinToString("")) }
            return fallback
        }
        val idx = headers.withIndex().associate { (i, h) -> h to i }
        val prefixes = runCatching { Presets.modulesForSemester(semester).map { it.code.uppercase() } }
            .getOrDefault(emptyList())

        val state = sortedMapOf<String, Map<String, String>>() // sorted → order independent
        for (r in rows) {
            if (r.size <= codeIdx) continue
            val code = r[codeIdx].trim()
            if (code.isEmpty()) continue
            if (prefixes.isNotEmpty() && prefixes.none { code.uppercase().startsWith(it) }) continue
            val cells = LinkedHashMap<String, String>()
            for (field in STATE_FIELDS) {
                val i = idx[field]
                cells[field] = if (i != null && i < r.size) r[i].trim() else ""
            }
            state[code] = cells
        }
        return state
    }

    /** SHA-256 over canonical JSON of the marks-state. Equal state ⇒ equal hash. */
    fun of(headers: List<String>, rows: List<List<String>>, semester: String): String {
        val state = marksState(headers, rows, semester)
        val canonical = canonicalJson(state)
        val digest = MessageDigest.getInstance("SHA-256").digest(canonical.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    private fun canonicalJson(state: Map<String, Map<String, String>>): String {
        val sb = StringBuilder("{")
        state.entries.sortedBy { it.key }.forEachIndexed { i, (code, cells) ->
            if (i > 0) sb.append(",")
            sb.append(quote(code)).append(":{")
            cells.entries.sortedBy { it.key }.forEachIndexed { j, (k, v) ->
                if (j > 0) sb.append(",")
                sb.append(quote(k)).append(":").append(quote(v))
            }
            sb.append("}")
        }
        return sb.append("}").toString()
    }

    private fun quote(s: String): String {
        val b = StringBuilder("\"")
        for (c in s) when (c) {
            '"' -> b.append("\\\"")
            '\\' -> b.append("\\\\")
            '\n' -> b.append("\\n")
            '\r' -> b.append("\\r")
            '\t' -> b.append("\\t")
            else -> b.append(c)
        }
        return b.append("\"").toString()
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.FingerprintTest"`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/Fingerprint.kt android/app/src/test/java/ma/ensam/schoolapp/FingerprintTest.kt
git commit -m "feat(android): SHA-256 fingerprint + marks-state diffing (tested)"
```

---

### Task 9: Scraper parsing (CSRF, login-page detection, table extraction)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/remote/SchoolAppParsing.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/SchoolAppParsingTest.kt`

- [ ] **Step 1: Write the failing test** (fixtures mirror the real SchoolApp HTML shapes)

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.remote.SchoolAppParsing
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SchoolAppParsingTest {

    @Test fun extracts_csrf_token() {
        val html = """<form action="/login"><input name="_csrf" value="abc123"/></form>"""
        assertEquals("abc123", SchoolAppParsing.extractCsrf(html))
    }

    @Test fun missing_csrf_returns_null() {
        assertNull(SchoolAppParsing.extractCsrf("<form action=\"/login\"></form>"))
    }

    @Test fun detects_login_page() {
        val html = """<form action="/login"><input name="password" type="password"/></form>"""
        assertTrue(SchoolAppParsing.looksLikeLoginPage(html))
    }

    @Test fun marks_page_is_not_login_page() {
        val html = "<table><tr><th>CodeElem</th></tr></table>"
        assertFalse(SchoolAppParsing.looksLikeLoginPage(html))
    }

    @Test fun normalize_collapses_whitespace() {
        assertEquals("a b c", SchoolAppParsing.normalizeCell("  a\n  b\t c  "))
    }

    @Test fun extracts_largest_table_headers_and_rows() {
        val html = """
            <table><tr><th>x</th></tr><tr><td>1</td></tr></table>
            <table>
              <tr><th>CodeElem</th><th>CC</th><th>Moy</th></tr>
              <tr><td>API411</td><td>12</td><td>13.4</td></tr>
              <tr><td>API421</td><td>10</td><td>10.7</td></tr>
            </table>
        """.trimIndent()
        val (headers, rows) = SchoolAppParsing.extractTable(html)
        assertEquals(listOf("CodeElem", "CC", "Moy"), headers)
        assertEquals(2, rows.size)
        assertEquals(listOf("API411", "12", "13.4"), rows[0])
    }

    @Test fun extract_table_throws_when_no_table() {
        try {
            SchoolAppParsing.extractTable("<div>no tables here</div>")
            throw AssertionError("expected exception")
        } catch (e: IllegalStateException) {
            assertTrue(e.message!!.contains("No table"))
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SchoolAppParsingTest"`
Expected: FAIL — `SchoolAppParsing` unresolved.

- [ ] **Step 3: Write `SchoolAppParsing.kt`** (pure Jsoup, no Android/network — JVM-testable)

```kotlin
package ma.ensam.schoolapp.data.remote

import org.jsoup.Jsoup

/** Pure HTML-parsing helpers, translated from BeautifulSoup logic in watcher.py. */
object SchoolAppParsing {

    fun normalizeCell(text: String): String =
        text.trim().replace(Regex("\\s+"), " ")

    fun extractCsrf(html: String): String? {
        val token = Jsoup.parse(html).selectFirst("input[name=_csrf]") ?: return null
        val value = token.attr("value")
        return value.ifEmpty { null }
    }

    fun looksLikeLoginPage(html: String): Boolean {
        val doc = Jsoup.parse(html)
        return doc.selectFirst("form[action=/login]") != null &&
            doc.selectFirst("input[name=password]") != null
    }

    /** Largest <table> by row count → (headers, rows). Mirrors _extract_table. */
    fun extractTable(html: String): Pair<List<String>, List<List<String>>> {
        val doc = Jsoup.parse(html)
        val tables = doc.select("table")
        if (tables.isEmpty()) error("No table found on marks page")

        val best = tables.maxByOrNull { it.select("tr").size }!!
        val headers = best.select("th").map { normalizeCell(it.text()) }

        val rows = ArrayList<List<String>>()
        for (tr in best.select("tr")) {
            val tds = tr.select("td")
            if (tds.isEmpty()) continue
            val row = tds.map { normalizeCell(it.text()) }
            if (row.any { it.isNotEmpty() }) rows.add(row)
        }
        return headers to rows
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SchoolAppParsingTest"`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/remote/SchoolAppParsing.kt android/app/src/test/java/ma/ensam/schoolapp/SchoolAppParsingTest.kt
git commit -m "feat(android): Jsoup parsing helpers (CSRF, login detect, table) (tested)"
```

---

### Task 10: Network client (CookieJar, login flow, fetch) with MockWebServer

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/remote/InMemoryCookieJar.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/remote/SchoolAppClient.kt` (standalone file)
- Test: `android/app/src/test/java/ma/ensam/schoolapp/SchoolAppClientTest.kt`

- [ ] **Step 1: Write `InMemoryCookieJar.kt`** (replaces `requests.Session` cookie persistence)

```kotlin
package ma.ensam.schoolapp.data.remote

import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl

/** Simple per-host in-memory cookie store; survives across requests in one client. */
class InMemoryCookieJar : CookieJar {
    private val store = HashMap<String, MutableList<Cookie>>()

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val host = url.host
        val list = store.getOrPut(host) { mutableListOf() }
        for (c in cookies) {
            list.removeAll { it.name == c.name }
            list.add(c)
        }
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        val list = store[url.host] ?: return emptyList()
        list.removeAll { it.expiresAt < now }
        return list.toList()
    }

    @Synchronized
    fun clear() = store.clear()
}
```

- [ ] **Step 2: Write the failing test** (MockWebServer simulates login + marks pages)

> **Important — request order:** `checkOnce` always does `GET marks` **first**. Only if that page looks like the login form does it then do `GET /login` → `POST /login` → `GET marks` again. The enqueued responses below match that exact sequence. MockWebServer replies with enqueued responses in FIFO order regardless of path.

```kotlin
package ma.ensam.schoolapp

import kotlinx.coroutines.runBlocking
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class SchoolAppClientTest {
    private lateinit var server: MockWebServer

    @Before fun setUp() { server = MockWebServer(); server.start() }
    @After fun tearDown() { server.shutdown() }

    private fun baseUrl() = server.url("/").toString().trimEnd('/')

    private fun loginPage(csrf: String) =
        """<form action="/login"><input name="_csrf" value="$csrf"/><input name="password"/></form>"""

    private val tableHtml =
        """<table>
             <tr><th>CodeElem</th><th>CC</th><th>Moy</th></tr>
             <tr><td>API411</td><td>12</td><td>13.4</td></tr>
           </table>"""

    @Test fun valid_session_returns_table_directly() = runBlocking {
        // GET marks → already-authenticated table (no login needed)
        server.enqueue(MockResponse().setBody(tableHtml))

        val client = SchoolAppClient(baseUrl = baseUrl())
        val snap = client.checkOnce(email = "me@x.ma", password = "pw", semester = "S4")

        assertEquals(listOf("CodeElem", "CC", "Moy"), snap.headers)
        assertEquals(1, snap.rows.size)
        assertEquals("API411", snap.rows[0][0])
        assertEquals(64, snap.fingerprint.length)

        val req = server.takeRequest()
        assertEquals("/student/noteselem-encours", req.path)
    }

    @Test fun reauthenticates_when_session_expired() = runBlocking {
        server.enqueue(MockResponse().setBody(loginPage("tokA"))) // GET marks → login page
        server.enqueue(MockResponse().setBody(loginPage("tokB"))) // GET /login (inside login())
        server.enqueue(MockResponse().setBody("ok"))               // POST /login
        server.enqueue(MockResponse().setBody(tableHtml))          // GET marks → real table

        val client = SchoolAppClient(baseUrl = baseUrl())
        val snap = client.checkOnce(email = "me@x.ma", password = "pw", semester = "S4")
        assertEquals("API411", snap.rows[0][0])

        server.takeRequest() // GET marks
        val getLogin = server.takeRequest()
        assertEquals("/login", getLogin.path)
        val post = server.takeRequest()
        assertEquals("POST", post.method)
        // CSRF from the GET /login page (tokB) must be posted back
        assertTrue(post.body.readUtf8().contains("_csrf=tokB"))
    }

    @Test(expected = IllegalStateException::class)
    fun bad_credentials_throw() = runBlocking {
        server.enqueue(MockResponse().setBody(loginPage("t")))  // GET marks → login page
        server.enqueue(MockResponse().setBody(loginPage("t")))  // GET /login
        server.enqueue(MockResponse().setBody("ok"))            // POST /login
        server.enqueue(MockResponse().setBody(loginPage("t")))  // GET marks → STILL login → throw
        SchoolAppClient(baseUrl = baseUrl()).checkOnce("me@x.ma", "wrong", "S4")
        Unit
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SchoolAppClientTest"`
Expected: FAIL — `SchoolAppClient` constructor / `checkOnce` unresolved.

- [ ] **Step 4: Write `SchoolAppClient.kt`** (standalone file; translated from `_login` / `check_once` in watcher.py)

```kotlin
package ma.ensam.schoolapp.data.remote

import ma.ensam.schoolapp.data.Fingerprint
import ma.ensam.schoolapp.domain.model.Snapshot
import okhttp3.FormBody
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

class SchoolAppClient(
    private val baseUrl: String = "https://schoolapp.ensam-umi.ac.ma",
    private val timeoutSeconds: Long = 20,
) {
    private val cookieJar = InMemoryCookieJar()
    private val http = OkHttpClient.Builder()
        .cookieJar(cookieJar)
        .followRedirects(true)
        .followSslRedirects(true)
        .connectTimeout(timeoutSeconds, TimeUnit.SECONDS)
        .readTimeout(timeoutSeconds, TimeUnit.SECONDS)
        .build()

    private val loginUrl get() = "$baseUrl/login"
    private val marksUrl get() = "$baseUrl/student/noteselem-encours"

    private fun get(url: String): String {
        val req = Request.Builder().url(url)
            .header("User-Agent", "schoolapp-android/1.0").build()
        http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("GET $url failed: HTTP ${resp.code}")
            return resp.body?.string().orEmpty()
        }
    }

    private fun login(email: String, password: String) {
        val page = get(loginUrl)
        val csrf = SchoolAppParsing.extractCsrf(page)
            ?: error("Login page changed: CSRF token missing")
        val form = FormBody.Builder()
            .add("email", email).add("password", password).add("_csrf", csrf).build()
        val req = Request.Builder().url(loginUrl).post(form)
            .header("Referer", loginUrl)
            .header("User-Agent", "schoolapp-android/1.0").build()
        http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("Login POST failed: HTTP ${resp.code}")
        }
    }

    /**
     * Mirrors check_once login handling: fetch marks; if it looks like the
     * login page, authenticate and retry once. Returns a Snapshot of the table.
     */
    fun checkOnce(email: String, password: String, semester: String): Snapshot {
        var html = get(marksUrl)
        if (SchoolAppParsing.looksLikeLoginPage(html)) {
            login(email, password)
            html = get(marksUrl)
            if (SchoolAppParsing.looksLikeLoginPage(html)) {
                error("Login failed: verify email/password")
            }
        }
        val (headers, rows) = SchoolAppParsing.extractTable(html)
        return Snapshot(
            headers = headers,
            rows = rows,
            fingerprint = Fingerprint.of(headers, rows, semester),
        )
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.SchoolAppClientTest"`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/remote/
git add android/app/src/test/java/ma/ensam/schoolapp/SchoolAppClientTest.kt
git commit -m "feat(android): OkHttp SchoolAppClient with CookieJar + login flow (tested)"
```

---

### Task 11: Telegram notifier

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/remote/TelegramNotifier.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/TelegramNotifierTest.kt`

- [ ] **Step 1: Write the failing test**

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.data.remote.TelegramNotifier
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class TelegramNotifierTest {
    private lateinit var server: MockWebServer
    @Before fun setUp() { server = MockWebServer(); server.start() }
    @After fun tearDown() { server.shutdown() }

    @Test fun posts_message_with_html_parse_mode() {
        server.enqueue(MockResponse().setBody("""{"ok":true}"""))
        val notifier = TelegramNotifier(apiBase = server.url("/").toString().trimEnd('/'))
        notifier.send(token = "T", chatId = "C", message = "<b>hi</b>")

        val req = server.takeRequest()
        assertTrue(req.path!!.contains("/botT/sendMessage"))
        val body = req.body.readUtf8()
        assertTrue(body.contains("\"chat_id\":\"C\""))
        assertTrue(body.contains("\"parse_mode\":\"HTML\""))
        assertTrue(body.contains("<b>hi</b>"))
    }

    @Test(expected = IllegalStateException::class)
    fun api_error_throws() {
        server.enqueue(MockResponse().setBody("""{"ok":false,"description":"bad"}"""))
        TelegramNotifier(apiBase = server.url("/").toString().trimEnd('/'))
            .send(token = "T", chatId = "C", message = "x")
    }

    @Test(expected = IllegalArgumentException::class)
    fun blank_token_throws() {
        TelegramNotifier().send(token = "", chatId = "C", message = "x")
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.TelegramNotifierTest"`
Expected: FAIL — `TelegramNotifier` unresolved.

- [ ] **Step 3: Write `TelegramNotifier.kt`** (translated from `telegram_notifier.py`)

```kotlin
package ma.ensam.schoolapp.data.remote

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class TelegramNotifier(
    private val apiBase: String = "https://api.telegram.org",
) {
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private fun jsonEscape(s: String): String = buildString {
        for (c in s) when (c) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> append(c)
        }
    }

    fun send(token: String, chatId: String, message: String) {
        require(token.isNotBlank() && chatId.isNotBlank()) {
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set"
        }
        val payload = """{"chat_id":"${jsonEscape(chatId)}","text":"${jsonEscape(message)}","parse_mode":"HTML"}"""
        val body = payload.toRequestBody("application/json".toMediaType())
        val req = Request.Builder().url("$apiBase/bot$token/sendMessage").post(body).build()
        http.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful || !text.contains("\"ok\":true")) {
                error("Telegram API error: HTTP ${resp.code} $text")
            }
        }
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.TelegramNotifierTest"`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/remote/TelegramNotifier.kt android/app/src/test/java/ma/ensam/schoolapp/TelegramNotifierTest.kt
git commit -m "feat(android): Telegram notifier translated from telegram_notifier.py (tested)"
```

---

### Task 12: Grade diff (human-readable change summary)

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/domain/Diff.kt`
- Test: `android/app/src/test/java/ma/ensam/schoolapp/DiffTest.kt`

**Purpose:** Given an old and new `Snapshot` for a semester, list which elements are NEW or CHANGED and on which fields — the data Plan 2's notifications render. Mirrors the diff intent of `_build_diff_email`/`_tg_grade_section` without the HTML.

- [ ] **Step 1: Write the failing test**

```kotlin
package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Diff
import ma.ensam.schoolapp.domain.model.Snapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DiffTest {
    private val headers = listOf("CodeElem", "CC", "EX", "Moy", "Dec")
    private fun snap(rows: List<List<String>>) = Snapshot(headers, rows, "fp")

    @Test fun detects_new_element() {
        val old = snap(emptyList())
        val new = snap(listOf(listOf("API411", "12", "14", "13.4", "VORD")))
        val changes = Diff.compute(old, new, "S4")
        assertEquals(1, changes.size)
        assertEquals("API411", changes[0].code)
        assertTrue(changes[0].isNew)
    }

    @Test fun detects_changed_field() {
        val old = snap(listOf(listOf("API411", "12", "10", "10.6", "NV")))
        val new = snap(listOf(listOf("API411", "12", "16", "14.8", "VORD")))
        val changes = Diff.compute(old, new, "S4")
        assertEquals(1, changes.size)
        assertEquals(false, changes[0].isNew)
        // EX 10→16, Moy 10.6→14.8, Dec NV→VORD
        assertEquals("16", changes[0].fields["EX"]!!.second)
        assertEquals("10", changes[0].fields["EX"]!!.first)
        assertTrue(changes[0].fields.containsKey("Dec"))
    }

    @Test fun no_change_yields_empty() {
        val rows = listOf(listOf("API411", "12", "16", "14.8", "VORD"))
        assertTrue(Diff.compute(snap(rows), snap(rows), "S4").isEmpty())
    }

    @Test fun foreign_semester_elements_ignored() {
        val old = snap(emptyList())
        val new = snap(listOf(listOf("API311", "12", "14", "13.4", "VORD"))) // S3 elem under S4
        assertTrue(Diff.compute(old, new, "S4").isEmpty())
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.DiffTest"`
Expected: FAIL — `Diff` unresolved.

- [ ] **Step 3: Write `Diff.kt`**

```kotlin
package ma.ensam.schoolapp.domain

import ma.ensam.schoolapp.domain.model.Snapshot

/** A single element that changed between two snapshots. */
data class ElementChange(
    val code: String,
    val isNew: Boolean,
    /** field name -> (oldValue, newValue) */
    val fields: Map<String, Pair<String, String>>,
)

object Diff {

    private val FIELDS = listOf("CC", "EX", "TP", "MoySO", "RAT", "MoySR", "Moy", "Dec")

    fun compute(old: Snapshot, new: Snapshot, semester: String): List<ElementChange> {
        val prefixes = runCatching { Presets.modulesForSemester(semester).map { it.code.uppercase() } }
            .getOrDefault(emptyList())

        val oldByCode = byCode(old)
        val newByCode = byCode(new)
        val changes = ArrayList<ElementChange>()

        for ((code, newCells) in newByCode) {
            if (prefixes.isNotEmpty() && prefixes.none { code.uppercase().startsWith(it) }) continue
            val oldCells = oldByCode[code]
            if (oldCells == null) {
                changes.add(ElementChange(code, isNew = true, fields = emptyMap()))
                continue
            }
            val diffed = LinkedHashMap<String, Pair<String, String>>()
            for (f in FIELDS) {
                val o = oldCells[f] ?: "--"
                val n = newCells[f] ?: "--"
                if (o != n && !(o == "--" && n == "--")) diffed[f] = o to n
            }
            if (diffed.isNotEmpty()) changes.add(ElementChange(code, isNew = false, fields = diffed))
        }
        return changes.sortedBy { it.code }
    }

    private fun byCode(snap: Snapshot): Map<String, Map<String, String>> {
        val codeIdx = snap.headers.indexOf("CodeElem")
        if (codeIdx < 0) return emptyMap()
        val idx = snap.headers.withIndex().associate { (i, h) -> h to i }
        val out = LinkedHashMap<String, Map<String, String>>()
        for (r in snap.rows) {
            if (r.size <= codeIdx) continue
            val code = r[codeIdx].trim()
            if (code.isEmpty()) continue
            val cells = LinkedHashMap<String, String>()
            for (f in FIELDS) {
                val i = idx[f]
                cells[f] = if (i != null && i < r.size) r[i].trim() else "--"
            }
            out[code] = cells
        }
        return out
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest --tests "ma.ensam.schoolapp.DiffTest"`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the FULL unit suite (regression gate)**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest`
Expected: PASS — all tests from Tasks 6–12 green.

- [ ] **Step 6: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/domain/Diff.kt android/app/src/test/java/ma/ensam/schoolapp/DiffTest.kt
git commit -m "feat(android): snapshot diff producing element-change list (tested)"
```

---

## Phase 2 — Secure storage + minimal usable UI

### Task 13: Encrypted preferences

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/data/prefs/EncryptedPrefs.kt`

**Note:** `EncryptedSharedPreferences` uses the Android Keystore; it cannot run as a JVM unit test, so it is verified on-device in Task 16.

- [ ] **Step 1: Write `EncryptedPrefs.kt`**

```kotlin
package ma.ensam.schoolapp.data.prefs

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class EncryptedPrefs(context: Context) {

    private val prefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "schoolapp_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var email: String
        get() = prefs.getString(KEY_EMAIL, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_EMAIL, v).apply()

    var password: String
        get() = prefs.getString(KEY_PASSWORD, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_PASSWORD, v).apply()

    var telegramToken: String
        get() = prefs.getString(KEY_TG_TOKEN, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_TG_TOKEN, v).apply()

    var telegramChatId: String
        get() = prefs.getString(KEY_TG_CHAT, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_TG_CHAT, v).apply()

    var semester: String
        get() = prefs.getString(KEY_SEMESTER, "S4").orEmpty()
        set(v) = prefs.edit().putString(KEY_SEMESTER, v).apply()

    var pollIntervalSeconds: Int
        get() = prefs.getInt(KEY_INTERVAL, 900)
        set(v) = prefs.edit().putInt(KEY_INTERVAL, v).apply()

    var watcherEnabled: Boolean
        get() = prefs.getBoolean(KEY_WATCHER_ENABLED, false)
        set(v) = prefs.edit().putBoolean(KEY_WATCHER_ENABLED, v).apply()

    var lastHeartbeat: Long
        get() = prefs.getLong(KEY_HEARTBEAT, 0L)
        set(v) = prefs.edit().putLong(KEY_HEARTBEAT, v).apply()

    companion object {
        private const val KEY_EMAIL = "email"
        private const val KEY_PASSWORD = "password"
        private const val KEY_TG_TOKEN = "tg_token"
        private const val KEY_TG_CHAT = "tg_chat"
        private const val KEY_SEMESTER = "semester"
        private const val KEY_INTERVAL = "interval"
        private const val KEY_WATCHER_ENABLED = "watcher_enabled"
        private const val KEY_HEARTBEAT = "heartbeat"
    }
}
```

- [ ] **Step 2: Compile-check**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew compileDebugKotlin`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/data/prefs/EncryptedPrefs.kt
git commit -m "feat(android): EncryptedSharedPreferences wrapper for secrets/config"
```

---

### Task 14: Hilt module + MainViewModel

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/di/AppModule.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/ui/MainViewModel.kt`

- [ ] **Step 1: Write `di/AppModule.kt`**

```kotlin
package ma.ensam.schoolapp.di

import android.content.Context
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import ma.ensam.schoolapp.data.remote.TelegramNotifier
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides @Singleton
    fun provideEncryptedPrefs(@ApplicationContext ctx: Context): EncryptedPrefs = EncryptedPrefs(ctx)

    @Provides @Singleton
    fun provideSchoolAppClient(): SchoolAppClient = SchoolAppClient()

    @Provides @Singleton
    fun provideTelegramNotifier(): TelegramNotifier = TelegramNotifier()
}
```

- [ ] **Step 2: Write `ui/MainViewModel.kt`**

```kotlin
package ma.ensam.schoolapp.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import ma.ensam.schoolapp.domain.Calculator
import ma.ensam.schoolapp.domain.Presets
import ma.ensam.schoolapp.domain.SemesterResult
import ma.ensam.schoolapp.domain.model.Snapshot
import javax.inject.Inject

data class MainUiState(
    val email: String = "",
    val password: String = "",
    val semester: String = "S4",
    val loading: Boolean = false,
    val error: String? = null,
    val snapshot: Snapshot? = null,
    val calc: SemesterResult? = null,
)

@HiltViewModel
class MainViewModel @Inject constructor(
    private val prefs: EncryptedPrefs,
    private val client: SchoolAppClient,
) : ViewModel() {

    private val _state = MutableStateFlow(
        MainUiState(email = prefs.email, password = prefs.password, semester = prefs.semester)
    )
    val state: StateFlow<MainUiState> = _state.asStateFlow()

    fun onEmail(v: String) { _state.value = _state.value.copy(email = v) }
    fun onPassword(v: String) { _state.value = _state.value.copy(password = v) }
    fun onSemester(v: String) { _state.value = _state.value.copy(semester = v) }

    fun saveCredentials() {
        prefs.email = _state.value.email
        prefs.password = _state.value.password
        prefs.semester = _state.value.semester
    }

    fun checkNow() {
        val s = _state.value
        if (s.email.isBlank() || s.password.isBlank()) {
            _state.value = s.copy(error = "Enter email and password first")
            return
        }
        saveCredentials()
        _state.value = s.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val snap = withContext(Dispatchers.IO) {
                    client.checkOnce(s.email, s.password, s.semester)
                }
                _state.value = _state.value.copy(loading = false, snapshot = snap)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message ?: "Check failed")
            }
        }
    }

    /** Compute the calculator from the most recent scraped snapshot. */
    fun computeFromSnapshot() {
        val snap = _state.value.snapshot ?: run {
            _state.value = _state.value.copy(error = "Run a check first")
            return
        }
        val sem = _state.value.semester
        val marks = marksFromSnapshot(snap)
        val result = Calculator.computeSemester(Presets.modulesForSemester(sem), marks)
        _state.value = _state.value.copy(calc = result)
    }

    /** Mirrors _marks_from_snapshot: build the marks map from a scraped table. */
    private fun marksFromSnapshot(snap: Snapshot): Map<String, Double> {
        val codeIdx = snap.headers.indexOf("CodeElem")
        if (codeIdx < 0) return emptyMap()
        val idx = snap.headers.withIndex().associate { (i, h) -> h to i }
        val marks = HashMap<String, Double>()
        fun get(row: List<String>, key: String): Double? {
            val i = idx[key] ?: return null
            if (i >= row.size) return null
            return Calculator.toFloat(row[i])
        }
        for (row in snap.rows) {
            if (codeIdx >= row.size) continue
            val code = row[codeIdx].trim()
            if (code.isEmpty()) continue
            get(row, "CC")?.let { marks["$code.cc"] = it }
            get(row, "EX")?.let { marks["$code.ecrit"] = it; marks["$code.ex"] = it }
            get(row, "TP")?.let { marks["$code.tp"] = it }
            get(row, "RAT")?.let { marks["$code.rat"] = it }
        }
        return marks
    }
}
```

- [ ] **Step 3: Compile-check**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew compileDebugKotlin`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/di/AppModule.kt android/app/src/main/java/ma/ensam/schoolapp/ui/MainViewModel.kt
git commit -m "feat(android): Hilt module + MainViewModel (check + calculator wiring)"
```

---

### Task 15: Minimal Compose UI

**Files:**
- Create: `android/app/src/main/java/ma/ensam/schoolapp/ui/theme/Theme.kt`
- Create: `android/app/src/main/java/ma/ensam/schoolapp/ui/MainScreen.kt`
- Modify: `android/app/src/main/java/ma/ensam/schoolapp/MainActivity.kt`

- [ ] **Step 1: Write `ui/theme/Theme.kt`**

```kotlin
package ma.ensam.schoolapp.ui.theme

import android.os.Build
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

@Composable
fun SchoolAppTheme(content: @Composable () -> Unit) {
    val ctx = LocalContext.current
    // Material You dynamic color is API 31+; fall back to a static scheme below that.
    val colors = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        dynamicLightColorScheme(ctx)
    } else {
        lightColorScheme()
    }
    MaterialTheme(colorScheme = colors, content = content)
}
```

- [ ] **Step 2: Write `ui/MainScreen.kt`**

```kotlin
package ma.ensam.schoolapp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.FilterChip
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun MainScreen(vm: MainViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("SchoolApp Watcher", style = androidx.compose.material3.MaterialTheme.typography.headlineSmall)

        OutlinedTextField(
            value = state.email, onValueChange = vm::onEmail,
            label = { Text("Email") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.password, onValueChange = vm::onPassword,
            label = { Text("Password") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("S3", "S4").forEach { sem ->
                FilterChip(
                    selected = state.semester == sem,
                    onClick = { vm.onSemester(sem) },
                    label = { Text(sem) },
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = vm::checkNow, enabled = !state.loading) { Text("Check Now") }
            OutlinedButton(onClick = vm::computeFromSnapshot, enabled = state.snapshot != null) {
                Text("Calculate")
            }
        }

        if (state.loading) CircularProgressIndicator()
        state.error?.let { Text("Error: $it", color = androidx.compose.material3.MaterialTheme.colorScheme.error) }

        state.snapshot?.let { snap ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Grades (${snap.rows.size} rows)", style = androidx.compose.material3.MaterialTheme.typography.titleMedium)
                    Text(snap.headers.joinToString(" | "), style = androidx.compose.material3.MaterialTheme.typography.labelSmall)
                    Divider()
                    snap.rows.take(40).forEach { row ->
                        Text(row.joinToString(" | "), style = androidx.compose.material3.MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        state.calc?.let { calc ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Calculator — ${state.semester}", style = androidx.compose.material3.MaterialTheme.typography.titleMedium)
                    calc.modules.forEach { m ->
                        Text("${m.code}  Ord ${"%.2f".format(m.averageOrdinaire)}  Final ${"%.2f".format(m.averageFinal)}  [${m.status}]")
                    }
                    Divider()
                    Text("Semester (final): ${"%.2f".format(calc.semesterAverageFinal)} / 20",
                        style = androidx.compose.material3.MaterialTheme.typography.titleSmall)
                    Text("Non validés: ${calc.nonValidatedCodes.size} ${calc.nonValidatedCodes.joinToString(", ")}")
                }
            }
        }
    }
}
```

- [ ] **Step 3: Replace `MainActivity.kt`**

```kotlin
package ma.ensam.schoolapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Surface
import dagger.hilt.android.AndroidEntryPoint
import ma.ensam.schoolapp.ui.MainScreen
import ma.ensam.schoolapp.ui.theme.SchoolAppTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SchoolAppTheme {
                Surface {
                    MainScreen()
                }
            }
        }
    }
}
```

- [ ] **Step 4: Compile-check**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew compileDebugKotlin`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 5: Commit**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git add android/app/src/main/java/ma/ensam/schoolapp/ui/ android/app/src/main/java/ma/ensam/schoolapp/MainActivity.kt
git commit -m "feat(android): minimal Compose UI (credentials, check now, grades, calculator)"
```

---

### Task 16: End-to-end on-device verification

- [ ] **Step 1: Full unit suite (final regression gate)**

Run: `cd /home/notadil/Projects/schoolapp_watcher/android && ./gradlew testDebugUnitTest`
Expected: `BUILD SUCCESSFUL`, all tests green.

- [ ] **Step 2: Build + install on the connected Redmi**

Run: `./gradlew installDebug`
Expected: `BUILD SUCCESSFUL`, `Installed on 1 device`.

- [ ] **Step 3: Launch and stream logs**

Run (in one shell): `adb logcat -c && adb shell am start -n ma.ensam.schoolapp/.MainActivity && adb logcat -t 400 | grep -iE "schoolapp|AndroidRuntime|Hilt"`
Expected: app opens, no `FATAL EXCEPTION`. (Hilt wiring confirmed by the absence of a crash on launch.)

- [ ] **Step 4: Manual end-to-end test on the phone** (records the on-device acceptance criteria)

On the device:
1. Enter your real SchoolApp email + password.
2. Select **S4**.
3. Tap **Check Now** → after a few seconds, the grades card shows your real rows from `noteselem-encours`.
4. Tap **Calculate** → the calculator card shows per-module Ord/Final + status (VORD/RAT/NV) and the semester average.
5. Force-stop and relaunch the app; tap **Check Now** again without re-typing credentials → confirms `EncryptedPrefs` persisted them.

Expected: all five succeed. If login fails, re-check credentials; if parsing looks wrong, capture the page for a fixture:
`adb logcat` won't contain the HTML — instead re-run with a network capture only if needed (out of scope; the MockWebServer tests already cover parsing shapes).

- [ ] **Step 5: Commit a short verification note**

```bash
cd /home/notadil/Projects/schoolapp_watcher
git commit --allow-empty -m "test(android): Plan 1 verified end-to-end on Redmi (Android 13)"
```

---

## Self-Review (against the design spec)

- **Scraper (CSRF, login, session reuse, table parse)** → Tasks 9, 10. ✓
- **SHA-256 fingerprint + per-element diff ignoring row order** → Task 8 (`Fingerprint`), Task 12 (`Diff`). ✓
- **Calculator with S3/S4 presets + rattrapage** → Tasks 6, 7. ✓
- **Telegram Bot API direct call** → Task 11. ✓
- **EncryptedSharedPreferences for secrets** → Task 13. ✓
- **Hilt DI** → Tasks 3, 14. ✓
- **Material 3 Compose UI** → Task 15. ✓
- **Builds + installs on the real Android 13 Xiaomi** → Tasks 4, 16. ✓
- **Deferred to Plan 2:** Room persistence, WatcherService (FGS), WatchdogWorker, BootReceiver, MiuiUtils, onboarding (POST_NOTIFICATIONS + battery + auto-start), extras parsing (absences/sanctions/official modules/semesters), notification channels.
- **Deferred to Plan 3:** multi-screen navigation, dashboard with status/countdown, expandable colored grade cards, dedicated settings + calculator screens, release build with R8/signing, battery-bypass user guide.

**Type consistency check:** `Snapshot(headers, rows, fingerprint)` used identically in Tasks 5/8/10/12/14. `Fingerprint.of(...)`/`Fingerprint.marksState(...)` names match across Tasks 8/10/12. `SchoolAppClient.checkOnce(email, password, semester)` signature consistent across Tasks 10/14. `Calculator.computeSemester/calcElementGrade/calcElementRattrapage/toFloat` consistent across Tasks 7/14. No placeholders; every code step contains complete code. ✓

---

## Subsequent Plans (outline only — each becomes its own plan doc)

**Plan 2 — Persistence & Background Watcher (survives HyperOS):** Room (`SnapshotEntity`, `HistoryEntity`, DAO, DB) with instrumented DAO tests on the connected device; `WatcherRepository`; `NotificationHelper` (two channels: `watcher_status` LOW, `grade_updates` HIGH); `WatcherService` foreground service with coroutine loop writing a heartbeat to `EncryptedPrefs`; `WatchdogWorker` (15-min WorkManager) restarting the service when the heartbeat is stale; `BootReceiver`; `MiuiUtils` (HyperOS detection + auto-start + battery intents); onboarding flow (`POST_NOTIFICATIONS` + battery optimization + MIUI auto-start); extras parsing (absences/sanctions/official modules/semesters). On-device verification: simulate HyperOS kill with `adb shell am force-stop`/`am kill` and confirm the watchdog restarts the service; force a snapshot diff and confirm both a local notification and a Telegram message fire.

**Plan 3 — Full UI & Release:** bottom-nav navigation (Dashboard, Grades, Absences, History, Settings); dashboard with status/last-check/next-check/countdown and pause-resume; expandable module cards color-coded VORD/RAT/NV; absences + history screens; settings + dedicated calculator screen; release build (R8 rules, signing config, `assembleRelease`), install signed release APK on device; battery-bypass user guide doc.

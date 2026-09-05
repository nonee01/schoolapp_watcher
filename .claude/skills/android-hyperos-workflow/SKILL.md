---
name: android-hyperos-workflow
description: Use when building, testing, or deploying the schoolapp native Android app onto the connected Redmi 2209116AG (HyperOS) test device.
---

# Android HyperOS / Redmi Development Workflow

## Overview
The Android application ([android/](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/android)) is a native Kotlin project that communicates with the `schoolapp` local cache server. When deploying to the connected physical Xiaomi Redmi device (`sweet`, Android 13, API 33), special MIUI/HyperOS security features block standard automated Gradle installs.

## Build and Deployment Sequence
Always split compilation and installation to bypass `INSTALL_FAILED_USER_RESTRICTED` errors:

1. **Compilation (Gradle assemble)**:
   ```bash
   cd android
   ./gradlew assembleDebug
   ```
   *Note: First Gradle build downloads large dependencies and takes ~9 minutes. Always configure a high Bash command timeout (minimum 600s) for Gradle tasks.*

2. **Direct ADB Installation**:
   Install the generated `.apk` directly using ADB with the replace/reinstall flag:
   ```bash
   adb -s 3ad2f4880013 install -r app/build/outputs/apk/debug/app-debug.apk
   ```

## Development Guidelines
* **Dependency Injection**: Utilize **Hilt** for injecting repository and network resources.
* **Database Updates**: Any modifications to [Entities.kt](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/android/app/src/main/java/ma/ensam/schoolapp/data/db/Entities.kt) or [WatcherDao.kt](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/android/app/src/main/java/ma/ensam/schoolapp/data/db/WatcherDao.kt) require database schema version bumps in [AppDatabase.kt](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/android/app/src/main/java/ma/ensam/schoolapp/data/db/AppDatabase.kt).
* **WorkManager/Services**: Background synchronization logic resides in [WatchdogWorker.kt](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/android/app/src/main/java/ma/ensam/schoolapp/service/WatchdogWorker.kt) and [WatcherService.kt](file:///home/notadil/Projects/ensam_school/schoolapp_watcher/android/app/src/main/java/ma/ensam/schoolapp/service/WatcherService.kt). Ensure these do not run continuously to prevent excessive battery drain on HyperOS.

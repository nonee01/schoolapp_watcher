# Jsoup
-keep class org.jsoup.** { *; }
# OkHttp (R8 friendly; suppress warnings for optional deps)
-dontwarn okhttp3.**
-dontwarn okio.**
# Keep Hilt generated components
-keep class dagger.hilt.** { *; }
-keep class * extends dagger.hilt.android.lifecycle.HiltViewModel { *; }
# Compile-only annotations referenced by Tink (security-crypto) and Jsoup - absent at runtime
-dontwarn com.google.errorprone.annotations.**
-dontwarn org.jspecify.annotations.**
# Room generated implementations
-keep class * extends androidx.room.RoomDatabase { *; }
-dontwarn androidx.room.**

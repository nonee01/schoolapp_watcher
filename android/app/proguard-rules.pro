# Jsoup
-keep class org.jsoup.** { *; }
# OkHttp (R8 friendly; suppress warnings for optional deps)
-dontwarn okhttp3.**
-dontwarn okio.**
# Keep Hilt generated components
-keep class dagger.hilt.** { *; }
-keep class * extends dagger.hilt.android.lifecycle.HiltViewModel { *; }

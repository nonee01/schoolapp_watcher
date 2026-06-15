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

    @Provides @Singleton
    fun provideDatabase(@ApplicationContext ctx: Context): ma.ensam.schoolapp.data.db.AppDatabase =
        ma.ensam.schoolapp.data.db.AppDatabase.get(ctx)

    @Provides @Singleton
    fun provideWatcherDao(db: ma.ensam.schoolapp.data.db.AppDatabase): ma.ensam.schoolapp.data.db.WatcherDao =
        db.watcherDao()
}

package ma.ensam.schoolapp.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface WatcherDao {
    @Query("SELECT * FROM snapshots WHERE semester = :semester LIMIT 1")
    suspend fun getSnapshot(semester: String): SnapshotEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertSnapshot(snapshot: SnapshotEntity)

    @Insert
    suspend fun insertHistory(entry: HistoryEntity)

    @Query("SELECT * FROM history ORDER BY timestamp DESC LIMIT :limit")
    fun historyFlow(limit: Int): Flow<List<HistoryEntity>>

    @Query("SELECT * FROM history ORDER BY timestamp DESC LIMIT :limit")
    suspend fun recentHistory(limit: Int): List<HistoryEntity>
}

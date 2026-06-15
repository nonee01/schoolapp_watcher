package ma.ensam.schoolapp.data.db

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "snapshots")
data class SnapshotEntity(
    @PrimaryKey val semester: String,
    val headersJson: String,
    val rowsJson: String,
    val fingerprint: String,
    val extrasJson: String,
    val updatedAt: Long,
)

@Entity(tableName = "history")
data class HistoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val timestamp: Long,
    val type: String,
    val semester: String,
    val summary: String,
)

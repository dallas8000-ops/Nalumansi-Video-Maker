package com.nalumansi.videomaker

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.DataOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import org.json.JSONObject

class ApiClient(private val context: Context) {
    fun uploadBundledAsset(assetName: String, kind: String): String {
        val bytes = context.assets.open("sample-assets/$assetName").use { it.readBytes() }
        return uploadAsset(bytes, assetName, contentType(assetName), kind)
    }

    /** Uploads a file the user picked on-device (via ACTION_OPEN_DOCUMENT), used in
     * place of a bundled sample asset whenever "Replace with device image/audio" was used. */
    fun uploadUriAsset(uri: Uri, kind: String): String {
        val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw IllegalStateException("Could not read the selected file")
        val filename = queryDisplayName(uri) ?: "upload-${UUID.randomUUID()}"
        val mimeType = context.contentResolver.getType(uri) ?: contentType(filename)
        return uploadAsset(bytes, filename, mimeType, kind)
    }

    private fun uploadAsset(bytes: ByteArray, filename: String, mimeType: String, kind: String): String {
        val boundary = "----Nalumansi${UUID.randomUUID()}"
        val connection = URL("${BuildConfig.BACKEND_BASE_URL}/api/assets").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")

        DataOutputStream(connection.outputStream).use { output ->
            output.writeBytes("--$boundary\r\n")
            output.writeBytes("Content-Disposition: form-data; name=\"kind\"\r\n\r\n$kind\r\n")
            output.writeBytes("--$boundary\r\n")
            output.writeBytes("Content-Disposition: form-data; name=\"file\"; filename=\"$filename\"\r\n")
            output.writeBytes("Content-Type: $mimeType\r\n\r\n")
            output.write(bytes)
            output.writeBytes("\r\n--$boundary--\r\n")
        }

        val body = (if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream)
            .bufferedReader().use { it.readText() }
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("Asset upload failed: ${connection.responseCode} $body")
        }
        return body
    }

    fun queueGeneration(
        outfitAssetIds: List<String>,
        backgroundAssetId: String,
        durationSeconds: Int,
        musicAssetId: String?,
        musicStartSeconds: Float,
        musicVolume: Float,
        originalVolume: Float,
        muteOriginal: Boolean,
    ): String {
        val connection = URL("${BuildConfig.BACKEND_BASE_URL}/api/generations").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        val audio = JSONObject().apply {
            if (musicAssetId != null) put("music_asset_id", musicAssetId)
            put("music_start_seconds", musicStartSeconds.toDouble())
            put("music_volume", musicVolume.toDouble())
            put("original_audio_volume", originalVolume.toDouble())
            put("mute_original_audio", muteOriginal)
        }
        val json = JSONObject().apply {
            put("aspect_ratio", "9:16")
            put("duration_seconds", durationSeconds)
            put("outfit_asset_ids", org.json.JSONArray(outfitAssetIds))
            put("background_asset_id", backgroundAssetId)
            put("audio", audio)
        }
        connection.outputStream.use { it.write(json.toString().toByteArray()) }
        val body = (if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream)
            .bufferedReader().use { it.readText() }
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("Generation request failed: ${connection.responseCode} $body")
        }
        return body
    }

    /** Polls job progress: {"job_id","status","step","total_steps","video_url","error",...}. */
    fun getGenerationStatus(jobId: String): String {
        val connection = URL("${BuildConfig.BACKEND_BASE_URL}/api/generations/$jobId").openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        val body = (if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream)
            .bufferedReader().use { it.readText() }
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("Status check failed: ${connection.responseCode} $body")
        }
        return body
    }

    fun downloadVideo(videoUrl: String, destination: File) {
        val connection = URL(videoUrl).openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("Video download failed: ${connection.responseCode}")
        }
        connection.inputStream.use { input ->
            destination.outputStream().use { output -> input.copyTo(output) }
        }
    }

    private fun queryDisplayName(uri: Uri): String? {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (nameIndex >= 0 && cursor.moveToFirst()) return cursor.getString(nameIndex)
        }
        return null
    }

    private fun contentType(filename: String): String = when {
        filename.endsWith(".m4a", true) -> "audio/mp4"
        filename.endsWith(".mp3", true) -> "audio/mpeg"
        filename.endsWith(".wav", true) -> "audio/wav"
        filename.endsWith(".aac", true) -> "audio/aac"
        filename.endsWith(".ogg", true) -> "audio/ogg"
        filename.endsWith(".png", true) -> "image/png"
        filename.endsWith(".jpg", true) || filename.endsWith(".jpeg", true) -> "image/jpeg"
        filename.endsWith(".webp", true) -> "image/webp"
        else -> "application/octet-stream"
    }
}

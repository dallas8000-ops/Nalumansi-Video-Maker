package com.nalumansi.videomaker

import android.content.Context
import java.io.DataOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import org.json.JSONObject

class ApiClient(private val context: Context) {
    fun uploadBundledAsset(assetName: String, kind: String): String {
        val boundary = "----Nalumansi${UUID.randomUUID()}"
        val connection = URL("${BuildConfig.BACKEND_BASE_URL}/api/assets").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")

        val bytes = context.assets.open("sample-assets/$assetName").use { it.readBytes() }
        DataOutputStream(connection.outputStream).use { output ->
            output.writeBytes("--$boundary\r\n")
            output.writeBytes("Content-Disposition: form-data; name=\"kind\"\r\n\r\n$kind\r\n")
            output.writeBytes("--$boundary\r\n")
            output.writeBytes("Content-Disposition: form-data; name=\"file\"; filename=\"$assetName\"\r\n")
            output.writeBytes("Content-Type: ${contentType(assetName)}\r\n\r\n")
            output.write(bytes)
            output.writeBytes("\r\n--$boundary--\r\n")
        }

        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("Asset upload failed: ${connection.responseCode}")
        }
        return connection.inputStream.bufferedReader().use { it.readText() }
    }

    fun queueGeneration(outfitAssetIds: List<String>, backgroundAssetId: String): String {
        val connection = URL("${BuildConfig.BACKEND_BASE_URL}/api/generations").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        val json = JSONObject().apply {
            put("aspect_ratio", "9:16")
            put("duration_seconds", 8)
            put("outfit_asset_ids", org.json.JSONArray(outfitAssetIds))
            put("background_asset_id", backgroundAssetId)
            put("audio", JSONObject().put("music_volume", 1.0).put("original_audio_volume", 1.0))
        }
        connection.outputStream.use { it.write(json.toString().toByteArray()) }
        val body = (if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream)
            .bufferedReader().use { it.readText() }
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("Generation request failed: ${connection.responseCode} $body")
        }
        return body
    }

    private fun contentType(assetName: String): String = when {
        assetName.endsWith(".m4a") -> "audio/mp4"
        assetName.endsWith(".png") -> "image/png"
        else -> "application/octet-stream"
    }
}
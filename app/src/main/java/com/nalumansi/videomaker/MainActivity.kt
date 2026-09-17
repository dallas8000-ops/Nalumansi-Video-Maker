package com.nalumansi.videomaker

import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.provider.DocumentsContract
import org.json.JSONObject
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private enum class AppScreen { HOME, ASSETS, EDITOR, GENERATE, PROCESSING, RESULT }

private const val BUNDLED_BACKGROUND = "210354"
private val BUNDLED_OUTFITS = listOf("210405", "210421", "210434", "210447", "210456")
private const val BUNDLED_MUSIC_FILENAME = "Recording (35).m4a"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) { NalumansiApp() }
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun NalumansiApp() {
    val context = LocalContext.current
    var screen by rememberSaveable { mutableStateOf(AppScreen.HOME) }
    var selectedFormat by rememberSaveable { mutableStateOf("9:16") }
    // Luma's video model only accepts 5s or 9s generations — any other value is a 422 from the backend.
    // This is the length of EACH chained shot, not the total video (total ≈ duration × outfit count).
    var duration by rememberSaveable { mutableIntStateOf(9) }
    var outfitUri by rememberSaveable { mutableStateOf<Uri?>(null) }
    var backgroundUri by rememberSaveable { mutableStateOf<Uri?>(null) }
    var musicUri by rememberSaveable { mutableStateOf<Uri?>(null) }
    var selectedBackground by rememberSaveable { mutableStateOf(BUNDLED_BACKGROUND) }
    var selectedOutfits by rememberSaveable { mutableStateOf(BUNDLED_OUTFITS) }
    var bundledMusicSelected by rememberSaveable { mutableStateOf(true) }
    var importedImages by rememberSaveable { mutableStateOf(emptyList<String>()) }
    var importedAudio by rememberSaveable { mutableStateOf(emptyList<String>()) }
    var selectedImportedImages by rememberSaveable { mutableStateOf(emptyList<String>()) }
    var musicStart by rememberSaveable { mutableFloatStateOf(0f) }
    var musicVolume by rememberSaveable { mutableFloatStateOf(1f) }
    var originalVolume by rememberSaveable { mutableFloatStateOf(1f) }
    var muteOriginal by rememberSaveable { mutableStateOf(false) }

    // In-flight / finished job state. jobId surviving a rotation lets PROCESSING
    // pick the poll back up instead of losing track of a job already running server-side.
    var jobId by rememberSaveable { mutableStateOf<String?>(null) }
    var jobStep by rememberSaveable { mutableIntStateOf(0) }
    var jobTotalSteps by rememberSaveable { mutableIntStateOf(0) }
    var jobBusy by rememberSaveable { mutableStateOf(false) }
    var jobError by rememberSaveable { mutableStateOf<String?>(null) }
    var resultVideoPath by rememberSaveable { mutableStateOf<String?>(null) }

    val outfitPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { if (it != null) outfitUri = it }
    val backgroundPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { if (it != null) backgroundUri = it }
    val musicPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { if (it != null) musicUri = it }
    val scope = rememberCoroutineScope()
    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { treeUri ->
        if (treeUri != null) {
            scope.launch {
                val imported = withContext(Dispatchers.IO) { importFolder(context, treeUri) }
                importedImages = imported.filter { it.endsWith(".png", true) || it.endsWith(".jpg", true) || it.endsWith(".jpeg", true) }
                importedAudio = imported.filter { it.endsWith(".m4a", true) || it.endsWith(".mp3", true) || it.endsWith(".wav", true) }
            }
        }
    }

    fun resetJobState() {
        jobId = null
        jobStep = 0
        jobTotalSteps = 0
        jobBusy = false
        jobError = null
        resultVideoPath = null
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Nalumansi Video Maker") },
                navigationIcon = {
                    if (screen == AppScreen.ASSETS) {
                        OutlinedButton(onClick = { screen = AppScreen.HOME }) { Text("Home") }
                    } else if (screen == AppScreen.EDITOR) {
                        OutlinedButton(onClick = { screen = AppScreen.ASSETS }) { Text("Back") }
                    } else if (screen == AppScreen.GENERATE) {
                        OutlinedButton(onClick = { screen = AppScreen.EDITOR }) { Text("Back") }
                    } else if (screen == AppScreen.RESULT) {
                        OutlinedButton(onClick = { screen = AppScreen.HOME }) { Text("Home") }
                    }
                },
            )
        },
    ) { padding ->
        when (screen) {
            AppScreen.HOME -> HomeScreen(Modifier.padding(padding), outfitCount = selectedOutfits.size) {
                screen = AppScreen.ASSETS
            }
            AppScreen.ASSETS -> AssetsScreen(
                modifier = Modifier.padding(padding),
                selectedOutfits = selectedOutfits,
                selectedBackground = selectedBackground,
                bundledMusicSelected = bundledMusicSelected,
                customOutfitName = outfitUri?.let { displayNameOf(context, it) },
                customBackgroundName = backgroundUri?.let { displayNameOf(context, it) },
                customMusicName = musicUri?.let { displayNameOf(context, it) },
                onChooseOutfit = { outfitPicker.launch(arrayOf("image/*")) },
                onChooseBackground = { backgroundPicker.launch(arrayOf("image/*")) },
                onChooseMusic = { musicPicker.launch(arrayOf("audio/*")) },
                onClearOutfit = { outfitUri = null },
                onClearBackground = { backgroundUri = null },
                onClearMusic = { musicUri = null },
                onToggleOutfit = { label ->
                    selectedOutfits = if (label in selectedOutfits) selectedOutfits - label else selectedOutfits + label
                },
                onSelectBackground = { selectedBackground = it },
                onSelectBundledMusic = { bundledMusicSelected = it },
                importedImages = importedImages,
                importedAudio = importedAudio,
                selectedImportedImages = selectedImportedImages,
                onToggleImportedImage = { name ->
                    selectedImportedImages = if (name in selectedImportedImages) selectedImportedImages - name else selectedImportedImages + name
                },
                onImportFolder = { folderPicker.launch(null) },
                onContinue = { screen = AppScreen.EDITOR },
            )
            AppScreen.EDITOR -> EditorScreen(
                modifier = Modifier.padding(padding),
                format = selectedFormat,
                onFormatChange = { selectedFormat = it },
                duration = duration,
                onDurationChange = { duration = it },
                outfitCount = selectedOutfits.size,
                musicStart = musicStart,
                onMusicStartChange = { musicStart = it },
                musicVolume = musicVolume,
                onMusicVolumeChange = { musicVolume = it },
                originalVolume = originalVolume,
                onOriginalVolumeChange = { originalVolume = it },
                muteOriginal = muteOriginal,
                onMuteOriginalChange = { muteOriginal = it },
                onContinue = { screen = AppScreen.GENERATE },
            )
            AppScreen.GENERATE -> GenerateScreen(
                modifier = Modifier.padding(padding),
                outfitCount = selectedOutfits.size,
                durationSeconds = duration,
                error = jobError,
                busy = jobBusy,
            ) {
                scope.launch {
                    jobBusy = true
                    jobError = null
                    try {
                        val client = ApiClient(context)
                        val outfitIds = withContext(Dispatchers.IO) {
                            val customOutfit = outfitUri
                            if (customOutfit != null) {
                                listOf(JSONObject(client.uploadUriAsset(customOutfit, "outfit")).getString("asset_id"))
                            } else {
                                selectedOutfits.map { label ->
                                    JSONObject(client.uploadBundledAsset("Screenshot 2026-09-16 $label.png", "outfit")).getString("asset_id")
                                }
                            }
                        }
                        val backgroundId = withContext(Dispatchers.IO) {
                            val customBackground = backgroundUri
                            if (customBackground != null) {
                                JSONObject(client.uploadUriAsset(customBackground, "background")).getString("asset_id")
                            } else {
                                JSONObject(client.uploadBundledAsset("Screenshot 2026-09-16 $BUNDLED_BACKGROUND.png", "background")).getString("asset_id")
                            }
                        }
                        val musicId = withContext(Dispatchers.IO) {
                            val customMusic = musicUri
                            when {
                                customMusic != null -> JSONObject(client.uploadUriAsset(customMusic, "music")).getString("asset_id")
                                bundledMusicSelected -> JSONObject(client.uploadBundledAsset(BUNDLED_MUSIC_FILENAME, "music")).getString("asset_id")
                                else -> null
                            }
                        }
                        val response = withContext(Dispatchers.IO) {
                            JSONObject(
                                client.queueGeneration(
                                    outfitAssetIds = outfitIds,
                                    backgroundAssetId = backgroundId,
                                    durationSeconds = duration,
                                    musicAssetId = musicId,
                                    musicStartSeconds = musicStart,
                                    musicVolume = musicVolume,
                                    originalVolume = originalVolume,
                                    muteOriginal = muteOriginal,
                                )
                            )
                        }
                        jobId = response.getString("job_id")
                        jobTotalSteps = response.optInt("total_steps", outfitIds.size)
                        jobStep = response.optInt("step", 0)
                        jobBusy = false
                        screen = AppScreen.PROCESSING
                    } catch (error: Exception) {
                        jobError = error.message ?: "Generation request failed"
                        jobBusy = false
                    }
                }
            }
            AppScreen.PROCESSING -> {
                val currentJobId = jobId
                if (currentJobId != null) {
                    LaunchedEffect(currentJobId) {
                        val client = ApiClient(context)
                        while (true) {
                            try {
                                val statusBody = withContext(Dispatchers.IO) { JSONObject(client.getGenerationStatus(currentJobId)) }
                                jobStep = statusBody.optInt("step", jobStep)
                                jobTotalSteps = statusBody.optInt("total_steps", jobTotalSteps)
                                when (statusBody.optString("status", "running")) {
                                    "completed" -> {
                                        val videoUrl = statusBody.getString("video_url")
                                        // getExternalFilesDir can return null if external storage is
                                        // unavailable; fall back to internal storage (still shareable via FileProvider).
                                        val moviesDir = context.getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: context.filesDir
                                        val destination = File(moviesDir, "nalumansi-$currentJobId.mp4")
                                        withContext(Dispatchers.IO) { client.downloadVideo(videoUrl, destination) }
                                        resultVideoPath = destination.absolutePath
                                        screen = AppScreen.RESULT
                                        return@LaunchedEffect
                                    }
                                    "failed" -> {
                                        jobError = statusBody.optString("error", "Generation failed")
                                        screen = AppScreen.GENERATE
                                        return@LaunchedEffect
                                    }
                                    else -> delay(3000)
                                }
                            } catch (error: Exception) {
                                jobError = error.message ?: "Lost connection while checking progress"
                                screen = AppScreen.GENERATE
                                return@LaunchedEffect
                            }
                        }
                    }
                }
                ProcessingScreen(Modifier.padding(padding), step = jobStep, totalSteps = jobTotalSteps)
            }
            AppScreen.RESULT -> ResultScreen(
                modifier = Modifier.padding(padding),
                videoPath = resultVideoPath,
                onShare = {
                    resultVideoPath?.let { path ->
                        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", File(path))
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "video/mp4"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        context.startActivity(Intent.createChooser(intent, "Share video"))
                    }
                },
                onNewVideo = {
                    resetJobState()
                    screen = AppScreen.ASSETS
                },
            )
        }
    }
}

@Composable
private fun HomeScreen(modifier: Modifier, outfitCount: Int, onStart: () -> Unit) {
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("Create polished outfit videos", style = MaterialTheme.typography.headlineMedium)
        Text("Build an Instagram-ready fashion showcase from outfits, a showroom background, and music.")
        HorizontalDivider()
        Text("Current project", style = MaterialTheme.typography.titleMedium)
        Text("$outfitCount outfit${if (outfitCount == 1) "" else "s"}  |  1 background  |  1 music track")
        Button(onClick = onStart, modifier = Modifier.fillMaxWidth()) { Text("Start a new video") }
    }
}

@Composable
private fun AssetsScreen(
    modifier: Modifier,
    selectedOutfits: List<String>,
    selectedBackground: String,
    bundledMusicSelected: Boolean,
    customOutfitName: String?,
    customBackgroundName: String?,
    customMusicName: String?,
    onChooseOutfit: () -> Unit,
    onChooseBackground: () -> Unit,
    onChooseMusic: () -> Unit,
    onClearOutfit: () -> Unit,
    onClearBackground: () -> Unit,
    onClearMusic: () -> Unit,
    onToggleOutfit: (String) -> Unit,
    onSelectBackground: (String) -> Unit,
    onSelectBundledMusic: (Boolean) -> Unit,
    importedImages: List<String>,
    importedAudio: List<String>,
    selectedImportedImages: List<String>,
    onToggleImportedImage: (String) -> Unit,
    onImportFolder: () -> Unit,
    onContinue: () -> Unit,
) {
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("1. Choose your assets", style = MaterialTheme.typography.headlineSmall)
        Text("${selectedOutfits.size} sample outfit reference(s), a background, and a music track are pre-loaded — swap any of them for your own below.")
        OutlinedButton(onClick = onImportFolder) { Text("Import from designated folder") }
        if (importedImages.isNotEmpty() || importedAudio.isNotEmpty()) {
            Text("Imported library", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                importedImages.forEach { name ->
                    ImportedImagePreview(
                        name = name,
                        selected = name in selectedImportedImages,
                        onClick = { onToggleImportedImage(name) },
                    )
                }
            }
            importedAudio.forEach { name -> Text("Audio: $name") }
        }

        Text("Background", style = MaterialTheme.typography.titleMedium)
        if (customBackgroundName != null) {
            AssetSwapStatus(fileName = customBackgroundName, onClear = onClearBackground)
        } else {
            SampleAssetPreview(label = BUNDLED_BACKGROUND, selected = selectedBackground == BUNDLED_BACKGROUND, onClick = { onSelectBackground(BUNDLED_BACKGROUND) })
            OutlinedButton(onClick = onChooseBackground) { Text("Replace with device image") }
        }

        Text("Outfit references", style = MaterialTheme.typography.titleMedium)
        if (customOutfitName != null) {
            Text("Using a single device image replaces the sample set below.", style = MaterialTheme.typography.bodySmall)
            AssetSwapStatus(fileName = customOutfitName, onClear = onClearOutfit)
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BUNDLED_OUTFITS.forEach { label ->
                    SampleAssetPreview(label = label, selected = label in selectedOutfits, onClick = { onToggleOutfit(label) })
                }
            }
            Text("${selectedOutfits.size} outfit${if (selectedOutfits.size == 1) "" else "s"} selected — each becomes one chained shot in the final video.", style = MaterialTheme.typography.labelLarge)
            OutlinedButton(onClick = onChooseOutfit) { Text("Replace with a single device image") }
        }

        Text("Music", style = MaterialTheme.typography.titleMedium)
        if (customMusicName != null) {
            AssetSwapStatus(fileName = customMusicName, onClear = onClearMusic)
        } else {
            Text(BUNDLED_MUSIC_FILENAME)
            FilterChip(selected = bundledMusicSelected, onClick = { onSelectBundledMusic(!bundledMusicSelected) }, label = { Text(if (bundledMusicSelected) "Bundled music on" else "No music") })
            OutlinedButton(onClick = onChooseMusic) { Text("Replace with device audio") }
        }

        Button(
            onClick = onContinue,
            enabled = (customOutfitName != null || selectedOutfits.isNotEmpty()) && selectedBackground.isNotEmpty(),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Continue to editor") }
    }
}

@Composable
private fun AssetSwapStatus(fileName: String, onClear: () -> Unit) {
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Using: $fileName", style = MaterialTheme.typography.bodyMedium)
        TextButton(onClick = onClear) { Text("Use bundled instead") }
    }
}

@Composable
private fun EditorScreen(
    modifier: Modifier,
    format: String,
    onFormatChange: (String) -> Unit,
    duration: Int,
    onDurationChange: (Int) -> Unit,
    outfitCount: Int,
    musicStart: Float,
    onMusicStartChange: (Float) -> Unit,
    musicVolume: Float,
    onMusicVolumeChange: (Float) -> Unit,
    originalVolume: Float,
    onOriginalVolumeChange: (Float) -> Unit,
    muteOriginal: Boolean,
    onMuteOriginalChange: (Boolean) -> Unit,
    onContinue: () -> Unit,
) {
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("2. Edit your video", style = MaterialTheme.typography.headlineSmall)
        Text("Instagram format", style = MaterialTheme.typography.titleMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("9:16", "1:1", "16:9").forEach {
                FilterChip(selected = format == it, onClick = { onFormatChange(it) }, label = { Text(it) })
            }
        }
        Text("Shot duration", style = MaterialTheme.typography.titleMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(5, 9).forEach {
                FilterChip(selected = duration == it, onClick = { onDurationChange(it) }, label = { Text("${it}s") })
            }
        }
        Text(
            "Each outfit becomes its own $duration-second shot, chained onto the last. " +
                "Total video length ≈ ${duration * outfitCount}s across $outfitCount shot${if (outfitCount == 1) "" else "s"}.",
            style = MaterialTheme.typography.bodySmall,
        )
        Text("Movement", style = MaterialTheme.typography.titleMedium)
        Text("Slow walk toward camera, slight turn, natural fabric movement, elegant showroom lighting, no extra accessories.")
        Text("Audio", style = MaterialTheme.typography.titleMedium)
        Text("Music start: ${musicStart.toInt()} seconds")
        Slider(value = musicStart, onValueChange = onMusicStartChange, valueRange = 0f..30f, steps = 29)
        Text("Music volume: ${(musicVolume * 100).toInt()}%")
        Slider(value = musicVolume, onValueChange = onMusicVolumeChange)
        Text("Original audio: ${(originalVolume * 100).toInt()}%")
        Slider(value = originalVolume, onValueChange = onOriginalVolumeChange, enabled = !muteOriginal)
        Row {
            Checkbox(checked = muteOriginal, onCheckedChange = onMuteOriginalChange)
            Text("Mute original audio")
        }
        Button(onClick = onContinue, modifier = Modifier.fillMaxWidth()) { Text("Continue to generation") }
    }
}

@Composable
private fun GenerateScreen(modifier: Modifier, outfitCount: Int, durationSeconds: Int, error: String?, busy: Boolean, onGenerate: () -> Unit) {
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("3. Generate", style = MaterialTheme.typography.headlineSmall)
        Text(
            "$outfitCount outfit${if (outfitCount == 1) "" else "s"} will be chained into one continuous " +
                "~${outfitCount * durationSeconds}s video against the showroom background.",
        )
        Text(
            if (busy) "Uploading your assets..." else "Ready to submit. Generation runs as $outfitCount chained shots and can take several minutes.",
            style = MaterialTheme.typography.titleMedium,
        )
        if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
        Button(onClick = onGenerate, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
            if (busy) {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                    Text("Uploading...")
                }
            } else {
                Text("Generate video")
            }
        }
    }
}

@Composable
private fun ProcessingScreen(modifier: Modifier, step: Int, totalSteps: Int) {
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("Generating your video", style = MaterialTheme.typography.headlineSmall)
        Text(
            if (totalSteps > 0 && step > 0) {
                "Shot $step of $totalSteps — each shot continues from the last, so this takes a few minutes per outfit."
            } else {
                "Starting the first shot..."
            },
            style = MaterialTheme.typography.bodyMedium,
        )
        LinearProgressIndicator(
            progress = { if (totalSteps > 0) step.toFloat() / totalSteps else 0f },
            modifier = Modifier.fillMaxWidth(),
        )
        Text("Keep the app open — this screen updates automatically when each shot finishes.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ResultScreen(modifier: Modifier, videoPath: String?, onShare: () -> Unit, onNewVideo: () -> Unit) {
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("4. Your video is ready", style = MaterialTheme.typography.headlineSmall)
        Surface(tonalElevation = 2.dp, modifier = Modifier.fillMaxWidth().height(160.dp)) {
            Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (videoPath != null) {
                    Text("Saved on this device.", style = MaterialTheme.typography.titleMedium)
                    Text(videoPath, style = MaterialTheme.typography.bodySmall)
                } else {
                    Text("No video generated yet.")
                }
            }
        }
        if (videoPath != null) {
            Button(onClick = onShare, modifier = Modifier.fillMaxWidth()) { Text("Share video") }
        }
        OutlinedButton(onClick = onNewVideo, modifier = Modifier.fillMaxWidth()) { Text("Create another video") }
    }
}

@Composable
private fun SampleAssetPreview(label: String, selected: Boolean = false, onClick: () -> Unit = {}) {
    val context = LocalContext.current
    val bitmap = remember(label) {
        context.assets.open("sample-assets/Screenshot 2026-09-16 $label.png").use { BitmapFactory.decodeStream(it) }
    }
    Column(
        modifier = Modifier
            .size(82.dp)
            .clickable(onClick = onClick),
    ) {
        if (bitmap != null) {
            Surface(
                tonalElevation = if (selected) 6.dp else 0.dp,
                modifier = Modifier
                    .size(64.dp)
                    .border(
                        width = if (selected) 2.dp else 0.dp,
                        color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
                        shape = RoundedCornerShape(8.dp),
                    ),
            ) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "Sample asset $label",
                    modifier = Modifier.size(64.dp),
                )
            }
        }
        Text(if (selected) "Selected" else "Select", style = MaterialTheme.typography.labelSmall)
    }
}

private fun importFolder(context: android.content.Context, treeUri: Uri): List<String> {
    val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(
        treeUri,
        DocumentsContract.getTreeDocumentId(treeUri),
    )
    val importedDirectory = File(context.filesDir, "media-library").apply { mkdirs() }
    val imported = mutableListOf<String>()
    context.contentResolver.query(
        childrenUri,
        arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE),
        null,
        null,
        null,
    )?.use { cursor ->
        val idIndex = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID)
        val nameIndex = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME)
        val mimeIndex = cursor.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_MIME_TYPE)
        while (cursor.moveToNext()) {
            val name = cursor.getString(nameIndex)
            val mime = cursor.getString(mimeIndex)
            val supported = mime.startsWith("image/") || mime.startsWith("audio/")
            if (!supported) continue
            val documentUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, cursor.getString(idIndex))
            context.contentResolver.openInputStream(documentUri)?.use { input ->
                File(importedDirectory, name).outputStream().use { output -> input.copyTo(output) }
            }
            imported += name
        }
    }
    return imported
}

private fun displayNameOf(context: android.content.Context, uri: Uri): String? {
    context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        val nameIndex = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
        if (nameIndex >= 0 && cursor.moveToFirst()) return cursor.getString(nameIndex)
    }
    return uri.lastPathSegment
}

@Composable
private fun ImportedImagePreview(name: String, selected: Boolean, onClick: () -> Unit) {
    val file = File(LocalContext.current.filesDir, "media-library/$name")
    val bitmap = remember(name) { BitmapFactory.decodeFile(file.absolutePath) }
    Column(modifier = Modifier.size(100.dp).clickable(onClick = onClick)) {
        if (bitmap != null) {
            Image(bitmap = bitmap.asImageBitmap(), contentDescription = name, modifier = Modifier.size(76.dp))
        }
        Text(if (selected) "$name selected" else name, style = MaterialTheme.typography.labelSmall)
    }
}

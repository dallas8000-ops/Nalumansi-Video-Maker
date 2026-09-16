package com.nalumansi.videomaker

import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

private enum class AppScreen { HOME, ASSETS, EDITOR, GENERATE, RESULT }

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
    var screen by rememberSaveable { mutableStateOf(AppScreen.HOME) }
    var selectedFormat by rememberSaveable { mutableStateOf("9:16") }
    var duration by rememberSaveable { mutableFloatStateOf(8f) }
    var outfitUri by rememberSaveable { mutableStateOf<Uri?>(null) }
    var backgroundUri by rememberSaveable { mutableStateOf<Uri?>(null) }
    var musicUri by rememberSaveable { mutableStateOf<Uri?>(null) }
    var selectedBackground by rememberSaveable { mutableStateOf("210354") }
    var selectedOutfits by rememberSaveable {
        mutableStateOf(listOf("210405", "210421", "210434", "210447", "210456"))
    }
    var bundledMusicSelected by rememberSaveable { mutableStateOf(true) }
    var musicStart by rememberSaveable { mutableFloatStateOf(0f) }
    var musicVolume by rememberSaveable { mutableFloatStateOf(1f) }
    var originalVolume by rememberSaveable { mutableFloatStateOf(1f) }
    var muteOriginal by rememberSaveable { mutableStateOf(false) }
    var generationQueued by rememberSaveable { mutableStateOf(false) }

    val outfitPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { outfitUri = it }
    val backgroundPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { backgroundUri = it }
    val musicPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { musicUri = it }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Nalumansi Video Maker") },
                navigationIcon = {
                    if (screen != AppScreen.HOME) {
                        OutlinedButton(onClick = { screen = AppScreen.HOME }) { Text("Home") }
                    }
                },
            )
        },
    ) { padding ->
        when (screen) {
            AppScreen.HOME -> HomeScreen(Modifier.padding(padding)) { screen = AppScreen.ASSETS }
            AppScreen.ASSETS -> AssetsScreen(
                modifier = Modifier.padding(padding),
                selectedOutfits = selectedOutfits,
                selectedBackground = selectedBackground,
                bundledMusicSelected = bundledMusicSelected,
                onChooseOutfit = { outfitPicker.launch(arrayOf("image/*")) },
                onChooseBackground = { backgroundPicker.launch(arrayOf("image/*")) },
                onChooseMusic = { musicPicker.launch(arrayOf("audio/*")) },
                onToggleOutfit = { label ->
                    selectedOutfits = if (label in selectedOutfits) {
                        selectedOutfits - label
                    } else {
                        selectedOutfits + label
                    }
                },
                onSelectBackground = { selectedBackground = it },
                onSelectBundledMusic = { bundledMusicSelected = it },
                onContinue = { screen = AppScreen.EDITOR },
            )
            AppScreen.EDITOR -> EditorScreen(
                modifier = Modifier.padding(padding),
                format = selectedFormat,
                onFormatChange = { selectedFormat = it },
                duration = duration,
                onDurationChange = { duration = it },
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
            AppScreen.GENERATE -> GenerateScreen(Modifier.padding(padding), generationQueued) {
                generationQueued = true
                screen = AppScreen.RESULT
            }
            AppScreen.RESULT -> ResultScreen(Modifier.padding(padding), generationQueued) {
                generationQueued = false
                screen = AppScreen.ASSETS
            }
        }
    }
}

@Composable
private fun HomeScreen(modifier: Modifier, onStart: () -> Unit) {
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("Create polished outfit videos", style = MaterialTheme.typography.headlineMedium)
        Text("Build an Instagram-ready fashion showcase from outfits, a showroom background, and music.")
        HorizontalDivider()
        Text("Current project", style = MaterialTheme.typography.titleMedium)
        Text("5 outfits  |  1 background  |  1 music track")
        Button(onClick = onStart, modifier = Modifier.fillMaxWidth()) { Text("Start a new video") }
    }
}

@Composable
private fun AssetsScreen(
    modifier: Modifier,
    selectedOutfits: List<String>,
    selectedBackground: String,
    bundledMusicSelected: Boolean,
    onChooseOutfit: () -> Unit,
    onChooseBackground: () -> Unit,
    onChooseMusic: () -> Unit,
    onToggleOutfit: (String) -> Unit,
    onSelectBackground: (String) -> Unit,
    onSelectBundledMusic: (Boolean) -> Unit,
    onContinue: () -> Unit,
) {
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("1. Choose your assets", style = MaterialTheme.typography.headlineSmall)
        Text("Five outfit references, the 210354 background, and your M4A track are included.")
        Text("Background", style = MaterialTheme.typography.titleMedium)
        SampleAssetPreview(
            label = "210354",
            selected = selectedBackground == "210354",
            onClick = { onSelectBackground("210354") },
        )
        OutlinedButton(onClick = onChooseBackground) {
            Text("Replace with device image")
        }
        Text("Outfit references", style = MaterialTheme.typography.titleMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("210405", "210421", "210434", "210447", "210456").forEach { label ->
                SampleAssetPreview(
                    label = label,
                    selected = label in selectedOutfits,
                    onClick = { onToggleOutfit(label) },
                )
            }
        }
        OutlinedButton(onClick = onChooseOutfit) {
            Text("Replace with device images")
        }
        Text("Music", style = MaterialTheme.typography.titleMedium)
        Text("Recording (35).m4a")
        FilterChip(
            selected = bundledMusicSelected,
            onClick = { onSelectBundledMusic(!bundledMusicSelected) },
            label = { Text("Use bundled music") },
        )
        OutlinedButton(onClick = onChooseMusic) {
            Text("Replace with device audio")
        }
        Text("${selectedOutfits.size} outfits selected", style = MaterialTheme.typography.labelLarge)
        Button(
            onClick = onContinue,
            enabled = selectedOutfits.isNotEmpty() && selectedBackground.isNotEmpty(),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Continue to editor") }
    }
}

@Composable
private fun EditorScreen(
    modifier: Modifier,
    format: String,
    onFormatChange: (String) -> Unit,
    duration: Float,
    onDurationChange: (Float) -> Unit,
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
        Text("Duration: ${duration.toInt()} seconds")
        Slider(value = duration, onValueChange = onDurationChange, valueRange = 4f..15f, steps = 10)
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
private fun GenerateScreen(modifier: Modifier, queued: Boolean, onGenerate: () -> Unit) {
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("3. Generate", style = MaterialTheme.typography.headlineSmall)
        Text("Your five outfits will be combined with the 210354 showroom background and edited audio.")
        Text(if (queued) "Generation queued" else "Ready to generate", style = MaterialTheme.typography.titleMedium)
        Button(onClick = onGenerate, enabled = !queued, modifier = Modifier.fillMaxWidth()) {
            Text(if (queued) "Queued" else "Generate video")
        }
    }
}

@Composable
private fun ResultScreen(modifier: Modifier, queued: Boolean, onNewVideo: () -> Unit) {
    Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("4. Result", style = MaterialTheme.typography.headlineSmall)
        Text(if (queued) "Preparing your video" else "No video generated yet.")
        Surface(tonalElevation = 2.dp, modifier = Modifier.fillMaxWidth().height(220.dp)) {
            Column(
                modifier = Modifier.fillMaxSize().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SampleAssetPreview("210354", selected = true)
                Text(
                    if (queued) {
                        "Showroom preview loaded. The finished video will replace this image after the backend submits and completes the Luma generation job."
                    } else {
                        "Select assets and generate a video to see the result here."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
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
                modifier = Modifier.size(64.dp),
            ) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "Sample asset $label",
                    modifier = Modifier.size(64.dp),
                )
            }
        }
        Text(if (selected) "$label selected" else label, style = MaterialTheme.typography.labelSmall)
    }
}

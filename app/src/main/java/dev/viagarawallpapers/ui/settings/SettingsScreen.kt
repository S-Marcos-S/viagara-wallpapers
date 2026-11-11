// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers.ui.settings

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SystemUpdate
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.viagarawallpapers.BuildConfig
import dev.viagarawallpapers.R
import dev.viagarawallpapers.ui.theme.GlassCard
import dev.viagarawallpapers.update.DownloadStatus
import dev.viagarawallpapers.update.RootInstaller
import dev.viagarawallpapers.update.UpdateInfo
import dev.viagarawallpapers.update.UpdateManager
import dev.viagarawallpapers.util.HapticUtil
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onNavigateBack: () -> Unit,
) {
    val context = LocalContext.current
    val view = LocalView.current
    val colorScheme = MaterialTheme.colorScheme

    val updateInfo by UpdateManager.updateAvailable.collectAsState()
    val isCheckingUpdates by UpdateManager.isCheckingUpdates.collectAsState()
    val downloadStatus by UpdateManager.downloadStatus.collectAsState()
    var isBetaTester by remember { mutableStateOf(UpdateManager.isBetaTesterEnabled(context)) }

    LaunchedEffect(Unit) {
        UpdateManager.checkForUpdates(context, force = true)
    }

    val isRoot = remember { RootInstaller.isRootAvailable() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.settings_title),
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_back),
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                ),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
        modifier = Modifier.fillMaxSize(),
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            // Section: Updates
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = stringResource(R.string.settings_section_updates),
                        style = MaterialTheme.typography.labelMedium,
                        color = colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                    )

                    if (isCheckingUpdates) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(14.dp),
                            strokeWidth = 2.dp,
                            color = colorScheme.primary,
                        )
                    }
                }
            }

            item {
                UpdateStatusCard(
                    updateInfo = updateInfo,
                    isChecking = isCheckingUpdates,
                    downloadStatus = downloadStatus,
                    isRoot = isRoot,
                    onCheckAgain = {
                        UpdateManager.checkForUpdates(context, force = true)
                    },
                    onDownload = { info ->
                        UpdateManager.downloadUpdate(context, info)
                    },
                    onInstall = { uri, useRoot ->
                        UpdateManager.installUpdate(context, uri, useRoot)
                    },
                )
            }

            item {
                GlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    cornerRadiusDp = 14.dp,
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 14.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .padding(end = 12.dp),
                        ) {
                            Text(
                                text = stringResource(R.string.settings_beta_tester_title),
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Medium,
                                color = colorScheme.onSurface,
                            )
                            Text(
                                text = stringResource(R.string.settings_beta_tester_desc),
                                style = MaterialTheme.typography.bodySmall,
                                color = colorScheme.onSurfaceVariant,
                            )
                        }

                        Switch(
                            checked = isBetaTester,
                            onCheckedChange = { checked ->
                                isBetaTester = checked
                                UpdateManager.setBetaTesterEnabled(context, checked)
                                HapticUtil.tick(view)
                                UpdateManager.checkForUpdates(context, force = true)
                            },
                        )
                    }
                }
            }

            // Section: About
            item {
                Spacer(Modifier.height(6.dp))
                Text(
                    text = stringResource(R.string.settings_section_about),
                    style = MaterialTheme.typography.labelMedium,
                    color = colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                )
            }

            item {
                GlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    cornerRadiusDp = 14.dp,
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Icon(
                                imageVector = Icons.Filled.Info,
                                contentDescription = null,
                                tint = colorScheme.primary,
                                modifier = Modifier.size(20.dp),
                            )
                            Text(
                                text = stringResource(R.string.settings_app_name),
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = colorScheme.onSurface,
                            )
                        }

                        Text(
                            text = "v${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                            style = MaterialTheme.typography.bodySmall,
                            color = colorScheme.onSurfaceVariant,
                        )

                        if (BuildConfig.GIT_SHA.isNotBlank()) {
                            Text(
                                text = "Git SHA: ${BuildConfig.GIT_SHA.take(7)}",
                                style = MaterialTheme.typography.bodySmall,
                                fontFamily = FontFamily.Monospace,
                                color = colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
                            )
                        }

                        val formattedDate = remember {
                            SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())
                                .format(Date(BuildConfig.BUILD_TIME_MILLIS))
                        }
                        Text(
                            text = "Build: $formattedDate",
                            style = MaterialTheme.typography.bodySmall,
                            color = colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                        )
                    }
                }
            }

            item {
                GlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    cornerRadiusDp = 14.dp,
                    onClick = {
                        runCatching {
                            val intent = Intent(
                                Intent.ACTION_VIEW,
                                Uri.parse("https://github.com/S-Marcos-S/wallpapers-foss")
                            )
                            context.startActivity(intent)
                        }
                    },
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            modifier = Modifier.weight(1f),
                        ) {
                            Icon(
                                imageVector = Icons.Filled.Code,
                                contentDescription = null,
                                tint = colorScheme.primary,
                                modifier = Modifier.size(20.dp),
                            )
                            Column {
                                Text(
                                    text = stringResource(R.string.settings_source_code),
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.Medium,
                                    color = colorScheme.onSurface,
                                )
                                Text(
                                    text = stringResource(R.string.settings_source_code_desc),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = colorScheme.onSurfaceVariant,
                                )
                            }
                        }

                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.OpenInNew,
                            contentDescription = null,
                            tint = colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(18.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun UpdateStatusCard(
    updateInfo: UpdateInfo?,
    isChecking: Boolean,
    downloadStatus: DownloadStatus,
    isRoot: Boolean,
    onCheckAgain: () -> Unit,
    onDownload: (UpdateInfo) -> Unit,
    onInstall: (android.net.Uri, Boolean) -> Unit,
) {
    val colorScheme = MaterialTheme.colorScheme
    var isChangelogExpanded by remember { mutableStateOf(false) }

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadiusDp = 14.dp,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (updateInfo != null && updateInfo.hasUpdate) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = stringResource(R.string.update_available_title),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                            color = colorScheme.primary,
                        )
                        Text(
                            text = "${stringResource(R.string.update_version_label)}: ${updateInfo.displayVersion}",
                            style = MaterialTheme.typography.bodySmall,
                            color = colorScheme.onSurfaceVariant,
                        )
                    }

                    Icon(
                        imageVector = Icons.Filled.SystemUpdate,
                        contentDescription = null,
                        tint = colorScheme.primary,
                        modifier = Modifier.size(24.dp),
                    )
                }

                if (updateInfo.changelog.isNotBlank()) {
                    val formattedChangelog = remember(updateInfo.changelog, colorScheme) {
                        formatMarkdownToAnnotated(updateInfo.changelog, colorScheme)
                    }

                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(colorScheme.surfaceContainerHigh.copy(alpha = 0.5f))
                            .padding(8.dp)
                    ) {
                        if (isChangelogExpanded) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(max = 240.dp)
                                    .verticalScroll(rememberScrollState())
                            ) {
                                Text(
                                    text = formattedChangelog,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = colorScheme.onSurface,
                                )
                            }
                        } else {
                            Text(
                                text = formattedChangelog,
                                style = MaterialTheme.typography.bodySmall,
                                color = colorScheme.onSurface,
                                maxLines = 4,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }

                        Row(
                            modifier = Modifier
                                .clip(RoundedCornerShape(6.dp))
                                .clickable { isChangelogExpanded = !isChangelogExpanded }
                                .padding(vertical = 4.dp, horizontal = 2.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Icon(
                                imageVector = if (isChangelogExpanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                                contentDescription = null,
                                tint = colorScheme.primary,
                                modifier = Modifier.size(16.dp),
                            )
                            Text(
                                text = stringResource(if (isChangelogExpanded) R.string.action_show_less else R.string.action_show_more),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.SemiBold,
                                color = colorScheme.primary,
                            )
                        }
                    }
                }

                when (val status = downloadStatus) {
                    is DownloadStatus.Idle -> {
                        Button(
                            onClick = { onDownload(updateInfo) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(10.dp),
                            contentPadding = PaddingValues(vertical = 8.dp),
                        ) {
                            Text(
                                text = stringResource(R.string.action_download_update),
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                    is DownloadStatus.Downloading -> {
                        Column(
                            modifier = Modifier.fillMaxWidth(),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            LinearProgressIndicator(
                                progress = { status.progressPercent / 100f },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(6.dp)
                                    .clip(RoundedCornerShape(3.dp)),
                            )
                            Text(
                                text = "${status.progressPercent}%",
                                style = MaterialTheme.typography.labelSmall,
                                color = colorScheme.primary,
                                modifier = Modifier.align(Alignment.End),
                            )
                        }
                    }
                    is DownloadStatus.Finished -> {
                        val uri = status.fileUri
                        if (uri != null) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                if (isRoot) {
                                    Button(
                                        onClick = { onInstall(uri, true) },
                                        modifier = Modifier.weight(1f),
                                        shape = RoundedCornerShape(10.dp),
                                        contentPadding = PaddingValues(vertical = 8.dp),
                                    ) {
                                        Text(
                                            text = stringResource(R.string.action_install_root),
                                            style = MaterialTheme.typography.labelMedium,
                                            fontWeight = FontWeight.Bold,
                                            maxLines = 1,
                                        )
                                    }
                                }
                                Button(
                                    onClick = { onInstall(uri, false) },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(10.dp),
                                    colors = if (isRoot) ButtonDefaults.filledTonalButtonColors() else ButtonDefaults.buttonColors(),
                                    contentPadding = PaddingValues(vertical = 8.dp),
                                ) {
                                    Text(
                                        text = stringResource(R.string.action_install),
                                        style = MaterialTheme.typography.labelMedium,
                                        fontWeight = FontWeight.Bold,
                                        maxLines = 1,
                                    )
                                }
                            }
                        }
                    }
                    is DownloadStatus.InstallingRoot -> {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                            Text(
                                text = stringResource(R.string.update_installing_root),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                    is DownloadStatus.Failed -> {
                        Text(
                            text = "${stringResource(R.string.update_download_failed)}: ${status.error}",
                            style = MaterialTheme.typography.bodySmall,
                            color = colorScheme.error,
                        )
                        Button(
                            onClick = { onDownload(updateInfo) },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(10.dp),
                            contentPadding = PaddingValues(vertical = 8.dp),
                        ) {
                            Text(stringResource(R.string.action_retry))
                        }
                    }
                }
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (isChecking) stringResource(R.string.update_checking) else stringResource(R.string.update_up_to_date),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                        )
                        Text(
                            text = "${stringResource(R.string.update_current_version)}: v${BuildConfig.VERSION_NAME}",
                            style = MaterialTheme.typography.bodySmall,
                            color = colorScheme.onSurfaceVariant,
                        )
                    }

                    IconButton(
                        onClick = onCheckAgain,
                        enabled = !isChecking,
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Refresh,
                            contentDescription = stringResource(R.string.action_check_updates),
                        )
                    }
                }
            }
        }
    }
}

private fun formatMarkdownToAnnotated(text: String, colorScheme: ColorScheme): AnnotatedString {
    return buildAnnotatedString {
        val lines = text.lines()
        lines.forEachIndexed { index, rawLine ->
            val trimmed = rawLine.trim()
            when {
                trimmed.startsWith("---") || trimmed.startsWith("***") -> {
                    // subtle spacing
                }
                trimmed.startsWith("###") -> {
                    val content = trimmed.removePrefix("###").trim()
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = colorScheme.primary)) {
                        append(content)
                    }
                }
                trimmed.startsWith("##") -> {
                    val content = trimmed.removePrefix("##").trim()
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = colorScheme.primary)) {
                        append(content)
                    }
                }
                trimmed.startsWith("#") -> {
                    val content = trimmed.removePrefix("#").trim()
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = colorScheme.primary)) {
                        append(content)
                    }
                }
                trimmed.startsWith("- ") || trimmed.startsWith("* ") -> {
                    append("• ")
                    parseInlineMarkdown(trimmed.substring(2).trim(), colorScheme)
                }
                else -> {
                    parseInlineMarkdown(trimmed, colorScheme)
                }
            }

            if (index < lines.lastIndex && trimmed.isNotBlank()) {
                append("\n")
            }
        }
    }
}

private fun AnnotatedString.Builder.parseInlineMarkdown(line: String, colorScheme: ColorScheme) {
    val tokenRegex = Regex("""(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)""")
    var lastIndex = 0
    for (match in tokenRegex.findAll(line)) {
        if (match.range.first > lastIndex) {
            append(line.substring(lastIndex, match.range.first))
        }
        val fullMatch = match.value
        when {
            fullMatch.startsWith("**") && fullMatch.endsWith("**") -> {
                val inner = fullMatch.substring(2, fullMatch.length - 2)
                withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
                    append(inner)
                }
            }
            fullMatch.startsWith("*") && fullMatch.endsWith("*") -> {
                val inner = fullMatch.substring(1, fullMatch.length - 1)
                withStyle(SpanStyle(fontStyle = FontStyle.Italic)) {
                    append(inner)
                }
            }
            fullMatch.startsWith("`") && fullMatch.endsWith("`") -> {
                val inner = fullMatch.substring(1, fullMatch.length - 1)
                withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = colorScheme.surfaceContainerHighest)) {
                    append(inner)
                }
            }
            else -> append(fullMatch)
        }
        lastIndex = match.range.last + 1
    }
    if (lastIndex < line.length) {
        append(line.substring(lastIndex))
    }
}

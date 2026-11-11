# Viagara Wallpapers R8 Proguard rules

-keep class dev.viagarawallpapers.ViagaraWallpapersApp { *; }
-keep class dev.viagarawallpapers.MainActivity { *; }
-keep class dev.viagarawallpapers.wallpaper.VideoLiveWallpaperService { *; }
-keep class dev.viagarawallpapers.wallpaper.WallpaperCheckAlarmReceiver { *; }
-keep class dev.viagarawallpapers.update.MyPackageReplacedReceiver { *; }

# Keep data models used with JSON
-keepclassmembers class dev.viagarawallpapers.update.UpdateInfo { *; }
-keepclassmembers class dev.viagarawallpapers.wallpaper.WallpaperItem { *; }
-keepclassmembers class dev.viagarawallpapers.wallpaper.WallpaperCategory { *; }
-keepclassmembers class dev.viagarawallpapers.wallpaper.WallpaperCatalog { *; }
-keepclassmembers class dev.viagarawallpapers.wallpaper.WallpaperNotificationInfo { *; }

# Line numbers and source files for clean stacktraces
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

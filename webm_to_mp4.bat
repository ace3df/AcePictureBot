\FFmpeg\ffmpeg.exe -fflags +genpts -i %1 -vf "scale=640:trunc(ow/a/2)*2" -y -r 24 %2

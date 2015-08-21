set filters=fps=10,scale=380:-1:flags=lanczos

D:\Projects\Python\AcePictureBot\FFmpeg\ffmpeg.exe -v warning -i %1 -vf "%filters%,palettegen" -y palette.png
D:\Projects\Python\AcePictureBot\FFmpeg\ffmpeg.exe -v warning -i %1 -i palette.png -lavfi "%filters% [x]; [x][1:v] paletteuse" -y %2
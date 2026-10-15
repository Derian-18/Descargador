import os
import sys
from pathlib import Path

import yt_dlp

class VideoDownloaderSinDuplicados:
    def __init__(self, download_path="downloads", log=None, raise_errors=False):
        """
        log: función opcional log(mensaje, nivel) para mandar mensajes a la UI.
             nivel puede ser "info", "ok", "warn" o "err".
        raise_errors: si es True, los errores se vuelven a lanzar para que la UI
             los muestre. Si es False (CLI), los métodos devuelven False como antes.
        """
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.log_callback = log
        self.raise_errors = raise_errors
        self._ultimo_paso = -1

    def set_download_path(self, nueva_ruta):
        """Cambia la carpeta de descarga (la crea si no existe)."""
        ruta = Path(nueva_ruta)
        ruta.mkdir(parents=True, exist_ok=True)
        self.download_path = ruta

    # ------------------------------------------------------------------
    # BINARIOS INCLUIDOS (ffmpeg y Deno dentro del ejecutable)
    # ------------------------------------------------------------------
    @staticmethod
    def _carpeta_bin():
        """Carpeta con los binarios incluidos. Solo existe en el ejecutable."""
        base = getattr(sys, "_MEIPASS", None)
        return Path(base) / "bin" if base else None

    def _opciones_binarios(self):
        """Si corre como ejecutable, hace que yt-dlp use el ffmpeg y el Deno
        incluidos. Corriendo desde Python normal, no cambia nada."""
        opciones = {}
        carpeta = self._carpeta_bin()
        if carpeta is None or not carpeta.exists():
            return opciones

        ext = ".exe" if os.name == "nt" else ""
        for nombre in ("ffmpeg", "ffprobe", "deno"):
            ruta = carpeta / (nombre + ext)
            if ruta.exists() and os.name != "nt":
                try:
                    ruta.chmod(0o755)
                except OSError:
                    pass

        if (carpeta / ("ffmpeg" + ext)).exists():
            opciones['ffmpeg_location'] = str(carpeta)

        deno = carpeta / ("deno" + ext)
        if deno.exists():
            opciones['js_runtimes'] = {'deno': {'path': str(deno)}}
        return opciones

    # ------------------------------------------------------------------
    # LOG / ERRORES
    # ------------------------------------------------------------------
    def _log(self, mensaje, nivel="info"):
        """Imprime en la terminal y, si hay callback, también en la UI."""
        print(mensaje)
        if self.log_callback:
            try:
                self.log_callback(mensaje, nivel)
            except TypeError:
                self.log_callback(mensaje)

    def _fallo(self, e, nota=None):
        """Maneja un error: lo muestra y lo relanza si estamos en modo UI."""
        if self.raise_errors:
            # La UI ya muestra el error, solo lo relanzamos
            print(f"\n❌ Error: {e}")
            raise e
        self._log(f"\n❌ Error: {e}", "err")
        if nota:
            self._log(nota, "warn")
        return False

    class _YdlLogger:
        """Redirige los mensajes internos de yt-dlp a _log."""

        def __init__(self, owner):
            self.owner = owner

        def debug(self, msg):
            # Ignora el spam de porcentajes; el progreso va por los hooks
            if msg.startswith("[debug]") or ("[download]" in msg and "%" in msg):
                return
            self.owner._log(msg, "info")

        def info(self, msg):
            self.debug(msg)

        def warning(self, msg):
            self.owner._log(f"⚠️ {msg}", "warn")

        def error(self, msg):
            self.owner._log(f"❌ {msg}", "err")

    # ------------------------------------------------------------------
    # AUDIO
    # ------------------------------------------------------------------
    def descargar_audio_mp3(self, url, calidad_audio="192"):
        """Descarga SOLO el audio en formato MP3"""
        self._log(f"🎵 Extrayendo audio MP3 a {calidad_audio}kbps...")

        ydl_opts = {
            'noplaylist': True,
            'format': 'bestaudio/best',
            'outtmpl': str(self.download_path / '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': calidad_audio,
            }],
            'keepvideo': False,
            'quiet': False,
            'no_warnings': False,
            'logger': self._YdlLogger(self),
            'progress_hooks': [self._hook_progreso_audio],
        }

        ydl_opts.update(self._opciones_binarios())

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self._log(f"🎵 Descargando audio de: {info.get('title', 'Video')}")
                ydl.download([url])
                self._log(f"✅ MP3 descargado en: {self.download_path}", "ok")
                return True
        except Exception as e:
            return self._fallo(e)

    def descargar_con_album_art(self, url, calidad_audio="192"):
        """Descarga MP3 con imagen de portada incrustada"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.download_path / '%(title)s.%(ext)s'),
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': calidad_audio,
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                }
            ],
            'noplaylist': True,
            'writethumbnail': True,
            'embedthumbnail': True,
            'quiet': False,
            'no_warnings': False,
            'logger': self._YdlLogger(self),
            'progress_hooks': [self._hook_progreso_audio],
        }

        ydl_opts.update(self._opciones_binarios())

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self._log(f"🎵 Descargando MP3 con portada: {info.get('title', 'Video')}")
                ydl.download([url])
                self._log(f"✅ MP3 con portada descargado en: {self.download_path}", "ok")
                return True
        except Exception as e:
            return self._fallo(e, "💡 Nota: La portada requiere ffmpeg instalado")

    # ------------------------------------------------------------------
    # VIDEO
    # ------------------------------------------------------------------
    def descargar_video(self, url, calidad="best"):
        """Descarga video normal (sin duplicados)"""
        ydl_opts = {
            'noplaylist': True,
            'format': self._obtener_mejor_formato_simple(calidad),
            'outtmpl': str(self.download_path / '%(title)s.%(ext)s'),
            'format_sort': ['res', 'ext:mp4:m4a', 'size'],
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'quiet': False,
            'no_warnings': False,
            'logger': self._YdlLogger(self),
            'progress_hooks': [self._hook_progreso],
        }

        ydl_opts.update(self._opciones_binarios())

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._log(f"📥 Descargando video: {url}")
                ydl.download([url])
                self.limpiar_temporales()
                self._log("✅ Video descargado", "ok")
                return True
        except Exception as e:
            return self._fallo(e)

    def _obtener_mejor_formato_simple(self, calidad):
        # Antes se forzaba ext=mp4 y 'best', que en YouTube solo deja el
        # formato 18 (360p con audio) y suele dar 403. Ahora se piden video y
        # audio por separado y se unen a mp4 con ffmpeg.
        formatos = {
            'best': 'bestvideo+bestaudio/best',
            '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
        }
        return formatos.get(calidad, 'bestvideo+bestaudio/best')

    # ------------------------------------------------------------------
    # PROGRESO
    # ------------------------------------------------------------------
    def _progreso(self, d, icono, mensaje_final):
        if d['status'] == 'downloading':
            # En descargas por fragmentos (DASH) total_bytes no existe,
            # por eso se usa también total_bytes_estimate.
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total:
                porcentaje = d['downloaded_bytes'] / total * 100
                paso = int(porcentaje // 10) * 10
                if paso != self._ultimo_paso:
                    self._ultimo_paso = paso
                    self._log(f"{icono} {paso}%")
        elif d['status'] == 'finished':
            self._ultimo_paso = -1
            self._log(mensaje_final)

    def _hook_progreso(self, d):
        self._progreso(d, "📊", "🔧 Procesando...")

    def _hook_progreso_audio(self, d):
        self._progreso(d, "🎵", "🎵 Convirtiendo a MP3...")

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------
    def limpiar_temporales(self):
        try:
            # '*.f[0-9]*' solo coincide con restos de formatos (.f137.mp4),
            # no con archivos legítimos como .flac o .flv
            for ext in ('*.part', '*.ytdl', '*.temp', '*.f[0-9]*', '*.webm', '*.m4a'):
                for archivo in self.download_path.glob(ext):
                    try:
                        archivo.unlink()
                    except OSError:
                        pass
        except OSError:
            pass

    def listar_archivos_descargados(self):
        videos = list(self.download_path.glob('*.mp4')) + list(self.download_path.glob('*.mkv'))
        mp3s = list(self.download_path.glob('*.mp3'))

        if videos or mp3s:
            print("\n📁 ARCHIVOS DESCARGADOS:")
            print("-" * 50)
            if mp3s:
                print("\n🎵 MP3s:")
                for archivo in mp3s:
                    tamaño = archivo.stat().st_size / (1024 * 1024)
                    print(f"  • {archivo.name} ({tamaño:.1f} MB)")
            if videos:
                print("\n🎬 Videos:")
                for archivo in videos[:10]:
                    tamaño = archivo.stat().st_size / (1024 * 1024)
                    print(f"  • {archivo.name} ({tamaño:.1f} MB)")
                if len(videos) > 10:
                    print(f"  ... y {len(videos) - 10} más")
        else:
            print("\n📁 No hay archivos descargados aún")
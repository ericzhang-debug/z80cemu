"""Small Windows audio output adapter for the PSG's unsigned mono PCM."""
import io
import queue
import threading
import wave

def pcm_wave(data, sample_rate):
    if sample_rate <= 0: raise ValueError('invalid sample rate')
    result = io.BytesIO()
    with wave.open(result, 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(1); stream.setframerate(sample_rate)
        stream.writeframes(bytes(data))
    return result.getvalue()

class WindowsAudioOutput:
    """Play short PCM blocks on a worker thread; never block the Tk thread.

    A full queue drops the newest block to bound latency and memory consumption.
    The caller can inspect `error` after a system playback failure.
    """
    def __init__(self, sample_rate=22050, backlog=4):
        if sample_rate <= 0 or backlog <= 0: raise ValueError('invalid audio settings')
        self.sample_rate = sample_rate
        self.queue = queue.Queue(maxsize=backlog)
        self.error = None
        self.closed = False
        self.thread = threading.Thread(target=self._worker, name='psg-audio', daemon=True)
        self.thread.start()

    def submit(self, data):
        if self.closed or not data: return False
        try: self.queue.put_nowait(bytes(data)); return True
        except queue.Full: return False

    def _worker(self):
        try:
            import winsound
            while True:
                data = self.queue.get()
                if data is None: return
                winsound.PlaySound(pcm_wave(data, self.sample_rate), winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        except Exception as error:
            self.error = str(error)

    def close(self):
        if self.closed: return
        self.closed = True
        while True:
            try: self.queue.put_nowait(None); break
            except queue.Full:
                try: self.queue.get_nowait()
                except queue.Empty: pass

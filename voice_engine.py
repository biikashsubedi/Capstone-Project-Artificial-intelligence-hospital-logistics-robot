import speech_recognition as sr


class VoiceController:
    def __init__(self, on_log, on_transcription, on_error, on_stop):
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        self.is_listening = False
        self.stop_listening_fn = None

        # Callback functions to update the UI safely
        self.on_log = on_log
        self.on_transcription = on_transcription
        self.on_error = on_error
        self.on_stop = on_stop

    def toggle(self):
        if not self.is_listening:
            self.start()
        else:
            self.stop(manual=True)

    def start(self):
        self.is_listening = True
        try:
            mic = sr.Microphone()
            with mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

            # Listens in background thread to prevent UI freezing
            self.stop_listening_fn = self.recognizer.listen_in_background(mic, self._audio_callback)
            return True
        except Exception as e:
            self.on_error(f"Check permissions. ({e})")
            self.stop(manual=True)
            return False

    def stop(self, manual=False):
        if self.stop_listening_fn:
            self.stop_listening_fn(wait_for_stop=False)
            self.stop_listening_fn = None

        self.is_listening = False
        self.on_stop(manual)

    def _audio_callback(self, recognizer, audio):
        if not self.is_listening: return

        self.on_log("⏳ Analyzing audio input...")
        try:
            text = recognizer.recognize_google(audio)
            self.on_transcription(text)
            self.stop(manual=False)
        except sr.UnknownValueError:
            self.on_error("Could not understand audio. Try again.")
            self.stop(manual=False)
        except sr.RequestError:
            self.on_error("Network error. Check internet connection.")
            self.stop(manual=False)
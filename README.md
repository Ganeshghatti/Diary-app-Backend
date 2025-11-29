# Diary-app-Backend

NOTE
diary/speech-to-text route may not work in local
google cloud expects audio in X format which doesn't match with expo voice record default output
So, I have setup conversion. This is working on EC2, but will not work on local

I have added imports and set this:
if os.getenv("env") == "production":
    from pydub import AudioSegment
    from pydub.utils import which
    AudioSegment.ffmpeg = which("ffmpeg")
    AudioSegment.ffprobe = which("ffprobe")


GPT GENERATED DOCS

1. Overview

While integrating audio recording in Expo (React Native) with a Flask + Google Cloud Speech-to-Text backend, the app consistently failed with errors like:


{"error": "No audio file provided"}


and later:

Audio conversion failed: [Errno 2] No such file or directory: 'ffprobe'

Even after the frontend was fixed and the backend received the file properly, audio conversion continued failing.

2. Issues Faced

#Issue 1 — Expo Go sending blob URI

On simulator, the recorded audio URI looked like:

blob:http://localhost:8081/xxxx

Flask cannot read blob URLs → backend never received a valid file.
This was resolved by testing on a real Android device using Expo Go, which produces a proper file URI:

file:///data/user/0/.../recording.m4a

#Issue 2 — Google Cloud STT rejecting audio format

Expo’s default recording format is AAC / M4A.
Google STT fails if:

* incorrect encoding is specified
* sample rate mismatches
* audio is in AAC container

The backend attempted to send the raw M4A directly, causing:

400 Invalid recognition 'config': bad encoding

#Issue 3 — Audio conversion failed on server

After adding a conversion step using pydub + ffmpeg, backend still failed:

Audio conversion failed: [Errno 2] No such file or directory: 'ffprobe'

This happened because:

* ffmpeg/ffprobe were installed for the *user*,
* BUT systemd (gunicorn service) runs in a restricted PATH
* pydub could not locate ffprobe inside the service environment

3. Approaches Tried

#Approach A — Send raw Expo recorded file to Google STT

Failed because Google STT requires:

* WAV (Linear16)
* correct sample rate
* correct encoding

#Approach B — Upload MP3 instead

Worked in Postman but Expo AV didn't generate MP3 easily without transcoding.

#Approach C — Convert audio on backend to WAV

Correct approach, but conversion failed due to missing ffprobe for systemd.

4. Final Working Solution

#Step 1 — Install ffmpeg on EC2

sudo apt update
sudo apt install -y ffmpeg

Verify:

ffmpeg -version
ffprobe -version

#Step 2 — Explicitly define ffprobe path in backend

from pydub import AudioSegment
from pydub.utils import which

AudioSegment.ffmpeg = which("ffmpeg")
AudioSegment.ffprobe = which("ffprobe")

If `which("ffprobe")` returned None:

AudioSegment.ffprobe = "/usr/bin/ffprobe"
AudioSegment.ffmpeg = "/usr/bin/ffmpeg"

#Step 3 — Add PATH inside systemd (gunicorn service)

In `/etc/systemd/system/diaryapp.service`:

Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

Reload + restart:

sudo systemctl daemon-reload
sudo systemctl restart diaryapp

#Step 4 — Convert any incoming audio → 16 kHz mono WAV

Using pydub:

sound = AudioSegment.from_file(filepath_original)
sound = sound.set_frame_rate(16000).set_channels(1)
sound.export(wav_path, format="wav")

STT always receives high-quality Linear16 WAV → Google Cloud accepts every time.

#Step 5 — Frontend stays unchanged

Expo uses:

Audio.RecordingOptionsPresets.HIGH_QUALITY

Perfectly fine — backend handles all conversions.

5. Final Result

After applying the fixes:

* Audio file uploads successfully
* Backend converts audio to WAV
* Google STT processes audio without errors
* The app returns accurate transcription
* Entire workflow (Android → Flask → GCP STT) works smoothly

6. Key Lessons Learned

* Avoid blob URIs; test audio recording on real devices.
* Google STT expects strict audio formats.
* Always convert incoming audio to 16kHz WAV on server.
* Systemd services do not inherit your shell PATH.
* Always explicitly specify ffmpeg/ffprobe paths in Python when using pydub.
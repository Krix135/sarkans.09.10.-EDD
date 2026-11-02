# Would You Rather? video generator

`make_video.py` makes a complete 1080p "Would You Rather?" video in the style of the big YouTube quiz channels.

**[▶ would_you_rather.mp4](would_you_rather.mp4)** is a finished 5½-minute video made with seed `2026`. Its subjects are Superpowers, Technology and Time Travel.

## What's in the video

| Part | What happens |
| --- | --- |
| **Intro** | The red and blue halves slam together, the title pops in and the narrator explains the rules: keep count of how often you side with the majority. |
| **Subject wheel** | Before each round, a 10-subject wheel spins and slows down. The pointer flicks on every peg and clicks with it, then the wheel lands on a **random subject**. |
| **Questions** | Each question has a red side and a blue side, each with an emoji and text. The narrator reads the question, then a **5-second countdown** starts with a ring timer and ticking. The last 3 seconds turn red. |
| **Reveal** | A ding plays, the percentages count up, each panel fills like a poll bar, the losing side dims and the winner gets a 👑 MAJORITY badge. |
| **Fun fact** | Every question ends with a real fact about the topic. It is shown on screen and read aloud. |
| **Outro** | A score table (*You ARE the majority / Perfectly balanced / A total original*) and a call to action. |

* **Subjects (10):** Food, Superpowers, Animals, Travel, Money, Technology, Space, School, Sports and Time Travel. Each has 5 questions, so there are 50 in total.
* **Voice:** the [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) neural text-to-speech model, run offline.
* **Music and sound effects:** all synthesised in code (the upbeat background loop, ticks, ding, whooshes, wheel clicks and fanfare), so there are no copyright problems. The music gets quieter while the narrator speaks.
* **Percentages:** based on how these classic questions usually split in online polls. Each video adds ±3% random jitter, so every run looks like a fresh poll.

## Make a new video

```bash
pip install kokoro-onnx soundfile scipy numpy pillow
python3 make_video.py                  # new random subjects every time
python3 make_video.py --seed 2026      # recreate the included video
python3 make_video.py --rounds 2 --per-round 3 --out short.mp4
python3 make_video.py --seed 7 --stills 5,30,60   # preview PNG frames only
```

You also need `ffmpeg`, plus the Inter and Noto Color Emoji fonts at the paths at the top of `make_video.py`. The first run downloads the voice model (about 120 MB) into `models/`. Narration clips are cached in `.cache/`, so later renders are faster.

To add your own questions, edit `questions.py`. Each line is
`(option A, emoji A, option B, emoji B, % who pick A, fun fact)`.

# Notes for Claude

## YouTube channel (`would_you_rather/`)

- **Channel name: FUNNY QUIZZ** (two Z's; spoken and written as "Funny Quizz", hashtag `#funnyquizz`).
  It replaced the old name "Quizzies". Use the new name in every new video, title, description and thumbnail.
- **Logo:** `would_you_rather/funny_quizz_logo.png` (the popcorn badge, made by `make_funny_quizz_logo.py`).
  The old `profile_picture.png` is retired.
- Every generator takes the name and the logo from `would_you_rather/brand.py`
  (`brand.NAME`, `brand.SPOKEN`, `brand.HASHTAG`, `brand.round_logo()`); change them there, not in each script.
- The channel makes vertical quiz Shorts (1080x1920). Each video gets a `*_description.txt`
  with a title, description and hashtags.
- Narrator: the user likes the ElevenLabs "Adam" voice. Recorded lines are kept in
  `would_you_rather/voice_packs/` so they can be reused without spending credits again.

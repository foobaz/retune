# retune
Encode a large music library to small portable form

### Synopsis
`retune.py [-e encode_kbps] [-c cutoff_kbps] src_dir [another_src ...] dest_dir`

### Description
Let's say you have a large collection of music in an archival, high bitrate
format like FLAC or 320 kbps MP3.  You like having the high quality files,
but their size makes it difficult to fit your music on portable devices like
a phone, laptop, or thumb drive.

Retune solves this problem by encoding a small, low bitrate music collection
from your large one.  If the bitrate of the original album is already low
enough, it copies the album without re-encoding it.

By default, Retune encodes to 96 kbps Opus format.  It skips encoding albums
below 192 kbps and copies them to the new library without sacrificing quality.
These parameters are adjustable with the `-e` and `-c` arguments.

### How it works
Retune does not depend on any 3rd party Python packages, only the standard
library.  It does depend on the `ffmpeg` command line tool to get bitrates
and to do the encoding.  Retune was developed with Python 3.6 and also tested
with Python 3.8.

By default Retune uses all CPU cores to encode files in parallel, and it can
take hours to encode large libraries - roughly 1 hour per 100 GB of music.  If
you don't want it monopolizing your CPU for all this time, use `-j` to set the
number of parallel jobs lower, or run Retune with `nice` to lower its priority.

# retune
Encode a large music library to small portable form

### Synopsis
`retune.py [-e encode_kbps] [-c cutoff_kbps] src_dir [another_src ...] dest_dir`

### Options

`-e`
Encoding bitrate in kbps.  Defaults to 96 kbps.

`-c`
Cutoff bitrate in kbps.  Albums with an overall bitrate below this value will
copied to the output directory without re-encoding.  Defaults to 192 kbps.

`-f`
Output format.  May be mp3, vorbis, aac, or opus.  Defaults to aac.

`-j`
Number of encoding jobs to run in parallel.  Defaults to the number of CPUs.

`-b`
Block utilization optimizer.  Dynamically adjusts the encoding bitrate to
produce output files with file sizes equal to or slightly less than a round
number of filesystem blocks, to minimize wasted space.  Most effective for
filesystems with block or cluster sizes of 32 kiB or above, such as exFAT.
Triples the encoding time.  Disabled by default.

### Description
Let's say you have a large collection of music in an archival, high bitrate
format like FLAC or 320 kbps MP3.  You like having the high quality files,
but their size makes it difficult to fit your music on portable devices like
a phone, laptop, or thumb drive.

Retune solves this problem by encoding a small, low bitrate music collection
from your large one.  If the bitrate of the original album is already low
enough, it copies the album without re-encoding it.

By default, Retune encodes to 96 kbps AAC format.  It skips encoding albums
below 192 kbps and copies them to the new library without sacrificing quality.
These parameters are adjustable with the `-e` and `-c` arguments.

### Block size optimization
Using the `-b` option encodes each file three time to find a bitrate that
makes maximum use of the given filesystem block or cluster size.  Here is an
example of how this affects the output files:
```
Unoptimized output                              Optimized for 2 MiB blocks using -b2097152

% du -hs *                                      % du -hs *
2.8M    01 Sunday Morning.m4a                   2.0M    01 Sunday Morning.m4a
4.3M    02 I'm Waiting for the Man.m4a          4.0M    02 I'm Waiting for the Man.m4a
2.5M    03 Femme Fatale.m4a                     2.0M    03 Femme Fatale.m4a
4.8M    04 Venus in Furs.m4a                    4.0M    04 Venus in Furs.m4a
4.0M    05 Run Run Run.m4a                      4.0M    05 Run Run Run.m4a
5.5M    06 All Tomorrow's Parties.m4a           6.0M    06 All Tomorrow's Parties.m4a
6.6M    07 Heroin.m4a                           6.0M    07 Heroin.m4a
2.5M    08 There She Goes Again.m4a             2.0M    08 There She Goes Again.m4a
2.1M    09 I'll Be Your Mirror.m4a              2.0M    09 I'll Be Your Mirror.m4a
3.0M    10 The Black Angel's Death Song.m4a     4.0M    10 The Black Angel's Death Song.m4a
7.1M    11 European Son.m4a                     8.0M    11 European Son.m4a
272K    cover.jpg                               272K    cover.jpg
 46M    .                                        44M    .
```

### How it works
Retune does not depend on any 3rd party Python packages, only the standard
library.  It does depend on the `ffmpeg` command line tool to get bitrates
and to do the encoding.  To encode to AAC (the default), ffmpeg must have
libfdk_aac enabled at compile time.  Retune was developed with Python 3.6 and
3.7 and also tested with Python 3.8.

By default Retune uses all CPU cores to encode files in parallel, and it can
take hours to encode large libraries - roughly 1 hour per 100 GB of music.  If
you don't want it monopolizing your CPU for all this time, use `-j` to set the
number of parallel jobs lower, or run Retune with `nice` to lower its priority.

#!/usr/bin/env python3

import argparse
import json
import threading
import os
import queue
import random
import shutil
import string
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('src', type=str, nargs='+', help='paths to input directories with music')
parser.add_argument('dst', type=str, help='path to output directory')
parser.add_argument('-j', metavar='jobs', type=int, default='0', help='number of parallel jobs, zero to autodetect')
parser.add_argument('-e', metavar='kbit/s', type=int, default='96', help='encoding bitrate for transcoded files in kbit/s')
parser.add_argument('-c', metavar='kbit/s', type=int, default='192', help='cutoff bitrate below which transcoding skipped')
args = parser.parse_args()

class copy_encoder():
    def __init__(self, src, tmp, dst):
        self.src = src
        self.tmp = tmp
        self.dst = dst

    def encode(self):
        try:
            shutil.copyfile(self.src, self.tmp)
        except:
            print('couldn\'t copy cover art from {} to {}'.format(self.src, self.tmp))
            return

        #os.remove(self.src)
        os.rename(self.tmp, self.dst)

class strip_encoder():
    def __init__(self, src, tmp, dst):
        self.src = src
        self.tmp = tmp
        self.dst = dst

    def encode(self):
        subprocess_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-i', self.src, '-vn', '-c:a', 'copy', '-sn', '-dn', self.tmp]
        out = subprocess.call(subprocess_args)
        if not out == 0:
            print('skipping track that failed conversion: {}'.format(self.src))
            return

        #os.remove(self.src)
        os.rename(self.tmp, self.dst)

class opus_encoder():
    def __init__(self, src, tmp, dst, bitrate):
        self.src = src
        self.tmp = tmp
        self.dst = dst
        self.bitrate = bitrate

    def encode(self):
        subprocess_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-i', self.src, '-vn', '-c:a', 'libopus', '-vbr', 'on', '-frame_duration', '60', '-b:a', str(self.bitrate), '-sn', '-dn', self.tmp]
        out = subprocess.call(subprocess_args)
        if not out == 0:
            print('skipping track that failed conversion: {}'.format(self.src))
            return

        #os.remove(self.src)
        os.rename(self.tmp, self.dst)

def work():
    while True:
        encoder = q.get()
        if encoder is poison_pill:
            q.task_done()
            return
        encoder.encode()
        q.task_done()

def process_album(src_root, album_root, album_dir, q):
    album_joined = os.path.join(album_root, album_dir)
    relative_dir = os.path.relpath(album_joined, src_root)
    total_duration = 0
    total_size = 0

    audio_files = list()
    art_files = list()
    for entry in os.scandir(album_joined):
        if not entry.is_file():
            continue

        #print('\t{}'.format(track_path))
        #track_joined = os.path.join(track_root, track_file)
        #print('examining file {}'.format(track_path))
        out = subprocess.check_output(['ffprobe', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-show_streams', '-show_format', '-print_format', 'json', entry.path])
        #print("out == {0}".format(out))
        j = json.loads(out.decode('utf-8'))
        #print('j == {}'.format(j))
        if not 'streams' in j:
            print('skipping track with no streams: {}'.format(entry.name))
            continue

        s = j['streams']
        has_audio = False
        has_video = False
        for stream in s:
            if not 'codec_type' in stream:
                continue
            codec_type = stream['codec_type']
            if codec_type == 'audio':
                has_audio = True
            elif codec_type == 'video':
                has_video = True

        if has_audio:
            if not 'format' in j:
                print('skipping track with no format: {}'.format(entry.name))
                continue
            f = j['format']

            if not 'duration' in f:
                print('skipping track with no duration: {}'.format(entry.name))
                continue
            duration_string = f['duration']
            if not 'size' in f:
                print('skipping track with no bitrate: {}'.format(entry.name))
                continue
            size_string = f['size']

            try:
                duration = float(duration_string)
                size = float(size_string)
            except ValueError:
                print('skipping track with unparseable fields: {}'.format(entry.name))
                continue

            total_duration += duration
            total_size += size
            audio_files.append(entry)
        elif has_video:
            art_files.append(entry)
        #print('album_root {} album_dir {} name {}'.format(album_root, album_dir, entry.name))
        #print('duration == {}, size == {}'.format(duration, size))

    if not total_duration > 0:
        return

    bitrate = 8 * total_size / total_duration
    #print('total_size == {} MB, total_duration == {} min, bitrate == {} kb/s'.format(round(total_size / 1e6), round(total_duration / 60), round(bitrate / 1e3)))
    transcode = (bitrate > args.c * 1e3)
    if transcode:
        print('transcoding {} kb/s album: {}'.format(round(bitrate / 1e3), album_dir))
    else:
        print('    copying {} kb/s album: {}'.format(round(bitrate / 1e3), album_dir))

    dst_dir = os.path.join(args.dst, relative_dir)
    os.makedirs(dst_dir, exist_ok=True)

    for entry in audio_files:
        #print('converting track: {}'.format(track_path))
        before_ext, ext = os.path.splitext(entry.name)
        random_string = ''.join(random.choice(string.digits + string.ascii_letters) for i in range(16))
        if transcode:
            filename = before_ext + '.opus'
            output = os.path.join(dst_dir, filename)
            temp_output = os.path.splitext(output)[0] + '-temporary' + random_string + '.opus'
            encoder = opus_encoder(entry.path, temp_output, output, args.e * 1e3)
        else:
            output = os.path.join(dst_dir, entry.name)
            #temp_output = before_ext + '-temporary' + random_string + ext
            temp_output = os.path.splitext(output)[0] + '-temporary' + random_string + ext
            encoder = strip_encoder(entry.path, temp_output, output)
        #send_conn.send(encoder)
        q.put(encoder)

    for entry in art_files:
        before_ext, ext = os.path.splitext(entry.name)
        random_string = ''.join(random.choice(string.digits + string.ascii_letters) for i in range(16))
        output = os.path.join(dst_dir, entry.name)
        temp_output = os.path.splitext(output)[0] + '-temporary' + random_string + ext
        encoder = copy_encoder(entry.path, temp_output, output)
        q.put(encoder)

job_count = args.j
if not job_count > 0:
    job_count = os.cpu_count()
    if not job_count:
        job_count = 1

poison_pill = None
q = queue.Queue(1)
for i in range(job_count):
    t = threading.Thread(target=work)
    t.start()

for s in args.src:
    process_album(s, s, '', q)
    for album_root, album_dirs, album_files in os.walk(s):
        for d in album_dirs:
            process_album(s, album_root, d, q)

for i in range(args.j):
    q.put(poison_pill)
q.join()

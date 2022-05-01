#!/usr/bin/env python3

import argparse
import json
import math
import os
import queue
import random
import shutil
import signal
import string
import subprocess
import threading

parser = argparse.ArgumentParser()
parser.add_argument('src', type=str, nargs='+', help='paths to input directories with music')
parser.add_argument('dst', type=str, help='path to output directory')
parser.add_argument('-j', metavar='jobs', type=int, default='0', help='number of parallel jobs, zero to autodetect')
parser.add_argument('-e', metavar='kbit/s', type=int, default='96', help='encoding bitrate for transcoded files in kbit/s')
parser.add_argument('-c', metavar='kbit/s', type=int, default='192', help='cutoff bitrate below which transcoding skipped')
parser.add_argument('-b', metavar='bytes', type=int, default='0', help='optimize efficiency for filesystem block or cluster size')
parser.add_argument('-f', metavar='format', type=str, default='aac', help='audio format may be mp3, vorbis, aac, or opus')
args = parser.parse_args()

class copy_encoder():
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def encode(self):
        _, ext = os.path.splitext(self.dst)
        tmp = tempfile(self.dst, ext)
        try:
            shutil.copyfile(self.src, tmp)
        except:
            print('couldn\'t copy cover art from {} to {}'.format(self.src, tmp))
            return

        os.rename(tmp, self.dst)

class strip_encoder():
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def encode(self):
        _, ext = os.path.splitext(self.dst)
        tmp = tempfile(self.dst, ext)
        subprocess_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-i', self.src, '-map_metadata', '-1', '-vn', '-c:a', 'copy', '-sn', '-dn', tmp]
        try:
            out = subprocess.call(subprocess_args)
        except:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
            return

        if not out == 0:
            print('skipping track that failed conversion: {}'.format(self.src))
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
            return

        os.rename(tmp, self.dst)

class opus_encoder():
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def encode(self):
        encoder(self.src, self.dst, '.opus', ['libopus', '-vbr', 'on', '-frame_duration', '60'])

class aac_encoder():
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def encode(self):
        encoder(self.src, self.dst, '.m4a', ['libfdk_aac'])

class mp3_encoder():
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def encode(self):
        encoder(self.src, self.dst, '.mp3', ['libmp3lame', '-abr', '1'])

class vorbis_encoder():
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def encode(self):
        encoder(self.src, self.dst, '.ogg', ['libvorbis'])

def encoder(src, dst, ext, codec_args):
        #print('encoding {0} to {1}'.format(src, dst))
        bitrate = args.e * 1000
        tmp = tempfile(dst, ext)
        subprocess_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-i', src, '-map_metadata', '-1', '-vn', '-c:a'] + codec_args + ['-b:a', str(bitrate), '-sn', '-dn', tmp]
        try:
            out = subprocess.call(subprocess_args)
        except:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
            return

        if not out == 0:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
            print('skipping track that failed conversion: {}'.format(src))
            return

        if args.b > 0:
            # optimize efficiency for large filesystem block size by trying
            # different bitrates to find one producing a filesize only
            # slightly less than a round number of blocks

            result_first = os.stat(tmp)
            size_first = result_first.st_size
            blocks_first = size_first / args.b
            fractional_first, whole_first = math.modf(blocks_first)
            if fractional_first == 0:
                os.rename(tmp, dst)
                return
            if whole_first > 0:
                lower = whole_first * args.b
                upper = (whole_first + 1) * args.b
                #print('lower: {0}, upper: {1}, lower / size_first: {2}, size_first / upper: {3}'.format(lower, upper, lower / size_first, size_first / upper))
                if lower / size_first > size_first / upper:
                    target = lower
                else:
                    target = upper
            else:
                target = args.b

            bitrate_second = math.floor(bitrate * target / size_first)

            #print('size_first: {0}, target {1}, bitrate_second: {2}'.format(size_first, target, bitrate_second))

            tmp_second = tempfile(dst, ext)
            subprocess_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-i', src, '-map_metadata', '-1', '-vn', '-c:a'] + codec_args + ['-b:a', str(bitrate_second), '-sn', '-dn', tmp_second]
            try:
                out = subprocess.call(subprocess_args)
            except:
                try:
                    os.remove(tmp_second)
                except FileNotFoundError:
                    pass
                os.rename(tmp, dst)
                return

            if not out == 0:
                try:
                    os.remove(tmp_second)
                except FileNotFoundError:
                    pass
                os.rename(tmp, dst)
                return

            result_second = os.stat(tmp_second)
            size_second = result_second.st_size
            blocks_second = size_second / args.b
            fractional_second, whole_second = math.modf(blocks_second)
            if fractional_second == 0:
                try:
                    os.remove(tmp)
                except FileNotFoundError:
                    pass
                os.rename(tmp_second, dst)
                return

            bitrate_third = math.floor((bitrate * (size_second - target) + bitrate_second * (target - size_first)) / (size_second - size_first))
            #print('size_second: {0}, target: {1}, bitrate_third: {2}'.format(size_second, target, bitrate_third))

            tmp_third = tempfile(dst, ext)
            subprocess_args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-i', src, '-map_metadata', '-1', '-vn', '-c:a'] + codec_args + ['-b:a', str(bitrate_third), '-sn', '-dn', tmp_third]
            try:
                out = subprocess.call(subprocess_args)
            except:
                if not out == 0:
                    if fractional_first > fractional_second:
                        try:
                            os.remove(tmp_second)
                        except FileNotFoundError:
                            pass
                        try:
                            os.remove(tmp_third)
                        except FileNotFoundError:
                            pass
                        os.rename(tmp, dst)
                    else:
                        try:
                            os.remove(tmp)
                        except FileNotFoundError:
                            pass
                        try:
                            os.remove(tmp_third)
                        except FileNotFoundError:
                            pass
                        os.rename(tmp_second, dst)
                    return

            if not out == 0:
                if fractional_first > fractional_second:
                    try:
                        os.remove(tmp_second)
                    except FileNotFoundError:
                        pass
                    try:
                        os.remove(tmp_third)
                    except FileNotFoundError:
                        pass
                    os.rename(tmp, dst)
                else:
                    try:
                        os.remove(tmp)
                    except FileNotFoundError:
                        pass
                    try:
                        os.remove(tmp_third)
                    except FileNotFoundError:
                        pass
                    os.rename(tmp_second, dst)
                return

            result_third = os.stat(tmp_third)
            size_third = result_third.st_size
            #print('size_third: {0}'.format(size_third))
            blocks_third = size_third / args.b
            fractional_third, whole_third = math.modf(blocks_third)

            if fractional_third == 0 or (fractional_third >= fractional_first and fractional_third >= fractional_second):
                #print('keeping the third with size: {0}, target: {1}'.format(size_third, target))
                try:
                    os.remove(tmp)
                except FileNotFoundError:
                    pass
                try:
                    os.remove(tmp_second)
                except FileNotFoundError:
                    pass
                os.rename(tmp_third, dst)
            elif fractional_second >= fractional_first and fractional_second >= fractional_third:
                #print('keeping the second with size: {0}, target: {1}'.format(size_second, target))
                try:
                    os.remove(tmp)
                except FileNotFoundError:
                    pass
                try:
                    os.remove(tmp_third)
                except FileNotFoundError:
                    pass
                os.rename(tmp_second, dst)
            else:
                #print('keeping the first with size: {0}, target: {1}'.format(size_first, target))
                try:
                    os.remove(tmp_second)
                except FileNotFoundError:
                    pass
                try:
                    os.remove(tmp_third)
                except FileNotFoundError:
                    pass
                os.rename(tmp, dst)
        else:
            os.rename(tmp, dst)

def tempfile(base, ext):
    random_string = ''.join(random.choice(string.digits + string.ascii_letters) for i in range(16))
    temp_output = os.path.splitext(base)[0] + '-temporary' + random_string + ext
    return temp_output

def work():
    while True:
        #print('getting task from queue')
        encoder = q.get()
        #print('got task: {0}'.format(encoder))
        if encoder is None:
            #print('in work(), stopping')
            q.task_done()
            break

        if not quitting:
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
        try:
            out = subprocess.check_output(['ffprobe', '-hide_banner', '-loglevel', 'error', '-threads', '1', '-show_streams', '-show_format', '-print_format', 'json', entry.path])
        except:
            return

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
            #if not 'size' in f:
            #    print('skipping track with no bitrate: {}'.format(entry.name))
            #    continue
            #size_string = f['size']

            try:
                duration = float(duration_string)
                #size = float(size_string)
                #print('st_size: {0}, st_blocks: {1}, st_blksize: {2}'.format(result.st_size, result.st_blocks, result.st_blksize))
            except ValueError:
                print('skipping track with unparseable fields: {}'.format(entry.name))
                continue
            total_duration += duration

            result = os.stat(entry.path)
            size = result.st_size
            if args.b > 0:
                size = math.ceil(size / args.b) * args.b
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
    transcode = (bitrate > args.c * 1000)
    if transcode:
        print('transcoding {} kb/s album: {}'.format(round(bitrate / 1e3), album_joined))
    else:
        print('    copying {} kb/s album: {}'.format(round(bitrate / 1e3), album_joined))

    dst_dir = os.path.join(args.dst, relative_dir)
    os.makedirs(dst_dir, exist_ok=True)

    for entry in audio_files:
        before_ext, ext = os.path.splitext(entry.name)
        if transcode:
            if args.f == 'mp3':
                filename = before_ext + '.mp3'
                output = os.path.join(dst_dir, filename)
                encoder = mp3_encoder(entry.path, output)
            elif args.f == 'vorbis':
                filename = before_ext + '.ogg'
                output = os.path.join(dst_dir, filename)
                encoder = vorbis_encoder(entry.path, output)
            elif args.f == 'aac':
                filename = before_ext + '.m4a'
                output = os.path.join(dst_dir, filename)
                encoder = aac_encoder(entry.path, output)
            elif args.f == 'opus':
                filename = before_ext + '.opus'
                output = os.path.join(dst_dir, filename)
                encoder = opus_encoder(entry.path, output)
            else:
                return
        else:
            output = os.path.join(dst_dir, entry.name)
            #temp_output = before_ext + '-temporary' + random_string + ext
            encoder = strip_encoder(entry.path, output)
        #send_conn.send(encoder)
        q.put(encoder)
        if quitting:
            #print('in process_album(), quitting early after {0}'.format(output))
            return

    for entry in art_files:
        before_ext, ext = os.path.splitext(entry.name)
        random_string = ''.join(random.choice(string.digits + string.ascii_letters) for i in range(16))
        output = os.path.join(dst_dir, entry.name)
        temp_output = os.path.splitext(output)[0] + '-temporary' + random_string + ext
        encoder = copy_encoder(entry.path, output)
        q.put(encoder)

def process_library():
    for s in args.src:
        process_album(s, s, '', q)
        for album_root, album_dirs, album_files in os.walk(s):
            for d in album_dirs:
                process_album(s, album_root, d, q)
                if quitting:
                    #print('in process_library(), quitting early after {0}'.format(d))
                    return

def exit_handler(signum, frame):
    global quitting
    quitting = True
    #print('in exit_handler(), quitting: {0}'.format(quitting))

global quitting
quitting = False
#stop_working = False
signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGTERM, exit_handler)
signal.signal(signal.SIGQUIT, exit_handler)

job_count = args.j
if not job_count > 0:
    job_count = os.cpu_count()
    if not job_count:
        job_count = 1

#poison_pill = None
q = queue.Queue(1)
for i in range(job_count):
    t = threading.Thread(target=work)
    t.start()

process_library()

for i in range(job_count):
    q.put(None)

q.join()

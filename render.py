"""
Builds a ~21 second vertical (720x1280) news-style video from a few images and three short lines.
Called by the GitHub Actions workflow; all inputs arrive as environment variables:
  INPUT_KEY     unique id for this video (output file name)
  INPUT_TITLE   headline
  INPUT_LINES   JSON list of 3 short lines
  INPUT_IMAGES  JSON list of image URLs (1 to 5)
  INPUT_LOOK    dramatic | glam | sports | mystery | breaking
  INPUT_CLIPS   (optional) JSON list of direct links to stock video clips; used for shots 2-5 instead of still images
Music (optional): INPUT_MUSIC = direct link to an mp3 (used if given), otherwise a random .mp3 from the repo's music/ folder.
Output: out/<key>.mp4
"""
import glob, json, os, random, re, subprocess, sys, textwrap, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H, FPS, XF = 720, 1280, 25, 0.5          # size, frame rate, cross-fade seconds
BIG_W, BIG_H = 1440, 2560                    # images are prepared at 2x so zooms stay sharp

LOOKS = {   # accent colour, ffmpeg colour grade, camera moves, transitions (ffmpeg xfade names)
    'dramatic': dict(accent='#ffd400', eq='eq=brightness=-0.10:contrast=1.15:saturation=1.05', zoom=['in', 'out', 'in', 'out', 'in'], tr=['fade', 'wipeleft', 'wiperight', 'fade', 'wipeleft']),
    'glam':     dict(accent='#ff5fc8', eq='eq=brightness=0.04:contrast=1.05:saturation=1.25',  zoom=['out', 'in', 'out', 'in', 'out'], tr=['fade', 'fade', 'wiperight', 'fade', 'wiperight']),
    'sports':   dict(accent='#39ff88', eq='eq=contrast=1.25:saturation=1.45',                  zoom=['in', 'out', 'in', 'out', 'in'], tr=['wipeleft', 'wiperight', 'wipeleft', 'wiperight', 'fade']),
    'mystery':  dict(accent='#ff3b3b', eq='hue=s=0,eq=brightness=-0.12:contrast=1.2',          zoom=['in', 'out', 'in', 'in', 'out'], tr=['fade', 'fade', 'fade', 'wipeleft', 'fade']),
    'breaking': dict(accent='#ff3b3b', eq='eq=contrast=1.3:saturation=1.1',                    zoom=['in', 'out', 'in', 'out', 'in'], tr=['wiperight', 'wipeleft', 'wiperight', 'wipeleft', 'fade']),
}

def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode:
        print(r.stdout[-3000:]); sys.exit('ffmpeg failed: ' + ' '.join(cmd[:6]))

def font(size):
    for name in ('Montserrat:bold', 'Montserrat', 'DejaVu Sans:bold'):
        p = subprocess.run(['fc-match', '-f', '%{file}', name], stdout=subprocess.PIPE, text=True).stdout
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def download(urls, folder):
    out = []
    for i, u in enumerate(urls):
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (video-render bot)'})
            data = urllib.request.urlopen(req, timeout=25).read()
            path = os.path.join(folder, 'src%d.bin' % i)
            open(path, 'wb').write(data)
            im = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
            if im.width < 300 or im.height < 300: continue
            out.append(ImageOps.fit(im, (BIG_W, BIG_H), Image.LANCZOS, centering=(0.5, 0.35)))
        except Exception as e:
            print('skipped image', u[:80], e)
    return out

def download_clips(urls, folder):
    out = []
    for i, u in enumerate(urls):
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (video-render bot)'})
            data = urllib.request.urlopen(req, timeout=60).read()
            if len(data) < 30000: continue
            path = os.path.join(folder, 'clip%d.mp4' % i)
            open(path, 'wb').write(data); out.append(path)
        except Exception as e:
            print('skipped clip', u[:80], e)
    return out

def text_overlay(text, size, color, where, path):
    """Transparent 720x1280 PNG: wrapped text on a soft dark panel so it stays readable on any photo."""
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    f = font(size)
    lines = []
    for chunk in textwrap.wrap(text, width=max(12, int(620 / (size * 0.58)))):
        lines.append(chunk)
    lh = int(size * 1.25); th = lh * len(lines)
    tw = max(d.textlength(l, font=f) for l in lines)
    cy = H // 2 if where == 'center' else int(H * 0.78)
    pad = 28
    box = (int((W - tw) / 2 - pad), int(cy - th / 2 - pad), int((W + tw) / 2 + pad), int(cy + th / 2 + pad))
    d.rounded_rectangle(box, radius=22, fill=(0, 0, 0, 150))
    y = cy - th / 2
    for l in lines:
        x = (W - d.textlength(l, font=f)) / 2
        d.text((x + 2, y + 2), l, font=f, fill=(0, 0, 0, 255))
        d.text((x, y), l, font=f, fill=color)
        y += lh
    img.save(path)

def main():
    key = os.environ['INPUT_KEY']; title = os.environ.get('INPUT_TITLE', '')
    lines = json.loads(os.environ.get('INPUT_LINES') or '[]')[:3]
    urls = json.loads(os.environ.get('INPUT_IMAGES') or '[]')[:5]
    look = LOOKS.get(os.environ.get('INPUT_LOOK', 'dramatic'), LOOKS['dramatic'])
    work = 'work'; os.makedirs(work, exist_ok=True); os.makedirs('out', exist_ok=True)

    imgs = download(urls, work)
    clips = download_clips(json.loads(os.environ.get('INPUT_CLIPS') or '[]')[:4], work)
    if not imgs and not clips: sys.exit('No usable images or clips could be downloaded.')
    if not imgs:   # clips only: use a frame from the first clip as the opening still
        run(['ffmpeg', '-y', '-i', clips[0], '-frames:v', '1', os.path.join(work, 'frame.jpg')])
        imgs = [ImageOps.fit(Image.open(os.path.join(work, 'frame.jpg')).convert('RGB'), (BIG_W, BIG_H), Image.LANCZOS)]

    short = title if len(title) <= 110 else re.sub(r'\s+\S*$', '', title[:107]) + '...'
    shots = [(short, 5, 50, look['accent'], 'center')] + [(l, 4, 44, '#ffffff', 'bottom') for l in lines] + [('FULL STORY IN THE COMMENTS', 3, 42, look['accent'], 'center')]

    segs = []
    for i, (txt, ln, size, color, where) in enumerate(shots):
        last = i == len(shots) - 1
        dur = ln + (0 if last else XF)                  # overlap with the next shot for the transition
        frames = int(dur * FPS)
        ov = os.path.join(work, 'txt%d.png' % i); text_overlay(txt, size, color, where, ov)
        out = os.path.join(work, 'seg%d.mp4' % i)
        tail = ("[1:v]format=rgba,fade=t=in:st=0.3:d=0.4:alpha=1[tx];[bg][tx]overlay=0:0:format=auto,format=yuv420p[v]")
        clip = clips[(i - 1) % len(clips)] if (clips and i >= 1) else None   # shot 1 stays a photo; the rest are moving clips
        if clip:
            fc = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,fps=%d,%s,vignette=PI/5[bg];" % (W, H, W, H, FPS, look['eq'])) + tail
            inp = ['-stream_loop', '-1', '-i', clip]
        else:
            base = os.path.join(work, 'img%d.jpg' % i); imgs[i % len(imgs)].save(base, quality=92)
            z = ("min(1+0.0011*on,1.28)" if look['zoom'][i % 5] == 'in' else "max(1.28-0.0011*on,1)")
            fc = ("[0:v]zoompan=z='%s':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=%d:s=%dx%d:fps=%d,%s,vignette=PI/5[bg];" % (z, frames, W, H, FPS, look['eq'])) + tail
            inp = ['-i', base]
        run(['ffmpeg', '-y'] + inp + ['-loop', '1', '-framerate', str(FPS), '-t', '%.2f' % dur, '-i', ov,
             '-filter_complex', fc, '-map', '[v]', '-frames:v', str(frames), '-r', str(FPS),
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', out])
        segs.append((out, ln))

    # chain the shots with cross-fades / wipes
    total = sum(ln for _, ln in segs)
    cmd = ['ffmpeg', '-y']
    for path, _ in segs: cmd += ['-i', path]
    parts, prev, acc = [], '[0:v]', 0.0
    for i in range(1, len(segs)):
        acc += segs[i - 1][1]
        tag = '[x%d]' % i if i < len(segs) - 1 else '[vout]'
        parts.append('%s[%d:v]xfade=transition=%s:duration=%s:offset=%s%s' % (prev, i, look['tr'][i % 5], XF, acc, tag))
        prev = tag
    cmd += ['-filter_complex', ';'.join(parts)]
    tracks = sorted(glob.glob('music/*.mp3') + glob.glob('music/*.m4a'))
    link = (os.environ.get('INPUT_MUSIC') or '').strip()
    if link:
        try:
            req = urllib.request.Request(link, headers={'User-Agent': 'Mozilla/5.0 (video-render bot)'})
            data = urllib.request.urlopen(req, timeout=40).read()
            if len(data) > 50000:
                open(os.path.join(work, 'music_dl.mp3'), 'wb').write(data); tracks = [os.path.join(work, 'music_dl.mp3')]
        except Exception as e:
            print('Could not download the music link, using the music/ folder instead:', e)
    final = os.path.join('out', key + '.mp4')
    if tracks:
        music = random.choice(tracks)
        cmd += ['-stream_loop', '-1', '-i', music, '-map', '[vout]', '-map', '%d:a' % len(segs),
                '-af', 'afade=t=in:d=1,afade=t=out:st=%s:d=1.5,volume=0.6' % (total - 1.5), '-c:a', 'aac', '-b:a', '128k']
    else:
        print('No music file found in music/, making a silent video.')
        cmd += ['-map', '[vout]']
    cmd += ['-t', str(total), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', final]
    run(cmd)
    print('Wrote', final, round(os.path.getsize(final) / 1e6, 2), 'MB')

if __name__ == '__main__':
    main()

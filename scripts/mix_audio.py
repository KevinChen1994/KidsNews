#!/usr/bin/env python3
"""Make a simple ducked voice + reusable music audition, using local ffmpeg."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--voice', required=True)
    p.add_argument('--music', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--music-db', type=float, default=-24)
    a = p.parse_args()
    out = Path(a.output)
    if out.exists():
        p.error('Output exists; choose a new filename')
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                     'format=duration', '-of', 'default=nw=1:nk=1', a.voice], text=True).strip())
    if not -60 <= a.music_db <= -6:
        p.error('music-db must be between -60 and -6')
    out.parent.mkdir(parents=True, exist_ok=True)
    graph = (
        '[0:a]aresample=44100,loudnorm=I=-18:TP=-2:LRA=7,asplit=2[v][sc];'
        f'[1:a]aresample=44100,volume={a.music_db}dB,'
        f'afade=t=in:d=1,afade=t=out:st={max(0,duration-3):.3f}:d=3[m];'
        '[m][sc]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=350[duck];'
        '[v][duck]amix=inputs=2:duration=first:normalize=0,'
        'loudnorm=I=-16:TP=-1.5:LRA=7[out]'
    )
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-i', a.voice,
                    '-stream_loop', '-1', '-i', a.music, '-filter_complex', graph,
                    '-map', '[out]', '-t', str(duration), '-ar', '44100', '-ac', '2',
                    '-c:a', 'libmp3lame', '-b:a', '192k', str(out)], check=True)
    out.with_suffix('.mix.json').write_text(json.dumps({
        'voice': str(Path(a.voice).resolve()), 'music': str(Path(a.music).resolve()),
        'music_db': a.music_db, 'voice_seconds': duration,
        'description': 'Simple continuous bed audition; editorial pauses and scene transitions need separate assembly.',
        'filter_graph': graph}, ensure_ascii=False, indent=2) + '\n')
    print(out.resolve())


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Assemble cached TTS with explicit pauses and short, non-looping music cues."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def duration(path):
    return float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=nw=1:nk=1', str(path)], text=True))


def normalized(text):
    return re.sub(r'\s+', '', text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    plan_path, output = Path(args.plan), Path(args.output)
    plan = json.loads(plan_path.read_text())
    bitrate = plan.get('output_bitrate', '192k')
    channels = plan.get('output_channels', 2)
    true_peak = float(plan.get('output_true_peak_db', -1.5))
    if bitrate not in ('40k', '48k', '64k', '96k', '128k', '192k') or channels not in (1, 2):
        parser.error('Unsupported output bitrate or channel count')
    if not -9 <= true_peak <= -1:
        parser.error('Output true peak target must be between -9 and -1 dBTP')
    voice = ROOT / plan['voice']
    metadata = json.loads(voice.with_suffix('.json').read_text())
    if metadata.get('status') != 'complete':
        parser.error('TTS must be complete before assembly')
    if output.exists() or output.with_suffix('.mix.json').exists():
        parser.error('Output already exists; inspect it or choose a new path')
    words = [word for sentence in metadata['result']['sentences']
             for word in sentence['words']]
    transcript, positions = '', []
    for word in words:
        chunk = normalized(word['word'])
        start = len(transcript)
        transcript += chunk
        positions.append((start, len(transcript), word['startTime'], word['endTime']))

    def anchor(text, edge):
        needle = normalized(text)
        offset = transcript.find(needle)
        if offset < 0 or transcript.find(needle, offset + 1) >= 0:
            raise ValueError(f'Anchor must match exactly once: {text}')
        target = offset if edge == 'start' else offset + len(needle) - 1
        return next(p[2 if edge == 'start' else 3]
                    for p in positions if p[0] <= target < p[1])

    voice_duration = duration(voice)
    leading = float(plan.get('leading_seconds', 0))
    tail = float(plan.get('tail_seconds', 0))
    pauses = sorted([{'at': anchor(p['after'], 'end'),
                      'seconds': float(p['seconds']), 'after': p['after']}
                     for p in plan.get('pauses', [])], key=lambda x: x['at'])
    if leading < 0 or tail < 0 or any(p['seconds'] <= 0 for p in pauses):
        parser.error('Invalid silence duration')
    if any(b['at'] - a['at'] < 0.02 for a, b in zip(pauses, pauses[1:])):
        parser.error('Pauses overlap')

    def timeline(source_time):
        return leading + source_time + sum(p['seconds'] for p in pauses
                                          if p['at'] <= source_time)

    total = timeline(voice_duration) + tail
    graph, parts = [], []

    def silence(seconds):
        label = f's{len(parts)}'
        graph.append(f'anullsrc=r=44100:cl=mono,atrim=duration={seconds:.6f}[{label}]')
        parts.append(f'[{label}]')

    if leading:
        silence(leading)
    previous = 0.0
    for end, pause_length in [(p['at'], p['seconds']) for p in pauses] + [(voice_duration, tail)]:
        label = f'v{len(parts)}'
        graph.append(f'[0:a]atrim=start={previous:.6f}:end={end:.6f},'
                     f'asetpts=PTS-STARTPTS,aresample=44100[{label}]')
        parts.append(f'[{label}]')
        if pause_length:
            silence(pause_length)
        previous = end
    graph.append(''.join(parts) + f'concat=n={len(parts)}:v=0:a=1,'
                 'loudnorm=I=-18:TP=-2:LRA=7[voice]')

    catalog = {t['id']: t for t in json.loads((ROOT / 'assets/music/catalog.json').read_text())['tracks']}
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n', '-i', str(voice)]
    music_labels, cues = [], []
    for index, cue in enumerate(plan.get('music', []), 1):
        track = catalog[cue['track_id']]
        if track.get('technical_validation') != 'decoded-successfully':
            parser.error(f'Music has not passed technical validation: {track["id"]}')
        path = ROOT / 'assets/music' / track['file']
        if 'at_seconds' in cue:
            start = float(cue['at_seconds'])
        elif 'before_voice_end' in cue:
            start = timeline(voice_duration) - float(cue['before_voice_end'])
        else:
            start = timeline(anchor(cue['at_text'], 'start'))
        length = float(cue['seconds'])
        db = float(cue['db'])
        if start < 0 or start + length > total + 0.05 or not -60 <= db <= -6:
            parser.error('Invalid music timing or level')
        if length > duration(path) + 0.05:
            parser.error('Cue exceeds source; music is never looped automatically')
        command += ['-i', str(path)]
        label = f'm{index}'
        fade = min(3, length / 3)
        graph.append(f'[{index}:a]atrim=duration={length:.6f},asetpts=PTS-STARTPTS,'
                     f'aresample=44100,volume={db}dB,afade=t=in:d=0.8,'
                     f'afade=t=out:st={length-fade:.6f}:d={fade:.6f},'
                     f'adelay={round(start*1000)}:all=1[{label}]')
        music_labels.append(f'[{label}]')
        cues.append(dict(cue, start_seconds=round(start, 3),
                         end_seconds=round(start + length, 3), file=str(path)))
    graph.append('[voice]' + ''.join(music_labels) +
                 f'amix=inputs={1+len(music_labels)}:duration=first:normalize=0,'
                 f'loudnorm=I=-16:TP={true_peak}:LRA=7[out]')
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_graph = ';'.join(graph)
    subprocess.run(command + ['-filter_complex', filter_graph, '-map', '[out]',
                             '-t', f'{total:.6f}', '-ar', '44100', '-ac', str(channels),
                             '-c:a', 'libmp3lame', '-b:a', bitrate, str(output)], check=True)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(output),
                    '-f', 'null', '-'], check=True)
    record = {'voice': str(voice), 'voice_sha256': hashlib.sha256(voice.read_bytes()).hexdigest(),
              'plan': str(plan_path.resolve()), 'pauses': pauses, 'music_cues': cues,
              'voice_seconds': voice_duration, 'output_seconds': duration(output),
              'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'output_bitrate': bitrate, 'output_channels': channels,
              'output_true_peak_db': true_peak,
              'review_status': '已通过', 'approval_mode': 'automatic-after-technical-checks',
              'human_listening_performed': False, 'technical_validation': 'decoded-successfully',
              'filter_graph': filter_graph}
    output.with_suffix('.mix.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output.resolve()), 'seconds': record['output_seconds'],
                      'review_status': record['review_status']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

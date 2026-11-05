#!/usr/bin/env python3
"""Validate local music files and rebuild the reusable library index, offline."""
from collections import Counter
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MUSIC = ROOT / 'assets/music'


def main():
    catalog_path = MUSIC / 'catalog.json'
    catalog = json.loads(catalog_path.read_text())
    previous = {t['id']: t for t in catalog['tracks']}
    additions = {}
    for manifest in sorted(MUSIC.glob('library-*.json')):
        if manifest.name.endswith('.results.json'):
            continue
        plan = json.loads(manifest.read_text())
        additions.update({t['id']: t for t in plan.get('tracks', [])})
    tracks = []
    for path in sorted(MUSIC.glob('*.mp3')):
        ident = path.stem
        old = previous.get(ident, {})
        intended = additions.get(ident, {})
        meta = json.loads(path.with_suffix('.json').read_text())
        if meta['status'] != 'complete':
            raise RuntimeError(f'Incomplete metadata: {ident}')
        info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                         'format=duration:stream=codec_name,sample_rate,channels', '-of', 'json', str(path)], text=True))
        duration = float(info['format']['duration'])
        expected = meta['request']['music_length_ms'] / 1000
        if abs(duration - expected) > 1:
            raise RuntimeError(f'Unexpected duration: {ident}')
        subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-i', str(path), '-f', 'null', '-'], check=True)
        role = intended.get('role', old.get('role'))
        if not role:
            raise RuntimeError(f'Missing role: {ident}')
        track = dict(old, id=ident, role=role, title=intended.get('title', old.get('title', ident)),
                     file=path.name, metadata=path.with_suffix('.json').name,
                     duration_seconds=duration, model=meta['request']['model_id'],
                     review=old.get('review', 'pending-listening'),
                     technical_validation='decoded-successfully',
                     loop_review='not-verified',
                     usage='signature' if role in ['开场','收尾'] else ('transition' if role == '转场' else 'background-bed'))
        tracks.append(track)
    catalog.update(tracks=tracks, total_tracks=len(tracks), total_seconds=sum(t['duration_seconds'] for t in tracks),
                   generation_mode='reuse-only', role_counts=dict(Counter(t['role'] for t in tracks)),
                   review_note='完整解码及目标时长检查通过；review逐曲记录用户认可/待听审状态，无缝循环接点另行验收；提示词见各曲目同名JSON。')
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n')
    lines=['# 可复用音乐库', '', f"共 {len(tracks)} 段，约 {catalog['total_seconds']/60:.1f} 分钟。一次性建库完成；每天只选库存，不再自动生成。", '',
           '音频已通过解码和目标时长检查。前25段用户已认可，新曲仍待听审，状态见目录。以下中文曲名和用途描述来自生成意图。', '',
           '## 怎么用', '',
           '- 片头固定使用 01-opening（最初的温暖钢琴与马林巴），片尾按需选择。转场每期少量使用。',
           '- 主底乐按叙事情绪选，避免连续几期用同一首；优先避开最近3期的主底乐，记录在每期 production.md。不要把音乐风格绑定到固定新闻领域。',
           '- 一期通常选1–3段底乐即可，讲关键解释、等待回答和需要专注时留白，不要求铺满十分钟。',
           '- 60–90秒底乐可以按段落截取。确需延长时做交叉淡化并听接点；当前曲目未验收为无缝循环，不能直接硬拼后宣称自然。',
           '- 缺合适配乐时留白或报告缺口，不自动请求新音乐。用户以后明确要求扩充，才修改 config/music-library.json。',
           '- 同时改变乐器、段落位置与音乐密度，比单纯堆曲目更能减少重复感；保持人声清楚。', '']
    for role in ['开场','好奇','轻快','安静','思考','叙事','转场','收尾']:
        lines.extend([f'## {role}', '', '| 曲目 | 时长 | 试听 |', '|---|---:|---|'])
        for t in tracks:
            if t['role'] == role:
                lines.append(f"| {t['title']} | {t['duration_seconds']:.0f}秒 | [{t['id']}]({t['file']}) |")
        lines.append('')
    lines.extend(['## 制作数据', '', '[机器可读目录](catalog.json)保存角色、时长、听审状态。各MP3同名JSON保存原提示词、模型、状态和生成ID；保留原始文件，剪辑另存。', ''])
    (MUSIC / 'library.md').write_text('\n'.join(lines))
    print(json.dumps({'tracks':len(tracks),'minutes':round(catalog['total_seconds']/60,2),'roles':catalog['role_counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

"""Offline checks for private transcript output and paid-request boundaries."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audio
from prepare_script import load_profile, prepare


class PrepareScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'config').mkdir()
        example = Path(__file__).resolve().parents[1] / 'config/local.example.json'
        (self.root / 'config/local.example.json').write_bytes(example.read_bytes())
        self.template = self.root / 'template.txt'
        self.template.write_text('{{listener_name}}，欢迎来到{{program_name}}。', encoding='utf-8')

    def test_generic_defaults_without_personal_configuration(self):
        output = self.root / 'samples/demo.txt'
        prepare(self.template, output, self.root)
        self.assertEqual(output.read_text(encoding='utf-8'), '小朋友，欢迎来到世界小报。')

    def test_personal_overrides_render_only_to_private_output(self):
        overrides = {'listener_name': '测试称呼', 'delivery': {'baidu_share_url': 'local-only'}}
        (self.root / 'config/local.json').write_text(json.dumps(overrides), encoding='utf-8')
        profile = load_profile(self.root)
        self.assertEqual(profile['delivery']['notion_database_id'], '')
        output = self.root / 'episodes/2099-01-01/script.txt'
        prepare(self.template, output, self.root)
        self.assertIn('测试称呼', output.read_text(encoding='utf-8'))
        self.assertNotIn('测试称呼', self.template.read_text(encoding='utf-8'))

    def test_existing_transcript_is_never_overwritten(self):
        output = self.root / 'samples/demo.txt'
        prepare(self.template, output, self.root)
        previous = output.read_bytes()
        with self.assertRaises(FileExistsError):
            prepare(self.template, output, self.root)
        self.assertEqual(output.read_bytes(), previous)

    def test_output_cannot_enter_public_folders(self):
        for destination in ('README.md', 'config/output.txt', 'samples/../public.txt'):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                prepare(self.template, self.root / destination, self.root)

    def test_output_symlink_cannot_escape_private_folders(self):
        (self.root / 'samples').symlink_to(self.root / 'config', target_is_directory=True)
        with self.assertRaises(ValueError):
            prepare(self.template, self.root / 'samples/output.txt', self.root)

    def test_unknown_or_malformed_tokens_fail_before_writing(self):
        for token in ('{{delivery}}', '{{unknown}}', '{{bad-token}}', '{{listener_name'):
            self.template.write_text(token, encoding='utf-8')
            output = self.root / 'samples/demo.txt'
            with self.subTest(token=token), self.assertRaises(ValueError):
                prepare(self.template, output, self.root)
            self.assertFalse(output.exists())

    def test_invalid_personal_configuration_fails(self):
        for overrides in ([], {'listener_name': None}, {'interests': 'invalid'}, {'delivery': None}):
            (self.root / 'config/local.json').write_text(json.dumps(overrides), encoding='utf-8')
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                load_profile(self.root)

    def test_unrendered_text_never_reaches_provider(self):
        args = SimpleNamespace(kind='tts', speaker=None, text_file=str(self.template),
                               output=str(self.root / 'samples/demo.mp3'))
        with patch.object(audio, 'volc_headers') as headers, patch.object(audio, 'post_json') as submit:
            with self.assertRaisesRegex(RuntimeError, 'prepare_script.py'):
                audio.generate(args)
        headers.assert_not_called()
        submit.assert_not_called()
        self.assertFalse((self.root / 'samples').exists())


if __name__ == '__main__':
    unittest.main()

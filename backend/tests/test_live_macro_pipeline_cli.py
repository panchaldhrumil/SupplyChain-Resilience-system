import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'live_macro_pipeline.py'

spec = importlib.util.spec_from_file_location('live_macro_pipeline', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_default_dates_are_applied_when_not_provided(monkeypatch):
    captured = {}

    def fake_parse_args(self, args=None, namespace=None):
        captured['args'] = args
        return type('Args', (), {
            'output': 'out',
            'from_date': '2024-01-01',
            'to_date': '2024-01-02',
            'no_enrich': False,
            'max_items_per_query': 20,
            'keep_previews': False,
            'no_db': False,
            'llm_classify': False,
        })()

    monkeypatch.setattr(module.argparse.ArgumentParser, 'parse_args', fake_parse_args)
    parsed = module.build_arg_parser().parse_args([])
    assert parsed.from_date == '2024-01-01'
    assert parsed.to_date == '2024-01-02'

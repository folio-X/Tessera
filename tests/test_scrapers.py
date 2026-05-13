"""Tests for scrapers (parse only — no live network)."""

from __future__ import annotations

from tessera.scrapers.anthropic import AnthropicScraper
from tessera.scrapers.openai import OpenAIScraper


def test_openai_parses_target_models_from_table() -> None:
    raw = """
    <html><body>
      <table>
        <tr><td>GPT-5</td><td>Input</td><td>$1.25</td><td>Output</td><td>$10.00</td></tr>
        <tr><td>GPT-5 mini</td><td>Input</td><td>$0.25</td><td>Output</td><td>$2.00</td></tr>
        <tr><td>Some other model</td><td>$99.00</td><td>$99.00</td></tr>
      </table>
    </body></html>
    """
    scraper = OpenAIScraper()
    prices = scraper.parse(raw)
    by_id = {p.model_id: p for p in prices}
    assert "openai-gpt-5" in by_id
    assert by_id["openai-gpt-5"].input_per_million == 1.25
    assert by_id["openai-gpt-5"].output_per_million == 10.0
    assert "openai-gpt-5-mini" in by_id


def test_anthropic_parses_opus_and_haiku() -> None:
    raw = """
    <html><body>
      <table>
        <tr><th>Model</th><th>Input</th><th>Output</th></tr>
        <tr><td>Claude Opus 4.7</td><td>$15</td><td>$75</td></tr>
        <tr><td>Claude Haiku 4.5</td><td>$1</td><td>$5</td></tr>
      </table>
    </body></html>
    """
    scraper = AnthropicScraper()
    prices = scraper.parse(raw)
    by_id = {p.model_id: p for p in prices}
    assert by_id["anthropic-claude-opus-4-7"].input_per_million == 15.0
    assert by_id["anthropic-claude-opus-4-7"].output_per_million == 75.0
    assert by_id["anthropic-claude-haiku-4-5"].input_per_million == 1.0
    assert by_id["anthropic-claude-haiku-4-5"].output_per_million == 5.0


def test_openai_empty_html_returns_empty_list() -> None:
    scraper = OpenAIScraper()
    assert scraper.parse("<html></html>") == []


def test_openai_never_invents_a_price() -> None:
    """If the table doesn't contain our model, parse must return [], not guess."""
    scraper = OpenAIScraper()
    raw = """
    <html><body>
      <table>
        <tr><td>Some Model That Is Not GPT-5</td><td>$1.00</td><td>$2.00</td></tr>
      </table>
    </body></html>
    """
    assert scraper.parse(raw) == []

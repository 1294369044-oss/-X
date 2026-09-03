import unittest
from datetime import datetime, timezone

from crawler.ai_intelligence import _same_event, calculate_importance, parse_feed


class AIIntelligenceRulesTest(unittest.TestCase):
    def test_rss_is_normalized_to_ai_schema(self):
        payload = b"""<?xml version="1.0"?><rss><channel><item>
          <title>Introducing GPT-9</title>
          <link>https://openai.com/news/gpt-9</link>
          <description>A new model.</description>
          <pubDate>Thu, 03 Sep 2026 08:00:00 GMT</pubDate>
        </item></channel></rss>"""
        source = {
            "name": "OpenAI 官方博客",
            "company": "OpenAI",
            "source_level": "official",
        }
        items = parse_feed(payload, source, datetime(2026, 9, 3, tzinfo=timezone.utc))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "ai")
        self.assertEqual(items[0]["company"], "OpenAI")
        self.assertEqual(items[0]["source_level"], "official")

    def test_explicitly_unconfirmed_media_item_is_rumor(self):
        payload = b"""<?xml version="1.0"?><rss><channel><item>
          <title>OpenAI project remains unconfirmed</title>
          <link>https://example.com/unconfirmed-openai-project</link>
          <description>No official confirmation.</description>
          <pubDate>Thu, 03 Sep 2026 08:00:00 GMT</pubDate>
        </item></channel></rss>"""
        source = {"name": "可靠媒体", "source_level": "reliable"}
        items = parse_feed(payload, source, datetime(2026, 9, 3, tzinfo=timezone.utc))
        self.assertEqual(items[0]["source_level"], "rumor")

    def test_clickbait_penalty_does_not_delete_item(self):
        normal = {
            "title": "Introducing GPT-9",
            "summary": "A new model",
            "source": "OpenAI",
            "source_level": "official",
        }
        clickbait = {**normal, "title": "震惊 Introducing GPT-9"}
        self.assertEqual(calculate_importance(normal) - calculate_importance(clickbait), 15)
        self.assertGreater(calculate_importance(clickbait), 0)

    def test_same_version_with_close_time_is_one_event(self):
        official = {
            "title": "Introducing GPT-9",
            "url": "https://openai.com/news/gpt-9",
            "company": "OpenAI",
            "published_at": "2026-09-03T08:00:00+00:00",
        }
        report = {
            "title": "OpenAI launches GPT-9 for developers",
            "url": "https://example.com/openai-gpt-9",
            "company": "OpenAI",
            "published_at": "2026-09-03T09:00:00+00:00",
        }
        self.assertTrue(_same_event(official, report))


if __name__ == "__main__":
    unittest.main()

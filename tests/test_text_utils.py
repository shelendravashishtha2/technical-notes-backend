from app.utils.text import parse_markdown_sections, slugify


def test_slugify():
    assert slugify("AWS S3 Buckets") == "aws-s3-buckets"


def test_parse_sections():
    sections = parse_markdown_sections("# Title\n\nIntro\n\n## Child\n\nBody")
    assert len(sections) == 2
    assert sections[0].title == "Title"
    assert sections[1].title == "Child"
    assert sections[1].parent_order_index == 0

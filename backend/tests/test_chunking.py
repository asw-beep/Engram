from app.ingestion.chunking import chunk_document
from app.ingestion.types import ParsedDocument, ParsedSection


def words(text):
    return len(text.split())


def section(text, heading="A", start_line=1):
    return ParsedSection((heading,), text, start_line, start_line + text.count("\n"), None, None)


def doc_of(text, start_line=1):
    return ParsedDocument([section(text, start_line=start_line)])


def two_sections(first, second):
    return ParsedDocument([section(first, "A", 1), section(second, "B", 3)])


def paragraphs(count, words_each):
    return "\n\n".join(" ".join(f"p{p}w{w}" for w in range(words_each)) for p in range(count))


def numbered_words(count):
    return " ".join(f"w{i}" for i in range(count))


def lines_of_words(line_count, words_each):
    return "\n".join(
        " ".join(f"l{line}w{w}" for w in range(words_each)) for line in range(line_count)
    )


def test_short_section_stays_one_chunk():
    chunks = chunk_document(doc_of("one two three"), words, 512, 50)
    assert [c.content for c in chunks] == ["one two three"]


def test_long_section_splits_on_paragraphs_within_limit():
    chunks = chunk_document(doc_of(paragraphs(3, words_each=300)), words, 512, 50)
    assert len(chunks) > 1 and all(c.token_count <= 512 for c in chunks)


def test_long_section_breaks_between_paragraphs_rather_than_inside_one():
    text = paragraphs(3, words_each=300)
    chunks = chunk_document(doc_of(text), words, 512, 50)
    assert chunks[0].content == text.split("\n\n")[0]


def test_single_long_paragraph_splits_on_whitespace():
    chunks = chunk_document(doc_of(" ".join(["w"] * 1500)), words, 512, 50)
    assert all(c.token_count <= 512 for c in chunks)


def test_overlap_only_between_pieces_of_one_section():
    chunks = chunk_document(doc_of(numbered_words(700)), words, 512, 50)
    assert chunks[1].content.split()[:50] == chunks[0].content.split()[-50:]
    separate = chunk_document(two_sections("a b", "c d"), words, 512, 50)
    assert separate[1].content == "c d"


def test_positions_run_from_zero():
    chunks = chunk_document(doc_of(numbered_words(1500)), words, 512, 50)
    assert [c.position for c in chunks] == list(range(len(chunks)))


def test_positions_continue_across_sections():
    chunks = chunk_document(two_sections("a b", "c d"), words, 512, 50)
    assert [(c.position, c.heading_path) for c in chunks] == [(0, ("A",)), (1, ("B",))]


def test_split_pieces_report_their_own_line_ranges():
    chunks = chunk_document(doc_of(lines_of_words(100, 20), start_line=10), words, 512, 50)
    assert chunks[0].start_line == 10
    assert chunks[1].start_line > chunks[0].start_line
    assert chunks[-1].end_line == 109

"""Build tier-appropriate lexicons for phases 3-6 from public-domain source texts.

`extract_lexicon.py` (the existing single-book pipeline) depends on
`spacy`'s `en_core_web_trf` transformer model plus a CUDA-preferring torch
install -- too heavy to pull down just to fill in four word lists. This
script does the same job (extract nouns/verbs/adjectives from a source
text) with `nltk`'s lightweight averaged-perceptron POS tagger instead,
which is a few tens of MB, not a few hundred, and runs fine on CPU.

Source texts are real public-domain books, chosen to match each phase's
`dominant_grades` in phases.yaml, downloaded once into
`data_handling/process_books/input/` (same convention as
`anneofgreengables.txt`, which already lives there for phase 0):

    phase 3 (grades 6-8)   -> The Adventures of Tom Sawyer, Mark Twain (Gutenberg #74)
    phase 4 (grades 9-10)  -> Pride and Prejudice, Jane Austen (Gutenberg #1342)
    phase 5 (grade 11)     -> Moby-Dick, Herman Melville (Gutenberg #2701)
    phase 6 (grade 12)     -> On Liberty, John Stuart Mill (Gutenberg #34901)

No word is invented: every entry in every output lexicon is a lemma that
actually occurred at least MIN_COUNT times in its source book, so the
provenance of each phase's vocabulary is a specific, named, human-authored
text, not a guess from a language model.

CROSS-BOOK FILTER (2026-09-22, lead-approved): a word is kept in a phase's
final lexicon only if it ALSO occurs in at least one of the other three
source books' raw extractions. This is a narrow cut aimed at single-book
domain jargon -- "whaleman", "leviathan", "astern" (Moby-Dick, phase 5)
used in a modern-topic story -- not a push toward shared vocabulary in
general: it drops 3-12% of each phase's candidates (see the pairwise
overlap table recorded in docs/DECISIONS.md), and the resulting overlap
between the rebuilt phases stays in the same 20-50% band as before
filtering, well short of the 70-90% band that made the pre-rebuild
lexicons useless. Applied before the top-N frequency cap, not after --
otherwise a low-frequency single-book word could still occupy a slot
that should have gone to a cross-book-present one.

Usage:
    python build_phase_lexicons.py
Writes:
    data_handling/process_books/output/{book}_lexicon.json   (raw, per book, UNFILTERED)
    ../../config/lexicons/phase_{3,4,5,6}.json                (final, filtered + capped + sorted)
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

HERE = Path(__file__).resolve().parent
INPUT_DIR = HERE / "input"
OUTPUT_DIR = HERE / "output"
LEXICON_DIR = HERE.parents[1] / "config" / "lexicons"

# (book filename, output stem, phase id, max words per category)
BOOKS = [
    ("tomsawyer.txt", "tomsawyer", 3, 400),
    ("prideandprejudice.txt", "prideandprejudice", 4, 400),
    ("mobydick.txt", "mobydick", 5, 400),
    ("onliberty.txt", "onliberty", 6, 400),
]

MIN_COUNT = 2  # drop hapax legomena / OCR noise; keep only words seen >=2 times

GUTENBERG_START_RE = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE | re.DOTALL)
GUTENBERG_END_RE = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK", re.IGNORECASE)

# Penn Treebank tags -> our three buckets, and the wordnet POS
# WordNetLemmatizer needs to lemmatize each bucket correctly.
# Nouns are matched exactly (NN, NNS) and NOT by prefix, so proper nouns
# (NNP, NNPS -- character names, place names) are excluded, matching what
# spacy's NOUN-vs-PROPN split already gave phase 0's lexicon.
EXACT_TAG_BUCKETS = {
    "NN": ("nouns", "n"),
    "NNS": ("nouns", "n"),
}
PREFIX_TAG_BUCKETS = {
    "VB": ("verbs", "v"),
    "JJ": ("adjectives", "a"),
}


def strip_gutenberg_boilerplate(text: str) -> str:
    start_match = GUTENBERG_START_RE.search(text)
    end_match = GUTENBERG_END_RE.search(text)
    start = start_match.end() if start_match else 0
    end = end_match.start() if end_match else len(text)
    return text[start:end]


def extract_pos(text: str, lemmatizer: WordNetLemmatizer, stop_words: set[str]) -> dict[str, Counter]:
    """Tokenize, POS-tag and lemmatize; return a Counter per bucket."""
    counters = {"nouns": Counter(), "verbs": Counter(), "adjectives": Counter()}

    for sentence in nltk.sent_tokenize(text):
        tokens = nltk.word_tokenize(sentence)
        tagged = nltk.pos_tag(tokens)
        for word, tag in tagged:
            bucket = EXACT_TAG_BUCKETS.get(tag)
            if bucket is None:
                for prefix, (bucket_name, wn_pos) in PREFIX_TAG_BUCKETS.items():
                    if tag.startswith(prefix):
                        bucket = (bucket_name, wn_pos)
                        break
            if bucket is None:
                continue

            lower = word.lower()
            if not lower.isalpha() or len(lower) < 2:
                continue
            if lower in stop_words:
                continue

            bucket_name, wn_pos = bucket
            lemma = lemmatizer.lemmatize(lower, pos=wn_pos)
            counters[bucket_name][lemma] += 1

    return counters


def cap_and_sort(counter: Counter, max_words: int) -> list[str]:
    """Deterministic top-N: frequency descending, alphabetical tie-break."""
    kept = [word for word, count in counter.items() if count >= MIN_COUNT]
    kept.sort(key=lambda w: (-counter[w], w))
    return kept[:max_words]


def cross_book_filter(counter: Counter, other_books_words: set[str]) -> Counter:
    """Keep only words that also occur (any part of speech) in at least one
    of the OTHER source books -- drops single-book domain jargon."""
    return Counter({word: count for word, count in counter.items() if word in other_books_words})


def main() -> None:
    nltk.download("punkt_tab", quiet=True)
    nltk.download("averaged_perceptron_tagger_eng", quiet=True)
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)
    nltk.download("stopwords", quiet=True)

    lemmatizer = WordNetLemmatizer()
    stop_words = set(stopwords.words("english"))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LEXICON_DIR.mkdir(parents=True, exist_ok=True)

    # Pass 1: extract every book's raw counters (unfiltered) first, so the
    # cross-book filter in pass 2 can see all four books at once.
    book_counters: dict[str, dict[str, Counter]] = {}
    for book_filename, stem, phase_id, max_words in BOOKS:
        book_path = INPUT_DIR / book_filename
        raw_text = book_path.read_text(encoding="utf-8")
        clean_text = strip_gutenberg_boilerplate(raw_text)

        counters = extract_pos(clean_text, lemmatizer, stop_words)
        book_counters[stem] = counters

        raw_output = {name: sorted(counter.keys()) for name, counter in counters.items()}
        raw_path = OUTPUT_DIR / f"{stem}_lexicon.json"
        with raw_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(raw_output, f, ensure_ascii=False, indent=4)

    all_words_by_book = {
        stem: {word for counter in counters.values() for word in counter} for stem, counters in book_counters.items()
    }

    # Pass 2: cross-book filter, then cap + write each phase's final lexicon.
    for book_filename, stem, phase_id, max_words in BOOKS:
        other_books_words: set[str] = set()
        for other_stem, words in all_words_by_book.items():
            if other_stem != stem:
                other_books_words |= words

        counters = book_counters[stem]
        filtered = {name: cross_book_filter(counter, other_books_words) for name, counter in counters.items()}
        final = {name: cap_and_sort(counter, max_words) for name, counter in filtered.items()}

        phase_path = LEXICON_DIR / f"phase_{phase_id}.json"
        with phase_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(final, f, ensure_ascii=False, indent=4)

        sizes = {name: len(words) for name, words in final.items()}
        dropped = {name: len(counters[name]) - len(filtered[name]) for name in counters}
        print(f"phase {phase_id} ({stem}): kept {sizes}, dropped by cross-book filter {dropped} -> {phase_path}")


if __name__ == "__main__":
    main()

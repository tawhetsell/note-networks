//! Tokenization + stopword filtering — port of the Python `tokens()` function.
//!
//! Rules (must match build_graph.py):
//!   1. Strip YAML frontmatter before tokenizing
//!   2. Lowercase
//!   3. Replace any non-word/non-whitespace character with a space
//!   4. Split on whitespace
//!   5. Drop tokens that are in the stopword set, ≤ 3 chars, or all digits

use crate::frontmatter::strip as strip_frontmatter;
use once_cell::sync::Lazy;
use regex::Regex;
use std::collections::HashSet;

/// Core English stopwords — verbatim from build_graph.py `_STOP_CORE`.
const STOP_CORE: &str = "\
a an the and or but if then so of in on at by for with to from as \
is are was were be been being have has had do does did this that \
these those i you he she it we they them my your his her its our \
their what which who when where why how not no yes into about more \
also such one two three all any some can will would could should \
may might must shall s t";

/// Dialogue + informal-prose noise — verbatim from build_graph.py `_STOP_EXTRA`.
const STOP_EXTRA: &str = "\
yeah okay right like just well gonna want know said say get got \
go come back see think look let now even still only really quite \
very much more most least less than between among upon whether \
though although however therefore thus hence perhaps indeed \
shall must ought need seem become made make take give keep \
us them who whom whose mr mrs dr sir";

pub static STOPWORDS: Lazy<HashSet<&'static str>> = Lazy::new(|| {
    STOP_CORE
        .split_whitespace()
        .chain(STOP_EXTRA.split_whitespace())
        .collect()
});

/// `[^\w\s]` — matches any character that is neither a word char nor whitespace.
/// Replaced with a space before splitting (same behaviour as the Python `re.sub`).
static PUNCT_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"[^\w\s]").expect("punct regex"));

/// Tokenize a note body for graph building.
/// Frontmatter is stripped before tokenization.
pub fn tokenize(text: &str) -> Vec<String> {
    let body    = strip_frontmatter(text);
    let lower   = body.to_lowercase();
    let cleaned = PUNCT_RE.replace_all(&lower, " ");
    cleaned
        .split_whitespace()
        .filter(|t| keep(t))
        .map(|t| t.to_string())
        .collect()
}

fn keep(t: &str) -> bool {
    // > 3 chars, not a stopword, not purely numeric
    t.chars().count() > 3
        && !STOPWORDS.contains(t)
        && !t.chars().all(|c| c.is_ascii_digit())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_frontmatter_first() {
        let text   = "---\nid: x\ntags: [a]\n---\n\nThe philosophers wrote.";
        let toks   = tokenize(text);
        // "the" filtered by stopwords; "philosophers" + "wrote" kept; frontmatter ignored
        assert!(toks.contains(&"philosophers".to_string()));
        assert!(toks.contains(&"wrote".to_string()));
        assert!(!toks.contains(&"tags".to_string()));
        assert!(!toks.contains(&"id".to_string()));
    }

    #[test]
    fn filters_short_tokens() {
        let toks = tokenize("a an the of is at by");
        assert!(toks.is_empty());
    }

    #[test]
    fn filters_pure_digits() {
        let toks = tokenize("Year 2026 brought changes.");
        assert!(!toks.contains(&"2026".to_string()));
        assert!(toks.contains(&"year".to_string()));
        assert!(toks.contains(&"brought".to_string()));
        assert!(toks.contains(&"changes".to_string()));
    }

    #[test]
    fn lowercases_and_strips_punctuation() {
        let toks = tokenize("Hello, World!  These—are—words.");
        assert!(toks.contains(&"hello".to_string()));
        assert!(toks.contains(&"world".to_string()));
        assert!(toks.contains(&"words".to_string()));
    }
}

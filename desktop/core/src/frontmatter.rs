//! YAML frontmatter parser — sufficient for the simple schema used by
//! note-networks notes and Obsidian-style markdown.  Not a full YAML parser.
//!
//! Handles:
//!   - `key: value`           (string)
//!   - `key: "quoted value"`  (quotes stripped)
//!   - `key: 42`              (integer — coerced to string in the map)
//!   - `key: [a, b, c]`       (inline list)
//!   - `key:` + `- item` lines on subsequent lines (multi-line list, Obsidian style)

use once_cell::sync::Lazy;
use regex::Regex;
use std::collections::HashMap;

/// `^---\n.*?\n---\n` with DOTALL semantics, tolerating CRLF line endings.
/// Python's text mode strips `\r` on read; Rust does not, so we accept either.
static FM_RE: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(?s)^---\r?\n(.*?)\r?\n---\r?\n").expect("frontmatter regex"));

/// A frontmatter value is either a single string or a list of strings.
/// Integers are stringified — the consumer (graph builder) parses them.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Str(String),
    List(Vec<String>),
}

impl Value {
    pub fn as_str(&self) -> Option<&str> {
        if let Value::Str(s) = self { Some(s) } else { None }
    }
    pub fn as_list(&self) -> Option<&[String]> {
        if let Value::List(v) = self { Some(v) } else { None }
    }
    pub fn as_usize(&self) -> Option<usize> {
        self.as_str().and_then(|s| s.parse().ok())
    }
}

pub type Frontmatter = HashMap<String, Value>;

/// Strip the leading `---\n…\n---\n` block from a note's raw text, leaving the body.
/// If no frontmatter is present, returns the original text unchanged.
pub fn strip(text: &str) -> &str {
    if let Some(m) = FM_RE.find(text) {
        &text[m.end()..]
    } else {
        text
    }
}

/// Parse the frontmatter block.  Returns an empty map if no frontmatter is present.
pub fn parse(text: &str) -> Frontmatter {
    let mut out = Frontmatter::new();
    let Some(caps) = FM_RE.captures(text) else {
        return out;
    };
    let block = caps.get(1).map(|m| m.as_str()).unwrap_or("");

    // current_key tracks the most recently seen `key:` that had an empty value,
    // so the following `- item` lines get attached to it as a list.
    let mut current_key: Option<String> = None;

    for line in block.lines() {
        let stripped = line.trim();

        // Multi-line list item (e.g. Obsidian's "  - tag")
        if let Some(rest) = stripped.strip_prefix("- ") {
            if let Some(key) = &current_key {
                let item = strip_quotes(rest.trim());
                match out.get_mut(key) {
                    Some(Value::List(list)) => list.push(item),
                    _                       => { out.insert(key.clone(), Value::List(vec![item])); }
                }
            }
            continue;
        }

        // Reset the multi-line-list pointer if we see anything that isn't a list item
        current_key = None;

        let Some(colon) = line.find(':') else {
            continue;
        };
        let key = line[..colon].trim().to_string();
        let val = line[colon + 1..].trim();
        let val = strip_quotes(val);

        if val.starts_with('[') && val.ends_with(']') {
            // Inline list: [a, b, c]
            let inner = &val[1..val.len() - 1];
            let list: Vec<String> = inner
                .split(',')
                .map(|s| strip_quotes(s.trim()))
                .filter(|s| !s.is_empty())
                .collect();
            out.insert(key, Value::List(list));
        } else if val.is_empty() {
            // Open a multi-line list; subsequent `- item` lines will populate it
            out.insert(key.clone(), Value::List(Vec::new()));
            current_key = Some(key);
        } else {
            out.insert(key, Value::Str(val));
        }
    }
    out
}

/// Trim a single layer of matching surrounding quotes (either kind).
fn strip_quotes(s: &str) -> String {
    let s = s.trim();
    if (s.starts_with('"') && s.ends_with('"') && s.len() >= 2)
        || (s.starts_with('\'') && s.ends_with('\'') && s.len() >= 2)
    {
        s[1..s.len() - 1].to_string()
    } else {
        s.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_frontmatter_returns_empty() {
        assert!(parse("Just a body, no frontmatter.").is_empty());
    }

    #[test]
    fn strip_with_no_frontmatter_returns_original() {
        let body = "Hello world.";
        assert_eq!(strip(body), body);
    }

    #[test]
    fn inline_list_parses() {
        let text = "---\ntags: [a, b, c]\n---\n\nBody";
        let fm   = parse(text);
        assert_eq!(fm["tags"].as_list().unwrap(), &["a", "b", "c"]);
    }

    #[test]
    fn multiline_list_parses_obsidian_style() {
        let text = "---\ntags:\n  - philosophy\n  - stoic\nspeaker: ME\n---\n\nBody";
        let fm   = parse(text);
        assert_eq!(fm["tags"].as_list().unwrap(), &["philosophy", "stoic"]);
        assert_eq!(fm["speaker"].as_str().unwrap(), "ME");
    }

    #[test]
    fn quoted_strings_strip_quotes() {
        let text = "---\nsource: \"Meditations IV.3\"\n---\n\nBody";
        let fm   = parse(text);
        assert_eq!(fm["source"].as_str().unwrap(), "Meditations IV.3");
    }

    #[test]
    fn integer_field_round_trips_via_as_usize() {
        let text = "---\nword_count: 710\n---\n\nBody";
        let fm   = parse(text);
        assert_eq!(fm["word_count"].as_usize().unwrap(), 710);
    }

    #[test]
    fn strip_removes_frontmatter_block() {
        let text = "---\nid: x\n---\n\nBody content";
        assert_eq!(strip(text), "\nBody content");
    }
}

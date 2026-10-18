//! JSON text identical to what Python's `json.dumps` writes.

use std::io;

use serde::Serialize;
use serde_json::ser::{Formatter, PrettyFormatter, Serializer};

fn write_with<T: Serialize + ?Sized, F: Formatter>(value: &T, formatter: F) -> String {
    let mut out = Vec::new();
    let mut serializer = Serializer::with_formatter(&mut out, formatter);
    value
        .serialize(&mut serializer)
        .expect("store types serialize to memory without error");
    String::from_utf8(out).expect("serde_json writes UTF-8")
}

/// `json.dumps(value, ensure_ascii=False, indent=1)`: the resource store format.
pub fn to_store_json<T: Serialize + ?Sized>(value: &T) -> String {
    write_with(value, PrettyFormatter::with_indent(b" "))
}

/// `json.dumps(value, ensure_ascii=False)` without indent: `", "` between items
/// and `": "` after keys.
pub fn to_python_compact_json<T: Serialize + ?Sized>(value: &T) -> String {
    write_with(value, PythonCompact)
}

struct PythonCompact;

impl Formatter for PythonCompact {
    fn begin_array_value<W: ?Sized + io::Write>(&mut self, writer: &mut W, first: bool) -> io::Result<()> {
        if first { Ok(()) } else { writer.write_all(b", ") }
    }

    fn begin_object_key<W: ?Sized + io::Write>(&mut self, writer: &mut W, first: bool) -> io::Result<()> {
        if first { Ok(()) } else { writer.write_all(b", ") }
    }

    fn begin_object_value<W: ?Sized + io::Write>(&mut self, writer: &mut W) -> io::Result<()> {
        writer.write_all(b": ")
    }
}

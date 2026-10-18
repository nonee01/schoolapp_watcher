//! HTML extractors, one module per file of `schoolapp/extractors/`.

pub mod absences;
pub mod courses;
pub mod grades;
pub mod tables;

pub use absences::{parse_absence_summary, parse_absences, parse_sanctions};
pub use courses::parse_courses;
pub use grades::{parse_element_grades, parse_module_grades};

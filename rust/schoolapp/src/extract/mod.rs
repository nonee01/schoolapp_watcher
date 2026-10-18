//! HTML extractors, one module per file of `schoolapp/extractors/`.

pub mod absences;
pub mod courses;
pub mod documents;
pub mod grades;
pub mod profile;
pub mod results;
pub mod stats;
pub mod tables;

pub use absences::{parse_absence_summary, parse_absences, parse_sanctions};
pub use courses::parse_courses;
pub use documents::build_documents;
pub use grades::{parse_element_grades, parse_module_grades};
pub use profile::parse_profile;
pub use results::{parse_diploma, parse_semester_results, parse_year_results};
pub use stats::parse_mark_statistics;

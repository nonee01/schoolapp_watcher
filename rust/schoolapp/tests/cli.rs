use std::process::Command;

fn schoolapp_rs() -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_schoolapp-rs"));
    cmd.env_remove("SCHOOLAPP_EMAIL").env_remove("SCHOOLAPP_PASSWORD");
    cmd
}

#[test]
fn missing_credentials_is_a_usage_error() {
    let out = schoolapp_rs().arg("fetch-all").output().unwrap();
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("Missing credentials"), "{out:?}");
}

#[test]
fn help_is_reachable_both_ways() {
    let flag = schoolapp_rs().args(["fetch-all", "--help"]).output().unwrap();
    let sub = schoolapp_rs().args(["help", "fetch-all"]).output().unwrap();
    assert!(flag.status.success() && sub.status.success());
    assert_eq!(flag.stdout, sub.stdout);
    assert!(String::from_utf8_lossy(&flag.stdout).contains("--no-history"));
}

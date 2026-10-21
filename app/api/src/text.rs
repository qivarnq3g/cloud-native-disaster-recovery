use unicode_normalization::UnicodeNormalization;

use crate::error::ApiError;

pub const MAX_TITLE_CHARS: usize = 100;
pub const MAX_DESCRIPTION_CHARS: usize = 1000;

pub fn title(input: &str) -> Result<String, ApiError> {
    let s = input.nfc().collect::<String>().trim().to_string();
    if s.chars().any(char::is_control) {
        return Err(ApiError::InvalidInput(
            "Tiêu đề có ký tự không hợp lệ.".into(),
        ));
    }
    let n = s.chars().count();
    if n == 0 {
        return Err(ApiError::InvalidInput(
            "Tiêu đề không được để trống.".into(),
        ));
    }
    if n > MAX_TITLE_CHARS {
        return Err(ApiError::InvalidInput(format!(
            "Tiêu đề tối đa {MAX_TITLE_CHARS} ký tự."
        )));
    }
    Ok(s)
}

pub fn description(input: &str) -> Result<String, ApiError> {
    let s = input
        .replace("\r\n", "\n")
        .nfc()
        .collect::<String>()
        .trim()
        .to_string();
    if s.chars().any(|c| c.is_control() && c != '\n') {
        return Err(ApiError::InvalidInput(
            "Mô tả có ký tự không hợp lệ.".into(),
        ));
    }
    if s.chars().count() > MAX_DESCRIPTION_CHARS {
        return Err(ApiError::InvalidInput(format!(
            "Mô tả tối đa {MAX_DESCRIPTION_CHARS} ký tự."
        )));
    }
    Ok(s)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trims_surrounding_whitespace() {
        assert_eq!(title("  Xin chào  ").unwrap(), "Xin chào");
    }

    #[test]
    fn normalizes_nfc_before_counting() {
        let nfd = "e\u{301}".repeat(100);
        let result = title(&nfd).unwrap();
        assert_eq!(result.chars().count(), 100);
        assert_eq!(result, "é".repeat(100));
    }

    #[test]
    fn limits_title_length() {
        assert!(title(&"a".repeat(100)).is_ok());
        assert!(matches!(
            title(&"a".repeat(101)),
            Err(ApiError::InvalidInput(_))
        ));
        assert!(matches!(title("   "), Err(ApiError::InvalidInput(_))));
    }

    #[test]
    fn rejects_control_chars_in_title() {
        assert!(matches!(title("a\u{7}b"), Err(ApiError::InvalidInput(_))));
        assert!(matches!(
            title("dòng 1\ndòng 2"),
            Err(ApiError::InvalidInput(_))
        ));
    }

    #[test]
    fn description_keeps_newlines_and_converts_crlf() {
        assert_eq!(description("a\r\nb").unwrap(), "a\nb");
        assert_eq!(description("").unwrap(), "");
        assert!(matches!(
            description("a\tb"),
            Err(ApiError::InvalidInput(_))
        ));
    }

    #[test]
    fn limits_description_length() {
        assert!(description(&"ă".repeat(1000)).is_ok());
        assert!(matches!(
            description(&"ă".repeat(1001)),
            Err(ApiError::InvalidInput(_))
        ));
    }
}

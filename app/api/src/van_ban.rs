use unicode_normalization::UnicodeNormalization;

use crate::loi::ApiLoi;

pub const TIEU_DE_TOI_DA: usize = 100;
pub const MO_TA_TOI_DA: usize = 1000;

pub fn tieu_de(dau_vao: &str) -> Result<String, ApiLoi> {
    let s = dau_vao.nfc().collect::<String>().trim().to_string();
    if s.chars().any(char::is_control) {
        return Err(ApiLoi::DuLieuSai("Tiêu đề có ký tự không hợp lệ.".into()));
    }
    let n = s.chars().count();
    if n == 0 {
        return Err(ApiLoi::DuLieuSai("Tiêu đề không được để trống.".into()));
    }
    if n > TIEU_DE_TOI_DA {
        return Err(ApiLoi::DuLieuSai(format!("Tiêu đề tối đa {TIEU_DE_TOI_DA} ký tự.")));
    }
    Ok(s)
}

pub fn mo_ta(dau_vao: &str) -> Result<String, ApiLoi> {
    let s = dau_vao.replace("\r\n", "\n").nfc().collect::<String>().trim().to_string();
    if s.chars().any(|c| c.is_control() && c != '\n') {
        return Err(ApiLoi::DuLieuSai("Mô tả có ký tự không hợp lệ.".into()));
    }
    if s.chars().count() > MO_TA_TOI_DA {
        return Err(ApiLoi::DuLieuSai(format!("Mô tả tối đa {MO_TA_TOI_DA} ký tự.")));
    }
    Ok(s)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bo_khoang_trang_hai_dau() {
        assert_eq!(tieu_de("  Xin chào  ").unwrap(), "Xin chào");
    }

    #[test]
    fn chuan_hoa_nfc_truoc_khi_dem() {
        let nfd = "e\u{301}".repeat(100);
        let ket_qua = tieu_de(&nfd).unwrap();
        assert_eq!(ket_qua.chars().count(), 100);
        assert_eq!(ket_qua, "é".repeat(100));
    }

    #[test]
    fn gioi_han_do_dai_tieu_de() {
        assert!(tieu_de(&"a".repeat(100)).is_ok());
        assert!(matches!(tieu_de(&"a".repeat(101)), Err(ApiLoi::DuLieuSai(_))));
        assert!(matches!(tieu_de("   "), Err(ApiLoi::DuLieuSai(_))));
    }

    #[test]
    fn tu_choi_ky_tu_dieu_khien_trong_tieu_de() {
        assert!(matches!(tieu_de("a\u{7}b"), Err(ApiLoi::DuLieuSai(_))));
        assert!(matches!(tieu_de("dòng 1\ndòng 2"), Err(ApiLoi::DuLieuSai(_))));
    }

    #[test]
    fn mo_ta_giu_xuong_dong_va_doi_crlf() {
        assert_eq!(mo_ta("a\r\nb").unwrap(), "a\nb");
        assert_eq!(mo_ta("").unwrap(), "");
        assert!(matches!(mo_ta("a\tb"), Err(ApiLoi::DuLieuSai(_))));
    }

    #[test]
    fn gioi_han_do_dai_mo_ta() {
        assert!(mo_ta(&"ă".repeat(1000)).is_ok());
        assert!(matches!(mo_ta(&"ă".repeat(1001)), Err(ApiLoi::DuLieuSai(_))));
    }
}

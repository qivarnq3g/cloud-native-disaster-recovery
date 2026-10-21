use utoipa::Modify;
use utoipa::OpenApi;
use utoipa::openapi::security::{HttpAuthScheme, HttpBuilder, SecurityScheme};

use crate::loi::ThanLoi;

#[derive(OpenApi)]
#[openapi(
    info(title = "API web đăng ảnh của đồ án DR", version = "1"),
    components(schemas(ThanLoi)),
    modifiers(&BaoMat)
)]
pub struct TaiLieu;

struct BaoMat;

impl Modify for BaoMat {
    fn modify(&self, api: &mut utoipa::openapi::OpenApi) {
        let c = api.components.get_or_insert_with(Default::default);
        c.add_security_scheme("ma_bi_mat", SecurityScheme::Http(HttpBuilder::new().scheme(HttpAuthScheme::Bearer).build()));
    }
}

pub fn tai_lieu() -> utoipa::openapi::OpenApi {
    crate::dinh_tuyen::cac_tuyen().split_for_parts().1
}

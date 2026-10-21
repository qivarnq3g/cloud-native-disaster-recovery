use utoipa::Modify;
use utoipa::OpenApi;
use utoipa::openapi::security::{HttpAuthScheme, HttpBuilder, SecurityScheme};

use crate::error::ErrorBody;

#[derive(OpenApi)]
#[openapi(
    info(title = "API web đăng ảnh của đồ án DR", version = "1"),
    components(schemas(ErrorBody)),
    modifiers(&SecurityAddon)
)]
pub struct ApiDoc;

struct SecurityAddon;

impl Modify for SecurityAddon {
    fn modify(&self, api: &mut utoipa::openapi::OpenApi) {
        let c = api.components.get_or_insert_with(Default::default);
        c.add_security_scheme(
            "secret_code",
            SecurityScheme::Http(HttpBuilder::new().scheme(HttpAuthScheme::Bearer).build()),
        );
    }
}

pub fn spec() -> utoipa::openapi::OpenApi {
    crate::routes::api_router().split_for_parts().1
}

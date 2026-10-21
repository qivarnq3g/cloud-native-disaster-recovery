FROM rust:1.97.1-alpine AS build
RUN apk add --no-cache build-base nasm
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY .sqlx ./.sqlx
COPY migrations ./migrations
COPY src ./src
ARG APP_VERSION=dev
ENV SQLX_OFFLINE=true APP_VERSION=${APP_VERSION}
RUN cargo build --release --locked --features production && strip target/release/api

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /src/target/release/api /api
EXPOSE 8080
ENTRYPOINT ["/api"]

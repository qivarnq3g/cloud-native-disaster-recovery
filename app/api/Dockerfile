FROM rust:1.97.1-alpine AS dung
RUN apk add --no-cache build-base nasm
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY .sqlx ./.sqlx
COPY migrations ./migrations
COPY src ./src
ARG PHIEN_BAN=dev
ENV SQLX_OFFLINE=true PHIEN_BAN=${PHIEN_BAN}
RUN cargo build --release --locked --features phat_hanh && strip target/release/api

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=dung /src/target/release/api /api
EXPOSE 8080
ENTRYPOINT ["/api"]

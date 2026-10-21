CREATE TABLE posts (
    id uuid PRIMARY KEY,
    idempotency_key uuid NOT NULL UNIQUE,
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 100),
    description text NOT NULL CHECK (char_length(description) <= 1000),
    image_sha256 bytea NOT NULL CHECK (octet_length(image_sha256) = 32),
    image_type text NOT NULL CHECK (image_type IN ('image/jpeg', 'image/png', 'image/webp')),
    image_bytes integer NOT NULL CHECK (image_bytes BETWEEN 1 AND 1048576),
    width integer NOT NULL CHECK (width > 0),
    height integer NOT NULL CHECK (height > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

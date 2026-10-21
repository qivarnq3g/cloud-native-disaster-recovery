CREATE TABLE bai (
    id uuid PRIMARY KEY,
    ma_lan_dang uuid NOT NULL UNIQUE,
    tieu_de text NOT NULL CHECK (char_length(tieu_de) BETWEEN 1 AND 100),
    mo_ta text NOT NULL CHECK (char_length(mo_ta) <= 1000),
    anh_sha256 bytea NOT NULL CHECK (octet_length(anh_sha256) = 32),
    anh_kieu text NOT NULL CHECK (anh_kieu IN ('image/jpeg', 'image/png', 'image/webp')),
    anh_byte integer NOT NULL CHECK (anh_byte BETWEEN 1 AND 1048576),
    rong integer NOT NULL CHECK (rong > 0),
    cao integer NOT NULL CHECK (cao > 0),
    tao_luc timestamptz NOT NULL DEFAULT now()
);

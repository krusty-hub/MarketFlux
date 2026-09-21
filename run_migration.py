"""
Minimal PostgreSQL wire-protocol client (pure stdlib) to run DDL migrations.
Uses SSL, simple startup, and MD5 password auth.
"""
import socket
import ssl
import struct
import hashlib
import sys

# ── connection params ──────────────────────────────────────────────────────
HOST = "db.sjwlhesqrjyqgvqnuxri.supabase.co"
PORT = 5432
DATABASE = "postgres"
USER = "postgres"
PASSWORD = "l7Z2jVZTrXkncfXp"

# ── migration SQL ──────────────────────────────────────────────────────────
SQL = """
-- TRADES TABLE
CREATE TABLE IF NOT EXISTS public.trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    pair TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    market_type TEXT NOT NULL DEFAULT 'crypto',
    direction TEXT NOT NULL,
    market_price NUMERIC(16, 6) NOT NULL,
    entry NUMERIC(16, 6),
    stop_loss NUMERIC(16, 6),
    take_profit NUMERIC(16, 6),
    position_size NUMERIC(16, 6),
    market_regime TEXT,
    trend TEXT,
    volatility NUMERIC(16, 6),
    session TEXT,
    liquidity_sweep BOOLEAN DEFAULT false,
    bos BOOLEAN DEFAULT false,
    choch BOOLEAN DEFAULT false,
    order_block BOOLEAN DEFAULT false,
    fvg BOOLEAN DEFAULT false,
    model_confidence NUMERIC(6, 4),
    model_version TEXT,
    prediction NUMERIC(16, 6),
    actual_outcome TEXT,
    actual_close_price NUMERIC(16, 6),
    pnl NUMERIC(16, 4),
    max_drawdown NUMERIC(8, 4),
    error_type TEXT,
    evaluated_at TIMESTAMPTZ,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trades_pair_time ON public.trades(pair, timeframe);
CREATE INDEX IF NOT EXISTS idx_trades_outcome ON public.trades(actual_outcome);
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON public.trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON public.trades(timestamp DESC);

-- RLS
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read their own or system trades" ON public.trades;
CREATE POLICY "Users can read their own or system trades"
    ON public.trades FOR SELECT
    USING (user_id IS NULL OR auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own trades" ON public.trades;
CREATE POLICY "Users can insert their own trades"
    ON public.trades FOR INSERT
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

DROP POLICY IF EXISTS "Users can update their own trades" ON public.trades;
CREATE POLICY "Users can update their own trades"
    ON public.trades FOR UPDATE
    USING (auth.uid() = user_id);

-- signal_results table
CREATE TABLE IF NOT EXISTS public.signal_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES public.trades(id) ON DELETE CASCADE,
    actual_price NUMERIC(16, 6),
    price_difference NUMERIC(16, 6),
    error_percentage NUMERIC(10, 6),
    result TEXT,
    evaluated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.signal_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access to signal_results" ON public.signal_results;
CREATE POLICY "Service role full access to signal_results"
    ON public.signal_results FOR ALL
    USING (true)
    WITH CHECK (true);
"""

# ── wire protocol helpers ──────────────────────────────────────────────────

def pack_msg(msg_type: bytes, body: bytes) -> bytes:
    return msg_type + struct.pack("!I", len(body) + 4) + body

def read_exactly(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise EOFError("Connection closed unexpectedly")
        data += chunk
    return data

def read_message(sock):
    header = read_exactly(sock, 5)
    msg_type = header[0:1]
    length = struct.unpack("!I", header[1:5])[0]
    body = read_exactly(sock, length - 4)
    return msg_type, body

def md5_password(password: str, user: str, salt: bytes) -> bytes:
    step1 = hashlib.md5((password + user).encode()).hexdigest().encode()
    step2 = hashlib.md5(step1 + salt).hexdigest()
    return ("md5" + step2).encode() + b"\x00"

def cstr(s: str) -> bytes:
    return s.encode() + b"\x00"

# ── main ───────────────────────────────────────────────────────────────────

def connect_and_migrate():
    print(f"Connecting to {HOST}:{PORT} ...")

    raw_sock = socket.create_connection((HOST, PORT), timeout=30)

    # Negotiate SSL (send SSLRequest)
    ssl_request = struct.pack("!II", 8, 80877103)
    raw_sock.sendall(ssl_request)
    response = raw_sock.recv(1)
    if response != b"S":
        print(f"SSL not supported by server (got {response!r}), trying plain...")
        conn = raw_sock
    else:
        ctx = ssl.create_default_context()
        conn = ctx.wrap_socket(raw_sock, server_hostname=HOST)
        print("SSL handshake OK")

    # Startup message
    startup_params = (
        b"user\x00" + cstr(USER) +
        b"database\x00" + cstr(DATABASE) +
        b"application_name\x00" + b"migration_script\x00" +
        b"\x00"
    )
    startup_body = struct.pack("!I", 196608) + startup_params  # protocol 3.0
    startup_msg = struct.pack("!I", len(startup_body) + 4) + startup_body
    conn.sendall(startup_msg)

    # Auth loop
    authed = False
    while not authed:
        msg_type, body = read_message(conn)

        if msg_type == b"R":  # Authentication
            auth_type = struct.unpack("!I", body[:4])[0]
            if auth_type == 0:
                print("Auth: OK (no password needed)")
                authed = True
            elif auth_type == 5:  # MD5
                salt = body[4:8]
                print("Auth: MD5 challenge")
                pwd_msg = pack_msg(b"p", md5_password(PASSWORD, USER, salt))
                conn.sendall(pwd_msg)
            elif auth_type == 3:  # Cleartext
                print("Auth: Cleartext password")
                pwd_msg = pack_msg(b"p", cstr(PASSWORD))
                conn.sendall(pwd_msg)
            else:
                print(f"Auth: Unsupported auth type {auth_type}")
                conn.close()
                sys.exit(1)

        elif msg_type == b"S":  # ParameterStatus
            key, _, val = body[:-1].partition(b"\x00")
            print(f"  Server param: {key.decode()} = {val.decode()}")

        elif msg_type == b"K":  # BackendKeyData
            pass

        elif msg_type == b"Z":  # ReadyForQuery
            print("Ready for query")
            authed = True

        elif msg_type == b"E":  # Error
            err = body.decode(errors="replace")
            print(f"ERROR during startup: {err}")
            conn.close()
            sys.exit(1)

        elif msg_type == b"N":  # Notice
            print(f"Notice: {body}")

        else:
            print(f"  Unknown message type {msg_type} during startup")

    # Send query
    print("\nRunning migration SQL...")
    query_msg = pack_msg(b"Q", SQL.encode() + b"\x00")
    conn.sendall(query_msg)

    # Read results
    errors = []
    done = False
    while not done:
        msg_type, body = read_message(conn)

        if msg_type == b"C":  # CommandComplete
            tag = body[:-1].decode()
            print(f"  ✓ {tag}")

        elif msg_type == b"Z":  # ReadyForQuery
            status = body[0:1]
            print(f"\nTransaction status: {status}")
            done = True

        elif msg_type == b"E":  # ErrorResponse
            # Parse error fields
            fields = {}
            parts = body[:-1].split(b"\x00")
            for part in parts:
                if part:
                    fields[chr(part[0])] = part[1:].decode(errors="replace")
            msg = fields.get("M", body.decode(errors="replace"))
            sev = fields.get("S", "ERROR")
            code = fields.get("C", "?")
            print(f"  ✗ {sev} [{code}]: {msg}")
            errors.append(msg)

        elif msg_type == b"N":  # NoticeResponse
            fields = {}
            parts = body[:-1].split(b"\x00")
            for part in parts:
                if part:
                    fields[chr(part[0])] = part[1:].decode(errors="replace")
            print(f"  Notice: {fields.get('M', '')}")

        elif msg_type == b"T":  # RowDescription
            pass

        elif msg_type == b"D":  # DataRow
            pass

        elif msg_type == b"I":  # EmptyQueryResponse
            pass

        else:
            print(f"  Unknown msg {msg_type!r}: {body[:80]}")

    conn.close()

    if errors:
        print(f"\n⚠  Migration completed with {len(errors)} error(s).")
        print("If errors say 'already exists', the table was already created — that's fine.")
    else:
        print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    connect_and_migrate()

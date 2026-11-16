from scrapy_impersonate.tls import (
    CURLINFO_SSL_DATA_IN,
    CURLINFO_SSL_DATA_OUT,
    TLSHandshakeCounter,
)

IN, OUT = CURLINFO_SSL_DATA_IN, CURLINFO_SSL_DATA_OUT
CHANGE_CIPHER_SPEC, ALERT, HANDSHAKE, APPLICATION_DATA = 20, 21, 22, 23


def record(direction, content_type, length):
    return direction, bytes([content_type, 3, 3]) + length.to_bytes(2, "big")


def message(direction, msg_type, size):
    return direction, bytes([msg_type]) + (size - 4).to_bytes(3, "big") + bytes(size - 4)


def change_cipher_spec(direction):
    return direction, b"\x01"


def replay(events, counter=None):
    counter = counter or TLSHandshakeCounter()
    for type_, data in events:
        counter(type_, data)
    return counter.size


# Debug callback traces of curl-impersonate (BoringSSL) fetching real sites. The
# expected sizes add up the records (5-byte header + length) of the handshake.
TLS13_HANDSHAKE = [
    record(OUT, HANDSHAKE, 1912),
    message(OUT, 1, 1912),  # ClientHello
    record(IN, HANDSHAKE, 1210),
    message(IN, 2, 1210),  # ServerHello
    record(OUT, CHANGE_CIPHER_SPEC, 1),
    change_cipher_spec(OUT),
    record(IN, CHANGE_CIPHER_SPEC, 1),  # the peer's message is not reported
    record(IN, APPLICATION_DATA, 3048),
    message(IN, 8, 94),  # EncryptedExtensions
    message(IN, 25, 2822),  # CompressedCertificate
    message(IN, 15, 79),  # CertificateVerify
    message(IN, 20, 36),  # Finished
    message(OUT, 20, 36),  # Finished, reported before its record
    record(OUT, APPLICATION_DATA, 53),
]
TLS13_AFTER_HANDSHAKE = [
    record(OUT, APPLICATION_DATA, 557),
    record(IN, APPLICATION_DATA, 445),
    message(IN, 4, 214),  # NewSessionTicket
    message(IN, 4, 214),  # NewSessionTicket
    record(IN, APPLICATION_DATA, 57),
    record(OUT, APPLICATION_DATA, 26),
    record(IN, APPLICATION_DATA, 26),
    record(IN, APPLICATION_DATA, 190),
]
TLS13_SIZE = (5 + 1912) + (5 + 1210) + (5 + 1) + (5 + 1) + (5 + 3048) + (5 + 53) + (5 + 445)

TLS12_HANDSHAKE = [
    record(OUT, HANDSHAKE, 2016),
    message(OUT, 1, 2016),  # ClientHello
    record(IN, HANDSHAKE, 76),
    message(IN, 2, 76),  # ServerHello
    record(IN, HANDSHAKE, 4074),
    message(IN, 11, 4074),  # Certificate
    record(IN, HANDSHAKE, 333),
    message(IN, 12, 333),  # ServerKeyExchange
    record(IN, HANDSHAKE, 4),
    message(IN, 14, 4),  # ServerHelloDone
    record(OUT, HANDSHAKE, 70),
    message(OUT, 16, 70),  # ClientKeyExchange
    record(OUT, CHANGE_CIPHER_SPEC, 1),
    change_cipher_spec(OUT),
    message(OUT, 20, 16),  # Finished, reported before its record
    record(OUT, HANDSHAKE, 40),
    record(OUT, APPLICATION_DATA, 700),
    record(IN, HANDSHAKE, 202),
    message(IN, 4, 202),  # NewSessionTicket
    record(IN, CHANGE_CIPHER_SPEC, 1),
    change_cipher_spec(IN),
    record(IN, HANDSHAKE, 40),
    message(IN, 20, 16),  # Finished
    record(IN, APPLICATION_DATA, 632),
]
TLS12_SIZE = (
    (5 + 2016)
    + (5 + 70)
    + (5 + 1)
    + (5 + 40)
    + sum(5 + length for length in (76, 4074, 333, 4, 202, 1, 40))
)


def test_tls13_handshake_records_are_counted():
    assert replay(TLS13_HANDSHAKE + TLS13_AFTER_HANDSHAKE) == TLS13_SIZE


def test_tls12_handshake_records_are_counted():
    assert replay(TLS12_HANDSHAKE) == TLS12_SIZE


def test_application_data_is_not_counted():
    application_data = [record(direction, APPLICATION_DATA, 1395) for direction in (IN, OUT)]

    assert replay(TLS13_HANDSHAKE + TLS13_AFTER_HANDSHAKE + application_data * 100) == (TLS13_SIZE)


def test_alerts_after_the_handshake_are_not_counted():
    close_notify = [record(OUT, ALERT, 2), (OUT, b"\x01\x00")]

    assert replay(TLS13_HANDSHAKE + TLS13_AFTER_HANDSHAKE + close_notify) == TLS13_SIZE


def test_tunnelled_handshake_is_counted_too():
    """TLS to an HTTPS proxy, then to the origin through it."""

    assert replay(TLS13_HANDSHAKE + TLS13_AFTER_HANDSHAKE + TLS12_HANDSHAKE) == (
        TLS13_SIZE + TLS12_SIZE
    )


def test_plain_http_is_zero():
    assert replay([(0, b"* Connected\n"), (2, b"GET / HTTP/1.1\r\n"), (3, b"hello")]) == 0


def test_debug_function_is_still_called():
    received = []
    counter = TLSHandshakeCounter(lambda type_, data: received.append((type_, data)))

    replay(TLS12_HANDSHAKE, counter)

    assert received == TLS12_HANDSHAKE
    assert counter.size == TLS12_SIZE

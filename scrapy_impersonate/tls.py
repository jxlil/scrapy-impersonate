from typing import Callable, Dict, Optional

# libcurl's curl_infotype values for the TLS data passed to CURLOPT_DEBUGFUNCTION
CURLINFO_SSL_DATA_IN = 5
CURLINFO_SSL_DATA_OUT = 6

RECORD_HEADER_SIZE = 5
HANDSHAKE_HEADER_SIZE = 4
CLIENT_HELLO = 1
FINISHED = 20


def is_record_header(data: bytes) -> bool:
    """Whether data is a 5-byte TLS record header.

    Layout: content type (1 byte, 20-24: change_cipher_spec..heartbeat), legacy
    version (2 bytes, 0x03XX), payload length (2 bytes, see record_length()).
    """
    return len(data) == RECORD_HEADER_SIZE and 20 <= data[0] <= 24 and data[1] == 3


def record_length(header: bytes) -> int:
    """Payload length of a record, read from bytes 3-4 of its header.

    TLS encodes multi-byte integers big-endian (most significant byte first), e.g.
    b"\\x07\\x78" is 0x0778 = 1912.
    """
    return int.from_bytes(header[3:5], "big")


def is_handshake_message(data: bytes) -> bool:
    """Whether data is a whole TLS handshake message.

    Layout: msg_type (1 byte), body length (3 bytes, big-endian), body. The debug
    callback reports unlabelled chunks, so the check is that the length in bytes 1-3
    matches the bytes that actually follow it, which a ChangeCipherSpec (1 byte), an
    alert (2 bytes) or a record header does not satisfy.
    """
    return (
        len(data) >= HANDSHAKE_HEADER_SIZE
        and int.from_bytes(data[1:4], "big") == len(data) - HANDSHAKE_HEADER_SIZE
    )


class _Direction:
    def __init__(self) -> None:
        self.done = False
        # the Finished message was reported before the record carrying it
        self.awaiting_finished_record = False
        # plaintext bytes of the last record not yet accounted to a message
        self.room = 0
        # size of the last record seen after the handshake, counted only if it
        # turns out to carry a post-handshake message (e.g. NewSessionTicket)
        self.pending = 0


class TLSHandshakeCounter:
    """
    CURLOPT_DEBUGFUNCTION callback measuring the bytes the TLS handshake takes on the wire.

    libcurl does not expose this, but with the BoringSSL backend of curl-impersonate
    the debug callback receives both the header of every TLS record and, decrypted,
    every handshake message. Counting whole records (header + payload, as stated by
    the header) rather than messages includes the record framing and the encryption
    overhead, i.e. what actually went over the wire.

    Since TLS 1.3 encrypted handshake records and application data records share the
    same outer content type, records are counted per direction until the one carrying
    that side's Finished message; after that, only records carrying a handshake
    message (NewSessionTicket) are. A new ClientHello starts counting again, which
    covers a TLS tunnel through an HTTPS proxy.
    """

    def __init__(self, debug_function: Optional[Callable[[int, bytes], None]] = None) -> None:
        self.size = 0
        self._debug_function = debug_function
        self._reset()

    def _reset(self) -> None:
        self._directions: Dict[int, _Direction] = {
            CURLINFO_SSL_DATA_IN: _Direction(),
            CURLINFO_SSL_DATA_OUT: _Direction(),
        }

    def __call__(self, type_: int, data: bytes) -> None:
        if self._debug_function is not None:
            self._debug_function(type_, data)

        direction = self._directions.get(type_)
        if direction is None:
            return

        if is_record_header(data):
            self._on_record(direction, record_length(data))
        else:
            self._on_message(type_, direction, data)

    def _on_record(self, direction: _Direction, length: int) -> None:
        if direction.done:
            direction.pending = RECORD_HEADER_SIZE + length
            return

        self.size += RECORD_HEADER_SIZE + length
        direction.room = length
        if direction.awaiting_finished_record:
            direction.done = True

    def _on_message(self, type_: int, direction: _Direction, data: bytes) -> None:
        handshake_message = is_handshake_message(data)

        if type_ == CURLINFO_SSL_DATA_OUT and handshake_message and data[0] == CLIENT_HELLO:
            pending = direction.pending
            self._reset()
            # the record carrying it may already have been reported
            self.size += pending
            return

        if direction.done:
            if handshake_message:
                self.size += direction.pending
                direction.pending = 0
            return

        fits = len(data) <= direction.room
        direction.room = direction.room - len(data) if fits else 0
        if handshake_message and data[0] == FINISHED:
            if fits:
                direction.done = True
            else:
                direction.awaiting_finished_record = True
